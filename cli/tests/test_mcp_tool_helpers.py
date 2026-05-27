"""Tests for api/MCP/tools/_helpers.py — the ToolHelpersMixin.

Every MCP tool class inherits from ``ToolHelpersMixin`` for response shaping
(``_ok`` / ``_err`` / ``_list_response``), payload trimming (``_filter_none``),
envelope extraction (``_extract_items_from_response``), and a few
domain-specific helpers (date-filter parsing, chart prep, statement display
formatting). None of it had test coverage before this file existed; this
locks in the current behavior so future refactors are safe.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest


API_DIR = Path(__file__).resolve().parents[2] / "api"
HELPERS_PATH = API_DIR / "MCP" / "tools" / "_helpers.py"


@pytest.fixture(scope="module")
def helpers_module():
    spec = importlib.util.spec_from_file_location("mcp_tool_helpers", HELPERS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["mcp_tool_helpers"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mixin(helpers_module):
    class _MixinUser(helpers_module.ToolHelpersMixin):
        """Bare subclass — the mixin's methods are all self-contained."""

    return _MixinUser()


# ---------- _ok ----------


def test_ok_wraps_data_in_success_envelope(mixin):
    assert mixin._ok({"x": 1}) == {"success": True, "data": {"x": 1}}


def test_ok_includes_optional_message(mixin):
    assert mixin._ok([1, 2], message="loaded") == {
        "success": True,
        "data": [1, 2],
        "message": "loaded",
    }


def test_ok_accepts_falsy_data(mixin):
    # 0, False, "" are valid payloads; the envelope must carry them through.
    assert mixin._ok(0) == {"success": True, "data": 0}
    assert mixin._ok([]) == {"success": True, "data": []}


# ---------- _err ----------


def test_err_formats_action_and_exception(mixin):
    result = mixin._err("list portfolios", RuntimeError("connection refused"))
    assert result == {
        "success": False,
        "error": "Failed to list portfolios: connection refused",
    }


def test_err_handles_exceptions_with_no_message(mixin):
    result = mixin._err("fetch", ValueError())
    assert result["success"] is False
    assert result["error"].startswith("Failed to fetch")


# ---------- _list_response ----------


def test_list_response_includes_count(mixin):
    assert mixin._list_response([{"a": 1}, {"a": 2}]) == {
        "success": True,
        "data": [{"a": 1}, {"a": 2}],
        "count": 2,
    }


def test_list_response_omits_pagination_when_no_limit(mixin):
    result = mixin._list_response([])
    assert "pagination" not in result
    assert result["count"] == 0


def test_list_response_includes_pagination_when_limit_set(mixin):
    result = mixin._list_response([{"x": 1}], skip=20, limit=10)
    assert result["pagination"] == {"skip": 20, "limit": 10}


# ---------- _filter_none ----------


def test_filter_none_drops_only_none(mixin):
    assert mixin._filter_none(a=1, b=None, c="x", d=0, e=False, f=[]) == {
        "a": 1,
        "c": "x",
        "d": 0,
        "e": False,
        "f": [],
    }


def test_filter_none_returns_empty_when_all_none(mixin):
    assert mixin._filter_none(a=None, b=None) == {}


def test_filter_none_handles_empty_kwargs(mixin):
    assert mixin._filter_none() == {}


# ---------- _extract_items_from_response ----------


def test_extract_items_from_response_returns_list_as_is(mixin):
    assert mixin._extract_items_from_response([{"a": 1}, {"b": 2}]) == [{"a": 1}, {"b": 2}]


def test_extract_items_from_response_default_key_items(mixin):
    assert mixin._extract_items_from_response({"items": [1, 2]}) == [1, 2]


def test_extract_items_from_response_default_key_data(mixin):
    assert mixin._extract_items_from_response({"data": [3, 4]}) == [3, 4]


def test_extract_items_from_response_default_key_results(mixin):
    assert mixin._extract_items_from_response({"results": [5]}) == [5]


def test_extract_items_from_response_custom_key_takes_priority(mixin):
    assert mixin._extract_items_from_response(
        {"items": [1], "expenses": [2, 3]},
        keys=["expenses", "items"],
    ) == [2, 3]


def test_extract_items_from_response_custom_key_misses_then_falls_back_to_defaults(mixin):
    # Custom key 'expenses' not present; should fall through to default 'items'.
    assert mixin._extract_items_from_response(
        {"items": [1, 2]},
        keys=["expenses"],
    ) == [1, 2]


def test_extract_items_from_response_skips_non_list_values(mixin):
    # 'items' is a dict (not a list), so the extractor must skip it and try the next key.
    assert mixin._extract_items_from_response(
        {"items": {"oops": "scalar"}, "data": [9]},
    ) == [9]


def test_extract_items_from_response_returns_empty_when_no_match(mixin):
    assert mixin._extract_items_from_response({"unrelated": "value"}) == []


def test_extract_items_from_response_returns_empty_for_none(mixin):
    assert mixin._extract_items_from_response(None) == []


def test_extract_items_from_response_returns_empty_for_scalar(mixin):
    assert mixin._extract_items_from_response("a string") == []
    assert mixin._extract_items_from_response(42) == []


# ---------- _format_statement_for_display ----------


def test_format_statement_extracts_account_from_checking_filename(mixin):
    result = mixin._format_statement_for_display(
        {"id": 1, "original_filename": "chase-checking-may.pdf", "status": "processed"}
    )
    assert result["account_name"] == "Checking Account"
    assert result["status"] == "Processed"
    assert result["id"] == 1


@pytest.mark.parametrize(
    "filename,expected_account",
    [
        ("monthly_savings.pdf", "Savings Account"),
        ("credit_card_2026.pdf", "Credit Card"),
        ("business_account.pdf", "Business Account"),
    ],
)
def test_format_statement_recognizes_account_keywords(mixin, filename, expected_account):
    result = mixin._format_statement_for_display({"original_filename": filename})
    assert result["account_name"] == expected_account


def test_format_statement_falls_back_to_filename_titlecase(mixin):
    result = mixin._format_statement_for_display(
        {"original_filename": "wells_fargo_2026.pdf"}
    )
    assert result["account_name"] == "Wells Fargo 2026"


def test_format_statement_handles_missing_filename(mixin):
    result = mixin._format_statement_for_display({"id": 7, "status": "pending"})
    assert result["account_name"] == "Unknown"
    assert result["status"] == "Pending"


def test_format_statement_formats_period_from_created_at(mixin):
    result = mixin._format_statement_for_display(
        {"created_at": "2026-05-15T10:00:00Z", "original_filename": "x.pdf"}
    )
    assert result["period"] == "May 2026"


def test_format_statement_marks_zero_transactions_as_na(mixin):
    result = mixin._format_statement_for_display({"extracted_count": 0})
    assert result["transaction_count"] == "N/A"


def test_format_statement_preserves_metadata(mixin):
    result = mixin._format_statement_for_display(
        {
            "id": 99,
            "original_filename": "x.pdf",
            "labels": ["payroll", "ach"],
            "notes": "annotated",
            "review_status": "in_progress",
            "extracted_count": 42,
        }
    )
    assert result["labels"] == ["payroll", "ach"]
    assert result["notes"] == "annotated"
    assert result["review_status"] == "in_progress"
    assert result["transaction_count"] == 42


# ---------- _prepare_payment_chart_data ----------


def test_prepare_payment_chart_data_buckets_by_date(mixin):
    payments = [
        {"payment_date": "2026-05-01", "amount": 100, "payment_method": "card"},
        {"payment_date": "2026-05-01", "amount": 50, "payment_method": "ach"},
        {"payment_date": "2026-05-02", "amount": 200, "payment_method": "card"},
    ]
    result = mixin._prepare_payment_chart_data(payments)

    timeline = {row["date"]: row["amount"] for row in result["timeline"]}
    assert timeline == {"2026-05-01": 150.0, "2026-05-02": 200.0}


def test_prepare_payment_chart_data_buckets_by_method(mixin):
    payments = [
        {"payment_date": "2026-05-01", "amount": 100, "payment_method": "card"},
        {"payment_date": "2026-05-01", "amount": 50, "payment_method": "ach"},
        {"payment_date": "2026-05-02", "amount": 200, "payment_method": "card"},
    ]
    result = mixin._prepare_payment_chart_data(payments)

    by_method = {row["method"]: row["amount"] for row in result["by_method"]}
    assert by_method == {"card": 300.0, "ach": 50.0}


def test_prepare_payment_chart_data_computes_summary(mixin):
    payments = [
        {"payment_date": "2026-05-01", "amount": 100, "payment_method": "card"},
        {"payment_date": "2026-05-02", "amount": 200, "payment_method": "ach"},
    ]
    summary = mixin._prepare_payment_chart_data(payments)["summary"]
    assert summary["total_amount"] == 300.0
    assert summary["total_payments"] == 2
    assert summary["average_amount"] == 150.0
    assert summary["date_range"] == {"earliest": "2026-05-01", "latest": "2026-05-02"}


def test_prepare_payment_chart_data_handles_empty_list(mixin):
    result = mixin._prepare_payment_chart_data([])
    assert result["timeline"] == []
    assert result["by_method"] == []
    assert result["summary"]["total_amount"] == 0
    assert result["summary"]["total_payments"] == 0
    assert result["summary"]["average_amount"] == 0
    assert result["summary"]["date_range"] == {"earliest": None, "latest": None}


def test_prepare_payment_chart_data_skips_malformed_dates(mixin):
    payments = [
        {"payment_date": "not-a-date", "amount": 100, "payment_method": "card"},
        {"payment_date": "2026-05-01", "amount": 50, "payment_method": "card"},
    ]
    result = mixin._prepare_payment_chart_data(payments)
    # The malformed-date payment is excluded from timeline but still counts in by_method totals.
    timeline = {row["date"]: row["amount"] for row in result["timeline"]}
    assert timeline == {"2026-05-01": 50.0}
    by_method = {row["method"]: row["amount"] for row in result["by_method"]}
    assert by_method == {"card": 150.0}


# ---------- _parse_date_filter ----------


def _iso(when: datetime) -> str:
    return when.isoformat()


def test_parse_date_filter_returns_none_when_no_keyword(mixin):
    payments = [{"payment_date": _iso(datetime.now())}]
    assert mixin._parse_date_filter("show me payments", payments) is None


def test_parse_date_filter_yesterday(mixin):
    yesterday_iso = _iso(datetime.now() - timedelta(days=1))
    payments = [
        {"payment_date": yesterday_iso, "id": 1},
        {"payment_date": _iso(datetime.now() - timedelta(days=3)), "id": 2},
    ]
    filtered, applied, desc = mixin._parse_date_filter("yesterday's payments", payments)
    assert applied is True
    assert desc == "yesterday"
    assert [p["id"] for p in filtered] == [1]


def test_parse_date_filter_today(mixin):
    payments = [
        {"payment_date": _iso(datetime.now()), "id": 1},
        {"payment_date": _iso(datetime.now() - timedelta(days=2)), "id": 2},
    ]
    filtered, applied, desc = mixin._parse_date_filter("show today", payments)
    assert applied is True
    assert desc == "today"
    assert [p["id"] for p in filtered] == [1]


def test_parse_date_filter_this_week(mixin):
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())
    payments = [
        {"payment_date": _iso(start_of_week + timedelta(hours=1)), "id": 1},
        {"payment_date": _iso(start_of_week - timedelta(days=1)), "id": 2},
    ]
    filtered, applied, desc = mixin._parse_date_filter("this week", payments)
    assert applied is True
    assert desc == "this week"
    assert {p["id"] for p in filtered} == {1}


def test_parse_date_filter_past_week_uses_rolling_7_days(mixin):
    payments = [
        {"payment_date": _iso(datetime.now() - timedelta(days=3)), "id": 1},
        {"payment_date": _iso(datetime.now() - timedelta(days=10)), "id": 2},
    ]
    filtered, applied, desc = mixin._parse_date_filter("past week", payments)
    assert applied is True
    assert desc == "in the past 7 days"
    assert [p["id"] for p in filtered] == [1]


def test_parse_date_filter_past_month_uses_rolling_30_days(mixin):
    payments = [
        {"payment_date": _iso(datetime.now() - timedelta(days=15)), "id": 1},
        {"payment_date": _iso(datetime.now() - timedelta(days=45)), "id": 2},
    ]
    filtered, applied, desc = mixin._parse_date_filter("past month", payments)
    assert applied is True
    assert desc == "in the past 30 days"
    assert [p["id"] for p in filtered] == [1]
