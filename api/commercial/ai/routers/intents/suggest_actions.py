# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""suggest_actions intent handler — strategic action plan from invoice data."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


_PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}


class SuggestActionsHandler:
    intent = "suggest_actions"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        result = await ctx.tools.suggest_invoice_actions()
        if not result.get("success"):
            logger.info("suggest_actions: tool failed; falling back. result=%s", result)
            return None
        return mcp_envelope(ctx, format_actions_response(result.get("data") or {}))


def _priority_emoji(priority: Any) -> str:
    return _PRIORITY_EMOJI.get(str(priority).lower(), "⚪")


def format_actions_response(data: dict[str, Any]) -> str:
    actions = data.get("suggested_actions") or []
    action_lines = "\n".join(
        f"• {_priority_emoji(action.get('priority', 'medium'))} "
        f"**{str(action.get('action', 'Unknown')).replace('_', ' ').title()}**\n"
        f"  📝 {action.get('description', 'No description')}\n"
        f"  🏷️ Priority: {str(action.get('priority', 'medium')).title()}\n"
        for action in actions
    )
    return (
        "🎯 **Strategic Action Plan**\n\n"
        "🚀 **🎯 Priority Actions:**\n"
        f"{action_lines}\n\n"
        "📊 **📈 Quick Metrics:**\n"
        f"• **Overdue Invoices:** {data.get('overdue_count', 0):,} 🚨\n"
        f"• **Clients with Balance:** {data.get('clients_with_balance', 0):,} 💰\n"
        f"• **Recent Invoices:** {data.get('recent_invoices_count', 0):,} 📄\n\n"
        "💡 **💼 Action Insights:**\n"
        "These strategic recommendations are based on your actual invoice data and "
        "business patterns, designed to optimize your cash flow and improve client "
        "relationships."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(SuggestActionsHandler())
