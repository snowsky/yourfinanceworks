# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""outstanding intent handler — clients with outstanding balances."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


NO_OUTSTANDING_MESSAGE = "No clients with outstanding balances found."


class OutstandingHandler:
    intent = "outstanding"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        result = await ctx.tools.get_clients_with_outstanding_balance()
        if not result.get("success"):
            logger.info("outstanding: tool failed; falling back. result=%s", result)
            return None
        clients = result.get("data") or []
        if not clients:
            return mcp_envelope(ctx, NO_OUTSTANDING_MESSAGE)
        return mcp_envelope(ctx, format_outstanding_response(clients))


def format_outstanding_response(clients: list[dict[str, Any]]) -> str:
    total = sum(client.get("outstanding_balance", 0) or 0 for client in clients)
    average = total / len(clients) if clients else 0
    detail_lines = "\n".join(
        f"• **{client.get('name', 'Unknown')}**\n"
        f"  💰 Outstanding Balance: ${client.get('outstanding_balance', 0):,.2f}\n"
        f"  📧 Email: {client.get('email', 'N/A')}\n"
        f"  📞 Phone: {client.get('phone', 'N/A')}\n"
        "  -----------------------------------------\n"
        for client in clients
    )
    return (
        "⚠️ **Outstanding Balance Report**\n\n"
        "📊 **📈 Outstanding Overview:**\n"
        f"• **Clients with Balances:** {len(clients):,}\n"
        f"• **Total Outstanding Amount:** ${total:,.2f}\n"
        f"• **Average Outstanding per Client:** ${average:,.2f}\n\n"
        "💰 **💵 Outstanding Details:**\n"
        f"{detail_lines}\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive outstanding balance information was retrieved using your "
        "actual client data through our advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(OutstandingHandler())
