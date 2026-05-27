"""Tests for the three handlers with sub-routing: payments, invoices, expenses.

Also covers ``intents/_helpers.detect_search_intent``, the shared utility that
recognizes "search ..." / "find ..." queries and extracts the captured term.
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
def helpers(intent_registry):
    return _load_module(
        "commercial.ai.routers.intents._helpers",
        "commercial/ai/routers/intents/_helpers.py",
    )


@pytest.fixture(scope="module")
def handlers(intent_registry, helpers):
    return {
        "payments": _load_module(
            "commercial.ai.routers.intents.payments",
            "commercial/ai/routers/intents/payments.py",
        ),
        "invoices": _load_module(
            "commercial.ai.routers.intents.invoices",
            "commercial/ai/routers/intents/invoices.py",
        ),
        "expenses": _load_module(
            "commercial.ai.routers.intents.expenses",
            "commercial/ai/routers/intents/expenses.py",
        ),
    }


def _ai_config():
    return SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini")


def _ctx(intent_registry, intent, *, tools, message="?", tool_options=None):
    return intent_registry.IntentContext(
        intent=intent,
        message=message,
        lower_message=message.lower(),
        tools=tools,
        ai_config=_ai_config(),
        page_context=None,
        db=None,
        tool_options=tool_options,
    )


class _RecordingTools:
    """Records each async tool call (name, kwargs) and returns the canned result for that name."""

    def __init__(self, **results):
        self.calls: list[tuple[str, dict]] = []
        self._results = results

    def __getattr__(self, name):
        async def _impl(**kwargs):
            self.calls.append((name, kwargs))
            return self._results.get(name, {"success": False})
        return _impl


# ---------- detect_search_intent ----------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("show me payments", (False, None)),
        ("list the invoices", (False, None)),
        ("search for acme", (True, "acme")),
        ("find invoices for client foo", (True, "invoices for client foo")),
        ("find 'widgets'", (True, "widgets")),
        ('search "lunch receipts"', (True, "lunch receipts")),
        ("search", (True, None)),
        ("find", (True, None)),
    ],
)
def test_detect_search_intent(helpers, message, expected):
    assert helpers.detect_search_intent(message) == expected


# ---------- payments ----------


def test_payments_renders_dashboard_without_date_filter(intent_registry, handlers):
    tools = _RecordingTools(
        query_payments={
            "success": True,
            "data": [
                {"id": 1, "invoice_number": "INV-1", "amount": 100.0, "payment_method": "card", "payment_date": "2026-05-01"},
                {"id": 2, "invoice_number": "INV-2", "amount": 250.5, "payment_method": "ach", "payment_date": "2026-05-02"},
            ],
            "date_filter_applied": False,
            "date_description": "",
        }
    )
    handler = handlers["payments"].PaymentsHandler()
    ctx = _ctx(intent_registry, "payments", tools=tools, message="how much did I get paid?")

    result = asyncio.run(handler.execute(ctx))
    body = result["data"]["response"]

    assert tools.calls == [("query_payments", {"query": "how much did I get paid?"})]
    assert "Payment Information Dashboard" in body
    assert "$350.50" in body
    assert "Date Range:** All Time" in body


def test_payments_renders_dashboard_with_date_filter(intent_registry, handlers):
    tools = _RecordingTools(
        query_payments={
            "success": True,
            "data": [
                {"id": 5, "invoice_number": "INV-5", "amount": 90, "payment_method": "card", "payment_date": "2026-05-10"},
            ],
            "date_filter_applied": True,
            "date_description": "in May 2026",
        }
    )
    handler = handlers["payments"].PaymentsHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, "payments", tools=tools, message="payments in May"))
    )["data"]["response"]

    assert "Payment Report in May 2026" in body
    assert "Date Range:** in May 2026" in body


def test_payments_no_results_without_date_filter(intent_registry, handlers):
    tools = _RecordingTools(query_payments={"success": True, "data": []})
    handler = handlers["payments"].PaymentsHandler()
    result = asyncio.run(handler.execute(_ctx(intent_registry, "payments", tools=tools)))
    assert result["data"]["response"] == "No payments found."


def test_payments_no_results_with_date_filter(intent_registry, handlers):
    tools = _RecordingTools(
        query_payments={
            "success": True,
            "data": [],
            "date_filter_applied": True,
            "date_description": "last week",
        }
    )
    handler = handlers["payments"].PaymentsHandler()
    result = asyncio.run(handler.execute(_ctx(intent_registry, "payments", tools=tools)))
    assert result["data"]["response"] == "No payments found last week."


def test_payments_returns_none_on_tool_failure(intent_registry, handlers):
    tools = _RecordingTools(query_payments={"success": False})
    handler = handlers["payments"].PaymentsHandler()
    assert asyncio.run(handler.execute(_ctx(intent_registry, "payments", tools=tools))) is None


# ---------- invoices ----------


def test_invoices_search_with_captured_query_calls_search_tool(intent_registry, handlers):
    tools = _RecordingTools(
        search_invoices={"success": True, "data": [{"id": 1, "amount": 100, "status": "paid"}]}
    )
    handler = handlers["invoices"].InvoicesHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, "invoices", tools=tools, message="search for acme"))
    )["data"]["response"]

    assert tools.calls == [("search_invoices", {"query": "acme"})]
    assert "Invoice Management Dashboard" in body


def test_invoices_search_keyword_without_query_defaults_to_list_with_limit_10(intent_registry, handlers):
    tools = _RecordingTools(
        list_invoices={"success": True, "data": [{"id": 1, "amount": 100, "status": "paid"}]}
    )
    handler = handlers["invoices"].InvoicesHandler()
    asyncio.run(
        handler.execute(_ctx(intent_registry, "invoices", tools=tools, message="search"))
    )

    assert tools.calls == [("list_invoices", {"limit": 10})]


def test_invoices_no_search_keyword_lists_with_limit_20(intent_registry, handlers):
    tools = _RecordingTools(
        list_invoices={"success": True, "data": [{"id": 1, "amount": 100, "status": "paid"}]}
    )
    handler = handlers["invoices"].InvoicesHandler()
    asyncio.run(
        handler.execute(_ctx(intent_registry, "invoices", tools=tools, message="show invoices"))
    )

    assert tools.calls == [("list_invoices", {"limit": 20})]


def test_invoices_tool_failure_returns_friendly_error_envelope(intent_registry, handlers):
    """Unique invoices behavior: tool failures get wrapped in an envelope, not None."""
    tools = _RecordingTools(list_invoices={"success": False, "error": "db locked"})
    handler = handlers["invoices"].InvoicesHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, "invoices", tools=tools, message="show invoices"))
    )

    assert result is not None
    assert result["data"]["response"] == "Error retrieving invoices: db locked"


def test_invoices_no_results_returns_friendly_message(intent_registry, handlers):
    tools = _RecordingTools(list_invoices={"success": True, "data": []})
    handler = handlers["invoices"].InvoicesHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, "invoices", tools=tools, message="show invoices"))
    )

    assert result["data"]["response"] == handlers["invoices"].NO_INVOICES_MESSAGE


def test_invoices_status_breakdown_counts(intent_registry, handlers):
    tools = _RecordingTools(
        list_invoices={
            "success": True,
            "data": [
                {"id": 1, "amount": 100, "status": "paid"},
                {"id": 2, "amount": 200, "status": "paid"},
                {"id": 3, "amount": 50, "status": "unpaid"},
            ],
        }
    )
    handler = handlers["invoices"].InvoicesHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, "invoices", tools=tools, message="show invoices"))
    )["data"]["response"]

    assert "Paid:** 2" in body
    assert "Unpaid:** 1" in body
    assert "$350.00" in body  # total


# ---------- expenses ----------


def test_expenses_search_with_captured_query_propagates_limit(intent_registry, handlers):
    tools = _RecordingTools(
        search_expenses={"success": True, "data": [{"id": 1, "amount": 12, "tax_amount": 1, "total_amount": 13}]}
    )
    handler = handlers["expenses"].ExpensesHandler()
    asyncio.run(
        handler.execute(
            _ctx(
                intent_registry,
                "expenses",
                tools=tools,
                message="find groceries",
                tool_options={"limit": 50},
            )
        )
    )

    assert tools.calls == [("search_expenses", {"query": "groceries", "limit": 50})]


def test_expenses_search_keyword_without_query_caps_at_10(intent_registry, handlers):
    tools = _RecordingTools(list_expenses={"success": True, "data": [{"id": 1, "amount": 10}]})
    handler = handlers["expenses"].ExpensesHandler()
    asyncio.run(
        handler.execute(
            _ctx(intent_registry, "expenses", tools=tools, message="search", tool_options={"limit": 25})
        )
    )
    # min(25, 10) -> 10
    assert tools.calls == [("list_expenses", {"limit": 10})]


def test_expenses_no_search_uses_requested_limit(intent_registry, handlers):
    tools = _RecordingTools(list_expenses={"success": True, "data": [{"id": 1, "amount": 10}]})
    handler = handlers["expenses"].ExpensesHandler()
    asyncio.run(
        handler.execute(
            _ctx(intent_registry, "expenses", tools=tools, message="show expenses", tool_options={"limit": 7})
        )
    )

    assert tools.calls == [("list_expenses", {"limit": 7})]


def test_expenses_default_limit_when_tool_options_missing(intent_registry, handlers):
    tools = _RecordingTools(list_expenses={"success": True, "data": [{"id": 1, "amount": 10}]})
    handler = handlers["expenses"].ExpensesHandler()
    asyncio.run(handler.execute(_ctx(intent_registry, "expenses", tools=tools, message="show expenses")))

    assert tools.calls == [("list_expenses", {"limit": 20})]


def test_expenses_renders_totals_including_tax(intent_registry, handlers):
    tools = _RecordingTools(
        list_expenses={
            "success": True,
            "data": [
                {"id": 1, "amount": 100, "tax_amount": 10, "total_amount": 110, "category": "food"},
                {"id": 2, "amount": 200, "tax_amount": 20, "total_amount": 220, "category": "travel"},
            ],
        }
    )
    handler = handlers["expenses"].ExpensesHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, "expenses", tools=tools, message="show expenses"))
    )["data"]["response"]

    assert "Total Amount (Pre-Tax):** $300.00" in body
    assert "Total Tax:** $30.00" in body
    assert "Total Amount (With Tax):** $330.00" in body


def test_expenses_tool_failure_returns_none(intent_registry, handlers):
    tools = _RecordingTools(list_expenses={"success": False})
    handler = handlers["expenses"].ExpensesHandler()
    assert (
        asyncio.run(handler.execute(_ctx(intent_registry, "expenses", tools=tools, message="show expenses")))
        is None
    )


def test_expenses_no_results_returns_friendly_message(intent_registry, handlers):
    tools = _RecordingTools(list_expenses={"success": True, "data": []})
    handler = handlers["expenses"].ExpensesHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, "expenses", tools=tools, message="show expenses"))
    )

    assert result["data"]["response"] == handlers["expenses"].NO_EXPENSES_MESSAGE
