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

from commercial.ai.routers.llm import llm_acompletion

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


async def _dispatch_reprocess_statement(tools, params):
    return await tools.reprocess_bank_statement(statement_id=int(params["statement_id"]))


async def _dispatch_update_statement(tools, params):
    statement_id = int(params["statement_id"])
    data = {}
    if "notes" in params:
        data["notes"] = params["notes"]
    if params.get("add_labels") or params.get("remove_labels"):
        current = await tools.get_bank_statement(statement_id=statement_id)
        if not current.get("success"):
            return current
        labels = current["data"].get("labels") or []
        additions = params.get("add_labels") or []
        removals = params.get("remove_labels") or []
        if not isinstance(additions, list) or not isinstance(removals, list):
            raise ValueError("Labels must be lists")
        data["labels"] = list(dict.fromkeys(label for label in labels + additions if label not in removals))
    await tools.api_client._make_request("PUT", f"/statements/{statement_id}", json=data)
    return {"success": True}


async def _dispatch_transaction_date(tools, params):
    statement_id = int(params["statement_id"])
    index = int(params["transaction_number"]) - 1
    new_date = datetime.strptime(params["date"], "%Y-%m-%d").date().isoformat()
    current = await tools.get_bank_statement(statement_id=statement_id)
    if not current.get("success"):
        return current
    transactions = current["data"].get("transactions") or []
    if not 0 <= index < len(transactions):
        raise ValueError("Invalid transaction number")
    transactions[index]["date"] = new_date
    await tools.api_client.replace_bank_statement_transactions(statement_id=statement_id, transactions=transactions)
    return {"success": True}


_ONBOARDING_ACTIONS = {
    "create_client": _dispatch_create_client,
    "set_branding": _dispatch_set_branding,
    "create_invoice": _dispatch_create_invoice,
    "create_expense": _dispatch_create_expense,
    "reprocess_statement": _dispatch_reprocess_statement,
    "update_statement": _dispatch_update_statement,
    "update_transaction_date": _dispatch_transaction_date,
}

_ONBOARDING_LABELS = {
    "create_client": "Client created",
    "set_branding": "Branding updated",
    "create_invoice": "Draft invoice created",
    "create_expense": "Expense recorded",
    "reprocess_statement": "Statement reprocessing started",
    "update_statement": "Statement updated",
    "update_transaction_date": "Transaction date updated",
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


async def _extract_onboarding_action(message: str, ai_config: Any, db) -> Optional[Dict[str, Any]]:
    """Use the LLM to map an onboarding message to one whitelisted action + params.

    Returns {"action": str, "params": dict} or None when no action is clearly intended.

    Routes the LLM round-trip through ``llm_acompletion(db, ...)``, which releases the
    tenant DB connection (rollback) before the call so it isn't held idle while waiting
    on the model, and runs it async so the event loop isn't blocked.
    """
    system = (
        "You map a user's onboarding message to ONE setup action. "
        "Allowed actions: create_client (params: name, email, phone), "
        "set_branding (params: brand_color, accent_color as #RRGGBB hex), "
        "create_invoice (params: client_id, amount, due_date YYYY-MM-DD, notes), "
        "create_expense (params: amount, currency, expense_date YYYY-MM-DD, category, vendor). "
        "reprocess_statement (params: statement_id), "
        "update_statement (params: statement_id, notes, add_labels array, remove_labels array), "
        "update_transaction_date (params: statement_id, transaction_number starting at 1, date YYYY-MM-DD). "
        f"Today is {datetime.now().date().isoformat()}. "
        "Use the current page entity ID only for statement actions on a statement page. "
        "Respond with ONLY compact JSON: {\"action\": <name|null>, \"params\": {...}}. "
        "Extract clean values: drop command words like 'create', 'add', 'with', 'named', 'called'. "
        "Example: 'create a client with John Doe, email jd@x.com' -> "
        "{\"action\":\"create_client\",\"params\":{\"name\":\"John Doe\",\"email\":\"jd@x.com\"}}. "
        "Use null when the message is a question or no action is clearly intended. "
        "Never invent IDs you were not given."
    )
    model = f"ollama/{ai_config.model_name}" if ai_config.provider_name == "ollama" else ai_config.model_name
    try:
        resp = await llm_acompletion(
            db,
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

    if not isinstance(parsed, dict):
        return None
    action = parsed.get("action")
    if action not in _ONBOARDING_ACTIONS:
        return None
    params = parsed.get("params") or {}
    if not isinstance(params, dict):
        return None
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
    proposal = await _extract_onboarding_action(message, ai_config, db)
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
    # Every chat write uses the same explicit proposal/confirmation boundary.
    # Page context helps resolve a proposal, but never authorizes execution.
    if page_context and not confirmed_action:
        message = f"Current page (context only): {json.dumps(page_context)}\nUser message: {message}"
    return await _handle_onboarding_action(message, confirmed_action, ai_config, db, current_user)
