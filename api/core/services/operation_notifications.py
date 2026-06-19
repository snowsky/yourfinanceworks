"""Shared 'best-effort operation notification' used by route handlers and the
in-process AI client, so the notification orchestration lives in exactly one place."""

import logging

from sqlalchemy.orm import Session

from core.services.notification_service import NotificationService
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider

logger = logging.getLogger(__name__)


def _tenant_company_name(tenant_id: int) -> str:
    from config import APP_NAME
    from core.models.database import get_master_db
    from core.models.models import Tenant

    master_db = next(get_master_db())
    try:
        tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
        return tenant.name if tenant else APP_NAME
    finally:
        master_db.close()


def maybe_send_operation_notification(
    db: Session,
    *,
    event_type: str,
    user_id: int,
    tenant_id: int,
    resource_type: str,
    resource_id: str,
    resource_name: str,
    details: dict,
) -> None:
    """Send an operation notification if the tenant has email enabled. Never raises."""
    try:
        from core.models.models_per_tenant import Settings

        email_settings = db.query(Settings).filter(Settings.key == "email_config").first()
        if not (email_settings and email_settings.value and email_settings.value.get("enabled")):
            return

        ecd = email_settings.value
        config = EmailProviderConfig(
            provider=EmailProvider(ecd["provider"]),
            from_email=ecd.get("from_email"),
            from_name=ecd.get("from_name"),
            aws_access_key_id=ecd.get("aws_access_key_id"),
            aws_secret_access_key=ecd.get("aws_secret_access_key"),
            aws_region=ecd.get("aws_region"),
            azure_connection_string=ecd.get("azure_connection_string"),
            mailgun_api_key=ecd.get("mailgun_api_key"),
            mailgun_domain=ecd.get("mailgun_domain"),
        )
        notification_service = NotificationService(db, EmailService(config))
        notification_service.send_operation_notification(
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
            company_name=_tenant_company_name(tenant_id),
        )
    except Exception as e:  # noqa: BLE001 - notifications must never break the operation
        logger.warning("Failed to send %s notification: %s", event_type, e)
