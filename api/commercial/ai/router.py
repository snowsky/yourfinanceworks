# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Any, Dict, List
from datetime import datetime, timedelta, timezone
import httpx
import logging
import os
import json

from core.models.database import get_master_db, get_db, set_tenant_context
from core.routers.auth import get_current_user
from core.models.models import MasterUser, Tenant
from core.models.models_per_tenant import Invoice, Client, ClientNote, AIConfig, AIChatHistory, Settings
from core.schemas.settings import Settings as SettingsSchema
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.feature_gate import require_feature
from commercial.ai.services.ai_config_service import AIConfigService
from core.constants.recommendation_codes import (
    CONSIDER_STRICTER_PAYMENT_TERMS,
    REVIEW_PAYMENT_TERMS_SLOW_CLIENTS,
    START_CREATING_INVOICES,
)

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

@router.get("/analyze-patterns", summary="Analyze invoice patterns and trends")
@require_feature("ai_invoice")
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
@require_feature("ai_invoice")
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

from pydantic import BaseModel, validator

class ChatRequest(BaseModel):
    message: str
    config_id: int = 0  # Default to 0 if not provided

# Helper class for authenticated API requests
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
            # Try to parse the error response
            try:
                # Start by getting the response text to debug
                error_text = e.response.text
                print(f"DEBUG: HTTP Error Response: {error_text}")

                try:
                    error_data = e.response.json()
                    # Handle standard FastAPI error format {"detail": ...}
                    if "detail" in error_data:
                        detail = error_data["detail"]
                        if isinstance(detail, list):
                            # Handle validation errors which are lists
                            errors = [f"{d.get('loc', [])[-1]}: {d.get('msg')}" for d in detail]
                            raise Exception(f"Validation error: {', '.join(errors)}")

                        # Map error codes to friendly messages
                        if detail == "CLIENT_ALREADY_EXISTS":
                            raise Exception("A client with this email address already exists.")

                        raise Exception(f"{detail}")
                    # Handle other JSON error formats
                    raise Exception(f"{error_data}")
                except json.JSONDecodeError:
                    # Fallback to text if not JSON
                    raise Exception(f"API Error: {error_text}")
            except Exception as inner_e:
                # If our custom parsing fails, raise the inner exception but preserve context
                # Check if it's the exception we just raised
                if str(inner_e) != "Request error: " + str(e):
                        raise inner_e
                raise Exception(f"Request error: {e}")
        except Exception as e:
                print(f"DEBUG: General Request Error: {e}")
                raise Exception(f"Request error: {e}")

    # Client Management Methods
    async def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client"""
        return await self._make_request("POST", "/clients/", json=client_data)

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

    # Expense Management Methods
    async def create_expense(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._make_request("POST", "/expenses/", json=expense_data)

    async def list_expenses(self, skip: int = 0, limit: int = 100, category: str = None, invoice_id: int = None, **kwargs) -> List[Dict[str, Any]]:
        params = {"skip": skip, "limit": limit}
        if category:
            params["category"] = category
        if invoice_id:
            params["invoice_id"] = invoice_id
        return await self._make_request(
            "GET", 
            "/expenses/",
            params=params
        )

    async def search_expenses(self, query: str, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        # Get all expenses and filter locally
        expenses = await self.list_expenses(skip=0, limit=1000)
        query_lower = query.lower()
        filtered_expenses = []

        for expense in expenses:
            searchable_fields = [
                expense.get('category', ''),
                expense.get('vendor', ''),
                expense.get('notes', ''),
                str(expense.get('amount', ''))
            ]

            if any(query_lower in str(field).lower() for field in searchable_fields if field):
                filtered_expenses.append(expense)

        end_idx = skip + limit
        return {
            "success": True,
            "data": filtered_expenses[skip:end_idx]
        }

    # Statement Management Methods
    async def list_statements(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        result = await self._make_request(
            "GET", 
            "/statements/",
            params={"skip": skip, "limit": limit}
        )
        return {
            "success": True,
            "data": result if isinstance(result, list) else result.get("statements", [])
        }

    async def close(self):
        await self._client.aclose()


@router.post("/chat")
@require_feature("ai_chat")
async def ai_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Chat with AI assistant using specified configuration
    """
    # Log the incoming request
    logger.info(f"AI Chat endpoint called with message: '{request.message}' by user: {current_user.email}")
    print(f"AI Chat endpoint called with message: '{request.message}' by user: {current_user.email}")

    # Manually set tenant context and get tenant database
    try:
        ai_config = None
        if request.config_id and request.config_id > 0:
            ai_config = db.query(AIConfig).filter(
                AIConfig.id == request.config_id,
                AIConfig.is_active == True
            ).first()
            if not ai_config:
                logger.warning(f"Requested AI config ID {request.config_id} not found or inactive, falling back to default")

        if not ai_config:
            # Get default AI configuration
            # No tenant_id filtering needed since we're in the tenant's database
            ai_config = db.query(AIConfig).filter(
                AIConfig.is_default == True,
                AIConfig.is_active == True
            ).first()

        # If no default config, check if there's only one active config and set it as default
        if not ai_config:
            active_configs = db.query(AIConfig).filter(AIConfig.is_active == True).all()
            if len(active_configs) == 1:
                config = active_configs[0]
                config.is_default = True
                db.commit()
                ai_config = config
                print(f"Auto-set single active AI config as default: {config.provider_name}")

        if not ai_config:
            # Fallback to environment variables using unified service
            print("No AI config found in database, checking environment variables...")
            logger.info("No AI config found in database, checking environment variables...")

            env_config = AIConfigService.get_ai_config(db, component="chat", require_ocr=False)

            if not env_config:
                return {
                    "success": False,
                    "error": "No AI configuration found. Please configure an AI provider in Settings > AI Provider Configurations."
                }

            # Create a temporary config object from environment variables
            class EnvAIConfig:
                def __init__(self, config_dict):
                    self.provider_name = config_dict["provider_name"]
                    self.model_name = config_dict["model_name"]
                    self.api_key = config_dict.get("api_key")
                    self.provider_url = config_dict.get("provider_url")
                    self.is_active = True
                    self.is_default = True

            ai_config = EnvAIConfig(env_config)
            print(f"Using AI config from environment: provider={ai_config.provider_name}, model={ai_config.model_name}")
            logger.info(f"Using AI config from environment: provider={ai_config.provider_name}, model={ai_config.model_name}")

        # Use AI to classify user intent and determine MCP tool
        logger.info(f"MCP Integration: Processing message: '{request.message}'")

        # Import litellm for intent classification
        try:
            from litellm import acompletion as completion
        except ImportError:
            return {
                "success": False,
                "error": "LiteLLM not installed. Please install it with: pip install litellm"
            }

        # Classify user intent using AI
        intent_prompt = f"""Classify this user message into one of these business data categories. Respond with ONLY the category name:

Categories:
- analyze_patterns: analyzing invoice patterns, trends, insights
- suggest_actions: suggesting actions, recommendations, next steps
- payments: payment queries, payment history, payment information
- clients: client management, customer information, client details, show clients, list clients
- invoices: invoice management, invoice information, invoice details, show invoices, list invoices, get invoices
- expenses: expense management, expense information, expense details, show expenses, list expenses
- statements: statement management, statement information, show statements, list statements
- currencies: currency information, exchange rates, show currencies
- outstanding: outstanding balances, unpaid amounts, debts
- overdue: overdue invoices, late payments
- statistics: statistics, summaries, totals, counts
- general: general questions not related to business data

User message: "{request.message}"

Category:"""

        # Pre-classification check for precise intents (skip LLM for specific patterns)
        lower_message = request.message.lower()

        # Check for client creation intent specifically
        if "create" in lower_message or "add" in lower_message or "new" in lower_message:
            # Fix false positive: "create invoice for client" should not trigger client creation
            # Ensure "invoice" or "expense" is not in the message when detecting client creation
            is_client_intent = ("client" in lower_message or "customer" in lower_message)
            if is_client_intent and "invoice" not in lower_message and "expense" not in lower_message:
                # Initialize basic components needed for this early path
                # Initialize MCP tools using current user's session
                from MCP.tools import InvoiceTools
                from MCP.api_client import InvoiceAPIClient

                # Create a token for the current user
                from core.routers.auth import create_access_token
                from datetime import timedelta

                access_token_expires = timedelta(minutes=30)
                jwt_token = create_access_token(
                    data={"sub": current_user.email}, expires_delta=access_token_expires
                )

                # Create a custom API client with JWT
                # Use module-level AuthenticatedAPIClient

                print(f"MCP Integration: Initializing API client with token...")
                api_client = AuthenticatedAPIClient(
                    base_url="http://localhost:8000/api/v1",
                    jwt_token=jwt_token
                )
                tools = InvoiceTools(api_client)

                print(f"MCP Integration: Detected client creation intent (Pre-LLM): '{request.message}'")

                # Use LLM to extract client details for robustness
                try:
                    from litellm import acompletion as completion

                    # Prepare extraction prompt
                    extraction_prompt = f"""Extract the client details from the following request. Return ONLY a JSON object with keys 'name', 'email', and 'phone'. 
If a field is not missing, set it to null.
Do not include any explanation, markdown formatting, or code blocks. Just the raw JSON string.

Request: "{request.message}"

JSON:"""

                    # Configure model parameters
                    extraction_model = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
                    extraction_params = {
                        "model": extraction_model,
                        "messages": [{"role": "user", "content": extraction_prompt}],
                        "temperature": 0.0, # Deterministic output
                        "max_tokens": 150
                    }

                    if ai_config.provider_name == "ollama" and ai_config.provider_url:
                        extraction_params["api_base"] = ai_config.provider_url
                    elif ai_config.api_key:
                        extraction_params["api_key"] = ai_config.api_key

                    print(f"MCP Integration: Extracting client details using LLM model: {extraction_model}")

                    extract_response = await completion(**extraction_params)
                    extract_content = extract_response.choices[0].message.content.strip()
                    # Clean up any potential markdown code blocks
                    extract_content = extract_content.replace('```json', '').replace('```', '').strip()

                    import json
                    client_details = json.loads(extract_content)
                    print(f"MCP Integration: Extracted details: {client_details}")

                    name = client_details.get("name")
                    email = client_details.get("email")
                    phone = client_details.get("phone")

                except Exception as e:
                    print(f"MCP Integration: LLM extraction failed: {e}. Falling back to regex.")
                    # Fallback to simple regex if LLM fails
                    import re
                    name = None
                    name_match = re.search(r'(?:create|add|new)\s+(?:a\s+)?client\s+(?:named\s+|called\s+)?["\']?([^"\',]+)["\']?', request.message, re.IGNORECASE)
                    if name_match:
                        name = name_match.group(1).strip()
                    else:
                        simple_match = re.search(r'(?:create|add|new)\s+(?:a\s+)?client\s+([a-zA-Z0-9\s]+?)(?:\s+with|\s*$)', request.message, re.IGNORECASE)
                        if simple_match:
                            name = simple_match.group(1).strip()

                    email = None
                    email_match = re.search(r'email\s+["\']?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)["\']?', request.message, re.IGNORECASE)
                    if email_match:
                        email = email_match.group(1)

                    phone = None
                    phone_match = re.search(r'phone\s+["\']?([0-9+\-\s()]{7,})["\']?', request.message, re.IGNORECASE)
                    if phone_match:
                        phone = phone_match.group(1)

                if name:
                    # Check if email is present (required by database)
                    if not email:
                        mcp_response = f"I see you want to create a client named '{name}', but I need their email address as it is required. Please provide the email address."
                        return {
                            "success": True,
                            "data": {
                                "response": mcp_response,
                                "provider": ai_config.provider_name,
                                "model": ai_config.model_name, # Fallback if not available
                                "source": "mcp_tools"
                            }
                        }

                    print(f"MCP Integration: Creating client: name='{name}', email='{email}', phone='{phone}'")
                    result = await tools.create_client(name=name, email=email, phone=phone)

                    if result.get("success"):
                        client = result.get("data", {})
                        mcp_response = f"""
✅ **Client Created Successfully**

👤 **Client Details:**
• **Name:** {client.get('name', name)}
• **ID:** {client.get('id', 'N/A')}
{f"• **Email:** {client.get('email')}" if client.get('email') else ""}
{f"• **Phone:** {client.get('phone')}" if client.get('phone') else ""}

You can now create invoices for this client.
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
                        print(f"Failed to create client: {result}")
                        # If failed, let it fall through to LLM? Or return error?
                        # Better to return error
                        return {
                            "success": True,  # Chat success, but op failed
                            "data": {
                                "response": f"Failed to create client: {result.get('error', 'Unknown error')}",
                                "provider": ai_config.provider_name,
                                "model": ai_config.model_name,
                                "source": "mcp_tools"
                            }
                        }

            elif "expense" in lower_message:
                # Initialize basic components needed for this early path
                from MCP.tools import InvoiceTools

                # Create a token for the current user
                from core.routers.auth import create_access_token
                from datetime import timedelta

                access_token_expires = timedelta(minutes=30)
                jwt_token = create_access_token(
                    data={"sub": current_user.email}, expires_delta=access_token_expires
                )

                print(f"MCP Integration: Initializing API client with token...")
                api_client = AuthenticatedAPIClient(
                    base_url="http://localhost:8000/api/v1",
                    jwt_token=jwt_token
                )
                tools = InvoiceTools(api_client)

                print(f"MCP Integration: Detected expense creation intent (Pre-LLM): '{request.message}'")

                # Use LLM to extract expense details
                try:
                    from litellm import acompletion as completion
                    import json
                    from datetime import datetime

                    # Prepare extraction prompt
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    extraction_prompt = f"""Extract the expense details from the following request. Return ONLY a JSON object.
Required keys: 'amount' (number), 'category' (string), 'expense_date' (YYYY-MM-DD).
Optional keys: 'vendor' (string), 'notes' (string), 'currency' (default 'USD').
If the date is "today", use {current_date}.
Do not include any explanation, markdown formatting, or code blocks. Just the raw JSON string.

Request: "{request.message}"

JSON:"""

                    # Configure model parameters
                    extraction_model = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
                    extraction_params = {
                        "model": extraction_model,
                        "messages": [{"role": "user", "content": extraction_prompt}],
                        "temperature": 0.0, 
                        "max_tokens": 150
                    }

                    if ai_config.provider_name == "ollama" and ai_config.provider_url:
                        extraction_params["api_base"] = ai_config.provider_url
                    elif ai_config.api_key:
                        extraction_params["api_key"] = ai_config.api_key

                    print(f"MCP Integration: Extracting expense details using LLM model: {extraction_model}")

                    extract_response = await completion(**extraction_params)
                    extract_content = extract_response.choices[0].message.content.strip()
                    extract_content = extract_content.replace('```json', '').replace('```', '').strip()

                    expense_details = json.loads(extract_content)
                    print(f"MCP Integration: Extracted expense details: {expense_details}")

                    # Validate required fields
                    amount = expense_details.get("amount")
                    category = expense_details.get("category")
                    expense_date = expense_details.get("expense_date")

                    if str(amount) and category and expense_date:
                            # Set defaults
                            if not expense_details.get("currency"):
                                expense_details["currency"] = "USD"

                            print(f"MCP Integration: Creating expense with details: {expense_details}")
                            result = await tools.create_expense(**expense_details)

                            # Check for success (API returns wrapped response or object)
                            expense_data = None
                            if result and isinstance(result, dict):
                                if "id" in result:
                                    expense_data = result
                                elif result.get("success") and "data" in result:
                                    expense_data = result.get("data")

                            if expense_data and "id" in expense_data:
                                expense = expense_data
                                mcp_response = f"""
✅ **Expense Created Successfully**

💸 **Expense Details:**
• **ID:** {expense.get('id', 'N/A')}
• **Amount:** ${expense.get('amount', 0):,.2f} {expense.get('currency', 'USD')}
• **Category:** {expense.get('category', 'N/A')}
• **Date:** {expense.get('expense_date', 'N/A')}
{f"• **Vendor:** {expense.get('vendor')}" if expense.get('vendor') else ""}

Expense has been recorded.
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
                                error_msg = result.get('detail', 'Unknown error') if isinstance(result, dict) else str(result)
                                print(f"Failed to create expense: {result}")
                                return {
                                    "success": True,
                                    "data": {
                                        "response": f"Failed to create expense: {error_msg}",
                                        "provider": ai_config.provider_name,
                                        "model": ai_config.model_name,
                                        "source": "mcp_tools"
                                    }
                                }
                    else:
                            return {
                                "success": True,
                                "data": {
                                    "response": "I understood you want to create an expense, but missing required details (Amount, Category, or Date). Please specify them.",
                                    "provider": ai_config.provider_name,
                                    "model": ai_config.model_name,
                                    "source": "mcp_tools"
                                }
                            }

                except Exception as e:
                    print(f"MCP Integration: Expense extraction/creation failed: {e}")
                    import traceback
                    traceback.print_exc()
                    return {
                        "success": True,
                        "data": {
                            "response": f"Failed to process expense creation request: {str(e)}",
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }
        # Get intent classification
        model_name = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name

        # Standardize model parameters
        model_params = AIConfigService.get_model_parameters(model_name, max_tokens=50, temperature=0.1)

        kwargs = {
            "model": model_name, 
            "messages": [{"role": "user", "content": intent_prompt}],
            **model_params
        }

        if ai_config.provider_name == "ollama" and ai_config.provider_url:
            kwargs["api_base"] = ai_config.provider_url
        elif ai_config.api_key:
            kwargs["api_key"] = ai_config.api_key

        try:
            intent_response = await completion(**kwargs)
            intent = intent_response.choices[0].message.content.strip().lower()
            # Handle empty or invalid responses
            if not intent or intent == "" or len(intent) > 50:
                intent = "general"
            # Simple keyword fallback for common patterns
            if intent == "general":
                msg_lower = request.message.lower()
                if any(word in msg_lower for word in ["invoice", "invoices", "show invoice", "list invoice"]):
                    intent = "invoices"
                elif any(word in msg_lower for word in ["client", "clients", "customer", "customers"]):
                    intent = "clients"
                elif any(word in msg_lower for word in ["payment", "payments"]):
                    intent = "payments"
                elif any(word in msg_lower for word in ["expense", "expenses"]):
                    intent = "expenses"
                elif any(word in msg_lower for word in ["bank", "statements", "show statements", "list statements"]):
                    intent = "statements"
                elif any(word in msg_lower for word in ["currency", "currencies", "exchange rate", "exchange rates", "show currencies", "list currencies"]):
                    intent = "currencies"
                elif any(word in msg_lower for word in ["outstanding", "outstanding balance", "unpaid", "unpaid amount", "show outstanding", "list outstanding"]):
                    intent = "outstanding"
                elif any(word in msg_lower for word in ["overdue", "late payment", "show overdue", "list overdue"]):
                    intent = "overdue"
                elif any(word in msg_lower for word in ["statistics", "summary", "total", "count", "show statistics", "list statistics"]):
                    intent = "statistics"
                else:
                    intent = "general"

            logger.info(f"MCP Integration: AI classified intent as: '{intent}'")
        except Exception as e:
            print(f"MCP Integration: Intent classification failed: {e}")
            intent = "general"

        # Initialize MCP tools using current user's session
        from MCP.tools import InvoiceTools
        from MCP.api_client import InvoiceAPIClient
        from fastapi import Request

        # Create a token for the current user to use with MCP tools
        from core.routers.auth import create_access_token
        from datetime import timedelta

        # Create a token for the current user
        access_token_expires = timedelta(minutes=30)
        jwt_token = create_access_token(
            data={"sub": current_user.email}, expires_delta=access_token_expires
        )

        print(f"MCP Integration: Initializing API client with token...")
        api_client = AuthenticatedAPIClient(
            base_url="http://localhost:8000/api/v1",
            jwt_token=jwt_token
        )
        tools = InvoiceTools(api_client)
        print("MCP Integration: API client and tools initialized successfully")

        # Execute MCP tool based on AI-classified intent
        if intent == "analyze_patterns":
            print(f"MCP Integration: Detected analyze pattern in message: '{request.message}'")
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

        elif intent == "suggest_actions":
            print(f"MCP Integration: Detected suggest pattern in message: '{request.message}'")
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
                        # Ensure priority is a string
                        if not isinstance(priority, str):
                            priority = str(priority)
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

        elif intent == "payments":
            print(f"MCP Integration: Detected payment pattern in message: '{request.message}'")
            try:
                print("MCP Integration: Querying payments with natural language...")
                result = await tools.query_payments(query=request.message)

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

        elif intent == "clients":
            lower_message = request.message.lower()
            print(f"MCP Integration: Detected client management pattern in message: '{request.message}'")
            print(f"MCP Integration: lower_message: '{lower_message}'")
            print(f"MCP Integration: Checking patterns: {[phrase for phrase in ['client', 'customer', 'list clients', 'search client', 'find client', 'show clients', 'get clients'] if phrase in lower_message]}")
            try:
                if "create" in lower_message or "add" in lower_message or "new" in lower_message:
                    # Client creation intent
                    print(f"MCP Integration: Detected client creation intent in message: '{request.message}'")

                    # Extract client details using regex
                    import re

                    # Extract name (required)
                    # Patterns: "create client named X", "create client X", "add client X", "new client X"
                    name = None
                    name_match = re.search(r'(?:create|add|new)\s+(?:a\s+)?client\s+(?:named\s+|called\s+)?["\']?([^"\',]+)["\']?', lower_message, re.IGNORECASE)
                    if name_match:
                        name = name_match.group(1).strip()
                    else:
                        # Fallback: try to find a name after "client" if no quotes
                        simple_match = re.search(r'(?:create|add|new)\s+(?:a\s+)?client\s+([a-zA-Z0-9\s]+?)(?:\s+with|\s*$)', lower_message, re.IGNORECASE)
                        if simple_match:
                            name = simple_match.group(1).strip()

                    # Extract email (optional)
                    email = None
                    email_match = re.search(r'email\s+["\']?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)["\']?', lower_message, re.IGNORECASE)
                    if email_match:
                        email = email_match.group(1)

                    # Extract phone (optional)
                    phone = None
                    phone_match = re.search(r'phone\s+["\']?([0-9+\-\s()]{7,})["\']?', lower_message, re.IGNORECASE)
                    if phone_match:
                        phone = phone_match.group(1)

                    if name:
                        print(f"MCP Integration: Creating client: name='{name}', email='{email}', phone='{phone}'")
                        result = await tools.create_client(name=name, email=email, phone=phone)

                        if result.get("success"):
                            client = result.get("data", {})
                            mcp_response = f"""
✅ **Client Created Successfully**

👤 **Client Details:**
• **Name:** {client.get('name', name)}
• **ID:** {client.get('id', 'N/A')}
{f"• **Email:** {client.get('email')}" if client.get('email') else ""}
{f"• **Phone:** {client.get('phone')}" if client.get('phone') else ""}

You can now create invoices for this client.
                            """.strip()
                        else:
                            mcp_response = f"Failed to create client: {result.get('error', 'Unknown error')}"
                    else:
                        mcp_response = "I understood you want to create a client, but I couldn't extract the client name. Please specify the name, e.g., 'Create a client named John Doe'."

                elif "search" in lower_message or "find" in lower_message:
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

                if "create" not in lower_message and "add" not in lower_message and "new" not in lower_message:
                    # Only process list/search results here, creation is handled above
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
                    else:
                        # Fallback for search/list errors
                        mcp_response = f"Error retrieving clients: {result.get('error', 'Unknown error')}"

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

        elif intent == "currencies":
            print(f"MCP Integration: Detected currency pattern in message: '{request.message}'")
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

        elif intent == "outstanding":
            print(f"MCP Integration: Detected outstanding balance pattern in message: '{request.message}'")
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

        elif intent == "overdue":
            print(f"MCP Integration: Detected overdue invoice pattern in message: '{request.message}'")
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


        elif intent == "invoices":
            lower_message = request.message.lower()
            print(f"MCP Integration: Detected invoice pattern in message: '{request.message}'")
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
                else:
                    # Fallback for search/list errors
                    mcp_response = f"Error retrieving invoices: {result.get('error', 'Unknown error')}"

                return {
                    "success": True,
                    "data": {
                        "response": mcp_response,
                        "provider": ai_config.provider_name,
                        "model": ai_config.model_name,
                        "source": "mcp_tools"
                    }
                }
            except Exception as e:
                print(f"MCP Integration: Exception during tool execution: {e}")
                # Fallback to LLM
                pass

        elif intent == "expenses":
            lower_message = request.message.lower()
            print(f"MCP Integration: Detected expense management pattern in message: '{request.message}'")
            try:
                if "search" in lower_message or "find" in lower_message:
                    # Extract search query from message
                    import re
                    search_match = re.search(r'(?:search|find)\s+(?:for\s+)?["\']?([^"\']+)["\']?', lower_message)
                    if search_match:
                        search_query = search_match.group(1)
                        print(f"MCP Integration: Searching expenses with query: '{search_query}'")
                        result = await tools.search_expenses(query=search_query)
                    else:
                        # Default search
                        result = await tools.list_expenses(limit=10)
                else:
                    # List all expenses
                    print("MCP Integration: Listing expenses...")
                    result = await tools.list_expenses(limit=20)

                if result.get("success"):
                    expenses = result.get("data", [])
                    if expenses:
                        # Calculate totals
                        total_amount = sum(exp.get('amount', 0) or 0 for exp in expenses)
                        total_tax = sum(exp.get('tax_amount', 0) or 0 for exp in expenses)
                        total_with_tax = sum((exp.get('total_amount') or exp.get('amount', 0) or 0) for exp in expenses)

                        # Format expense details for f-string
                        expense_lines = '\n'.join([f"• **Expense #{exp.get('id', 'N/A')}**\n" +
                                        f"  📝 Category: {exp.get('category', 'Unknown')}\n" +
                                        f"  🏪 Vendor: {exp.get('vendor', 'N/A')}\n" +
                                        f"  💰 Amount: ${(exp.get('amount') or 0):,.2f}\n" +
                                        f"  📊 Tax: ${(exp.get('tax_amount') or 0):,.2f}\n" +
                                        f"  💳 Total: ${(exp.get('total_amount') or exp.get('amount') or 0):,.2f}\n" +
                                        f"  📅 Date: {exp.get('expense_date', 'N/A')}\n" +
                                        "  -----------------------------------------\n"
                                        for exp in expenses])
                        mcp_response = f"""
💸 **Expense Management Dashboard**

📊 **📈 Expense Overview:**
• **Total Expenses:** {len(expenses):,}
• **Total Amount (Pre-Tax):** ${total_amount:,.2f}
• **Total Tax:** ${total_tax:,.2f}
• **Total Amount (With Tax):** ${total_with_tax:,.2f}
• **Average Expense:** ${(total_amount / len(expenses)) if len(expenses) > 0 else 0:,.2f}

💸 **💼 Expense Details:**
{expense_lines}

📋 **📊 Data Source:**
This comprehensive expense information was retrieved using your actual expense data through our advanced MCP tools.
                        """.strip()
                    else:
                        mcp_response = "No expenses found matching your query."

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

        elif intent == "statements":
            print(f"MCP Integration: Detected statement pattern in message: '{request.message}'")
            logger.info(f"MCP Integration: Detected statement pattern in message: '{request.message}'")
            try:
                print("MCP Integration: Listing statements...")
                logger.info("MCP Integration: Listing statements...")
                result = await tools.list_statements()
                print(f"MCP Integration: Statements result: {result}")
                logger.info(f"MCP Integration: Statements result: {result}")

                if result.get("success"):
                    statements = result.get("data", [])
                    print(f"MCP Integration: Retrieved {len(statements)} statements")
                    logger.info(f"MCP Integration: Retrieved {len(statements)} statements")
                    if statements:
                        # Format statement details for f-string
                        statement_lines = '\n'.join([f"• **Statement #{stmt.get('id', 'N/A')}**\n" +
                                        f"  🏦 Account: {stmt.get('account_name', 'Unknown')}\n" +
                                        f"  📅 Period: {stmt.get('statement_period', 'N/A')}\n" +
                                        f"  📊 Status: {stmt.get('status', 'Unknown').title()}\n" +
                                        f"  📄 Transactions: {stmt.get('transaction_count', 'N/A')}\n" +
                                        f"  📅 Imported: {stmt.get('created_at', 'N/A')}\n" +
                                        "  -----------------------------------------\n"
                                        for stmt in statements])
                        mcp_response = f"""
🏦 **Statement Management Dashboard**

📊 **📈 Statement Overview:**
• **Total Statements:** {len(statements):,}
• **Processed Statements:** {len([s for s in statements if s.get('status') == 'processed']):,}
• **Pending Statements:** {len([s for s in statements if s.get('status') == 'pending']):,}

🏦 **💼 Statement Details:**
{statement_lines}

📋 **📊 Data Source:**
This comprehensive bank statement information was retrieved using your actual bank statement data through our advanced MCP tools.
                        """.strip()
                    else:
                        mcp_response = "No bank statements found."

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

        elif intent == "statistics":
            print(f"MCP Integration: Detected statistics pattern in message: '{request.message}'")
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

        # For general queries or unmatched intents, use the regular LLM
        else:
            print(f"MCP Integration: Intent '{intent}' - falling back to LLM")
        # Import litellm here to avoid circular imports
        try:
            from litellm import acompletion as completion
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
            "messages": [{"role": "user", "content": request.message}],
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
        response = await completion(**kwargs)

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

class ChatMessageRequest(BaseModel):
    message: str
    sender: str  # 'user' or 'ai'

    @validator('sender')
    def validate_sender(cls, v):
        if v not in ['user', 'ai']:
            raise ValueError('sender must be either "user" or "ai"')
        return v

@router.post("/chat/message")
def save_ai_chat_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    try:
        chat_message = AIChatHistory(
            user_id=current_user.id,
            tenant_id=getattr(current_user, 'tenant_id', None),
            message=request.message,
            sender=request.sender,
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
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    try:
        # Validate pagination parameters
        limit = max(1, min(100, limit))  # Clamp between 1 and 100
        offset = max(0, offset)

        # Get retention period from core.settings (default 7 days, max 30 days)
        # Use the same approach as settings router - get from key-value store
        retention_setting = db.query(Settings).filter(Settings.key == "ai_chat_history_retention_days").first()
        retention_days = 7  # default
        if retention_setting and retention_setting.value:
            try:
                retention_days = int(retention_setting.value)
                # Ensure retention is within allowed range (1-30 days)
                retention_days = max(1, min(30, retention_days))
            except (ValueError, TypeError):
                retention_days = 7

        try:
            user_id = current_user.id
            logger.info(f"AI Chat History: retention_days={retention_days}, user_id={user_id}, limit={limit}, offset={offset}")
        except AttributeError as e:
            logger.error(f"AI Chat History: current_user has no id attribute: {e}, user_attrs={dir(current_user)}")
            raise HTTPException(status_code=500, detail="User authentication error")

        # Calculate cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        # Get total count for pagination info
        total_count = db.query(AIChatHistory).filter(
            AIChatHistory.user_id == current_user.id,
            AIChatHistory.created_at >= cutoff_date
        ).count()

        # Get chat history within retention period, ordered by most recent first, then paginate
        history = db.query(AIChatHistory).filter(
            AIChatHistory.user_id == current_user.id,
            AIChatHistory.created_at >= cutoff_date
        ).order_by(AIChatHistory.created_at.desc()).offset(offset).limit(limit).all()

        # For initial load (offset=0), reverse to get chronological order (oldest first in the batch)
        # For pagination, keep descending order since we're prepending
        if offset == 0:
            history = list(reversed(history))

        # Purge old messages (older than retention period) - only on first request
        if offset == 0:
            deleted_count = db.query(AIChatHistory).filter(
                AIChatHistory.user_id == current_user.id,
                AIChatHistory.created_at < cutoff_date
            ).delete()

            if deleted_count > 0:
                db.commit()
                logger.info(f"Purged {deleted_count} old AI chat messages for user {current_user.id}")

        return [{
            "id": msg.id,
            "message": msg.message,
            "sender": msg.sender,
            "created_at": msg.created_at.isoformat()
        } for msg in history]
    except Exception as e:
        logger.error(f"AI Chat History error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get AI chat history: {str(e)}"
        )

@router.post("/summarize-client-notes/{client_id}")
@require_feature("ai_chat")
async def summarize_client_notes(
    client_id: int,
    language: str = "English",
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Summarize client notes using AI
    """
    try:
        # Get client notes
        notes = db.query(ClientNote).filter(ClientNote.client_id == client_id).all()

        if not notes:
            logger.info(f"Summarize Client Notes: No notes found for client {client_id}")
            return {
                "success": False,
                "message": "No notes found to summarize."
            }

        # Combine notes into a single text
        notes_text = "\n".join([f"- {note.note} (Date: {note.created_at.strftime('%Y-%m-%d')})" for note in notes])
        logger.info(f"Summarize Client Notes: Found {len(notes)} notes for client {client_id}")
        logger.info(f"Summarize Client Notes: Notes text: {notes_text}")

        # Get AI config
        ai_config = db.query(AIConfig).filter(
            AIConfig.is_default == True,
            AIConfig.is_active == True
        ).first()

        if not ai_config:
            # Fallback to single active config
            active_configs = db.query(AIConfig).filter(AIConfig.is_active == True).all()
            if len(active_configs) == 1:
                config = active_configs[0]
                config.is_default = True
                db.commit()
                ai_config = config

        if not ai_config:
            # Fallback to environment variables
            from commercial.ai.services.ai_config_service import AIConfigService
            env_config = AIConfigService.get_ai_config(db, component="chat", require_ocr=False)

            if not env_config:
                 return {
                    "success": False,
                    "error": "No AI configuration found."
                }

            class EnvAIConfig:
                def __init__(self, config_dict):
                    self.provider_name = config_dict["provider_name"]
                    self.model_name = config_dict["model_name"]
                    self.api_key = config_dict.get("api_key")
                    self.provider_url = config_dict.get("provider_url")
                    self.is_active = True
                    self.is_default = True
                    self.max_tokens = 1000
                    self.temperature = 0.5

            ai_config = EnvAIConfig(env_config)

        # Construct prompt
        prompt = f"""You are a helpful assistant. Please summarize the following client notes for me in {language}. Even if the notes are brief, provide a summary or restatement of the content in {language}.

Client Notes:
{notes_text}

Summary ({language}):"""

        logger.info(f"Summarize Client Notes: Using provider: {ai_config.provider_name}, model: {ai_config.model_name}, language: {language}")
        logger.info(f"Summarize Client Notes: Generated prompt: {prompt}")

        # Call AI provider (Reuse logic from chat or use litellm if available/preferred, here copying structure for consistency)
        ai_response = ""

        if ai_config.provider_name == "ollama":
            payload = {
                "model": ai_config.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {
                    "num_predict": ai_config.max_tokens or 4096,
                    "temperature": ai_config.temperature or 0.1
                }
            }
            if ai_config.provider_url:
                url = f"{ai_config.provider_url}/api/chat"
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, timeout=60.0)
                    response.raise_for_status()
                    ai_response = response.json()["message"]["content"]

        elif ai_config.provider_name == "openai":
            headers = {
                "Authorization": f"Bearer {ai_config.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": ai_config.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": ai_config.max_tokens or 4096,
                "temperature": ai_config.temperature or 0.1
            }
            url = "https://api.openai.com/v1/chat/completions"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                ai_response = response.json()["choices"][0]["message"]["content"]

        elif ai_config.provider_name == "anthropic":
             headers = {
                "x-api-key": ai_config.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
             payload = {
                "model": ai_config.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": ai_config.max_tokens or 4096,
                "temperature": ai_config.temperature or 0.1
            }
             url = "https://api.anthropic.com/v1/messages"
             async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                ai_response = response.json()["content"][0]["text"]

        else:
             # Basic fallback if provider not explicitly matched but exists (could use litellm generic)
             return {
                "success": False,
                "error": f"Unsupported provider for summarization: {ai_config.provider_name}"
            }

        return {
            "success": True,
            "data": {
                "summary": ai_response,
                "provider": ai_config.provider_name,
                "model": ai_config.model_name
            }
        }

    except Exception as e:
        logger.error(f"Summarize Client Notes error: {repr(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
