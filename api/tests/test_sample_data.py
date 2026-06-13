"""Tests for onboarding sample-data seeding."""

from datetime import datetime, timezone

import pytest

from core.models.models_per_tenant import Client, Expense, Invoice, Payment
from core.services.sample_data import SampleDataError, SampleDataService


def _service(db):
    return SampleDataService(db)


def _real_client(db):
    c = Client(name="Real Co", email="real@example.com", is_sample=False)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_status_empty_tenant(db_session):
    s = _service(db_session).sample_data_status()
    assert s == {"has_sample_data": False, "has_any_data": False}


def test_seed_creates_status_diverse_set(db_session):
    counts = _service(db_session).seed(user_id=None)
    assert counts["clients"] == 3
    assert counts["invoices"] == 6
    assert counts["expenses"] == 4
    assert counts["payments"] == 2

    invoices = db_session.query(Invoice).all()
    assert all(inv.is_sample for inv in invoices)
    assert all(inv.subtotal is not None for inv in invoices)
    statuses = {inv.status for inv in invoices}
    assert {"draft", "sent", "paid", "partially_paid", "overdue"} <= statuses
    assert all(c.is_sample for c in db_session.query(Client).all())
    assert all(e.is_sample for e in db_session.query(Expense).all())


def test_status_after_seed(db_session):
    _service(db_session).seed(user_id=None)
    s = _service(db_session).sample_data_status()
    assert s == {"has_sample_data": True, "has_any_data": True}


def test_seed_refused_when_real_data_exists(db_session):
    _real_client(db_session)
    with pytest.raises(SampleDataError):
        _service(db_session).seed(user_id=None)


def test_seed_refused_when_sample_already_exists(db_session):
    _service(db_session).seed(user_id=None)
    with pytest.raises(SampleDataError):
        _service(db_session).seed(user_id=None)


def test_clear_removes_only_sample(db_session):
    real = _real_client(db_session)
    real_inv = Invoice(
        number="REAL-1", amount=10.0, subtotal=10.0, currency="USD",
        due_date=datetime.now(timezone.utc), status="draft",
        client_id=real.id, is_sample=False,
    )
    db_session.add(real_inv)
    db_session.commit()

    sample_client = Client(name="Sample Co", email="s@example.com", is_sample=True)
    db_session.add(sample_client)
    db_session.commit()
    db_session.refresh(sample_client)
    sample_inv = Invoice(
        number="SAMPLE-9", amount=5.0, subtotal=5.0, currency="USD",
        due_date=datetime.now(timezone.utc), status="sent",
        client_id=sample_client.id, is_sample=True,
    )
    db_session.add(sample_inv)
    db_session.commit()
    db_session.refresh(sample_inv)
    db_session.add(Payment(invoice_id=sample_inv.id, amount=5.0, currency="USD",
                           payment_date=datetime.now(timezone.utc), payment_method="card"))
    db_session.commit()

    removed = _service(db_session).clear()
    assert removed["invoices"] == 1
    assert removed["clients"] == 1
    assert removed["payments"] == 1

    assert db_session.query(Client).filter(Client.id == real.id).count() == 1
    assert db_session.query(Invoice).filter(Invoice.id == real_inv.id).count() == 1
    assert db_session.query(Invoice).filter(Invoice.is_sample == True).count() == 0  # noqa: E712
    assert db_session.query(Client).filter(Client.is_sample == True).count() == 0  # noqa: E712
