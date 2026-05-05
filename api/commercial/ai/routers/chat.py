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
from commercial.ai.routers.intent_routing import TOOL_INTENTS, parse_agent_tool_plan
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
- cashflow: cash flow forecasts, runway, burn rate, cash projections, scenario planning, low cash alerts
- general: general questions not related to business data

{page_context_block}
User message: "{request.message}"

Category:"""

        # Let the model decide natural-language intent first. Deterministic handlers
        # still exist for explicit actions, but phrase-level routing stays AI based.
        lower_message = request.message.lower()

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

        tool_plan = await _plan_mcp_tool_intents(
            message=request.message,
            page_context_block=page_context_block,
            ai_config=ai_config,
        )
        if tool_plan:
            intent = tool_plan[0]["intent"]
            logger.info(f"MCP Integration: AI agent tool plan selected intents: {tool_plan}")
        else:
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
                if intent not in {*TOOL_INTENTS, "general"}:
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

        if tool_plan:
            planned_results = []
            for planned_tool in tool_plan:
                planned_intent = planned_tool["intent"]
                planned_result = await dispatch_intent(
                    intent=planned_intent,
                    tools=tools,
                    message=request.message,
                    lower_message=lower_message,
                    ai_config=ai_config,
                    page_context=page_context,
                    db=db,
                    tool_options=planned_tool.get("options") or {},
                )
                if planned_result is not None:
                    planned_results.append((planned_intent, planned_result))

            if len(planned_results) == 1:
                return planned_results[0][1]

            if planned_results:
                synthesized = await _synthesize_tool_results(
                    message=request.message,
                    planned_results=planned_results,
                    page_context_block=page_context_block,
                    ai_config=ai_config,
                )
                return {
                    "success": True,
                    "data": {
                        "response": synthesized,
                        "provider": ai_config.provider_name,
                        "model": ai_config.model_name,
                        "source": "mcp_tools",
                        "tool_plan": [intent for intent, _ in planned_results],
                    }
                }

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


async def _plan_mcp_tool_intents(
    *,
    message: str,
    page_context_block: str,
    ai_config,
) -> list[str]:
    """Ask the AI model to choose the MCP tool intents needed to answer."""
    try:
        from litellm import acompletion as completion
    except ImportError:
        return []

    model_name = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
    model_params = AIConfigService.get_model_parameters(model_name, max_tokens=120, temperature=0.0)
    prompt = f"""You are the tool-planning step for a YourFinanceWORKS assistant.
Decide which MCP tool intents are required to answer the user using their business/accounting data.
Return ONLY compact JSON with this exact shape:
{{"tools":[{{"intent":"payments"}}],"reason":"brief"}}

Rules:
- If no YourFinanceWORKS data is needed, return {{"tools":[],"reason":"no business data needed"}}.
- Choose one tool when one is enough.
- Choose multiple tools only when the answer requires combining domains.
- Include "limit" when the user asks for a specific number of records, such as last 4 expenses.
- Do not answer the user. Only plan tool intents.

Allowed tool intents:
analyze_patterns, suggest_actions, payments, clients, invoices, expenses, statements, currencies, outstanding, overdue, statistics, investments, cashflow

Examples:
- "can you analyze my invoice patterns?" -> {{"tools":[{{"intent":"analyze_patterns"}}],"reason":"invoice pattern analysis"}}
- "what actions should I take?" -> {{"tools":[{{"intent":"suggest_actions"}}],"reason":"recommendations from business data"}}
- "how many clients?" -> {{"tools":[{{"intent":"clients"}}],"reason":"client count"}}
- "show my invoices" -> {{"tools":[{{"intent":"invoices"}}],"reason":"invoice list"}}
- "what expenses did I have?" -> {{"tools":[{{"intent":"expenses"}}],"reason":"expense list"}}
- "how much did I spend in last 4 expenses?" -> {{"tools":[{{"intent":"expenses","limit":4}}],"reason":"last four expenses"}}
- "how much did I get paid?" -> {{"tools":[{{"intent":"payments"}}],"reason":"payment total"}}
- "how much have I collected?" -> {{"tools":[{{"intent":"payments"}}],"reason":"payment total"}}
- "do I have overdue invoices?" -> {{"tools":[{{"intent":"overdue"}}],"reason":"overdue invoice check"}}
- "what is my cash runway?" -> {{"tools":[{{"intent":"cashflow"}}],"reason":"cash runway"}}
- "what was my net income?" -> {{"tools":[{{"intent":"payments"}},{{"intent":"expenses"}}],"reason":"payments minus expenses"}}
- "write a generic email" -> {{"tools":[],"reason":"no business data needed"}}

{page_context_block}
User message: "{message}"

JSON:"""

    kwargs = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "timeout": 20,
        **model_params,
    }
    if ai_config.provider_name == "ollama" and ai_config.provider_url:
        kwargs["api_base"] = ai_config.provider_url
    elif ai_config.api_key:
        kwargs["api_key"] = ai_config.api_key

    try:
        response = await completion(**kwargs)
        raw_plan = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.info(f"MCP Integration: agent tool planning failed: {exc}")
        return []

    return parse_agent_tool_plan(raw_plan)


async def _synthesize_tool_results(
    *,
    message: str,
    planned_results: list[tuple[str, dict]],
    page_context_block: str,
    ai_config,
) -> str:
    """Use the chat model to combine multiple MCP tool outputs into one answer."""
    tool_outputs = []
    for intent, result in planned_results:
        data = result.get("data", {}) if isinstance(result, dict) else {}
        tool_outputs.append(
            {
                "intent": intent,
                "response": data.get("response"),
                "source": data.get("source"),
            }
        )

    fallback = "\n\n".join(
        output["response"] for output in tool_outputs if output.get("response")
    )
    try:
        from litellm import acompletion as completion
    except ImportError:
        return fallback

    model_name = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
    prompt = f"""Answer the user's question using only the MCP tool outputs below.
If a value is not present in the tool outputs, say it is not available.

{page_context_block}
User question: {message}

MCP tool outputs JSON:
{json.dumps(tool_outputs, ensure_ascii=False)}

Answer:"""

    kwargs = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "timeout": 60,
        **AIConfigService.get_model_parameters(model_name, max_tokens=500, temperature=0.1),
    }
    if ai_config.provider_name == "ollama" and ai_config.provider_url:
        kwargs["api_base"] = ai_config.provider_url
    elif ai_config.api_key:
        kwargs["api_key"] = ai_config.api_key

    try:
        response = await completion(**kwargs)
        return response.choices[0].message.content if response.choices else fallback
    except Exception as exc:
        logger.info(f"MCP Integration: tool result synthesis failed: {exc}")
        return fallback
