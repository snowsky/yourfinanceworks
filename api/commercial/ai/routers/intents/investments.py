# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""Investments intent handler.

Migrated from the legacy ``if intent == 'investments':`` branch in
``intent_handlers.dispatch_intent``. Behavior is preserved 1:1 — same MCP
tool call, same markdown rendering, same license-denial copy.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


INVESTMENTS_DISABLED_MESSAGE = (
    "The Investment Management feature is not enabled for your account. "
    "Please contact your administrator or upgrade your license to access "
    "your investment data."
)

NO_PORTFOLIOS_MESSAGE = "You don't have any investment portfolios set up yet."


class InvestmentsHandler:
    intent = "investments"
    license_feature = "investments"
    license_denied_message = INVESTMENTS_DISABLED_MESSAGE

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        result = await ctx.tools.list_portfolios()
        if not result.get("success"):
            logger.info(
                "investments handler: list_portfolios failed; falling back to LLM. result=%s",
                result,
            )
            return None
        portfolios = result.get("data") or []
        if not portfolios:
            return mcp_envelope(ctx, NO_PORTFOLIOS_MESSAGE)
        return mcp_envelope(ctx, format_portfolios_response(portfolios))


def format_portfolios_response(portfolios: list[dict[str, Any]]) -> str:
    """Render the legacy markdown layout from a list of portfolio dicts."""
    lines: list[str] = []
    total_market_value = 0.0
    for portfolio in portfolios:
        val = portfolio.get("total_value", 0) or 0
        total_market_value += val
        perf = portfolio.get("return_percentage", 0) or 0
        perf_str = f"{perf:+.2f}%" if perf != 0 else "0.00%"
        lines.append(
            f"• **{portfolio.get('name', 'Unnamed Portfolio')}** ({portfolio.get('type', 'Unknown')})\n"
            f"  💰 Value: ${val:,.2f} | 📈 Return: {perf_str}\n"
            f"  📊 Holdings: {portfolio.get('holdings_count', 0)}"
        )
    portfolio_display = "\n".join(lines)
    return (
        "📈 **Investment Portfolio Overview**\n\n"
        "📊 **Business Summary:**\n"
        f"• **Total Portfolios:** {len(portfolios)}\n"
        f"• **Total Market Value:** ${total_market_value:,.2f}\n\n"
        "💼 **Individual Portfolios:**\n"
        f"{portfolio_display}\n\n"
        "📋 **Data Source:**\n"
        "This information was retrieved from your investment management plugin "
        "via advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(InvestmentsHandler())
