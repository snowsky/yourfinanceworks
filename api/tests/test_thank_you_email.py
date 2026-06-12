"""Tests for the invoice paid -> client thank-you email helper.

The send is gated by the invoice_settings.thank_you_email toggle and the
tenant's email_config; the email-service build is the seam we stub so no real
provider is constructed.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.models.models_per_tenant import Client, Settings
from core.services import thank_you_email as mod
from core.services.thank_you_email import send_invoice_paid_thank_you


def _set(db, key, value):
    db.add(Settings(key=key, value=value))
    db.commit()


def _client(db, email="payer@example.com", name="Acme Co"):
    c = Client(name=name, email=email)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _invoice_for(client):
    return SimpleNamespace(
        id=1, client_id=client.id, number="INV-100", amount=250.0, currency="USD"
    )


@pytest.fixture
def fake_service(monkeypatch):
    svc = Mock()
    svc.send_email.return_value = True
    svc.config = SimpleNamespace(from_email="billing@acme.com", from_name="Acme")
    monkeypatch.setattr(mod, "_build_email_service", lambda db: svc)
    return svc


def test_no_send_when_toggle_off(db_session):
    _set(db_session, "invoice_settings", {"thank_you_email": False})
    client = _client(db_session)
    assert send_invoice_paid_thank_you(db_session, _invoice_for(client)) is False


def test_sends_by_default_when_setting_absent(db_session, fake_service):
    # No invoice_settings row at all -> thank-you is ON by default.
    client = _client(db_session)
    assert send_invoice_paid_thank_you(db_session, _invoice_for(client)) is True
    fake_service.send_email.assert_called_once()


def test_sends_by_default_when_key_missing(db_session, fake_service):
    # invoice_settings exists but predates the thank_you_email key -> default ON.
    _set(db_session, "invoice_settings", {"prefix": "INV-"})
    client = _client(db_session)
    assert send_invoice_paid_thank_you(db_session, _invoice_for(client)) is True
    fake_service.send_email.assert_called_once()


def test_no_send_when_client_has_no_email(db_session, fake_service):
    _set(db_session, "invoice_settings", {"thank_you_email": True})
    client = _client(db_session, email=None)
    assert send_invoice_paid_thank_you(db_session, _invoice_for(client)) is False
    fake_service.send_email.assert_not_called()


def test_no_send_when_email_not_configured(db_session, monkeypatch):
    # Toggle on + client email, but no email service available.
    _set(db_session, "invoice_settings", {"thank_you_email": True})
    monkeypatch.setattr(mod, "_build_email_service", lambda db: None)
    client = _client(db_session)
    assert send_invoice_paid_thank_you(db_session, _invoice_for(client)) is False


def test_sends_when_enabled_and_configured(db_session, fake_service):
    _set(db_session, "invoice_settings", {"thank_you_email": True})
    client = _client(db_session, email="payer@example.com", name="Acme Co")

    result = send_invoice_paid_thank_you(db_session, _invoice_for(client))

    assert result is True
    fake_service.send_email.assert_called_once()
    msg = fake_service.send_email.call_args.args[0]
    assert msg.to_email == "payer@example.com"
    assert "INV-100" in msg.subject
    assert "INV-100" in msg.html_body
    assert "250.00" in msg.text_body
    assert msg.from_email == "billing@acme.com"


def test_never_raises_on_send_error(db_session, monkeypatch):
    _set(db_session, "invoice_settings", {"thank_you_email": True})
    client = _client(db_session)
    boom = Mock()
    boom.send_email.side_effect = RuntimeError("smtp down")
    boom.config = SimpleNamespace(from_email="b@a.com", from_name="A")
    monkeypatch.setattr(mod, "_build_email_service", lambda db: boom)

    # Must swallow the error and report no send, never propagate.
    assert send_invoice_paid_thank_you(db_session, _invoice_for(client)) is False
