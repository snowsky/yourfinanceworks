from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Any, Dict, List
from datetime import datetime, timedelta, timezone
import asyncio
import httpx

from models.database import get_db
from routers.auth import get_current_user
from models.models_per_tenant import User, Invoice, Client, Payment, AIConfig
from models.models import Tenant

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

@router.get("/analyze-patterns", summary="Analyze invoice patterns and trends")
async def analyze_patterns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
                # Calculate paid amount from payments
                paid_amount = sum(payment.amount for payment in inv.payments)
                if currency not in total_revenue_by_currency:
                    total_revenue_by_currency[currency] = 0
                total_revenue_by_currency[currency] += paid_amount
            
            if inv.status in ["pending", "draft", "overdue"]:
                if currency not in outstanding_revenue_by_currency:
                    outstanding_revenue_by_currency[currency] = 0
                outstanding_revenue_by_currency[currency] += inv.amount
        
        # Get client payment patterns (explicit join)
        from sqlalchemy.orm import aliased
        InvoiceAlias = aliased(Invoice)
        PaymentAlias = aliased(Payment)
        client_payments_raw = (
            db.query(
                Client.name,
                func.avg(PaymentAlias.payment_date - InvoiceAlias.due_date).label('avg_payment_delay')
            )
            .join(InvoiceAlias, InvoiceAlias.client_id == Client.id)
            .join(PaymentAlias, PaymentAlias.invoice_id == InvoiceAlias.id)
            # No tenant_id filtering needed since we're in the tenant's database
            .group_by(Client.name)
            .all()
        )
        
        # Convert SQLAlchemy Row objects to dictionaries
        client_payments = []
        for row in client_payments_raw:
            client_payments.append({
                "name": row[0],
                "avg_payment_delay": row[1].days if row[1] else None
            })
        
        # Sort clients by payment speed
        fastest_paying_clients = sorted(client_payments, key=lambda x: x["avg_payment_delay"] or 999)[:3]
        slowest_paying_clients = sorted(client_payments, key=lambda x: x["avg_payment_delay"] or 0, reverse=True)[:3]
        
        # Generate recommendations
        recommendations = []
        if overdue_invoices > 0:
            recommendations.append(f"Send reminders for {overdue_invoices} overdue invoices")
        
        # Calculate total outstanding and total revenue across all currencies
        total_outstanding = sum(outstanding_revenue_by_currency.values())
        total_revenue = sum(total_revenue_by_currency.values())
        
        if total_outstanding > total_revenue * 0.3:
            recommendations.append("Consider implementing stricter payment terms")
        if slowest_paying_clients:
            recommendations.append("Review payment terms for slow-paying clients")
        if total_invoices == 0:
            recommendations.append("Start creating invoices to track your business")
        
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Provides actionable recommendations and suggestions based on the
    analysis of invoice patterns, such as sending reminders for overdue
    invoices or reviewing payment terms for slow-paying clients.
    """
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
async def chat_with_ai(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat with AI using configured provider and MCP tools"""
    try:
        message = request.get("message", "")
        config_id = request.get("config_id")
        
        if not message:
            return {
                "success": False,
                "error": "Message is required"
            }
        
        # Get AI configuration
        if config_id:
            # No tenant_id filtering needed since we're in the tenant's database
            ai_config = db.query(AIConfig).filter(
                AIConfig.id == config_id,
                AIConfig.is_active == True
            ).first()
        else:
            # Get default active configuration
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
        api_client = AuthenticatedAPIClient(
            base_url="http://localhost:8000/api/v1",
            jwt_token=jwt_token
        )
        tools = InvoiceTools(api_client)
        
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
                    mcp_response = f"""
**Invoice Pattern Analysis**

📊 **Summary:**
- Total Invoices: {data.get('total_invoices', 0)}
- Paid Invoices: {data.get('paid_invoices', 0)}
- Unpaid Invoices: {data.get('unpaid_invoices', 0)}
- Overdue Invoices: {data.get('overdue_invoices', 0)}
- Total Revenue: ${data.get('total_revenue', 0)}
- Outstanding Revenue: ${data.get('outstanding_revenue', 0)}

💡 **Recommendations:**
{chr(10).join([f"- {rec}" for rec in data.get('recommendations', [])])}

This analysis was performed using your actual invoice data through our MCP tools.
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
                    
                    mcp_response = f"""
**Suggested Actions**

🎯 **Recommended Actions:**
{chr(10).join([f"- **{action.get('action', 'Unknown')}**: {action.get('description', 'No description')} (Priority: {action.get('priority', 'medium')})" for action in actions])}

📈 **Summary:**
- Overdue Invoices: {data.get('overdue_count', 0)}
- Clients with Balance: {data.get('clients_with_balance', 0)}
- Recent Invoices: {data.get('recent_invoices_count', 0)}

These suggestions are based on your actual invoice data and business patterns.
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
                            response_title = f"**Payments {date_description}**"
                        else:
                            response_title = "**Payment Information**"
                        
                        mcp_response = f"""
{response_title}

💰 **Payments ({len(payments)} found):**
{chr(10).join([f"- **Payment #{payment.get('id', 'N/A')}** - Invoice #{payment.get('invoice_number', 'N/A')}" +
                f" - Amount: ${payment.get('amount', 0)}" +
                f" - Method: {payment.get('payment_method', 'Unknown')}" +
                f" - Date: {payment.get('payment_date', 'N/A')}"
                for payment in payments])}

This information was retrieved using your actual payment data through our MCP tools.
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
        elif any(phrase in lower_message for phrase in ["client", "customer", "list clients", "search client", "find client"]) and not any(phrase in lower_message for phrase in ["payment", "pay", "paid"]):
            print(f"MCP Integration: Detected client management pattern in message: '{message}'")
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
                    result = await tools.list_clients(limit=20)
                
                if result.get("success"):
                    clients = result.get("data", [])
                    if clients:
                        mcp_response = f"""
**Client Information**

👥 **Clients ({len(clients)} found):**
{chr(10).join([f"- **{client.get('name', 'Unknown')}** (ID: {client.get('id', 'N/A')})" + 
                (f" - Email: {client.get('email', 'N/A')}" if client.get('email') else "") +
                (f" - Phone: {client.get('phone', 'N/A')}" if client.get('phone') else "") +
                (f" - Balance: ${client.get('balance', 0)}" if client.get('balance') else "")
                for client in clients])}

This information was retrieved using your actual client data through our MCP tools.
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
                        mcp_response = f"""
**Invoice Information**

📄 **Invoices ({len(invoices)} found):**
{chr(10).join([f"- **Invoice #{inv.get('invoice_number', inv.get('id', 'N/A'))}** - {inv.get('client_name', 'Unknown Client')}" +
                f" - Amount: ${inv.get('amount', 0)}" +
                f" - Status: {inv.get('status', 'Unknown')}" +
                f" - Due: {inv.get('due_date', 'N/A')}"
                for inv in invoices])}

This information was retrieved using your actual invoice data through our MCP tools.
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
                        mcp_response = f"""
**Currency Information**

💱 **Active Currencies ({len(currencies)} found):**
{chr(10).join([f"- **{currency.get('code', 'N/A')}** ({currency.get('symbol', '')}) - {currency.get('name', 'Unknown')}"
                for currency in currencies])}

This information was retrieved using your actual currency data through our MCP tools.
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
                        mcp_response = f"""
**Outstanding Balances**

⚠️ **Clients with Outstanding Balances ({len(clients)} found):**
{chr(10).join([f"- **{client.get('name', 'Unknown')}** - Balance: ${client.get('balance', 0)}"
                for client in clients])}

This information was retrieved using your actual client data through our MCP tools.
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
                        mcp_response = f"""
**Overdue Invoices**

🚨 **Overdue Invoices ({len(invoices)} found):**
{chr(10).join([f"- **Invoice #{inv.get('invoice_number', inv.get('id', 'N/A'))}** - {inv.get('client_name', 'Unknown Client')}" +
                f" - Amount: ${inv.get('amount', 0)}" +
                f" - Due Date: {inv.get('due_date', 'N/A')}" +
                f" - Days Overdue: {inv.get('days_overdue', 'N/A')}"
                for inv in invoices])}

This information was retrieved using your actual invoice data through our MCP tools.
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
**Invoice Statistics**

📊 **Summary:**
- Total Invoices: {stats.get('total_invoices', 0)}
- Total Revenue: ${stats.get('total_revenue', 0)}
- Paid Invoices: {stats.get('paid_invoices', 0)}
- Unpaid Invoices: {stats.get('unpaid_invoices', 0)}
- Overdue Invoices: {stats.get('overdue_invoices', 0)}
- Average Invoice Amount: ${stats.get('average_invoice_amount', 0)}

This information was retrieved using your actual invoice data through our MCP tools.
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
