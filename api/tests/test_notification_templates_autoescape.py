"""Autoescape regression tests for notification email templates.

HTML email templates render user/tenant/client-controlled values (client names,
expense categories, settings values, branding footer text, ...). Without
autoescaping, a value like ``<script>...`` lands verbatim in the HTML body — a
stored-XSS vector in any mail client that renders HTML.

The paired plain-text templates must NOT escape: plain text is not HTML, and
escaping would corrupt it (turning ``&`` into ``&amp;``, ``<`` into ``&lt;``).

These tests pin both halves of that contract.
"""

import pytest

from core.services.notification_templates import (
    APPROVAL_DIGEST_HTML_TEMPLATE,
    APPROVAL_DIGEST_TEXT_TEMPLATE,
    APPROVAL_ESCALATION_HTML_TEMPLATE,
    APPROVAL_ESCALATION_TEXT_TEMPLATE,
    APPROVAL_REMINDER_HTML_TEMPLATE,
    APPROVAL_REMINDER_TEXT_TEMPLATE,
    DUNNING_HTML_TEMPLATE,
    DUNNING_TEXT_TEMPLATE,
    OPERATION_HTML_TEMPLATE,
    OPERATION_TEXT_TEMPLATE,
    THANK_YOU_HTML_TEMPLATE,
    THANK_YOU_TEXT_TEMPLATE,
)

XSS = "<script>alert(1)</script>"
ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"

HTML_TEMPLATES = [
    OPERATION_HTML_TEMPLATE,
    APPROVAL_REMINDER_HTML_TEMPLATE,
    APPROVAL_ESCALATION_HTML_TEMPLATE,
    APPROVAL_DIGEST_HTML_TEMPLATE,
    THANK_YOU_HTML_TEMPLATE,
    DUNNING_HTML_TEMPLATE,
]

TEXT_TEMPLATES = [
    OPERATION_TEXT_TEMPLATE,
    APPROVAL_REMINDER_TEXT_TEMPLATE,
    APPROVAL_ESCALATION_TEXT_TEMPLATE,
    APPROVAL_DIGEST_TEXT_TEMPLATE,
    THANK_YOU_TEXT_TEMPLATE,
    DUNNING_TEXT_TEMPLATE,
]


# --- Policy: the escaping behaviour is intrinsic to the template object -------

@pytest.mark.parametrize("template", HTML_TEMPLATES)
def test_html_templates_autoescape_enabled(template):
    assert template.environment.autoescape is True


@pytest.mark.parametrize("template", TEXT_TEMPLATES)
def test_text_templates_autoescape_disabled(template):
    assert template.environment.autoescape is False


# --- Behaviour: a real payload is escaped in HTML, raw in text ----------------

def _operation_ctx(**overrides):
    ctx = {
        "subject": "Notification",
        "event_color": "#3b82f6",
        "company_name": "Acme",
        "event_title": "New Invoice Created",
        "event_type": "invoice_created",
        "recipient_name": "Dana",
        "event_description": "A new invoice was created.",
        "resource_type": "invoice",
        "resource_name": "INV-100",
        "details": {"amount": "$10.00"},
        "timestamp": "2026-06-12 10:00",
    }
    ctx.update(overrides)
    return ctx


def test_operation_html_escapes_description_and_detail_values():
    html = OPERATION_HTML_TEMPLATE.render(
        **_operation_ctx(
            event_description=XSS,
            resource_name=XSS,
            details={"note": XSS},
        )
    )
    assert XSS not in html
    assert ESCAPED in html


def test_operation_text_does_not_escape():
    text = OPERATION_TEXT_TEMPLATE.render(**_operation_ctx(event_description=XSS))
    assert XSS in text
    assert ESCAPED not in text


def test_thank_you_html_escapes_client_name():
    html = THANK_YOU_HTML_TEMPLATE.render(
        client_name=XSS,
        invoice_number="INV-1",
        amount="10.00",
        currency="USD",
        company_name="Acme",
    )
    assert XSS not in html
    assert ESCAPED in html


def test_thank_you_text_does_not_escape_client_name():
    text = THANK_YOU_TEXT_TEMPLATE.render(
        client_name=XSS,
        invoice_number="INV-1",
        amount="10.00",
        currency="USD",
        company_name="Acme",
    )
    assert XSS in text


def test_approval_reminder_html_escapes_malicious_expense_category():
    # pending_list is built by joining "#<id> (<category>)" — category is
    # user-controlled, so a hostile category name must not reach the HTML raw.
    html = APPROVAL_REMINDER_HTML_TEMPLATE.render(
        company_name="Acme",
        recipient_name="Dana",
        pending_count=1,
        timestamp="2026-06-12 10:00",
        details={
            "total_pending": 1,
            "total_amount": "$10.00",
            "oldest_submission": "2026-06-01 09:00",
            "pending_list": f"#1 ({XSS})",
        },
    )
    assert XSS not in html
    assert ESCAPED in html
