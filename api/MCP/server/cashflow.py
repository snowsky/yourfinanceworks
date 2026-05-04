"""Cash Flow Forecasting tool registrations."""
from typing import List, Optional

from ._shared import mcp, server_context


@mcp.tool()
async def get_cashflow_forecast(
    period: str = "30d",
    current_balance: Optional[float] = None,
) -> dict:
    """
    Get projected cash inflows, outflows, daily balances, and alerts.

    Args:
        period: Forecast period, one of 7d, 30d, 90d, or 365d
        current_balance: Optional override for starting cash balance
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_cashflow_forecast(
        period=period,
        current_balance=current_balance,
    )


@mcp.tool()
async def get_cashflow_runway(current_balance: Optional[float] = None) -> dict:
    """
    Calculate cash runway from recent burn rate and current balance.

    Args:
        current_balance: Optional override for starting cash balance
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_cashflow_runway(
        current_balance=current_balance,
    )


@mcp.tool()
async def run_cashflow_scenario(
    description: str,
    period: str = "30d",
    delayed_invoice_ids: Optional[List[int]] = None,
    delay_days: int = 30,
    additional_expense: Optional[float] = None,
    additional_expense_date: Optional[str] = None,
    revenue_change_percent: Optional[float] = None,
    expense_change_percent: Optional[float] = None,
    current_balance: Optional[float] = None,
) -> dict:
    """
    Run a cash flow what-if scenario.

    Args:
        description: Human-readable scenario description
        period: Forecast period, one of 7d, 30d, 90d, or 365d
        delayed_invoice_ids: Invoice IDs to delay in the scenario
        delay_days: Number of days to delay selected invoices
        additional_expense: Optional one-time added expense amount
        additional_expense_date: ISO date for the added expense, YYYY-MM-DD
        revenue_change_percent: Percent change to projected revenue, minimum -100
        expense_change_percent: Percent change to projected expenses, minimum -100
        current_balance: Optional override for starting cash balance
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.run_cashflow_scenario(
        description=description,
        period=period,
        delayed_invoice_ids=delayed_invoice_ids,
        delay_days=delay_days,
        additional_expense=additional_expense,
        additional_expense_date=additional_expense_date,
        revenue_change_percent=revenue_change_percent,
        expense_change_percent=expense_change_percent,
        current_balance=current_balance,
    )


@mcp.tool()
async def get_cashflow_alerts(current_balance: Optional[float] = None) -> dict:
    """
    Get cash flow alerts based on configured thresholds.

    Args:
        current_balance: Optional override for starting cash balance
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_cashflow_alerts(
        current_balance=current_balance,
    )


@mcp.tool()
async def get_cashflow_thresholds() -> dict:
    """Get cash flow alert threshold and projection settings."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_cashflow_thresholds()


@mcp.tool()
async def update_cashflow_thresholds(settings: dict) -> dict:
    """
    Update cash flow alert threshold and projection settings.

    Args:
        settings: Partial cash flow settings object with fields such as
            safety_threshold, warning_threshold, currency,
            include_bank_statement_patterns, bank_statement_lookback_days,
            bank_statement_intervals, bank_statement_inflow_categories, and
            bank_statement_outflow_categories
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_cashflow_thresholds(settings=settings)
