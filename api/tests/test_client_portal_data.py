"""Unit tests for client-portal invoice summary math."""

from datetime import datetime
from types import SimpleNamespace

from core.routers.client_portal import _invoice_summary, _paid_amount


def _inv(amount, payments):
    return SimpleNamespace(
        id=1,
        number="INV-1",
        status="partially_paid",
        currency="USD",
        amount=amount,
        due_date=datetime(2026, 1, 1),
        created_at=datetime(2026, 1, 1),
        payments=[SimpleNamespace(amount=p) for p in payments],
    )


def test_paid_and_outstanding():
    s = _invoice_summary(_inv(100.0, [30.0, 20.0]))
    assert s["paid_amount"] == 50.0
    assert s["outstanding"] == 50.0


def test_no_payments():
    s = _invoice_summary(_inv(100.0, []))
    assert s["paid_amount"] == 0
    assert s["outstanding"] == 100.0


def test_fully_paid():
    s = _invoice_summary(_inv(100.0, [100.0]))
    assert s["outstanding"] == 0.0


def test_paid_amount_ignores_none():
    assert _paid_amount(_inv(100.0, [None, 25.0])) == 25.0
