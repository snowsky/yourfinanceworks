# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""currencies intent handler — active currency dashboard."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


NO_CURRENCIES_MESSAGE = "No active currencies found."


class CurrenciesHandler:
    intent = "currencies"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        result = await ctx.tools.list_currencies(active_only=True)
        if not result.get("success"):
            logger.info("currencies: tool failed; falling back. result=%s", result)
            return None
        currencies = result.get("data") or []
        if not currencies:
            return mcp_envelope(ctx, NO_CURRENCIES_MESSAGE)
        return mcp_envelope(ctx, format_currencies_response(currencies))


def format_currencies_response(currencies: list[dict[str, Any]]) -> str:
    detail_lines = "\n".join(
        f"• **{currency.get('code', 'N/A')}** ({currency.get('symbol', '')})\n"
        f"  📝 Name: {currency.get('name', 'Unknown')}\n"
        f"  📊 Status: {'Active' if currency.get('is_active', True) else 'Inactive'}\n"
        "  -----------------------------------------\n"
        for currency in currencies
    )
    return (
        "💱 **Currency Management Dashboard**\n\n"
        "📊 **📈 Currency Overview:**\n"
        f"• **Active Currencies:** {len(currencies):,}\n"
        f"• **Supported Currencies:** {len(currencies):,}\n\n"
        "💱 **💵 Currency Details:**\n"
        f"{detail_lines}\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive currency information was retrieved using your actual "
        "currency data through our advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(CurrenciesHandler())
