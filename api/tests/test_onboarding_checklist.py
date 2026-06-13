"""Tests for the onboarding activation checklist."""

from datetime import datetime, timezone

from core.models.models_per_tenant import Client, Expense, Invoice, Settings
from core.services.onboarding_checklist import (
    OnboardingChecklistService,
    CHECKLIST_DISMISS_KEY,
)


def _service(db):
    return OnboardingChecklistService(db)


def _status(db):
    return _service(db).checklist_status()


def _done_keys(status):
    return {s["key"] for s in status["steps"] if s["done"]}


def test_empty_tenant_all_incomplete(db_session):
    s = _status(db_session)
    assert s["total"] == 5
    assert s["completed"] == 0
    assert s["all_complete"] is False
    assert s["dismissed"] is False
    assert _done_keys(s) == set()
    assert [step["key"] for step in s["steps"]] == [
        "add_client",
        "create_invoice",
        "record_expense",
        "customize_branding",
        "send_invoice",
    ]


def test_add_client_step(db_session):
    db_session.add(Client(name="Acme", email="a@x.com"))
    db_session.commit()
    assert _done_keys(_status(db_session)) == {"add_client"}


def test_draft_invoice_completes_create_not_send(db_session):
    db_session.add(Client(name="Acme", email="a@x.com"))
    db_session.commit()
    client = db_session.query(Client).first()
    db_session.add(
        Invoice(
            number="INV-1",
            amount=100.0,
            subtotal=100.0,
            currency="USD",
            status="draft",
            due_date=datetime.now(timezone.utc),
            client_id=client.id,
        )
    )
    db_session.commit()
    done = _done_keys(_status(db_session))
    assert "create_invoice" in done
    assert "send_invoice" not in done


def test_sent_invoice_completes_send(db_session):
    db_session.add(Client(name="Acme", email="a@x.com"))
    db_session.commit()
    client = db_session.query(Client).first()
    db_session.add(
        Invoice(
            number="INV-2",
            amount=100.0,
            subtotal=100.0,
            currency="USD",
            status="sent",
            due_date=datetime.now(timezone.utc),
            client_id=client.id,
        )
    )
    db_session.commit()
    assert "send_invoice" in _done_keys(_status(db_session))


def test_expense_and_branding_steps(db_session):
    db_session.add(
        Expense(
            category="Software",
            currency="USD",
            amount=49.0,
            expense_date=datetime.now(timezone.utc),
            status="recorded",
        )
    )
    db_session.add(
        Settings(key="invoice_branding", value={"primary_color": "#123456"}, category="appearance")
    )
    db_session.commit()
    done = _done_keys(_status(db_session))
    assert "record_expense" in done
    assert "customize_branding" in done


def test_empty_branding_value_does_not_complete(db_session):
    db_session.add(Settings(key="invoice_branding", value={}, category="appearance"))
    db_session.commit()
    assert "customize_branding" not in _done_keys(_status(db_session))


def test_all_complete(db_session):
    db_session.add(Client(name="Acme", email="a@x.com"))
    db_session.commit()
    client = db_session.query(Client).first()
    db_session.add(
        Invoice(
            number="INV-3",
            amount=100.0,
            subtotal=100.0,
            currency="USD",
            status="paid",
            due_date=datetime.now(timezone.utc),
            client_id=client.id,
        )
    )
    db_session.add(
        Expense(
            category="Travel",
            currency="USD",
            amount=10.0,
            expense_date=datetime.now(timezone.utc),
            status="recorded",
        )
    )
    db_session.add(
        Settings(key="invoice_branding", value={"primary_color": "#abcdef"}, category="appearance")
    )
    db_session.commit()
    s = _status(db_session)
    assert s["completed"] == 5
    assert s["all_complete"] is True
