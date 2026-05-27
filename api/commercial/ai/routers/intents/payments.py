# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""payments intent handler — natural-language payment query with optional date filter."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)


logger = logging.getLogger(__name__)


class PaymentsHandler:
    intent = "payments"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        # The MCP tool parses the user's natural-language query itself and
        # echoes back whether/how it applied a date filter.
        result = await ctx.tools.query_payments(query=ctx.message)
        if not result.get("success"):
            logger.info("payments: tool failed; falling back. result=%s", result)
            return None

        payments = result.get("data") or []
        date_filter_applied = bool(result.get("date_filter_applied", False))
        date_description = str(result.get("date_description", ""))

        if not payments:
            if date_filter_applied:
                return mcp_envelope(ctx, f"No payments found {date_description}.")
            return mcp_envelope(ctx, "No payments found.")

        return mcp_envelope(
            ctx,
            format_payments_response(payments, date_filter_applied, date_description),
        )


def format_payments_response(
    payments: list[dict[str, Any]],
    date_filter_applied: bool,
    date_description: str,
) -> str:
    title = (
        f"💰 **Payment Report {date_description}**"
        if date_filter_applied
        else "💰 **Payment Information Dashboard**"
    )
    total = sum(payment.get("amount", 0) or 0 for payment in payments)
    detail_lines = "\n".join(
        f"• **Payment #{payment.get('id', 'N/A')}**\n"
        f"  📄 Invoice: #{payment.get('invoice_number', 'N/A')}\n"
        f"  💰 Amount: ${payment.get('amount', 0):,.2f}\n"
        f"  💳 Method: {payment.get('payment_method', 'Unknown')}\n"
        f"  📅 Date: {payment.get('payment_date', 'N/A')}\n"
        for payment in payments
    )
    date_range = date_description if date_filter_applied else "All Time"
    return (
        f"{title}\n\n"
        "📊 **📈 Payment Summary:**\n"
        f"• **Total Payments:** {len(payments):,}\n"
        f"• **Total Amount:** ${total:,.2f}\n"
        f"• **Date Range:** {date_range}\n\n"
        "💳 **💵 Payment Details:**\n"
        f"{detail_lines}\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive payment information was retrieved using your actual "
        "payment data through our advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(PaymentsHandler())
