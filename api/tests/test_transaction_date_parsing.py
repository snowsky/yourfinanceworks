"""Unit tests for parse_transaction_date.

Regression coverage for the bug where bank-statement transaction ingestion silently
substituted *today's* date for any unparseable/missing date (corrupting financial records
with a plausible-but-wrong date). The helper now returns None instead of fabricating a
date; callers decide whether to skip (worker) or reject (API).

Pure-function tests: no DB / heavy imports.
"""

from datetime import date, datetime

import pytest

from core.utils.date_parsing import parse_transaction_date


@pytest.mark.unit
class TestParseTransactionDate:
    def test_none_returns_none(self):
        assert parse_transaction_date(None) is None

    def test_empty_or_whitespace_returns_none(self):
        assert parse_transaction_date("") is None
        assert parse_transaction_date("   ") is None

    def test_unparseable_returns_none_not_today(self):
        # The core regression: garbage must NOT become today's date.
        assert parse_transaction_date("N/A") is None
        assert parse_transaction_date("Jan 15") is None
        assert parse_transaction_date("not-a-date") is None

    def test_iso_date_string(self):
        assert parse_transaction_date("2024-01-15") == date(2024, 1, 15)

    def test_iso_datetime_string_truncated_to_date(self):
        assert parse_transaction_date("2024-01-15T08:30:00") == date(2024, 1, 15)

    def test_date_passthrough(self):
        assert parse_transaction_date(date(2024, 1, 15)) == date(2024, 1, 15)

    def test_datetime_passthrough_truncated(self):
        assert parse_transaction_date(datetime(2024, 1, 15, 8, 30)) == date(2024, 1, 15)
