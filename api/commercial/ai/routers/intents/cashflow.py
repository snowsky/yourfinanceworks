# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""cashflow intent handler — license-gated cash flow analytics with sub-routing.

Three sub-paths keyed off the chat message:

  * "runway" / "burn rate"           -> get_cashflow_runway
  * "alert" / "threshold" / "low cash" -> get_cashflow_alerts
  * everything else                  -> get_cashflow_forecast (default 30d)

The forecast period is derived from the message ("week"/"7" -> 7d,
"quarter"/"90" -> 90d, "year"/"annual"/"365" -> 365d, otherwise 30d).
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


CASHFLOW_DISABLED_MESSAGE = (
    "The Cash Flow Forecasting feature is not enabled for your account. "
    "Please contact your administrator or upgrade your license to access "
    "forecasts, runway analysis, and scenario planning."
)


_RUNWAY_KEYWORDS = ("runway", "burn rate")
_ALERT_KEYWORDS = ("alert", "threshold", "low cash")


class CashflowHandler:
    intent = "cashflow"
    license_feature = "cash_flow"
    license_denied_message = CASHFLOW_DISABLED_MESSAGE

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        lower = ctx.lower_message

        if any(keyword in lower for keyword in _RUNWAY_KEYWORDS):
            result = await ctx.tools.get_cashflow_runway()
            if not result.get("success"):
                logger.info("cashflow runway: tool failed; falling back. result=%s", result)
                return None
            return mcp_envelope(ctx, format_runway_response(result.get("data") or {}))

        if any(keyword in lower for keyword in _ALERT_KEYWORDS):
            result = await ctx.tools.get_cashflow_alerts()
            if not result.get("success"):
                logger.info("cashflow alerts: tool failed; falling back. result=%s", result)
                return None
            return mcp_envelope(ctx, format_alerts_response(result.get("data") or {}))

        period = period_from_message(lower)
        result = await ctx.tools.get_cashflow_forecast(period=period)
        if not result.get("success"):
            logger.info("cashflow forecast: tool failed; falling back. result=%s", result)
            return None
        return mcp_envelope(ctx, format_forecast_response(result.get("data") or {}, period))


def period_from_message(lower_message: str) -> str:
    """Pick a forecast horizon from keywords in the user's message."""
    if any(token in lower_message for token in ("90", "quarter")):
        return "90d"
    if "7" in lower_message or "week" in lower_message:
        return "7d"
    if any(token in lower_message for token in ("year", "annual", "365")):
        return "365d"
    return "30d"


def format_runway_response(data: dict[str, Any]) -> str:
    runway_days = data.get("runway_days")
    runway_text = "net positive" if runway_days is None else f"{runway_days} days"
    return (
        "💵 **Cash Runway**\n\n"
        f"• **Current Balance:** ${data.get('current_balance', 0):,.2f}\n"
        f"• **Average Daily Burn:** ${data.get('average_daily_burn', 0):,.2f}\n"
        f"• **Average Daily Income:** ${data.get('average_daily_income', 0):,.2f}\n"
        f"• **Net Daily Burn:** ${data.get('net_daily_burn', 0):,.2f}\n"
        f"• **Runway:** {runway_text}\n"
        f"• **Monthly Burn Rate:** ${data.get('monthly_burn_rate', 0):,.2f}\n"
        f"• **Monthly Income Rate:** ${data.get('monthly_income_rate', 0):,.2f}"
    )


def format_alerts_response(data: dict[str, Any]) -> str:
    alerts = data.get("alerts") or []
    alert_lines = (
        "\n".join(f"• {alert}" for alert in alerts)
        if alerts
        else "No cash flow alerts are active."
    )
    return (
        "💵 **Cash Flow Alerts**\n\n"
        f"• **Current Balance:** ${data.get('current_balance', 0):,.2f}\n"
        f"• **Safety Threshold:** ${data.get('safety_threshold', 0):,.2f}\n"
        f"• **Warning Threshold:** ${data.get('warning_threshold', 0):,.2f}\n\n"
        f"{alert_lines}"
    )


def format_forecast_response(data: dict[str, Any], requested_period: str) -> str:
    alerts = data.get("alerts") or []
    alert_lines = (
        "\n".join(f"• {alert}" for alert in alerts) if alerts else "No forecast alerts."
    )
    period = data.get("period", requested_period)
    return (
        f"💵 **Cash Flow Forecast ({period})**\n\n"
        f"• **Current Balance:** ${data.get('current_balance', 0):,.2f}\n"
        f"• **Projected End Balance:** ${data.get('projected_end_balance', 0):,.2f}\n"
        f"• **Projected Inflows:** ${data.get('total_projected_inflows', 0):,.2f}\n"
        f"• **Projected Outflows:** ${data.get('total_projected_outflows', 0):,.2f}\n"
        f"• **Net Change:** ${data.get('net_change', 0):,.2f}\n\n"
        f"{alert_lines}"
    )


def register(registry: IntentRegistry) -> None:
    registry.register(CashflowHandler())
