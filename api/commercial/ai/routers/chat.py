# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

import json
import logging
import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.models.models_per_tenant import AIConfig
from core.utils.feature_gate import require_feature
from commercial.ai.services.ai_config_service import AIConfigService
from commercial.ai.routers.chat_models import ChatRequest
from commercial.ai.routers.action_handlers import handle_early_actions
from commercial.ai.routers.intent_handlers import dispatch_intent
from commercial.ai.routers.auth_client import AuthenticatedAPIClient

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

router = APIRouter()


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
        # Get AI configuration using centralized service
        # This prioritizes database settings, then falls back to environment variables
        config_dict = AIConfigService.get_ai_config(db, component="chat", require_ocr=False)

        if not config_dict:
            return {
                "success": False,
                "error": "No AI configuration found. Please configure an AI provider in Settings > AI Provider Configurations."
            }

        # Convert dictionary to an object with attributes for backward compatibility
        class AIConfigObj:
            def __init__(self, d):
                self.provider_name = d["provider_name"]
                self.model_name = d["model_name"]
                self.api_key = d.get("api_key")
                self.provider_url = d.get("provider_url")
                self.is_active = True
                self.is_default = True

        ai_config = AIConfigObj(config_dict)
        print(f"Using AI config: provider={ai_config.provider_name}, model={ai_config.model_name}, source={config_dict.get('source', 'unknown')}")
        logger.info(f"Using AI config: provider={ai_config.provider_name}, model={ai_config.model_name}, source={config_dict.get('source', 'unknown')}")

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
        page_context = request.page_context if isinstance(request.page_context, dict) else None
        page_context_block = ""
        if page_context:
            try:
                page_context_block = f"\nCurrent page context (JSON): {json.dumps(page_context, ensure_ascii=False)}\n"
            except Exception:
                page_context_block = f"\nCurrent page context: {page_context}\n"

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
- investments: investment portfolios, holdings, performance, dividends, trade history
- general: general questions not related to business data

{page_context_block}
User message: "{request.message}"

Category:"""

        # Pre-classification check for precise intents (skip LLM for specific patterns)
        lower_message = request.message.lower()

        # PRE-CLASSIFICATION FAST-PATH
        # If the user is asking for specific common things, we skip the LLM classification to save time and increase accuracy
        intent = "general"
        msg_lower = lower_message
        if any(word in msg_lower for word in ["overdue", "late payment"]):
            intent = "overdue"
            logger.info(f"Fast-path: Detected 'overdue' intent via keywords")
        elif any(word in msg_lower for word in ["outstanding balance", "unpaid"]):
            intent = "outstanding"
            logger.info(f"Fast-path: Detected 'outstanding' intent via keywords")
        elif any(word in msg_lower for word in ["show invoices", "list invoices"]):
            intent = "invoices"
            logger.info(f"Fast-path: Detected 'invoices' intent via keywords")

        if intent == "general":
            # Only call LLM if fast-path didn't match
            # Handle early actions (statement context actions + client/expense creation fast paths)
            result = await handle_early_actions(
                message=request.message,
                lower_message=lower_message,
                page_context=page_context,
                ai_config=ai_config,
                db=db,
                current_user_email=current_user.email,
            )
            if result is not None:
                return result

            # Get intent classification
            model_name = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name

            # Standardize model parameters
            model_params = AIConfigService.get_model_parameters(model_name, max_tokens=50, temperature=0.1)

            kwargs = {
                "model": model_name,
                "messages": [{"role": "user", "content": intent_prompt}],
                "timeout": 30,  # 30 second timeout for intent classification
                **model_params
            }

            if ai_config.provider_name == "ollama" and ai_config.provider_url:
                kwargs["api_base"] = ai_config.provider_url
            elif ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key

            try:
                intent_response = await completion(**kwargs)
                intent = intent_response.choices[0].message.content.strip().lower()
                
                # Clean up Gemma/local model responses like "Category: overdue"
                if "category:" in intent:
                    intent = intent.split("category:")[-1].strip()
                if ":" in intent:
                    intent = intent.split(":")[-1].strip()
                # Remove any trailing punctuation
                intent = intent.rstrip(".").rstrip("!")

                # Handle empty or invalid responses
                if not intent or intent == "" or len(intent) > 50:
                    intent = "general"
                # Simple keyword fallback for common patterns
                if intent == "general":
                    msg_lower = lower_message
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
                    elif any(word in msg_lower for word in ["investment", "investments", "portfolio", "portfolios", "holding", "holdings", "dividend", "dividends"]):
                        intent = "investments"
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

        # In Docker, we should try 'localhost' then 'api' as the hostname
        # The internal API client needs to reach the FastAPI service
        api_base_host = os.getenv("API_INTERNAL_URL", "http://localhost:8000")
        print(f"MCP Integration: Initializing API client with token using host {api_base_host}...")
        api_client = AuthenticatedAPIClient(
            base_url=f"{api_base_host}/api/v1",
            jwt_token=jwt_token
        )
        tools = InvoiceTools(api_client)
        print("MCP Integration: API client and tools initialized successfully")

        # Dispatch to intent handlers
        result = await dispatch_intent(
            intent=intent,
            tools=tools,
            message=request.message,
            lower_message=lower_message,
            ai_config=ai_config,
            page_context=page_context,
            db=db,
        )
        if result is not None:
            return result

        # For general queries or unmatched intents, use the regular LLM
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

        user_content = request.message
        if page_context_block:
            user_content = f"{page_context_block.strip()}\n\nUser message: {request.message}"

        # Prepare the completion call
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": user_content}],
            "max_tokens": 500,
            "timeout": 60  # 60 second timeout for main AI response
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
