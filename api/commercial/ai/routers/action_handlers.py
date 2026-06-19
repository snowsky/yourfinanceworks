# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _split_labels(raw: str) -> List[str]:
    parts = re.split(r",|\s+and\s+", raw, flags=re.IGNORECASE)
    return [p.strip().strip("\"'") for p in parts if p.strip()]


async def _init_tools(db, current_user):
    from MCP.tools import InvoiceTools
    from commercial.ai.inprocess.base import InProcessAPIClient

    return InvoiceTools(InProcessAPIClient(db=db, current_user=current_user))


async def _dispatch_create_client(tools, params):
    return await tools.create_client(
        name=params["name"], email=params.get("email"), phone=params.get("phone")
    )


async def _dispatch_set_branding(tools, params):
    return await tools.set_branding(
        brand_color=params.get("brand_color"), accent_color=params.get("accent_color")
    )


async def _dispatch_create_invoice(tools, params):
    return await tools.create_invoice(
        client_id=int(params["client_id"]), amount=float(params["amount"]),
        due_date=params["due_date"], status="draft", notes=params.get("notes"),
    )


async def _dispatch_create_expense(tools, params):
    return await tools.create_expense(
        amount=float(params["amount"]), currency=params.get("currency", "USD"),
        expense_date=params["expense_date"], category=params["category"], vendor=params.get("vendor"),
    )


_ONBOARDING_ACTIONS = {
    "create_client": _dispatch_create_client,
    "set_branding": _dispatch_set_branding,
    "create_invoice": _dispatch_create_invoice,
    "create_expense": _dispatch_create_expense,
}

_ONBOARDING_LABELS = {
    "create_client": "Client created",
    "set_branding": "Branding updated",
    "create_invoice": "Draft invoice created",
    "create_expense": "Expense recorded",
}


# Leading command-filler words an extractor sometimes leaves on a captured name,
# e.g. "create a client with John Doe" -> "with John Doe".
_NAME_FILLER_PREFIXES = ("with ", "named ", "called ", "for ", "the ", "a ")


def _clean_onboarding_name(name: Optional[str]) -> Optional[str]:
    """Strip leading command-filler words from an extracted name (iteratively)."""
    if not isinstance(name, str):
        return name
    cleaned = name.strip()
    changed = True
    while changed:
        changed = False
        lowered = cleaned.lower()
        for pref in _NAME_FILLER_PREFIXES:
            if lowered.startswith(pref):
                cleaned = cleaned[len(pref):].strip()
                changed = True
                break
    return cleaned


async def _extract_onboarding_action(message: str, ai_config: Any) -> Optional[Dict[str, Any]]:
    """Use the LLM to map an onboarding message to one whitelisted action + params.

    Returns {"action": str, "params": dict} or None when no action is clearly intended.

    Uses async ``acompletion`` so the LLM round-trip does not block the event loop —
    a sync call here would serialize all concurrent /ai/chat requests and starve
    unrelated endpoints.
    """
    try:
        from litellm import acompletion
    except ImportError:
        return None

    system = (
        "You map a user's onboarding message to ONE setup action. "
        "Allowed actions: create_client (params: name, email, phone), "
        "set_branding (params: brand_color, accent_color as #RRGGBB hex), "
        "create_invoice (params: client_id, amount, due_date YYYY-MM-DD, notes), "
        "create_expense (params: amount, currency, expense_date YYYY-MM-DD, category, vendor). "
        "Respond with ONLY compact JSON: {\"action\": <name|null>, \"params\": {...}}. "
        "Extract clean values: drop command words like 'create', 'add', 'with', 'named', 'called'. "
        "Example: 'create a client with John Doe, email jd@x.com' -> "
        "{\"action\":\"create_client\",\"params\":{\"name\":\"John Doe\",\"email\":\"jd@x.com\"}}. "
        "Use null when the message is a question or no action is clearly intended. "
        "Never invent IDs you were not given."
    )
    model = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
    try:
        resp = await acompletion(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": message}],
            api_key=getattr(ai_config, "api_key", None),
            api_base=getattr(ai_config, "provider_url", None),
            temperature=0,
        )
        content = resp["choices"][0]["message"]["content"].strip()
        parsed = json.loads(content)
    except Exception as exc:
        logger.warning("Onboarding action extraction failed: %s", exc)
        return None

    action = parsed.get("action")
    if action not in _ONBOARDING_ACTIONS:
        return None
    params = parsed.get("params") or {}
    if params.get("name"):
        params["name"] = _clean_onboarding_name(params["name"])
    return {"action": action, "params": params}


async def _handle_onboarding_action(
    message: str, confirmed_action: Optional[Dict[str, Any]], ai_config: Any, db, current_user,
) -> Optional[Dict[str, Any]]:
    # Execute path: only after explicit confirmation.
    if confirmed_action:
        action = confirmed_action.get("action")
        params = confirmed_action.get("params") or {}
        dispatch = _ONBOARDING_ACTIONS.get(action)
        if dispatch is None:
            return {"success": False, "error": f"Unknown onboarding action: {action}"}
        tools = await _init_tools(db, current_user)
        try:
            result = await dispatch(tools, params)
        except Exception as exc:
            logger.warning("Onboarding action %s failed: %s", action, exc)
            return {"success": False, "error": f"Could not complete {action}: {exc}"}
        if not result.get("success"):
            return {"success": False, "error": result.get("error", f"{action} failed")}
        return {
            "success": True,
            "data": {
                "response": f"✅ {_ONBOARDING_LABELS.get(action, 'Done')}.",
                "executed_action": action,
                "result": result,
                "source": "onboarding",
            },
        }

    # Propose path: classify + return for confirmation, never execute.
    proposal = await _extract_onboarding_action(message, ai_config)
    if proposal is None:
        return None  # let the normal chat path answer the question
    return {
        "success": True,
        "data": {
            "type": "proposed_action",
            "action": proposal["action"],
            "params": proposal["params"],
            "source": "onboarding",
        },
    }


async def handle_early_actions(
    message: str,
    lower_message: str,
    page_context: Optional[Dict[str, Any]],
    ai_config: Any,
    db: Session,
    current_user,
    mode: Optional[str] = None,
    confirmed_action: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    # Onboarding mode: propose/confirm gate, isolated from the live write fast-path.
    if mode == "onboarding":
        return await _handle_onboarding_action(message, confirmed_action, ai_config, db, current_user)

    # Page-aware statement actions (use current page context if available)
    entity = page_context.get("entity") if isinstance(page_context, dict) else None
    entity_type = entity.get("type") if isinstance(entity, dict) else None
    entity_id = entity.get("id") if isinstance(entity, dict) else None
    if entity_type in {"bank_statement", "statement", "statements"} and entity_id:
        try:
            statement_id = int(entity_id)
        except (TypeError, ValueError):
            statement_id = None

        if statement_id:
            if any(k in lower_message for k in ["reprocess", "re-process", "reanalyze", "re-analyze", "retry extraction", "re-run"]):
                tools = await _init_tools(db, current_user)
                result = await tools.reprocess_bank_statement(statement_id=statement_id)
                if result.get("success"):
                    return {
                        "success": True,
                        "data": {
                            "response": f"✅ Reprocessing started for statement #{statement_id}.",
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

            note_match = re.search(r"(?:set|update|add)?\s*(?:note|notes)\s*(?:to|:)\s*(.+)$", message, re.IGNORECASE)
            if not note_match:
                note_match = re.search(r"(?:add)\s*(?:note|notes)\s+(.+)$", message, re.IGNORECASE)

            add_labels_match = re.search(r"(?:add|set)\s*(?:label|labels|tag|tags)\s*(?:to|:)\s*(.+)$", message, re.IGNORECASE)
            remove_labels_match = re.search(r"(?:remove|delete)\s*(?:label|labels|tag|tags)\s*(?:named\s+)?(.+)$", message, re.IGNORECASE)

            if note_match or add_labels_match or remove_labels_match:
                tools = await _init_tools(db, current_user)
                notes_value = note_match.group(1).strip() if note_match else None
                labels_to_add = _split_labels(add_labels_match.group(1)) if add_labels_match else []
                labels_to_remove = _split_labels(remove_labels_match.group(1)) if remove_labels_match else []

                current_labels: List[str] = []
                if labels_to_add or labels_to_remove:
                    current_statement = await tools.get_bank_statement(statement_id=statement_id)
                    if current_statement.get("success"):
                        current_labels = current_statement.get("data", {}).get("labels") or []

                updated_labels = current_labels
                if labels_to_add:
                    updated_labels = list({*current_labels, *labels_to_add})
                if labels_to_remove:
                    updated_labels = [lbl for lbl in updated_labels if lbl not in set(labels_to_remove)]

                result = await tools.update_bank_statement_meta(
                    statement_id=statement_id,
                    notes=notes_value,
                    labels=updated_labels if (labels_to_add or labels_to_remove) else None
                )
                if result.get("success"):
                    response_lines = [f"✅ Updated statement #{statement_id}."]
                    if notes_value:
                        response_lines.append("• Notes updated")
                    if labels_to_add or labels_to_remove:
                        response_lines.append("• Labels updated")
                    return {
                        "success": True,
                        "data": {
                            "response": "\n".join(response_lines),
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

            # Update transaction date in the current statement
            if any(k in lower_message for k in ["transaction", "transactions"]) and "date" in lower_message and any(k in lower_message for k in ["update", "change", "set"]):
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", message)
                if not date_match:
                    return {
                        "success": True,
                        "data": {
                            "response": "I can update the transaction date, but I need the target date in YYYY-MM-DD format.",
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

                new_date = date_match.group(1)
                index = None
                if re.search(r"\bfirst\b|\b1st\b", lower_message):
                    index = 0
                elif re.search(r"\bsecond\b|\b2nd\b", lower_message):
                    index = 1
                elif re.search(r"\bthird\b|\b3rd\b", lower_message):
                    index = 2
                else:
                    index_match = re.search(r"(?:transaction|tx|entry)\s*#?\s*(\d+)", lower_message)
                    if index_match:
                        index = int(index_match.group(1)) - 1

                if index is None:
                    return {
                        "success": True,
                        "data": {
                            "response": "Which transaction should I update? You can say \"first transaction\" or \"transaction 3\".",
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

                tools = await _init_tools(db, current_user)
                current_statement = await tools.get_bank_statement(statement_id=statement_id)
                if not current_statement.get("success"):
                    return {
                        "success": True,
                        "data": {
                            "response": f"Couldn't load statement #{statement_id} to update transactions.",
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

                transactions = current_statement.get("data", {}).get("transactions") or []
                if index < 0 or index >= len(transactions):
                    return {
                        "success": True,
                        "data": {
                            "response": f"Statement #{statement_id} has {len(transactions)} transaction(s). Please pick a valid transaction number.",
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

                transactions[index]["date"] = new_date
                try:
                    await tools.api_client.replace_bank_statement_transactions(statement_id=statement_id, transactions=transactions)
                except Exception as e:
                    return {
                        "success": True,
                        "data": {
                            "response": f"Failed to update transaction date: {str(e)}",
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

                return {
                    "success": True,
                    "data": {
                        "response": f"✅ Updated transaction {index + 1} date to {new_date} for statement #{statement_id}.",
                        "provider": ai_config.provider_name,
                        "model": ai_config.model_name,
                        "source": "mcp_tools"
                    }
                }

    # Check for client creation intent specifically
    if "create" in lower_message or "add" in lower_message or "new" in lower_message:
        # Fix false positive: "create invoice for client" should not trigger client creation
        # Ensure "invoice" or "expense" is not in the message when detecting client creation
        is_client_intent = ("client" in lower_message or "customer" in lower_message)
        if is_client_intent and "invoice" not in lower_message and "expense" not in lower_message:
            # Initialize basic components needed for this early path
            # Initialize MCP tools using current user's session
            tools = await _init_tools(db, current_user)

            print(f"MCP Integration: Detected client creation intent (Pre-LLM): '{message}'")

            # Use LLM to extract client details for robustness
            try:
                from litellm import acompletion as completion

                # Prepare extraction prompt
                extraction_prompt = f"""Extract the client details from the following request. Return ONLY a JSON object with keys 'name', 'email', and 'phone'.
If a field is not missing, set it to null.
Do not include any explanation, markdown formatting, or code blocks. Just the raw JSON string.

Request: "{message}"

JSON:"""

                # Configure model parameters
                extraction_model = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
                extraction_params = {
                    "model": extraction_model,
                    "messages": [{"role": "user", "content": extraction_prompt}],
                    "temperature": 0.0, # Deterministic output
                    "max_tokens": 150,
                    "timeout": 30  # 30 second timeout for client extraction
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

                client_details = json.loads(extract_content)
                print(f"MCP Integration: Extracted details: {client_details}")

                name = client_details.get("name")
                email = client_details.get("email")
                phone = client_details.get("phone")

            except Exception as e:
                print(f"MCP Integration: LLM extraction failed: {e}. Falling back to regex.")
                # Fallback to simple regex if LLM fails
                name = None
                name_match = re.search(r'(?:create|add|new)\s+(?:a\s+)?client\s+(?:named\s+|called\s+)?["\']?([^"\',]+)["\']?', message, re.IGNORECASE)
                if name_match:
                    name = name_match.group(1).strip()
                else:
                    simple_match = re.search(r'(?:create|add|new)\s+(?:a\s+)?client\s+([a-zA-Z0-9\s]+?)(?:\s+with|\s*$)', message, re.IGNORECASE)
                    if simple_match:
                        name = simple_match.group(1).strip()

                email = None
                email_match = re.search(r'email\s+["\']?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)["\']?', message, re.IGNORECASE)
                if email_match:
                    email = email_match.group(1)

                phone = None
                phone_match = re.search(r'phone\s+["\']?([0-9+\-\s()]{7,})["\']?', message, re.IGNORECASE)
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
            tools = await _init_tools(db, current_user)

            print(f"MCP Integration: Detected expense creation intent (Pre-LLM): '{message}'")

            # Use LLM to extract expense details
            try:
                from litellm import acompletion as completion

                # Prepare extraction prompt
                current_date = datetime.now().strftime("%Y-%m-%d")
                extraction_prompt = f"""Extract the expense details from the following request. Return ONLY a JSON object.
Required keys: 'amount' (number), 'category' (string), 'expense_date' (YYYY-MM-DD).
Optional keys: 'vendor' (string), 'notes' (string), 'currency' (default 'USD').
If the date is "today", use {current_date}.
Do not include any explanation, markdown formatting, or code blocks. Just the raw JSON string.

Request: "{message}"

JSON:"""

                # Configure model parameters
                extraction_model = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
                extraction_params = {
                    "model": extraction_model,
                    "messages": [{"role": "user", "content": extraction_prompt}],
                    "temperature": 0.0,
                    "max_tokens": 150,
                    "timeout": 30  # 30 second timeout for expense extraction
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

    return None
