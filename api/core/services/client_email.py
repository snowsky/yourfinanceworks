"""Shared helper to build a tenant's EmailService from stored config.

Several flows (thank-you emails, payment reminders, digests) need to construct
an EmailService from the tenant's `email_config` Settings row. This centralises
that so they stay consistent.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from core.models.models_per_tenant import Settings
from core.services.email_service import (
    EmailProvider,
    EmailProviderConfig,
    EmailService,
)

logger = logging.getLogger(__name__)


def build_tenant_email_service(db: Session) -> Optional[EmailService]:
    """Return an EmailService from the tenant's stored email_config, or None."""
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
