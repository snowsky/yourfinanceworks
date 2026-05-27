"""Smoke tests for the seven single-tool intents migrated to the registry:
analyze_patterns, suggest_actions, currencies, outstanding, overdue,
statements, statistics.

Each handler is exercised through its public ``execute(ctx)`` coroutine with
a stub tools object. We check three branches per handler:
  * tool success with non-empty data → handler returns an envelope whose body
    contains identifying markdown
  * tool failure → handler returns ``None`` (caller falls back to LLM)
  * (where applicable) tool success with empty data → handler returns the
    no-results message
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
def handlers(intent_registry):
    return {
        "analyze_patterns": _load_module(
            "commercial.ai.routers.intents.analyze_patterns",
            "commercial/ai/routers/intents/analyze_patterns.py",
        ),
        "suggest_actions": _load_module(
            "commercial.ai.routers.intents.suggest_actions",
            "commercial/ai/routers/intents/suggest_actions.py",
        ),
        "currencies": _load_module(
            "commercial.ai.routers.intents.currencies",
            "commercial/ai/routers/intents/currencies.py",
        ),
        "outstanding": _load_module(
            "commercial.ai.routers.intents.outstanding",
            "commercial/ai/routers/intents/outstanding.py",
        ),
        "overdue": _load_module(
            "commercial.ai.routers.intents.overdue",
            "commercial/ai/routers/intents/overdue.py",
        ),
        "statements": _load_module(
            "commercial.ai.routers.intents.statements",
            "commercial/ai/routers/intents/statements.py",
        ),
        "statistics": _load_module(
            "commercial.ai.routers.intents.statistics",
            "commercial/ai/routers/intents/statistics.py",
        ),
    }


def _ai_config():
    return SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini")


def _ctx(intent_registry, intent: str, *, tools):
    return intent_registry.IntentContext(
        intent=intent,
        message="?",
        lower_message="?",
        tools=tools,
        ai_config=_ai_config(),
        page_context=None,
        db=None,
        tool_options=None,
    )


class _Tools:
    """Bag of async-method attributes; each method returns the canned result it was given."""

    def __init__(self, **methods):
        for name, result in methods.items():
            async def _impl(_r=result, **_kwargs):
                return _r
            setattr(self, name, _impl)


# ---------- analyze_patterns ----------


def test_analyze_patterns_renders_report(intent_registry, handlers):
    tools = _Tools(
        analyze_invoice_patterns={
            "success": True,
            "data": {
                "total_invoices": 100,
                "paid_invoices": 70,
                "partially_paid_invoices": 5,
                "unpaid_invoices": 20,
                "overdue_invoices": 5,
                "total_revenue_by_currency": {"USD": 50000.0, "EUR": 12000.0},
                "outstanding_revenue_by_currency": {"USD": 3000.0},
                "recommendations": ["Follow up on overdue", "Send reminders"],
            },
        }
    )
    handler = handlers["analyze_patterns"].AnalyzePatternsHandler()
    result = asyncio.run(handler.execute(_ctx(intent_registry, "analyze_patterns", tools=tools)))
    body = result["data"]["response"]
    assert "Invoice Pattern Analysis Report" in body
    assert "USD $50,000.00" in body
    assert "Follow up on overdue" in body


def test_analyze_patterns_returns_none_on_tool_failure(intent_registry, handlers):
    tools = _Tools(analyze_invoice_patterns={"success": False})
    handler = handlers["analyze_patterns"].AnalyzePatternsHandler()
    assert asyncio.run(handler.execute(_ctx(intent_registry, "analyze_patterns", tools=tools))) is None


# ---------- suggest_actions ----------


def test_suggest_actions_renders_priority_emojis(intent_registry, handlers):
    tools = _Tools(
        suggest_invoice_actions={
            "success": True,
            "data": {
                "suggested_actions": [
                    {"action": "send_reminder", "priority": "high", "description": "Email overdue clients"},
                    {"action": "review", "priority": "low", "description": "Audit unpaid"},
                ],
                "overdue_count": 5,
                "clients_with_balance": 12,
                "recent_invoices_count": 30,
            },
        }
    )
    handler = handlers["suggest_actions"].SuggestActionsHandler()
    body = asyncio.run(handler.execute(_ctx(intent_registry, "suggest_actions", tools=tools)))["data"]["response"]
    assert "🔴" in body  # high priority
    assert "🟢" in body  # low priority
    assert "Send Reminder" in body
    assert "Overdue Invoices:** 5" in body


def test_suggest_actions_returns_none_on_tool_failure(intent_registry, handlers):
    tools = _Tools(suggest_invoice_actions={"success": False})
    handler = handlers["suggest_actions"].SuggestActionsHandler()
    assert asyncio.run(handler.execute(_ctx(intent_registry, "suggest_actions", tools=tools))) is None


# ---------- currencies ----------


def test_currencies_renders_dashboard(intent_registry, handlers):
    tools = _Tools(
        list_currencies={
            "success": True,
            "data": [
                {"code": "USD", "symbol": "$", "name": "US Dollar", "is_active": True},
                {"code": "EUR", "symbol": "€", "name": "Euro", "is_active": True},
            ],
        }
    )
    handler = handlers["currencies"].CurrenciesHandler()
    body = asyncio.run(handler.execute(_ctx(intent_registry, "currencies", tools=tools)))["data"]["response"]
    assert "Currency Management Dashboard" in body
    assert "USD" in body and "EUR" in body
    assert "Active Currencies:** 2" in body


def test_currencies_returns_no_currencies_message(intent_registry, handlers):
    tools = _Tools(list_currencies={"success": True, "data": []})
    handler = handlers["currencies"].CurrenciesHandler()
    result = asyncio.run(handler.execute(_ctx(intent_registry, "currencies", tools=tools)))
    assert result["data"]["response"] == handlers["currencies"].NO_CURRENCIES_MESSAGE


# ---------- outstanding ----------


def test_outstanding_renders_aggregate(intent_registry, handlers):
    tools = _Tools(
        get_clients_with_outstanding_balance={
            "success": True,
            "data": [
                {"name": "Acme", "outstanding_balance": 500, "email": "a@x.com", "phone": "555"},
                {"name": "Beta", "outstanding_balance": 1500, "email": "b@x.com", "phone": "666"},
            ],
        }
    )
    handler = handlers["outstanding"].OutstandingHandler()
    body = asyncio.run(handler.execute(_ctx(intent_registry, "outstanding", tools=tools)))["data"]["response"]
    assert "Outstanding Balance Report" in body
    assert "$2,000.00" in body
    assert "$1,000.00" in body  # average


def test_outstanding_returns_empty_message(intent_registry, handlers):
    tools = _Tools(get_clients_with_outstanding_balance={"success": True, "data": []})
    handler = handlers["outstanding"].OutstandingHandler()
    result = asyncio.run(handler.execute(_ctx(intent_registry, "outstanding", tools=tools)))
    assert result["data"]["response"] == handlers["outstanding"].NO_OUTSTANDING_MESSAGE


# ---------- overdue ----------


def test_overdue_renders_alert_with_averages(intent_registry, handlers):
    tools = _Tools(
        get_overdue_invoices={
            "success": True,
            "data": [
                {"invoice_number": "INV-1", "client_name": "Acme", "amount": 100, "due_date": "2026-01-01", "days_overdue": 10},
                {"invoice_number": "INV-2", "client_name": "Beta", "amount": 300, "due_date": "2026-02-01", "days_overdue": 20},
            ],
        }
    )
    handler = handlers["overdue"].OverdueHandler()
    body = asyncio.run(handler.execute(_ctx(intent_registry, "overdue", tools=tools)))["data"]["response"]
    assert "Overdue Invoice Alert Report" in body
    assert "$400.00" in body
    assert "15.0 days" in body  # avg of 10 + 20


def test_overdue_returns_empty_message(intent_registry, handlers):
    tools = _Tools(get_overdue_invoices={"success": True, "data": []})
    handler = handlers["overdue"].OverdueHandler()
    result = asyncio.run(handler.execute(_ctx(intent_registry, "overdue", tools=tools)))
    assert result["data"]["response"] == handlers["overdue"].NO_OVERDUE_MESSAGE


# ---------- statements ----------


def test_statements_counts_processed_and_pending(intent_registry, handlers):
    tools = _Tools(
        list_statements={
            "success": True,
            "data": [
                {"id": 1, "account_name": "Chase", "statement_period": "2026-05", "status": "processed", "transaction_count": 50, "created_at": "2026-05-01"},
                {"id": 2, "account_name": "BofA", "statement_period": "2026-05", "status": "pending", "transaction_count": 0, "created_at": "2026-05-02"},
                {"id": 3, "account_name": "Wells", "statement_period": "2026-05", "status": "processed", "transaction_count": 30, "created_at": "2026-05-03"},
            ],
        }
    )
    handler = handlers["statements"].StatementsHandler()
    body = asyncio.run(handler.execute(_ctx(intent_registry, "statements", tools=tools)))["data"]["response"]
    assert "Total Statements:** 3" in body
    assert "Processed Statements:** 2" in body
    assert "Pending Statements:** 1" in body


def test_statements_returns_empty_message(intent_registry, handlers):
    tools = _Tools(list_statements={"success": True, "data": []})
    handler = handlers["statements"].StatementsHandler()
    result = asyncio.run(handler.execute(_ctx(intent_registry, "statements", tools=tools)))
    assert result["data"]["response"] == handlers["statements"].NO_STATEMENTS_MESSAGE


# ---------- statistics ----------


def test_statistics_computes_rates(intent_registry, handlers):
    tools = _Tools(
        get_invoice_stats={
            "success": True,
            "data": {
                "total_invoices": 100,
                "paid_invoices": 75,
                "unpaid_invoices": 20,
                "overdue_invoices": 5,
                "total_revenue": 50000.0,
                "average_invoice_amount": 500.0,
            },
        }
    )
    handler = handlers["statistics"].StatisticsHandler()
    body = asyncio.run(handler.execute(_ctx(intent_registry, "statistics", tools=tools)))["data"]["response"]
    assert "Payment Rate:** 75.0%" in body
    assert "Overdue Rate:** 5.0%" in body


def test_statistics_avoids_divide_by_zero(intent_registry, handlers):
    tools = _Tools(
        get_invoice_stats={"success": True, "data": {"total_invoices": 0}}
    )
    handler = handlers["statistics"].StatisticsHandler()
    body = asyncio.run(handler.execute(_ctx(intent_registry, "statistics", tools=tools)))["data"]["response"]
    assert "Payment Rate:** 0.0%" in body
    assert "Overdue Rate:** 0.0%" in body


def test_statistics_returns_none_on_tool_failure(intent_registry, handlers):
    tools = _Tools(get_invoice_stats={"success": False})
    handler = handlers["statistics"].StatisticsHandler()
    assert asyncio.run(handler.execute(_ctx(intent_registry, "statistics", tools=tools))) is None


# ---------- registry contents ----------


def test_default_registry_contains_all_migrated_intents(intent_registry, handlers):
    # Force-load the intents package by loading each handler then registering manually,
    # mirroring what intents/__init__.py does at runtime.
    registry = intent_registry.IntentRegistry()
    handlers["analyze_patterns"].register(registry)
    handlers["suggest_actions"].register(registry)
    handlers["currencies"].register(registry)
    handlers["outstanding"].register(registry)
    handlers["overdue"].register(registry)
    handlers["statements"].register(registry)
    handlers["statistics"].register(registry)

    assert sorted(registry.registered_intents()) == [
        "analyze_patterns",
        "currencies",
        "outstanding",
        "overdue",
        "statements",
        "statistics",
        "suggest_actions",
    ]
