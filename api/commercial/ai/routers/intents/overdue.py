# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""overdue intent handler — overdue invoice alert report."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


NO_OVERDUE_MESSAGE = "No overdue invoices found."


class OverdueHandler:
    intent = "overdue"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        result = await ctx.tools.get_overdue_invoices()
        if not result.get("success"):
            logger.info("overdue: tool failed; falling back. result=%s", result)
            return None
        invoices = result.get("data") or []
        if not invoices:
            return mcp_envelope(ctx, NO_OVERDUE_MESSAGE)
        return mcp_envelope(ctx, format_overdue_response(invoices))


def format_overdue_response(invoices: list[dict[str, Any]]) -> str:
    total = sum(inv.get("amount", 0) or 0 for inv in invoices)
    avg_days = sum(inv.get("days_overdue", 0) or 0 for inv in invoices) / len(invoices)
    avg_amount = total / len(invoices)
    detail_lines = "\n".join(
        f"• **Invoice #{inv.get('invoice_number', inv.get('id', 'N/A'))}**\n"
        f"  👤 Client: {inv.get('client_name', 'Unknown Client')}\n"
        f"  💰 Amount: ${inv.get('amount', 0):,.2f}\n"
        f"  📅 Due Date: {inv.get('due_date', 'N/A')}\n"
        f"  ⏰ Days Overdue: {inv.get('days_overdue', 'N/A')}\n"
        "  -----------------------------------------\n"
        for inv in invoices
    )
    return (
        "🚨 **Overdue Invoice Alert Report**\n\n"
        "📊 **📈 Overdue Overview:**\n"
        f"• **Overdue Invoices:** {len(invoices):,}\n"
        f"• **Total Overdue Amount:** ${total:,.2f}\n"
        f"• **Average Days Overdue:** {avg_days:.1f} days\n"
        f"• **Average Overdue Amount:** ${avg_amount:,.2f}\n\n"
        "🚨 **💸 Overdue Details:**\n"
        f"{detail_lines}\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive overdue invoice information was retrieved using your "
        "actual invoice data through our advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(OverdueHandler())
