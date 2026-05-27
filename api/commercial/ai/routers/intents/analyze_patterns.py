# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""analyze_patterns intent handler — invoice pattern analysis dashboard."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


class AnalyzePatternsHandler:
    intent = "analyze_patterns"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        result = await ctx.tools.analyze_invoice_patterns()
        if not result.get("success"):
            logger.info("analyze_patterns: tool failed; falling back. result=%s", result)
            return None
        return mcp_envelope(ctx, format_analysis_response(result.get("data") or {}))


def _format_revenue_by_currency(revenue: dict) -> str:
    if not revenue or not isinstance(revenue, dict):
        return "None"
    return ", ".join(f"{currency} ${amount:,.2f}" for currency, amount in revenue.items())


def format_analysis_response(data: dict[str, Any]) -> str:
    recommendation_lines = "\n".join(f"• {rec}" for rec in (data.get("recommendations") or []))
    return (
        "🎯 **Invoice Pattern Analysis Report**\n\n"
        "📊 **📈 Business Overview:**\n"
        f"• **Total Invoices:** {data.get('total_invoices', 0):,}\n"
        f"• **Paid Invoices:** {data.get('paid_invoices', 0):,} ✅\n"
        f"• **Partially Paid:** {data.get('partially_paid_invoices', 0):,} ⚠️\n"
        f"• **Unpaid Invoices:** {data.get('unpaid_invoices', 0):,} ❌\n"
        f"• **Overdue Invoices:** {data.get('overdue_invoices', 0):,} 🚨\n\n"
        "💰 **💵 Financial Summary:**\n"
        f"• **Total Revenue:** {_format_revenue_by_currency(data.get('total_revenue_by_currency', {}))}\n"
        f"• **Outstanding Revenue:** {_format_revenue_by_currency(data.get('outstanding_revenue_by_currency', {}))}\n\n"
        "💡 **🎯 Strategic Recommendations:**\n"
        f"{recommendation_lines}\n\n"
        "📋 **📊 Analysis Details:**\n"
        "This comprehensive analysis was performed using your actual invoice data "
        "through our advanced MCP tools, providing real-time insights into your "
        "business performance and cash flow patterns."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(AnalyzePatternsHandler())
