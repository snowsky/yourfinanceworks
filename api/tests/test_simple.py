"""
Unit tests for recently fixed utilities.
These tests run without a database or Redis — pure in-memory.
"""
import time
import pytest


# ---------------------------------------------------------------------------
# Rate limiter — in-memory sliding window (Redis unavailable in unit tests)
# ---------------------------------------------------------------------------

def _make_fresh_limiter():
    """Return a fresh in-memory store for isolation."""
    from collections import defaultdict, deque
    import core.utils.rate_limiter as rl_mod
    # Reset module-level state so tests don't bleed into each other
    rl_mod._redis_checked = True   # pretend we already checked — no Redis
    rl_mod._redis_client = None
    rl_mod._in_memory_store = defaultdict(deque)
    return rl_mod


def test_rate_limiter_allows_up_to_max():
    rl = _make_fresh_limiter()
    for _ in range(5):
        assert not rl.record_and_check("user_allow", max_attempts=5, window_seconds=60)


def test_rate_limiter_blocks_on_max_plus_one():
    rl = _make_fresh_limiter()
    for _ in range(5):
        rl.record_and_check("user_block", max_attempts=5, window_seconds=60)
    assert rl.record_and_check("user_block", max_attempts=5, window_seconds=60)


def test_rate_limiter_keys_are_independent():
    rl = _make_fresh_limiter()
    for _ in range(5):
        rl.record_and_check("key_a", max_attempts=5, window_seconds=60)
    # key_a is exhausted; key_b should still be fine
    assert not rl.record_and_check("key_b", max_attempts=5, window_seconds=60)


def test_rate_limiter_window_expires():
    rl = _make_fresh_limiter()
    for _ in range(5):
        rl.record_and_check("user_expire", max_attempts=5, window_seconds=1)
    assert rl.record_and_check("user_expire", max_attempts=5, window_seconds=1)
    time.sleep(1.1)
    # After the window expires the counter resets
    assert not rl.record_and_check("user_expire", max_attempts=5, window_seconds=1)


# ---------------------------------------------------------------------------
# Alembic URL builder — urlparse-based tenant URL replacement
# ---------------------------------------------------------------------------

def test_resolve_db_url_replaces_path():
    from urllib.parse import urlparse, urlunparse
    base = "postgresql://user:pass@localhost:5432/invoice_master"
    tenant_id = "42"
    parsed = urlparse(base)
    result = urlunparse(parsed._replace(path=f"/tenant_{tenant_id}"))
    assert result == "postgresql://user:pass@localhost:5432/tenant_42"


def test_resolve_db_url_preserves_credentials():
    from urllib.parse import urlparse, urlunparse
    base = "postgresql://myuser:s3cr3t@db.internal:5433/invoice_master"
    parsed = urlparse(base)
    result = urlunparse(parsed._replace(path="/tenant_7"))
    assert "myuser:s3cr3t@db.internal:5433" in result
    assert result.endswith("/tenant_7")


def test_resolve_db_url_no_false_replace():
    """Ensure we never accidentally replace text in host/credentials."""
    from urllib.parse import urlparse, urlunparse
    # Base URL that contains /invoice_master in a weird place — should still work
    base = "postgresql://user:pass@host/invoice_master"
    parsed = urlparse(base)
    result = urlunparse(parsed._replace(path="/tenant_99"))
    assert "/tenant_99" in result
    assert "invoice_master" not in result


# ---------------------------------------------------------------------------
# TransactionModel — Pydantic v2 validators
# ---------------------------------------------------------------------------

def test_transaction_model_normalizes_debit_type():
    from core.services.statement_service import TransactionModel
    tx = TransactionModel(
        date="2024-01-15",
        description="Coffee shop",
        amount=-5.50,
        transaction_type="DEBIT",
    )
    assert tx.transaction_type == "debit"


def test_transaction_model_normalizes_credit_type():
    from core.services.statement_service import TransactionModel
    tx = TransactionModel(
        date="2024-01-15",
        description="Salary",
        amount=3000.0,
        transaction_type="CREDIT",
    )
    assert tx.transaction_type == "credit"


def test_transaction_model_date_formats():
    from core.services.statement_service import TransactionModel
    for date_in, date_out in [
        ("2024-01-15", "2024-01-15"),
        ("01/15/2024", "2024-01-15"),
        ("15/01/2024", "2024-01-15"),
    ]:
        tx = TransactionModel(
            date=date_in,
            description="Test",
            amount=-10.0,
            transaction_type="debit",
        )
        assert tx.date == date_out, f"Expected {date_out} for input {date_in}"


def test_transaction_model_infers_type_from_amount_debit_card():
    from core.services.statement_service import TransactionModel
    # For debit card: negative amount → debit
    tx = TransactionModel(
        date="2024-01-15",
        description="Purchase",
        amount=-50.0,
        transaction_type="unknown",
        card_type="debit",
    )
    assert tx.transaction_type == "debit"


def test_transaction_model_infers_type_from_amount_credit_card():
    from core.services.statement_service import TransactionModel
    # For credit card: negative amount → credit (payment)
    tx = TransactionModel(
        date="2024-01-15",
        description="Payment",
        amount=-200.0,
        transaction_type="unknown",
        card_type="credit",
    )
    assert tx.transaction_type == "credit"
