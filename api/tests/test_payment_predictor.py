"""Tests for payment-date forecasting (PaymentDatePredictor)."""

from datetime import datetime, timedelta, timezone

import pytest

from core.models.models_per_tenant import Client, Invoice, Payment
from core.services.payment_predictor import PaymentDatePredictor

NOW = datetime.now(timezone.utc)


def _client(db, name="C"):
    c = Client(name=name, email=f"{name}@ex.com", balance=0.0)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _invoice(db, client, *, status, created_days_ago, due_in_days=30, number):
    inv = Invoice(
        number=number,
        amount=100.0,
        currency="USD",
        created_at=NOW - timedelta(days=created_days_ago),
        due_date=NOW - timedelta(days=created_days_ago) + timedelta(days=due_in_days),
        status=status,
        client_id=client.id,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def _pay(db, inv, *, days_after_created):
    p = Payment(
        invoice_id=inv.id,
        amount=100.0,
        currency="USD",
        payment_date=inv.created_at + timedelta(days=days_after_created),
        payment_method="manual",
    )
    db.add(p)
    db.commit()
    return p


def _by_id(result, invoice_id):
    return next(i for i in result["items"] if i["invoice_id"] == invoice_id)


def test_uses_client_history(db_session):
    c = _client(db_session)
    # Three paid invoices, each paid ~10 days after issue.
    for n in range(3):
        paid = _invoice(db_session, c, status="paid", created_days_ago=60, number=f"P{n}")
        _pay(db_session, paid, days_after_created=10)
    # One outstanding invoice issued 2 days ago.
    out = _invoice(db_session, c, status="pending", created_days_ago=2, number="OUT-1")

    result = PaymentDatePredictor(db_session).predict_outstanding()
    item = _by_id(result, out.id)
    assert item["basis"] == "client"
    assert item["avg_days_to_pay"] == 10
    assert item["sample_size"] == 3
    # issued 2 days ago + ~10 days => ~8 days out
    assert item["expected_in_days"] == pytest.approx(8, abs=1)


def test_high_confidence_with_enough_samples(db_session):
    c = _client(db_session)
    for n in range(5):
        paid = _invoice(db_session, c, status="paid", created_days_ago=90, number=f"P{n}")
        _pay(db_session, paid, days_after_created=7)
    out = _invoice(db_session, c, status="overdue", created_days_ago=1, number="OUT-1")

    item = _by_id(PaymentDatePredictor(db_session).predict_outstanding(), out.id)
    assert item["confidence"] == "high"


def test_falls_back_to_global_average(db_session):
    # Client A builds global history; client B has none.
    a = _client(db_session, "A")
    for n in range(4):
        paid = _invoice(db_session, a, status="paid", created_days_ago=60, number=f"A{n}")
        _pay(db_session, paid, days_after_created=20)
    b = _client(db_session, "B")
    out = _invoice(db_session, b, status="pending", created_days_ago=1, number="OUT-B")

    item = _by_id(PaymentDatePredictor(db_session).predict_outstanding(), out.id)
    assert item["basis"] == "global"
    assert item["confidence"] == "low"
    assert item["avg_days_to_pay"] == 20


def test_falls_back_to_due_date_without_history(db_session):
    c = _client(db_session)
    out = _invoice(db_session, c, status="pending", created_days_ago=1, due_in_days=14, number="OUT-1")

    item = _by_id(PaymentDatePredictor(db_session).predict_outstanding(), out.id)
    assert item["basis"] == "due_date"
    assert item["confidence"] == "none"
    assert item["avg_days_to_pay"] is None
    assert item["predicted_date"] == item["due_date"]


def test_predicted_date_never_in_past(db_session):
    c = _client(db_session)
    for n in range(2):
        paid = _invoice(db_session, c, status="paid", created_days_ago=90, number=f"P{n}")
        _pay(db_session, paid, days_after_created=5)
    # Outstanding invoice issued 60 days ago: issue + 5 days is far in the past.
    out = _invoice(db_session, c, status="overdue", created_days_ago=60, number="OUT-OLD")

    item = _by_id(PaymentDatePredictor(db_session).predict_outstanding(), out.id)
    assert item["expected_in_days"] == 0  # clamped to today, not negative


def test_excludes_paid_and_draft(db_session):
    c = _client(db_session)
    _invoice(db_session, c, status="paid", created_days_ago=5, number="PAID")
    _invoice(db_session, c, status="draft", created_days_ago=5, number="DRAFT")
    _invoice(db_session, c, status="cancelled", created_days_ago=5, number="CANC")

    result = PaymentDatePredictor(db_session).predict_outstanding()
    assert result["count"] == 0
