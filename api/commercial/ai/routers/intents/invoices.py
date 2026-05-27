# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""invoices intent handler — search-or-list routing with friendly-error envelope.

Unlike most other handlers, the legacy invoices branch returned a *successful*
envelope even when the MCP tool failed — the user got an "Error retrieving
invoices: ..." string instead of an LLM fallback. That behavior is preserved
here: failures route through ``format_error_envelope`` rather than returning
``None``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    ArgSpec,
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)
from commercial.ai.routers.intents._helpers import detect_search_intent


logger = logging.getLogger(__name__)


NO_INVOICES_MESSAGE = "No invoices found matching your query."


class InvoicesHandler:
    intent = "invoices"
    license_feature: Optional[str] = None
    license_denied_message = ""
    args_schema = [
        ArgSpec(
            name="limit",
            type=int,
            default=20,
            min_value=1,
            max_value=100,
            description="Maximum number of invoices to return on the default list path.",
        ),
    ]

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        list_limit = ctx.validated_args["limit"]
        is_search, query = detect_search_intent(ctx.lower_message)
        if is_search and query:
            result = await ctx.tools.search_invoices(query=query)
        elif is_search:
            # Search keyword without a captured query falls back to a small page;
            # keep this hardcoded so search-fallbacks don't get massive.
            result = await ctx.tools.list_invoices(limit=10)
        else:
            result = await ctx.tools.list_invoices(limit=list_limit)

        if not result.get("success"):
            # Legacy behavior: don't fall back to the LLM on an MCP failure;
            # show the user the underlying error wrapped in our envelope.
            return mcp_envelope(
                ctx,
                f"Error retrieving invoices: {result.get('error', 'Unknown error')}",
            )

        invoices = result.get("data") or []
        if not invoices:
            return mcp_envelope(ctx, NO_INVOICES_MESSAGE)
        return mcp_envelope(ctx, format_invoices_response(invoices))


def format_invoices_response(invoices: list[dict[str, Any]]) -> str:
    total = sum(inv.get("amount", 0) or 0 for inv in invoices)
    avg = total / len(invoices) if invoices else 0
    status_counts: dict[str, int] = {}
    for inv in invoices:
        status = inv.get("status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    status_lines = "\n".join(
        f"• **{status.title()}:** {count:,}" for status, count in status_counts.items()
    )
    invoice_lines = "\n".join(
        f"• **Invoice #{inv.get('invoice_number', inv.get('id', 'N/A'))}**\n"
        f"  👤 Client: {inv.get('client_name', 'Unknown Client')}\n"
        f"  💰 Amount: ${inv.get('amount', 0):,.2f}\n"
        f"  📊 Status: {str(inv.get('status', 'Unknown')).title()}\n"
        f"  📅 Due: {inv.get('due_date', 'N/A')}\n"
        "  -----------------------------------------\n"
        for inv in invoices
    )
    return (
        "📄 **Invoice Management Dashboard**\n\n"
        "📊 **📈 Invoice Overview:**\n"
        f"• **Total Invoices:** {len(invoices):,}\n"
        f"• **Total Amount:** ${total:,.2f}\n"
        f"• **Average Invoice Amount:** ${avg:,.2f}\n\n"
        "📋 **📊 Status Breakdown:**\n"
        f"{status_lines}\n\n"
        "📄 **💼 Invoice Details:**\n"
        f"{invoice_lines}\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive invoice information was retrieved using your actual "
        "invoice data through our advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(InvoicesHandler())
