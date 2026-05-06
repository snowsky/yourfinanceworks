# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

TOOL_INTENTS = {
    "analyze_patterns",
    "suggest_actions",
    "payments",
    "clients",
    "invoices",
    "expenses",
    "statements",
    "currencies",
    "outstanding",
    "overdue",
    "statistics",
    "investments",
    "cashflow",
}


def parse_agent_tool_plan(raw_plan: str | None, *, max_tools: int = 3) -> list[dict]:
    """Parse the model's JSON-ish tool plan into known MCP intents and args."""
    if not raw_plan:
        return []

    import json

    raw_plan = raw_plan.strip()
    payload = None
    try:
        payload = json.loads(raw_plan)
    except json.JSONDecodeError:
        start = raw_plan.find("{")
        end = raw_plan.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(raw_plan[start:end + 1])
            except json.JSONDecodeError:
                payload = None

    raw_tools = []
    if isinstance(payload, dict):
        tools_value = payload.get("tools") or payload.get("tool") or payload.get("intents") or payload.get("intent")
        if isinstance(tools_value, list):
            raw_tools = tools_value
        elif isinstance(tools_value, str):
            raw_tools = [tools_value]
    elif isinstance(payload, list):
        raw_tools = payload

    if not raw_tools:
        raw_tools = [raw_plan]

    tools = []
    for raw_tool in raw_tools:
        options = {}
        if isinstance(raw_tool, dict):
            intent = normalize_tool_intent(
                str(raw_tool.get("intent") or raw_tool.get("name") or raw_tool.get("tool") or "")
            )
            raw_limit = raw_tool.get("limit")
            if raw_limit is not None:
                try:
                    options["limit"] = max(1, min(100, int(raw_limit)))
                except (TypeError, ValueError):
                    pass
        else:
            intent = normalize_tool_intent(str(raw_tool))

        if intent and not any(tool["intent"] == intent for tool in tools):
            tools.append({"intent": intent, "options": options})
        if len(tools) >= max_tools:
            break
    return tools


def normalize_tool_intent(raw_intent: str | None) -> str | None:
    """Normalize the model's routing answer to a known tool intent."""
    if not raw_intent:
        return None

    normalized = raw_intent.strip().lower()
    if normalized in {"none", "general", "no_tool", "no tools", "no-tool"}:
        return None

    for candidate in TOOL_INTENTS:
        if candidate == normalized or candidate in normalized:
            return candidate
    return None
