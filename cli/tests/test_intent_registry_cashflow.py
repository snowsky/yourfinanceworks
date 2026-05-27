"""Tests for the cashflow handler.

Covers the three sub-routes (runway / alerts / forecast), period parsing,
and tool-failure fallback semantics. The license-deny path is already
exercised by the registry-level tests (see test_intent_registry.py); here
we just confirm the handler declares the correct ``license_feature`` value
so the registry's existing gate logic applies.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


API_DIR = Path(__file__).resolve().parents[2] / "api"


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, API_DIR / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def intent_registry():
    return _load_module(
        "commercial.ai.routers.intent_registry",
        "commercial/ai/routers/intent_registry.py",
    )


@pytest.fixture(scope="module")
def cashflow(intent_registry):
    return _load_module(
        "commercial.ai.routers.intents.cashflow",
        "commercial/ai/routers/intents/cashflow.py",
    )


def _ai_config():
    return SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini")


def _ctx(intent_registry, *, tools, message):
    return intent_registry.IntentContext(
        intent="cashflow",
        message=message,
        lower_message=message.lower(),
        tools=tools,
        ai_config=_ai_config(),
        page_context=None,
        db=None,
        tool_options=None,
    )


class _RecordingTools:
    def __init__(self, **results):
        self.calls: list[tuple[str, dict]] = []
        self._results = results

    def __getattr__(self, name):
        async def _impl(**kwargs):
            self.calls.append((name, kwargs))
            return self._results.get(name, {"success": False})
        return _impl


# ---------- handler declaration ----------


def test_cashflow_handler_declares_license_feature(cashflow):
    handler = cashflow.CashflowHandler()
    assert handler.intent == "cashflow"
    assert handler.license_feature == "cash_flow"
    assert "not enabled" in handler.license_denied_message


# ---------- period parsing ----------


@pytest.mark.parametrize(
    "message,expected_period",
    [
        ("forecast for the next quarter", "90d"),
        ("90 day cash flow", "90d"),
        ("weekly forecast", "7d"),
        ("show me 7 days of cash flow", "7d"),
        ("annual forecast", "365d"),
        ("year ahead", "365d"),
        ("365 day projection", "365d"),
        ("default cash flow forecast", "30d"),
        ("show me cash flow", "30d"),
    ],
)
def test_period_from_message(cashflow, message, expected_period):
    assert cashflow.period_from_message(message.lower()) == expected_period


# ---------- runway sub-route ----------


def test_runway_keyword_routes_to_runway_tool(intent_registry, cashflow):
    tools = _RecordingTools(
        get_cashflow_runway={
            "success": True,
            "data": {
                "current_balance": 10000.0,
                "average_daily_burn": 200.0,
                "average_daily_income": 50.0,
                "net_daily_burn": 150.0,
                "runway_days": 67,
                "monthly_burn_rate": 6000.0,
                "monthly_income_rate": 1500.0,
            },
        }
    )
    handler = cashflow.CashflowHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="what's my runway?"))
    )["data"]["response"]

    assert tools.calls == [("get_cashflow_runway", {})]
    assert "Cash Runway" in body
    assert "67 days" in body


def test_runway_with_no_runway_days_shows_net_positive(intent_registry, cashflow):
    tools = _RecordingTools(
        get_cashflow_runway={"success": True, "data": {"runway_days": None, "current_balance": 5000}}
    )
    handler = cashflow.CashflowHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="show burn rate"))
    )["data"]["response"]

    assert "Runway:** net positive" in body


def test_burn_rate_keyword_also_routes_to_runway(intent_registry, cashflow):
    tools = _RecordingTools(
        get_cashflow_runway={"success": True, "data": {"runway_days": 30, "current_balance": 0}}
    )
    handler = cashflow.CashflowHandler()
    asyncio.run(handler.execute(_ctx(intent_registry, tools=tools, message="what's my burn rate")))
    assert tools.calls == [("get_cashflow_runway", {})]


# ---------- alerts sub-route ----------


def test_alert_keyword_routes_to_alerts_tool(intent_registry, cashflow):
    tools = _RecordingTools(
        get_cashflow_alerts={
            "success": True,
            "data": {
                "current_balance": 1000.0,
                "safety_threshold": 5000.0,
                "warning_threshold": 2000.0,
                "alerts": ["Balance below safety threshold", "Negative trend"],
            },
        }
    )
    handler = cashflow.CashflowHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="any cash flow alerts?"))
    )["data"]["response"]

    assert tools.calls == [("get_cashflow_alerts", {})]
    assert "Cash Flow Alerts" in body
    assert "Balance below safety threshold" in body
    assert "Negative trend" in body


def test_alerts_with_empty_list_shows_no_alerts_message(intent_registry, cashflow):
    tools = _RecordingTools(
        get_cashflow_alerts={"success": True, "data": {"alerts": [], "current_balance": 10000}}
    )
    handler = cashflow.CashflowHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="show alerts"))
    )["data"]["response"]
    assert "No cash flow alerts are active." in body


def test_threshold_and_low_cash_keywords_also_route_to_alerts(intent_registry, cashflow):
    handler = cashflow.CashflowHandler()
    for message in ("am I near my threshold?", "do I have low cash"):
        tools = _RecordingTools(get_cashflow_alerts={"success": True, "data": {"alerts": []}})
        asyncio.run(handler.execute(_ctx(intent_registry, tools=tools, message=message)))
        assert tools.calls == [("get_cashflow_alerts", {})]


# ---------- forecast sub-route (default) ----------


def test_default_routes_to_forecast_with_30d_period(intent_registry, cashflow):
    tools = _RecordingTools(
        get_cashflow_forecast={
            "success": True,
            "data": {
                "current_balance": 10000.0,
                "projected_end_balance": 8000.0,
                "total_projected_inflows": 5000.0,
                "total_projected_outflows": 7000.0,
                "net_change": -2000.0,
                "period": "30d",
                "alerts": [],
            },
        }
    )
    handler = cashflow.CashflowHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="show me cash flow"))
    )["data"]["response"]

    assert tools.calls == [("get_cashflow_forecast", {"period": "30d"})]
    assert "Cash Flow Forecast (30d)" in body
    assert "Projected End Balance:** $8,000.00" in body
    assert "No forecast alerts." in body


def test_forecast_period_derived_from_message_keywords(intent_registry, cashflow):
    handler = cashflow.CashflowHandler()
    for message, expected in [
        ("quarterly forecast please", "90d"),
        ("show me the weekly outlook", "7d"),
        ("annual forecast", "365d"),
    ]:
        tools = _RecordingTools(
            get_cashflow_forecast={"success": True, "data": {"period": expected, "alerts": []}}
        )
        asyncio.run(handler.execute(_ctx(intent_registry, tools=tools, message=message)))
        assert tools.calls == [("get_cashflow_forecast", {"period": expected})]


def test_forecast_uses_data_period_when_present(intent_registry, cashflow):
    """When the tool echoes back a different period than requested, the response shows the echoed one."""
    tools = _RecordingTools(
        get_cashflow_forecast={
            "success": True,
            "data": {"period": "60d", "current_balance": 0, "projected_end_balance": 0,
                     "total_projected_inflows": 0, "total_projected_outflows": 0,
                     "net_change": 0, "alerts": []},
        }
    )
    handler = cashflow.CashflowHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="show cash flow"))
    )["data"]["response"]
    assert "Cash Flow Forecast (60d)" in body


# ---------- failure semantics ----------


def test_runway_tool_failure_returns_none(intent_registry, cashflow):
    tools = _RecordingTools(get_cashflow_runway={"success": False})
    handler = cashflow.CashflowHandler()
    assert (
        asyncio.run(handler.execute(_ctx(intent_registry, tools=tools, message="runway"))) is None
    )


def test_alerts_tool_failure_returns_none(intent_registry, cashflow):
    tools = _RecordingTools(get_cashflow_alerts={"success": False})
    handler = cashflow.CashflowHandler()
    assert (
        asyncio.run(handler.execute(_ctx(intent_registry, tools=tools, message="alerts"))) is None
    )


def test_forecast_tool_failure_returns_none(intent_registry, cashflow):
    tools = _RecordingTools(get_cashflow_forecast={"success": False})
    handler = cashflow.CashflowHandler()
    assert (
        asyncio.run(handler.execute(_ctx(intent_registry, tools=tools, message="cash flow"))) is None
    )
