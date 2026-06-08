"""Client-facing thank-you email when an invoice is paid in full.

Best-effort and self-contained so it can be triggered from the payment flow
(`sync_invoice_status`) without DI: it reads the tenant's email config + the
`invoice_settings.thank_you_email` toggle directly and never raises into the
caller. A failed or unconfigured send simply returns False.
"""

import logging

from sqlalchemy.orm import Session

from config import APP_NAME
from core.models.models_per_tenant import Client, Settings
from core.services.email_service import (
    EmailMessage,
    EmailProvider,
    EmailProviderConfig,
    EmailService,
)
from core.services.notification_templates import (
    THANK_YOU_HTML_TEMPLATE,
    THANK_YOU_TEXT_TEMPLATE,
)

logger = logging.getLogger(__name__)


def _build_email_service(db: Session):
    """Build an EmailService from the tenant's stored email_config, or None."""
    record = db.query(Settings).filter(Settings.key == "email_config").first()
    cfg = record.value if record else None
    if not cfg or not cfg.get("provider"):
        return None
    config = EmailProviderConfig(
        provider=EmailProvider(cfg["provider"]),
        from_email=cfg.get("from_email"),
        from_name=cfg.get("from_name"),
        aws_access_key_id=cfg.get("aws_access_key_id"),
        aws_secret_access_key=cfg.get("aws_secret_access_key"),
        aws_region=cfg.get("aws_region"),
        azure_connection_string=cfg.get("azure_connection_string"),
        mailgun_api_key=cfg.get("mailgun_api_key"),
        mailgun_domain=cfg.get("mailgun_domain"),
    )
    return EmailService(config)


def _thank_you_enabled(db: Session) -> bool:
    record = db.query(Settings).filter(Settings.key == "invoice_settings").first()
    value = record.value if record else None
    return bool(value and value.get("thank_you_email"))


def send_invoice_paid_thank_you(db: Session, invoice) -> bool:
    """Email the client a thank-you for a fully-paid invoice.

    Returns True only if an email was actually sent. Never raises — the caller
    is the payment path and must not fail because of a notification.
    """
    try:
        if not _thank_you_enabled(db):
            return False

        client = db.query(Client).filter(Client.id == invoice.client_id).first()
        to_email = getattr(client, "email", None) if client else None
        if not to_email:
            return False

        service = _build_email_service(db)
        if service is None:
            return False

        company_name = service.config.from_name or APP_NAME
        amount = f"{float(invoice.amount):,.2f}"
        context = {
            "client_name": client.name or "there",
            "invoice_number": invoice.number,
            "amount": amount,
            "currency": invoice.currency or "",
            "company_name": company_name,
        }

        message = EmailMessage(
            to_email=to_email,
            to_name=client.name or "",
            subject=f"Thank you for your payment — invoice {invoice.number}",
            html_body=THANK_YOU_HTML_TEMPLATE.render(**context),
            text_body=THANK_YOU_TEXT_TEMPLATE.render(**context),
            from_email=service.config.from_email,
            from_name=company_name,
        )
        return bool(service.send_email(message))
    except Exception as e:  # pragma: no cover - defensive; must never break payments
        logger.warning(
            f"Thank-you email failed for invoice {getattr(invoice, 'id', '?')}: {e}"
        )
        return False
