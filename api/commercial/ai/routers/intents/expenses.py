# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""expenses intent handler — search-or-list routing with planner-driven page size."""

from __future__ import annotations

import logging
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)
from commercial.ai.routers.intents._helpers import (
    _requested_limit_from_options,
    detect_search_intent,
)


logger = logging.getLogger(__name__)


NO_EXPENSES_MESSAGE = "No expenses found matching your query."


class ExpensesHandler:
    intent = "expenses"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        requested_limit = _requested_limit_from_options(ctx.tool_options, default=20)
        is_search, query = detect_search_intent(ctx.lower_message)
        if is_search and query:
            result = await ctx.tools.search_expenses(query=query, limit=requested_limit)
        elif is_search:
            result = await ctx.tools.list_expenses(limit=min(requested_limit, 10))
        else:
            result = await ctx.tools.list_expenses(limit=requested_limit)

        if not result.get("success"):
            logger.info("expenses: tool failed; falling back. result=%s", result)
            return None

        expenses = result.get("data") or []
        if not expenses:
            return mcp_envelope(ctx, NO_EXPENSES_MESSAGE)
        return mcp_envelope(ctx, format_expenses_response(expenses))


def format_expenses_response(expenses: list[dict[str, Any]]) -> str:
    pre_tax = sum(exp.get("amount", 0) or 0 for exp in expenses)
    tax = sum(exp.get("tax_amount", 0) or 0 for exp in expenses)
    with_tax = sum(
        (exp.get("total_amount") or exp.get("amount", 0) or 0) for exp in expenses
    )
    average = pre_tax / len(expenses) if expenses else 0
    expense_lines = "\n".join(
        f"• **Expense #{exp.get('id', 'N/A')}**\n"
        f"  📝 Category: {exp.get('category', 'Unknown')}\n"
        f"  🏪 Vendor: {exp.get('vendor', 'N/A')}\n"
        f"  💰 Amount: ${(exp.get('amount') or 0):,.2f}\n"
        f"  📊 Tax: ${(exp.get('tax_amount') or 0):,.2f}\n"
        f"  💳 Total: ${(exp.get('total_amount') or exp.get('amount') or 0):,.2f}\n"
        f"  📅 Date: {exp.get('expense_date', 'N/A')}\n"
        "  -----------------------------------------\n"
        for exp in expenses
    )
    return (
        "💸 **Expense Management Dashboard**\n\n"
        "📊 **📈 Expense Overview:**\n"
        f"• **Total Expenses:** {len(expenses):,}\n"
        f"• **Total Amount (Pre-Tax):** ${pre_tax:,.2f}\n"
        f"• **Total Tax:** ${tax:,.2f}\n"
        f"• **Total Amount (With Tax):** ${with_tax:,.2f}\n"
        f"• **Average Expense:** ${average:,.2f}\n\n"
        "💸 **💼 Expense Details:**\n"
        f"{expense_lines}\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive expense information was retrieved using your actual "
        "expense data through our advanced MCP tools."
    )


def register(registry: IntentRegistry) -> None:
    registry.register(ExpensesHandler())
