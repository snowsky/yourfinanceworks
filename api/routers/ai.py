from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Any, Dict, List
from datetime import datetime, timedelta, timezone
import asyncio
import httpx

from models.database import get_master_db, get_db, set_tenant_context
from routers.auth import get_current_user
from models.models import MasterUser, Tenant, Settings
from models.models_per_tenant import Invoice, Client, AIConfig, AIChatHistory
from schemas.settings import Settings as SettingsSchema
from services.tenant_database_manager import tenant_db_manager
from constants.recommendation_codes import (
    CONSIDER_STRICTER_PAYMENT_TERMS,
    REVIEW_PAYMENT_TERMS_SLOW_CLIENTS,
    START_CREATING_INVOICES,
)

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

@router.get("/analyze-patterns", summary="Analyze invoice patterns and trends")
async def analyze_patterns(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Analyzes historical invoice data to identify patterns, trends,
    and key metrics such as total invoices, paid/unpaid status,
    revenue, and client payment behavior.
    """
    try:
        # Get all invoices (no tenant_id filtering needed since we're in the tenant's database)
        invoices = db.query(Invoice).all()
        
        # Calculate basic metrics
        total_invoices = len(invoices)
        paid_invoices = len([inv for inv in invoices if inv.status == "paid"])
        partially_paid_invoices = len([inv for inv in invoices if inv.status == "partially_paid"])
        unpaid_invoices = len([inv for inv in invoices if inv.status in ["pending", "draft"]])
        overdue_invoices = len([inv for inv in invoices if inv.status == "overdue"])
        
        # Calculate revenue metrics with better error handling - grouped by currency
        total_revenue_by_currency = {}
        outstanding_revenue_by_currency = {}
        
        for inv in invoices:
            currency = inv.currency or "USD"
            
            if inv.status == "paid":
                if currency not in total_revenue_by_currency:
                    total_revenue_by_currency[currency] = 0
                total_revenue_by_currency[currency] += inv.amount
            elif inv.status == "partially_paid":
                # Calculate paid amount from payments - avoid relationship to prevent user_id column issues
                try:
                    # Use direct query to avoid Payment model relationship issues
                    from sqlalchemy import text
                    result = db.execute(text("SELECT SUM(amount) as total FROM payments WHERE invoice_id = :invoice_id"), 
                                     {"invoice_id": inv.id})
                    paid_amount = result.scalar() or 0
                except Exception as e:
                    print(f"Error calculating paid amount for invoice {inv.id}: {e}")
                    paid_amount = 0
                
                if currency not in total_revenue_by_currency:
                    total_revenue_by_currency[currency] = 0
                total_revenue_by_currency[currency] += paid_amount
            
            if inv.status in ["pending", "draft", "overdue"]:
                if currency not in outstanding_revenue_by_currency:
                    outstanding_revenue_by_currency[currency] = 0
                outstanding_revenue_by_currency[currency] += inv.amount
        
        # Get client payment patterns (simplified to avoid Payment model issues)
        # For now, we'll skip detailed payment analysis to avoid database schema conflicts
        fastest_paying_clients = []
        slowest_paying_clients = []
        
        # Generate recommendations
        recommendations = []
        if overdue_invoices > 0:
            recommendations.append(f"Send reminders for {overdue_invoices} overdue invoices")
        
        # Calculate total outstanding and total revenue across all currencies
        total_outstanding = sum(outstanding_revenue_by_currency.values())
        total_revenue = sum(total_revenue_by_currency.values())

        if total_outstanding > total_revenue * 0.3:
            recommendations.append(CONSIDER_STRICTER_PAYMENT_TERMS)
        if slowest_paying_clients:
            recommendations.append(REVIEW_PAYMENT_TERMS_SLOW_CLIENTS)
        if total_invoices == 0:
            recommendations.append(START_CREATING_INVOICES)

        # Debug logging
        print(f"Analyze patterns debug: total_invoices={total_invoices}, paid={paid_invoices}, partially_paid={partially_paid_invoices}, total_revenue_by_currency={total_revenue_by_currency}")

        return {
            "success": True,
            "data": {
                "total_invoices": total_invoices,
                "paid_invoices": paid_invoices,
                "partially_paid_invoices": partially_paid_invoices,
                "unpaid_invoices": unpaid_invoices,
                "overdue_invoices": overdue_invoices,
                "total_revenue_by_currency": total_revenue_by_currency,
                "outstanding_revenue_by_currency": outstanding_revenue_by_currency,
                "fastest_paying_clients": fastest_paying_clients,
                "slowest_paying_clients": slowest_paying_clients,
                "recommendations": recommendations
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    
@router.get("/suggest-actions", summary="Suggest actionable items based on invoice analysis")
async def suggest_actions(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Analyzes invoice data and suggests actionable items
    such as follow-up on overdue invoices, adjust payment terms, etc.
    """
    # Manually set tenant context and get tenant database
    try:
        # Get overdue invoices
        # No tenant_id filtering needed since we're in the tenant's database
        overdue_invoices = db.query(Invoice).filter(Invoice.status == "overdue").all()
        
        # Get clients with outstanding balances
        # No tenant_id filtering needed since we're in the tenant's database
        clients_with_balance = db.query(Client).filter(Client.balance > 0).all()
        
        # Get recent invoices that might need follow-up
        # No tenant_id filtering needed since we're in the tenant's database
        recent_invoices = db.query(Invoice).filter(
            and_(
                Invoice.status.in_(["pending", "draft"]),
                Invoice.due_date <= datetime.now(timezone.utc) + timedelta(days=7)
            )
        ).all()
        
        # Generate suggested actions
        suggested_actions = []
        
        if overdue_invoices:
            suggested_actions.append({
                "action": "send_overdue_reminders",
                "description": f"Send payment reminders for {len(overdue_invoices)} overdue invoices",
                "priority": "high"
            })
        
        if clients_with_balance:
            suggested_actions.append({
                "action": "review_payment_terms",
                "description": f"Review payment terms for {len(clients_with_balance)} clients with outstanding balances",
                "priority": "medium"
            })
        
        if recent_invoices:
            suggested_actions.append({
                "action": "follow_up_recent_invoices",
                "description": f"Follow up on {len(recent_invoices)} invoices due within 7 days",
                "priority": "medium"
            })
        
        # Check for low cash flow
        total_outstanding = sum(inv.amount for inv in overdue_invoices)
        if total_outstanding > 1000:  # Arbitrary threshold
            suggested_actions.append({
                "action": "implement_stricter_terms",
                "description": "Consider implementing stricter payment terms to improve cash flow",
                "priority": "low"
            })
        
        # If no specific actions, suggest general improvements
        if not suggested_actions:
            suggested_actions.append({
                "action": "review_business_processes",
                "description": "Review your invoicing and payment collection processes",
                "priority": "low"
            })
        
        return {
            "success": True,
            "data": {
                "suggested_actions": suggested_actions,
                "overdue_count": len(overdue_invoices),
                "clients_with_balance": len(clients_with_balance),
                "recent_invoices_count": len(recent_invoices)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    
@router.post("/chat")
async def ai_chat(
    message: str,
    config_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Chat with AI assistant using specified configuration
    """
    # Manually set tenant context and get tenant database
    try:
        # Get AI configuration
        # No tenant_id filtering needed since we're in the tenant's database
        ai_config = db.query(AIConfig).filter(
            AIConfig.is_default == True,
            AIConfig.is_active == True
        ).first()
        
        if not ai_config:
            return {
                "success": False,
                "error": "No active AI configuration found. Please configure an AI provider in Settings."
            }
        
        # Check for MCP tool patterns and execute them directly
        lower_message = message.lower()
        
        # Initialize MCP tools using current user's session
        from MCP.tools import InvoiceTools
        from MCP.api_client import InvoiceAPIClient
        from fastapi import Request
        
        # Create a token for the current user to use with MCP tools
        from routers.auth import create_access_token
        from datetime import timedelta
        
        # Create a token for the current user
        access_token_expires = timedelta(minutes=30)
        jwt_token = create_access_token(
            data={"sub": current_user.email}, expires_delta=access_token_expires
        )
        
        # Create a custom API client that uses the JWT token
        class AuthenticatedAPIClient:
            def __init__(self, base_url: str, jwt_token: str):
                self.base_url = base_url
                self.jwt_token = jwt_token
                self._client = httpx.AsyncClient(timeout=30.0)
            
            async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
                """Make authenticated request using JWT token"""
                try:
                    headers = {"Authorization": f"Bearer {self.jwt_token}"}
                    headers.update(kwargs.pop('headers', {}))
                    
                    response = await self._client.request(
                        method=method,
                        url=f"{self.base_url}{endpoint}",
                        headers=headers,
                        **kwargs
                    )
                    response.raise_for_status()
                    return response.json()
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        raise Exception("Authentication failed - token may be expired")
                    raise Exception(f"API request failed: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    raise Exception(f"Request error: {e}")
            
            # Client Management Methods
            async def list_clients(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
                return await self._make_request(
                    "GET", 
                    "/clients/",
                    params={"skip": skip, "limit": limit}
                )
            
            async def search_clients(self, query: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
                # Get all clients and filter locally
                clients = await self.list_clients(skip=0, limit=1000)
                query_lower = query.lower()
                filtered_clients = []
                
                for client in clients:
                    searchable_fields = [
                        client.get('name', ''),
                        client.get('email', ''),
                        client.get('phone', ''),
                        client.get('address', '')
                    ]
                    
                    if any(query_lower in str(field).lower() for field in searchable_fields if field):
                        filtered_clients.append(client)
                
                end_idx = skip + limit
                return filtered_clients[skip:end_idx]
            
            # Invoice Management Methods
            async def list_invoices(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
                return await self._make_request(
                    "GET", 
                    "/invoices/",
                    params={"skip": skip, "limit": limit}
                )
            
            async def search_invoices(self, query: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
                # Get all invoices and filter locally
                invoices = await self.list_invoices(skip=0, limit=1000)
                query_lower = query.lower()
                filtered_invoices = []
                
                for invoice in invoices:
                    searchable_fields = [
                        invoice.get('number', ''),
                        invoice.get('client_name', ''),
                        invoice.get('status', ''),
                        invoice.get('notes', ''),
                        str(invoice.get('amount', ''))
                    ]
                    
                    if any(query_lower in str(field).lower() for field in searchable_fields if field):
                        filtered_invoices.append(invoice)
                
                end_idx = skip + limit
                return filtered_invoices[skip:end_idx]
            
            # Payment Management Methods
            async def list_payments(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
                return await self._make_request(
                    "GET", 
                    "/payments/",
                    params={"skip": skip, "limit": limit}
                )
            
            # Currency Management Methods
            async def list_currencies(self, active_only: bool = True) -> List[Dict[str, Any]]:
                return await self._make_request(
                    "GET", 
                    "/currency/supported",
                    params={"active_only": active_only}
                )
            
            # Analytics Methods
            async def get_clients_with_outstanding_balance(self) -> List[Dict[str, Any]]:
                return await self._make_request("GET", "/clients/outstanding-balance")
            
            async def get_overdue_invoices(self) -> List[Dict[str, Any]]:
                return await self._make_request("GET", "/invoices/overdue")
            
            async def get_invoice_stats(self) -> Dict[str, Any]:
                return await self._make_request("GET", "/invoices/stats")
            
            async def analyze_invoice_patterns(self) -> Dict[str, Any]:
                return await self._make_request("GET", "/ai/analyze-patterns")
            
            async def suggest_invoice_actions(self) -> Dict[str, Any]:
                return await self._make_request("GET", "/ai/suggest-actions")
            
            async def close(self):
                await self._client.aclose()
        
        # Initialize the authenticated API client
        print(f"MCP Integration: Initializing API client with token: {jwt_token[:20]}...")
        api_client = AuthenticatedAPIClient(
            base_url="http://localhost:8000/api/v1",
            jwt_token=jwt_token
        )
        tools = InvoiceTools(api_client)
        print("MCP Integration: API client and tools initialized successfully")
        
        # Pattern 1: Analyze invoice patterns
        if any(phrase in lower_message for phrase in ["analyze", "analysis", "pattern", "trend", "insight"]):
            print(f"MCP Integration: Detected analyze pattern in message: '{message}'")
            try:
                # Execute MCP tool directly
                print("MCP Integration: Executing analyze_invoice_patterns...")
                result = await tools.analyze_invoice_patterns()
                print(f"MCP Integration: Result: {result}")
                
                if result.get("success"):
                    data = result.get("data", {})
                    
                    # Format revenue by currency for better display
                    def format_revenue_by_currency(revenue_data):
                        if not revenue_data or not isinstance(revenue_data, dict):
                            return "None"
                        return ", ".join([f"{currency} ${amount:,.2f}" for currency, amount in revenue_data.items()])
                    
                    # Format recommendations for f-string
                    recommendations_lines = '\n'.join([f"• {rec}" for rec in data.get('recommendations', [])])
                    mcp_response = f"""
🎯 **Invoice Pattern Analysis Report**

📊 **📈 Business Overview:**
• **Total Invoices:** {data.get('total_invoices', 0):,}
• **Paid Invoices:** {data.get('paid_invoices', 0):,} ✅
• **Partially Paid:** {data.get('partially_paid_invoices', 0):,} ⚠️
• **Unpaid Invoices:** {data.get('unpaid_invoices', 0):,} ❌
• **Overdue Invoices:** {data.get('overdue_invoices', 0):,} 🚨

💰 **💵 Financial Summary:**
• **Total Revenue:** {format_revenue_by_currency(data.get('total_revenue_by_currency', {}))}
• **Outstanding Revenue:** {format_revenue_by_currency(data.get('outstanding_revenue_by_currency', {}))}

💡 **🎯 Strategic Recommendations:**
{recommendations_lines}

📋 **📊 Analysis Details:**
This comprehensive analysis was performed using your actual invoice data through our advanced MCP tools, providing real-time insights into your business performance and cash flow patterns.
                    """.strip()
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # Pattern 2: Suggest actions
        elif any(phrase in lower_message for phrase in ["suggest", "action", "recommend", "what should", "next step"]):
            print(f"MCP Integration: Detected suggest pattern in message: '{message}'")
            try:
                # Execute MCP tool directly
                print("MCP Integration: Executing suggest_invoice_actions...")
                result = await tools.suggest_invoice_actions()
                print(f"MCP Integration: Result: {result}")
                
                if result.get("success"):
                    data = result.get("data", {})
                    actions = data.get("suggested_actions", [])
                    
                    # Helper function to get priority emoji
                    def get_priority_emoji(priority):
                        return {
                            'high': '🔴',
                            'medium': '🟡', 
                            'low': '🟢'
                        }.get(priority.lower(), '⚪')
                    
                    # Format actions for f-string
                    actions_lines = '\n'.join([f"• {get_priority_emoji(action.get('priority', 'medium'))} **{action.get('action', 'Unknown').replace('_', ' ').title()}**\n  📝 {action.get('description', 'No description')}\n  🏷️ Priority: {action.get('priority', 'medium').title()}\n" for action in actions])
                    mcp_response = f"""
🎯 **Strategic Action Plan**

🚀 **🎯 Priority Actions:**
{actions_lines}

📊 **📈 Quick Metrics:**
• **Overdue Invoices:** {data.get('overdue_count', 0):,} 🚨
• **Clients with Balance:** {data.get('clients_with_balance', 0):,} 💰
• **Recent Invoices:** {data.get('recent_invoices_count', 0):,} 📄

💡 **💼 Action Insights:**
These strategic recommendations are based on your actual invoice data and business patterns, designed to optimize your cash flow and improve client relationships.
                    """.strip()
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # Pattern 3: Payment queries (moved before client queries to prioritize payments)
        elif any(phrase in lower_message for phrase in ["payment", "pay", "paid", "list payments", "payment from", "received payment"]):
            print(f"MCP Integration: Detected payment pattern in message: '{message}'")
            try:
                print("MCP Integration: Querying payments with natural language...")
                result = await tools.query_payments(query=message)
                
                if result.get("success"):
                    payments = result.get("data", [])
                    date_filter_applied = result.get("date_filter_applied", False)
                    date_description = result.get("date_description", "")
                    
                    if payments:
                        # Format response based on whether date filtering was applied
                        if date_filter_applied:
                            response_title = f"💰 **Payment Report {date_description}**"
                        else:
                            response_title = "💰 **Payment Information Dashboard**"
                        
                        # Calculate total amount
                        total_amount = sum(payment.get('amount', 0) for payment in payments)
                        
                        # Format payment details for f-string
                        payment_lines = '\n'.join([f"• **Payment #{payment.get('id', 'N/A')}**\n  📄 Invoice: #{payment.get('invoice_number', 'N/A')}\n  💰 Amount: ${payment.get('amount', 0):,.2f}\n  💳 Method: {payment.get('payment_method', 'Unknown')}\n  📅 Date: {payment.get('payment_date', 'N/A')}\n" for payment in payments])
                        mcp_response = f"""
{response_title}

📊 **📈 Payment Summary:**
• **Total Payments:** {len(payments):,}
• **Total Amount:** ${total_amount:,.2f}
• **Date Range:** {date_description if date_filter_applied else "All Time"}

💳 **💵 Payment Details:**
{payment_lines}

📋 **📊 Data Source:**
This comprehensive payment information was retrieved using your actual payment data through our advanced MCP tools.
                        """.strip()
                    else:
                        if date_filter_applied:
                            mcp_response = f"No payments found {date_description}."
                        else:
                            mcp_response = "No payments found."
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # Pattern 4: Client management queries (moved after payment queries)
        elif any(phrase in lower_message for phrase in ["client", "customer", "list clients", "search client", "find client", "show clients", "get clients"]) and not any(phrase in lower_message for phrase in ["payment", "pay", "paid"]):
            print(f"MCP Integration: Detected client management pattern in message: '{message}'")
            print(f"MCP Integration: lower_message: '{lower_message}'")
            print(f"MCP Integration: Checking patterns: {[phrase for phrase in ['client', 'customer', 'list clients', 'search client', 'find client', 'show clients', 'get clients'] if phrase in lower_message]}")
            try:
                if "search" in lower_message or "find" in lower_message:
                    # Extract search query from message
                    import re
                    search_match = re.search(r'(?:search|find)\s+(?:for\s+)?["\']?([^"\']+)["\']?', lower_message)
                    if search_match:
                        search_query = search_match.group(1)
                        print(f"MCP Integration: Searching clients with query: '{search_query}'")
                        result = await tools.search_clients(query=search_query)
                    else:
                        # Default search
                        result = await tools.list_clients(limit=10)
                else:
                    # List all clients
                    print("MCP Integration: Listing clients...")
                    try:
                        result = await tools.list_clients(limit=20)
                        print(f"MCP Integration: list_clients result: {result}")
                    except Exception as e:
                        print(f"MCP Integration: Error calling list_clients: {e}")
                        result = {"success": False, "error": str(e)}

                if result.get("success"):
                    clients = result.get("data", [])
                    if clients:
                        # Calculate total outstanding balance
                        total_balance = sum(client.get('outstanding_balance', 0) for client in clients)
                        
                        # Format client details for f-string
                        client_lines = '\n'.join([f"• **{client.get('name', 'Unknown')}** (ID: {client.get('id', 'N/A')})\n" +
                                        (f"  📧 Email: {client.get('email', 'N/A')}\n" if client.get('email') else "") +
                                        (f"  📞 Phone: {client.get('phone', 'N/A')}\n" if client.get('phone') else "") +
                                        (f"  💰 Outstanding Balance: ${client.get('outstanding_balance', 0):,.2f}\n" if client.get('outstanding_balance') else "") +
                                        "  -----------------------------------------\n"
                                        for client in clients])
                        mcp_response = f"""
👥 **Client Management Dashboard**

📊 **📈 Client Overview:**
• **Total Clients:** {len(clients):,}
• **Total Outstanding Balance:** ${total_balance:,.2f}
• **Average Balance per Client:** ${(total_balance / len(clients)) if len(clients) > 0 else 0:,.2f}

👤 **💼 Client Details:**
{client_lines}

📋 **📊 Data Source:**
This comprehensive client information was retrieved using your actual client data through our advanced MCP tools.
                        """.strip()
                    else:
                        mcp_response = "No clients found matching your query."
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # Pattern 5: Invoice management queries
        elif any(phrase in lower_message for phrase in ["invoice", "bill", "list invoices", "search invoice", "find invoice"]):
            print(f"MCP Integration: Detected invoice management pattern in message: '{message}'")
            try:
                if "search" in lower_message or "find" in lower_message:
                    # Extract search query from message
                    import re
                    search_match = re.search(r'(?:search|find)\s+(?:for\s+)?["\']?([^"\']+)["\']?', lower_message)
                    if search_match:
                        search_query = search_match.group(1)
                        print(f"MCP Integration: Searching invoices with query: '{search_query}'")
                        result = await tools.search_invoices(query=search_query)
                    else:
                        # Default search
                        result = await tools.list_invoices(limit=10)
                else:
                    # List all invoices
                    print("MCP Integration: Listing invoices...")
                    result = await tools.list_invoices(limit=20)
                
                if result.get("success"):
                    invoices = result.get("data", [])
                    if invoices:
                        # Calculate totals
                        total_amount = sum(inv.get('amount', 0) for inv in invoices)
                        status_counts = {}
                        for inv in invoices:
                            status = inv.get('status', 'Unknown')
                            status_counts[status] = status_counts.get(status, 0) + 1
                        
                        # Format status breakdown for f-string
                        status_lines = '\n'.join([f"• **{status.title()}:** {count:,}" for status, count in status_counts.items()])
                        # Format invoice details for f-string
                        invoice_lines = '\n'.join([f"• **Invoice #{inv.get('invoice_number', inv.get('id', 'N/A'))}**\n" +
                                        f"  👤 Client: {inv.get('client_name', 'Unknown Client')}\n" +
                                        f"  💰 Amount: ${inv.get('amount', 0):,.2f}\n" +
                                        f"  📊 Status: {inv.get('status', 'Unknown').title()}\n" +
                                        f"  📅 Due: {inv.get('due_date', 'N/A')}\n" +
                                        "  -----------------------------------------\n"
                                        for inv in invoices])
                        mcp_response = f"""
📄 **Invoice Management Dashboard**

📊 **📈 Invoice Overview:**
• **Total Invoices:** {len(invoices):,}
• **Total Amount:** ${total_amount:,.2f}
• **Average Invoice Amount:** ${(total_amount / len(invoices)) if len(invoices) > 0 else 0:,.2f}

📋 **📊 Status Breakdown:**
{status_lines}

📄 **💼 Invoice Details:**
{invoice_lines}

📋 **📊 Data Source:**
This comprehensive invoice information was retrieved using your actual invoice data through our advanced MCP tools.
                        """.strip()
                    else:
                        mcp_response = "No invoices found matching your query."
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # Pattern 6: Currency queries
        elif any(phrase in lower_message for phrase in ["currency", "currencies", "list currencies", "exchange rate"]):
            print(f"MCP Integration: Detected currency pattern in message: '{message}'")
            try:
                print("MCP Integration: Listing currencies...")
                result = await tools.list_currencies(active_only=True)
                
                if result.get("success"):
                    currencies = result.get("data", [])
                    if currencies:
                        # Format currency details for f-string
                        currency_lines = '\n'.join([f"• **{currency.get('code', 'N/A')}** ({currency.get('symbol', '')})\n" +
                                        f"  📝 Name: {currency.get('name', 'Unknown')}\n" +
                                        f"  📊 Status: {'Active' if currency.get('is_active', True) else 'Inactive'}\n" +
                                        "  -----------------------------------------\n"
                                        for currency in currencies])
                        mcp_response = f"""
💱 **Currency Management Dashboard**

📊 **📈 Currency Overview:**
• **Active Currencies:** {len(currencies):,}
• **Supported Currencies:** {len(currencies):,}

💱 **💵 Currency Details:**
{currency_lines}

📋 **📊 Data Source:**
This comprehensive currency information was retrieved using your actual currency data through our advanced MCP tools.
                        """.strip()
                    else:
                        mcp_response = "No active currencies found."
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # Pattern 7: Outstanding balance queries
        elif any(phrase in lower_message for phrase in ["outstanding", "balance", "unpaid", "owe", "debt"]):
            print(f"MCP Integration: Detected outstanding balance pattern in message: '{message}'")
            try:
                print("MCP Integration: Getting clients with outstanding balance...")
                result = await tools.get_clients_with_outstanding_balance()
                
                if result.get("success"):
                    clients = result.get("data", [])
                    if clients:
                        # Calculate total outstanding balance
                        total_outstanding = sum(client.get('outstanding_balance', 0) for client in clients)
                        
                        # Format outstanding details for f-string
                        outstanding_lines = '\n'.join([f"• **{client.get('name', 'Unknown')}**\n" +
                                        f"  💰 Outstanding Balance: ${client.get('outstanding_balance', 0):,.2f}\n" +
                                        f"  📧 Email: {client.get('email', 'N/A')}\n" +
                                        f"  📞 Phone: {client.get('phone', 'N/A')}\n" +
                                        "  -----------------------------------------\n"
                                        for client in clients])
                        mcp_response = f"""
⚠️ **Outstanding Balance Report**

📊 **📈 Outstanding Overview:**
• **Clients with Balances:** {len(clients):,}
• **Total Outstanding Amount:** ${total_outstanding:,.2f}
• **Average Outstanding per Client:** ${(total_outstanding / len(clients)) if len(clients) > 0 else 0:,.2f}

💰 **💵 Outstanding Details:**
{outstanding_lines}

📋 **📊 Data Source:**
This comprehensive outstanding balance information was retrieved using your actual client data through our advanced MCP tools.
                        """.strip()
                    else:
                        mcp_response = "No clients with outstanding balances found."
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # Pattern 8: Overdue invoice queries
        elif any(phrase in lower_message for phrase in ["overdue", "late", "past due", "delinquent"]):
            print(f"MCP Integration: Detected overdue invoice pattern in message: '{message}'")
            try:
                print("MCP Integration: Getting overdue invoices...")
                result = await tools.get_overdue_invoices()
                
                if result.get("success"):
                    invoices = result.get("data", [])
                    if invoices:
                        # Calculate total overdue amount
                        total_overdue = sum(inv.get('amount', 0) for inv in invoices)
                        avg_days_overdue = sum(inv.get('days_overdue', 0) for inv in invoices) / len(invoices) if invoices else 0
                        
                        # Format overdue details for f-string
                        overdue_lines = '\n'.join([f"• **Invoice #{inv.get('invoice_number', inv.get('id', 'N/A'))}**\n" +
                                        f"  👤 Client: {inv.get('client_name', 'Unknown Client')}\n" +
                                        f"  💰 Amount: ${inv.get('amount', 0):,.2f}\n" +
                                        f"  📅 Due Date: {inv.get('due_date', 'N/A')}\n" +
                                        f"  ⏰ Days Overdue: {inv.get('days_overdue', 'N/A')}\n" +
                                        "  -----------------------------------------\n"
                                        for inv in invoices])
                        mcp_response = f"""
🚨 **Overdue Invoice Alert Report**

📊 **📈 Overdue Overview:**
• **Overdue Invoices:** {len(invoices):,}
• **Total Overdue Amount:** ${total_overdue:,.2f}
• **Average Days Overdue:** {avg_days_overdue:.1f} days
• **Average Overdue Amount:** ${(total_overdue / len(invoices)) if len(invoices) > 0 else 0:,.2f}

🚨 **💸 Overdue Details:**
{overdue_lines}

📋 **📊 Data Source:**
This comprehensive overdue invoice information was retrieved using your actual invoice data through our advanced MCP tools.
                        """.strip()
                    else:
                        mcp_response = "No overdue invoices found."
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # Pattern 9: Invoice statistics queries
        elif any(phrase in lower_message for phrase in ["stat", "statistic", "summary", "total", "count", "how many"]):
            print(f"MCP Integration: Detected statistics pattern in message: '{message}'")
            try:
                print("MCP Integration: Getting invoice statistics...")
                result = await tools.get_invoice_stats()
                
                if result.get("success"):
                    stats = result.get("data", {})
                    mcp_response = f"""
📊 **Invoice Statistics Dashboard**

📈 **📊 Business Metrics:**
• **Total Invoices:** {stats.get('total_invoices', 0):,}
• **Total Revenue:** ${stats.get('total_revenue', 0):,.2f}
• **Average Invoice Amount:** ${stats.get('average_invoice_amount', 0):,.2f}

📋 **📊 Status Breakdown:**
• **Paid Invoices:** {stats.get('paid_invoices', 0):,} ✅
• **Unpaid Invoices:** {stats.get('unpaid_invoices', 0):,} ❌
• **Overdue Invoices:** {stats.get('overdue_invoices', 0):,} 🚨

📊 **📈 Performance Insights:**
• **Payment Rate:** {((stats.get('paid_invoices', 0) / stats.get('total_invoices', 1) * 100) if stats.get('total_invoices', 0) > 0 else 0):.1f}%
• **Overdue Rate:** {((stats.get('overdue_invoices', 0) / stats.get('total_invoices', 1) * 100) if stats.get('total_invoices', 0) > 0 else 0):.1f}%

📋 **📊 Data Source:**
This comprehensive statistical analysis was performed using your actual invoice data through our advanced MCP tools.
                    """.strip()
                    
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
                else:
                    print(f"MCP Integration: Tool execution failed: {result}")
                    # Fallback to LLM if MCP fails
                    pass
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass
        
        # For other messages, use the regular LLM
        # Import litellm here to avoid circular imports
        try:
            from litellm import completion
        except ImportError:
            return {
                "success": False,
                "error": "LiteLLM not installed. Please install it with: pip install litellm"
            }
        
        # Format model name based on provider for LiteLLM
        model_name = ai_config.model_name
        
        if ai_config.provider_name == "ollama":
            # For Ollama, prefix with ollama/
            model_name = f"ollama/{ai_config.model_name}"
        elif ai_config.provider_name == "openai":
            # For OpenAI, use as-is (LiteLLM recognizes OpenAI models)
            model_name = ai_config.model_name
        elif ai_config.provider_name == "anthropic":
            # For Anthropic, use as-is (LiteLLM recognizes Anthropic models)
            model_name = ai_config.model_name
        elif ai_config.provider_name == "google":
            # For Google, use as-is (LiteLLM recognizes Google models)
            model_name = ai_config.model_name
        elif ai_config.provider_name == "custom":
            # For custom providers, use the model name as-is
            model_name = ai_config.model_name
        
        # Prepare the completion call
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 500
        }
        
        # Add provider-specific configuration
        if ai_config.provider_name == "openai":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
            if ai_config.provider_url:
                kwargs["api_base"] = ai_config.provider_url
        elif ai_config.provider_name == "ollama":
            if ai_config.provider_url:
                kwargs["api_base"] = ai_config.provider_url
        elif ai_config.provider_name == "anthropic":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
        elif ai_config.provider_name == "google":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
        elif ai_config.provider_name == "custom":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
            if ai_config.provider_url:
                kwargs["api_base"] = ai_config.provider_url
        
        # Make the completion call
        response = completion(**kwargs)
        
        ai_response = response.choices[0].message.content if response.choices else "I'm sorry, I couldn't generate a response."
        
        return {
            "success": True,
            "data": {
                "response": ai_response,
                "provider": ai_config.provider_name,
                "model": ai_config.model_name,
                "source": "llm"
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get AI response: {str(e)}"
        }
    
@router.post("/chat/message")
def save_ai_chat_message(
    message: str,
    sender: str,  # 'user' or 'ai'
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    # Get tenant_id if available
    tenant_id = getattr(current_user, 'tenant_id', None)
    # Manually set tenant context and get tenant database
    set_tenant_context(tenant_id)
    tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
    try:
        chat_message = AIChatHistory(
            user_id=current_user.id,
            tenant_id=tenant_id,
            message=message,
            sender=sender,
            created_at=datetime.now(timezone.utc)
        )
        db.add(chat_message)
        db.commit()
        db.refresh(chat_message)
        return {"success": True, "id": chat_message.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save AI chat message: {str(e)}"
        )
    
@router.get("/chat/history")
def get_ai_chat_history(
    db: Session = Depends(get_master_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    # Get tenant_id if available
    tenant_id = getattr(current_user, 'tenant_id', None)
    # Get retention days from settings (default 7, max 30)
    settings = master_db.query(Settings).filter(Settings.tenant_id == tenant_id).first()
    retention_days = 7
    if settings and hasattr(settings, 'ai_chat_history_retention_days'):
        retention_days = min(max(settings.ai_chat_history_retention_days or 7, 1), 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    # Manually set tenant context and get tenant database
    set_tenant_context(tenant_id)
    tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
    try:
        history = db.query(AIChatHistory).filter(
            AIChatHistory.user_id == current_user.id,
            (AIChatHistory.tenant_id == tenant_id) if tenant_id is not None else True,
            AIChatHistory.created_at >= cutoff
        ).order_by(AIChatHistory.created_at.asc()).all()
        # Purge old messages
        db.query(AIChatHistory).filter(
            AIChatHistory.user_id == current_user.id,
            (AIChatHistory.tenant_id == tenant_id) if tenant_id is not None else True,
            AIChatHistory.created_at < cutoff
        ).delete()
        db.commit()
        return [{
            "id": msg.id,
            "message": msg.message,
            "sender": msg.sender,
            "created_at": msg.created_at.isoformat()
        } for msg in history]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get AI chat history: {str(e)}"
        )