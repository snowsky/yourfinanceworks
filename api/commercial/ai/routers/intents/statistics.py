# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""statistics intent handler — invoice statistics dashboard."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


class StatisticsHandler:
    intent = "statistics"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        result = await ctx.tools.get_invoice_stats()
        if not result.get("success"):
            logger.info("statistics: tool failed; falling back. result=%s", result)
            return None
        return mcp_envelope(ctx, format_statistics_response(result.get("data") or {}))


def _safe_rate(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return (numerator / denominator) * 100


def format_statistics_response(stats: dict[str, Any]) -> str:
    total = stats.get("total_invoices", 0)
    paid = stats.get("paid_invoices", 0)
    overdue = stats.get("overdue_invoices", 0)
    payment_rate = _safe_rate(paid, total)
    overdue_rate = _safe_rate(overdue, total)
    return (
        "📊 **Invoice Statistics Dashboard**\n\n"
        "📈 **📊 Business Metrics:**\n"
        f"• **Total Invoices:** {total:,}\n"
        f"• **Total Revenue:** ${stats.get('total_revenue', 0):,.2f}\n"
        f"• **Average Invoice Amount:** ${stats.get('average_invoice_amount', 0):,.2f}\n\n"
        "📋 **📊 Status Breakdown:**\n"
        f"• **Paid Invoices:** {paid:,} ✅\n"
        f"• **Unpaid Invoices:** {stats.get('unpaid_invoices', 0):,} ❌\n"
        f"• **Overdue Invoices:** {overdue:,} 🚨\n\n"
        "📊 **📈 Performance Insights:**\n"
        f"• **Payment Rate:** {payment_rate:.1f}%\n"
        f"• **Overdue Rate:** {overdue_rate:.1f}%\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive statistical analysis was performed using your actual "
        "invoice data through our advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(StatisticsHandler())
