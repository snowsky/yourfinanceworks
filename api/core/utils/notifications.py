from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from core.models.models_per_tenant import Settings, User
from core.models.database import get_tenant_context
from core.services.notification_service import NotificationService
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider
from config import APP_NAME
import logging

logger = logging.getLogger(__name__)

def get_notification_service(db: Session) -> Optional[NotificationService]:
    """Get configured notification service"""
    try:
        # Get email configuration using parameterized query
        email_settings = db.query(Settings).filter(
            Settings.key == "email_config"  # SQLAlchemy ORM - safe parameterized query
        ).first()
        
        if not email_settings or not email_settings.value:
            tenant_id = get_tenant_context()
            logger.debug(
                "Email service not configured for notifications (tenant_id=%s)",
                tenant_id
            )
            return None
        
        email_config_data = email_settings.value
        if not email_config_data.get('enabled', False):
            logger.info("Email service disabled for notifications")
            return None
        
        # Create email service
        config = EmailProviderConfig(
            provider=EmailProvider(email_config_data['provider']),
            aws_access_key_id=email_config_data.get('aws_access_key_id'),
            aws_secret_access_key=email_config_data.get('aws_secret_access_key'),
            aws_region=email_config_data.get('aws_region'),
            azure_connection_string=email_config_data.get('azure_connection_string'),
            mailgun_api_key=email_config_data.get('mailgun_api_key'),
            mailgun_domain=email_config_data.get('mailgun_domain')
        )
        email_service = EmailService(config)
        
        return NotificationService(db, email_service)
        
    except Exception as e:
        logger.error(f"Failed to create notification service: {str(e)}")
        return None

def send_notification(
    db: Session,
    event_type: str,
    user_id: int,
    resource_type: str,
    resource_id: str,
    resource_name: str,
    details: Dict[str, Any],
    company_name: str = APP_NAME
) -> bool:
    """Send notification for an operation"""
    try:
        notification_service = get_notification_service(db)
        if not notification_service:
            return True  # Not an error, just not configured
        
        return notification_service.send_operation_notification(
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
            company_name=company_name
        )
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
        return False

def notify_user_created(db: Session, user: User, created_by_user_id: int) -> bool:
    """Send notification when a user is created"""
    return send_notification(
        db=db,
        event_type="user_created",
        user_id=created_by_user_id,
        resource_type="user",
        resource_id=str(user.id),
        resource_name=f"{user.first_name} {user.last_name}".strip() or user.email,
        details={
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    )

def notify_user_updated(db: Session, user: User, updated_by_user_id: int) -> bool:
    """Send notification when a user is updated"""
    return send_notification(
        db=db,
        event_type="user_updated",
        user_id=updated_by_user_id,
        resource_type="user",
        resource_id=str(user.id),
        resource_name=f"{user.first_name} {user.last_name}".strip() or user.email,
        details={
            "email": user.email,
            "role": user.role,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
    )

def notify_client_created(db: Session, client, created_by_user_id: int) -> bool:
    """Send notification when a client is created"""
    return send_notification(
        db=db,
        event_type="client_created",
        user_id=created_by_user_id,
        resource_type="client",
        resource_id=str(client.id),
        resource_name=client.name,
        details={
            "email": client.email or "N/A",
            "phone": client.phone or "N/A",
            "created_at": client.created_at.isoformat() if client.created_at else None
        }
    )

def notify_client_updated(db: Session, client, updated_by_user_id: int) -> bool:
    """Send notification when a client is updated"""
    return send_notification(
        db=db,
        event_type="client_updated",
        user_id=updated_by_user_id,
        resource_type="client",
        resource_id=str(client.id),
        resource_name=client.name,
        details={
            "email": client.email or "N/A",
            "phone": client.phone or "N/A",
            "updated_at": client.updated_at.isoformat() if client.updated_at else None
        }
    )

def notify_invoice_created(db: Session, invoice, created_by_user_id: int) -> bool:
    """Send notification when an invoice is created"""
    return send_notification(
        db=db,
        event_type="invoice_created",
        user_id=created_by_user_id,
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=invoice.number,
        details={
            "amount": f"${invoice.amount:.2f}",
            "currency": invoice.currency,
            "status": invoice.status,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None
        }
    )

def notify_invoice_updated(db: Session, invoice, updated_by_user_id: int) -> bool:
    """Send notification when an invoice is updated"""
    return send_notification(
        db=db,
        event_type="invoice_updated",
        user_id=updated_by_user_id,
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=invoice.number,
        details={
            "amount": f"${invoice.amount:.2f}",
            "currency": invoice.currency,
            "status": invoice.status,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None
        }
    )

def notify_invoice_sent(db: Session, invoice, sent_by_user_id: int, client_email: str) -> bool:
    """Send notification when an invoice is sent"""
    return send_notification(
        db=db,
        event_type="invoice_sent",
        user_id=sent_by_user_id,
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=invoice.number,
        details={
            "amount": f"${invoice.amount:.2f}",
            "currency": invoice.currency,
            "client_email": client_email,
            "sent_at": invoice.updated_at.isoformat() if invoice.updated_at else None
        }
    )

def notify_payment_created(db: Session, payment, created_by_user_id: int) -> bool:
    """Send notification when a payment is created"""
    return send_notification(
        db=db,
        event_type="payment_created",
        user_id=created_by_user_id,
        resource_type="payment",
        resource_id=str(payment.id),
        resource_name=f"Payment #{payment.id}",
        details={
            "amount": f"${payment.amount:.2f}",
            "currency": payment.currency,
            "payment_method": payment.payment_method,
            "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
            "created_at": payment.created_at.isoformat() if payment.created_at else None
        }
    )
