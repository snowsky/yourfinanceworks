# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""statements intent handler — bank statement management dashboard."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


NO_STATEMENTS_MESSAGE = "No bank statements found."


class StatementsHandler:
    intent = "statements"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        result = await ctx.tools.list_statements()
        if not result.get("success"):
            logger.info("statements: tool failed; falling back. result=%s", result)
            return None
        statements = result.get("data") or []
        if not statements:
            return mcp_envelope(ctx, NO_STATEMENTS_MESSAGE)
        return mcp_envelope(ctx, format_statements_response(statements))


def format_statements_response(statements: list[dict[str, Any]]) -> str:
    processed = len([s for s in statements if s.get("status") == "processed"])
    pending = len([s for s in statements if s.get("status") == "pending"])
    detail_lines = "\n".join(
        f"• **Statement #{stmt.get('id', 'N/A')}**\n"
        f"  🏦 Account: {stmt.get('account_name', 'Unknown')}\n"
        f"  📅 Period: {stmt.get('statement_period', 'N/A')}\n"
        f"  📊 Status: {str(stmt.get('status', 'Unknown')).title()}\n"
        f"  📄 Transactions: {stmt.get('transaction_count', 'N/A')}\n"
        f"  📅 Imported: {stmt.get('created_at', 'N/A')}\n"
        "  -----------------------------------------\n"
        for stmt in statements
    )
    return (
        "🏦 **Statement Management Dashboard**\n\n"
        "📊 **📈 Statement Overview:**\n"
        f"• **Total Statements:** {len(statements):,}\n"
        f"• **Processed Statements:** {processed:,}\n"
        f"• **Pending Statements:** {pending:,}\n\n"
        "🏦 **💼 Statement Details:**\n"
        f"{detail_lines}\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive bank statement information was retrieved using your "
        "actual bank statement data through our advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(StatementsHandler())
