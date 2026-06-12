"""Tests for invoice payment reminders (dunning).

The email-service build is stubbed (no real provider). Invoices are created
with due dates relative to "now" to drive cadence-step selection.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.models.models_per_tenant import Client, Invoice, Settings
from core.services import invoice_dunning as mod
from core.services.invoice_dunning import InvoiceDunningService, _status_line

CADENCE = [-7, -1, 3, 7, 14]


@pytest.fixture
def fake_email(monkeypatch):
    svc = Mock()
    svc.send_email.return_value = True
    svc.config = SimpleNamespace(from_email="billing@acme.com", from_name="Acme")
    monkeypatch.setattr(mod, "build_tenant_email_service", lambda db: svc)
    return svc


def _enable(db, cadence=CADENCE, enabled=True):
    db.add(Settings(key="invoice_settings", value={
        "payment_reminders_enabled": enabled,
        "reminder_cadence": cadence,
    }))
    db.commit()


def _client(db, email="payer@example.com"):
    c = Client(name="Payer Co", email=email, balance=0.0)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _invoice(db, client, *, days_overdue, status="overdue", number="INV-1"):
    inv = Invoice(
        number=number,
        amount=300.0,
        subtotal=300.0,
        currency="USD",
        due_date=datetime.now(timezone.utc) - timedelta(days=days_overdue),
        status=status,
        client_id=client.id,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def test_skipped_when_disabled(db_session, fake_email):
    _enable(db_session, enabled=False)
    _invoice(db_session, _client(db_session), days_overdue=10)
    assert InvoiceDunningService(db_session).process()["reason"] == "disabled"
    fake_email.send_email.assert_not_called()


def test_skipped_when_no_cadence(db_session, fake_email):
    _enable(db_session, cadence=[])
    _invoice(db_session, _client(db_session), days_overdue=10)
    assert InvoiceDunningService(db_session).process()["reason"] == "no_cadence"


def test_skipped_when_email_not_configured(db_session, monkeypatch):
    _enable(db_session)
    monkeypatch.setattr(mod, "build_tenant_email_service", lambda db: None)
    _invoice(db_session, _client(db_session), days_overdue=10)
    assert InvoiceDunningService(db_session).process()["reason"] == "email_not_configured"


def test_sends_due_step_and_is_idempotent(db_session, fake_email):
    _enable(db_session)
    inv = _invoice(db_session, _client(db_session), days_overdue=8)  # reaches step 7

    first = InvoiceDunningService(db_session).process()
    assert first["sent"] == 1
    db_session.refresh(inv)
    assert inv.reminder_last_offset == 7
    assert inv.reminder_last_sent_at is not None

    # Same day, nothing more advanced -> no resend.
    second = InvoiceDunningService(db_session).process()
    assert second["sent"] == 0
    fake_email.send_email.assert_called_once()


def test_collapses_missed_steps_to_latest(db_session, fake_email):
    _enable(db_session)
    inv = _invoice(db_session, _client(db_session), days_overdue=30)  # past all steps

    result = InvoiceDunningService(db_session).process()
    assert result["sent"] == 1
    db_session.refresh(inv)
    assert inv.reminder_last_offset == 14  # only the most advanced step
    fake_email.send_email.assert_called_once()


def test_advances_to_next_step(db_session, fake_email):
    _enable(db_session)
    inv = _invoice(db_session, _client(db_session), days_overdue=8)
    inv.reminder_last_offset = 3  # already sent the 3-day step
    db_session.commit()

    result = InvoiceDunningService(db_session).process()
    assert result["sent"] == 1
    db_session.refresh(inv)
    assert inv.reminder_last_offset == 7


def test_before_due_reminder(db_session, fake_email):
    _enable(db_session)
    # due in 2 days -> days_since_due = -2 -> reaches step -7 only
    inv = _invoice(db_session, _client(db_session), days_overdue=-2)
    result = InvoiceDunningService(db_session).process()
    assert result["sent"] == 1
    db_session.refresh(inv)
    assert inv.reminder_last_offset == -7


def test_not_yet_due_no_reminder(db_session, fake_email):
    _enable(db_session)
    # due in 30 days -> days_since_due = -30 -> no cadence step reached
    _invoice(db_session, _client(db_session), days_overdue=-30)
    assert InvoiceDunningService(db_session).process()["sent"] == 0
    fake_email.send_email.assert_not_called()


@pytest.mark.parametrize("status", ["paid", "draft", "cancelled"])
def test_excludes_non_dunnable_statuses(db_session, fake_email, status):
    _enable(db_session)
    _invoice(db_session, _client(db_session), days_overdue=10, status=status)
    assert InvoiceDunningService(db_session).process()["sent"] == 0


def test_no_send_without_client_email(db_session, fake_email):
    _enable(db_session)
    _invoice(db_session, _client(db_session, email=None), days_overdue=10)
    assert InvoiceDunningService(db_session).process()["sent"] == 0


def test_status_line_phrasing():
    assert _status_line(-3) == "due in 3 days"
    assert _status_line(-1) == "due in 1 day"
    assert _status_line(0) == "due today"
    assert _status_line(1) == "1 day overdue"
    assert _status_line(5) == "5 days overdue"


def _sent_message(fake_email):
    return fake_email.send_email.call_args.args[0]


def test_subject_escalates_upcoming(db_session, fake_email):
    _enable(db_session)
    _invoice(db_session, _client(db_session), days_overdue=-2)  # before due
    assert InvoiceDunningService(db_session).process()["sent"] == 1
    msg = _sent_message(fake_email)
    assert msg.subject.startswith("Upcoming payment")
    assert "INV-1" in msg.subject


def test_subject_escalates_reminder(db_session, fake_email):
    _enable(db_session)
    _invoice(db_session, _client(db_session), days_overdue=4)  # 0 <= days < 7
    assert InvoiceDunningService(db_session).process()["sent"] == 1
    assert _sent_message(fake_email).subject.startswith("Payment reminder")


def test_subject_escalates_overdue(db_session, fake_email):
    _enable(db_session)
    _invoice(db_session, _client(db_session), days_overdue=30)  # >= 7 days late
    assert InvoiceDunningService(db_session).process()["sent"] == 1
    msg = _sent_message(fake_email)
    assert msg.subject.startswith("Overdue notice")
    assert "Overdue" in msg.html_body  # escalated badge label


def test_tone_tier_boundaries():
    from core.services.invoice_dunning import _tone

    assert _tone(-1)["subject_prefix"] == "Upcoming payment"
    assert _tone(0)["subject_prefix"] == "Payment reminder"
    assert _tone(6)["subject_prefix"] == "Payment reminder"
    assert _tone(7)["subject_prefix"] == "Overdue notice"
    # All tiers expose the full key set the template/context relies on.
    for days in (-1, 0, 7):
        assert set(_tone(days)) == {
            "subject_prefix", "badge_label", "intro_line", "badge_bg", "urgency_color",
        }


def test_pay_link_included_when_available(db_session, fake_email, monkeypatch):
    _enable(db_session)
    monkeypatch.setattr(
        mod, "_build_portal_pay_url", lambda db: "https://app.example/portal/abc123"
    )
    _invoice(db_session, _client(db_session), days_overdue=10)
    assert InvoiceDunningService(db_session).process()["sent"] == 1
    msg = _sent_message(fake_email)
    assert "https://app.example/portal/abc123" in msg.html_body
    assert "https://app.example/portal/abc123" in msg.text_body


def test_no_pay_link_when_unavailable(db_session, fake_email, monkeypatch):
    _enable(db_session)
    monkeypatch.setattr(mod, "_build_portal_pay_url", lambda db: None)
    _invoice(db_session, _client(db_session), days_overdue=10)
    assert InvoiceDunningService(db_session).process()["sent"] == 1
    assert "href" not in _sent_message(fake_email).html_body


def test_portal_pay_url_none_when_feature_disabled(db_session, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://app.example")
    monkeypatch.setattr(mod, "feature_enabled", lambda fid, db: False)
    assert mod._build_portal_pay_url(db_session) is None


def test_portal_pay_url_none_without_frontend_url(db_session, monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    assert mod._build_portal_pay_url(db_session) is None
