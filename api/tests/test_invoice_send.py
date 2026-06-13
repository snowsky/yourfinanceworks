"""Tests for invoice send helpers (status transition + copy-to-sender BCC)."""

import pytest

from core.services.invoice_send import resolve_send_bcc, status_after_send


@pytest.mark.parametrize("current", ["draft", "approved"])
def test_status_advances_pre_send_to_sent(current):
    assert status_after_send(current) == "sent"


@pytest.mark.parametrize(
    "current",
    ["sent", "paid", "partially_paid", "overdue", "cancelled", "pending_approval", "rejected"],
)
def test_status_unchanged_for_non_pre_send(current):
    assert status_after_send(current) == current


def test_resolve_send_bcc_on_with_address():
    assert resolve_send_bcc(True, "owner@acme.com") == ["owner@acme.com"]


def test_resolve_send_bcc_off():
    assert resolve_send_bcc(False, "owner@acme.com") == []


@pytest.mark.parametrize("addr", [None, "", "   "])
def test_resolve_send_bcc_no_address(addr):
    assert resolve_send_bcc(True, addr) == []


# ---------------------------------------------------------------------------
# Task 2: BCC threading through EmailService._create_invoice_message
# ---------------------------------------------------------------------------

def _email_service(monkeypatch):
    from core.services.email_service import (
        EmailProvider,
        EmailProviderConfig,
        EmailService,
    )
    svc = EmailService(EmailProviderConfig(
        provider=EmailProvider.MAILGUN,
        from_email="owner@acme.com",
        from_name="Acme",
        mailgun_api_key="k",
        mailgun_domain="acme.com",
    ))
    # Trivial templates so rendering needs no template files.
    monkeypatch.setattr(svc, "_get_email_template", lambda t, fmt: "Invoice {{ invoice.number }}")
    return svc


def test_create_invoice_message_sets_bcc(monkeypatch):
    svc = _email_service(monkeypatch)
    msg = svc._create_invoice_message(
        invoice_data={"number": "INV-1"},
        client_data={"email": "client@x.com", "name": "Client"},
        company_data={"email": "owner@acme.com", "name": "Acme"},
        pdf_content=b"%PDF-1.4",
        template_type="invoice",
        portal_url=None,
        bcc=["owner@acme.com"],
    )
    assert msg.bcc == ["owner@acme.com"]


def test_create_invoice_message_bcc_defaults_empty(monkeypatch):
    svc = _email_service(monkeypatch)
    msg = svc._create_invoice_message(
        invoice_data={"number": "INV-1"},
        client_data={"email": "client@x.com", "name": "Client"},
        company_data={"email": "owner@acme.com", "name": "Acme"},
        pdf_content=b"%PDF-1.4",
        template_type="invoice",
        portal_url=None,
    )
    assert msg.bcc == []
