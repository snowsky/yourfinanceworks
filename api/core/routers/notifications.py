from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
import logging

from core.models.database import get_db, get_master_db
from core.models import EmailNotificationSettings, User
from core.models.models import MasterUser
from core.schemas.email_notifications import (
    EmailNotificationSettings as EmailNotificationSettingsSchema,
    EmailNotificationSettingsCreate,
    EmailNotificationSettingsUpdate
)
from core.routers.auth import get_current_user
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.audit import log_audit_event
from core.utils.rbac import require_admin_or_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class ExpenseDigestPreferencePayload(BaseModel):
    enabled: bool
    frequency: str = "weekly"


class ExpenseDigestPreferenceResponse(ExpenseDigestPreferencePayload):
    next_run_at: Optional[str] = None
    last_sent_at: Optional[str] = None


def _get_or_create_notification_settings(db: Session, user_id: int) -> EmailNotificationSettings:
    from core.services.expense_digest_service import ensure_expense_digest_preference_columns

    ensure_expense_digest_preference_columns(db)
    settings = db.query(EmailNotificationSettings).filter(
        EmailNotificationSettings.user_id == user_id
    ).first()
    if settings:
        return settings

    settings = EmailNotificationSettings(user_id=user_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _serialize_expense_digest_preferences(settings: EmailNotificationSettings) -> dict:
    return {
        "enabled": bool(settings.expense_digest_enabled),
        "frequency": settings.expense_digest_frequency
        if settings.expense_digest_frequency in {"daily", "weekly"}
        else "weekly",
        "next_run_at": settings.expense_digest_next_run_at.isoformat()
        if settings.expense_digest_next_run_at
        else None,
        "last_sent_at": settings.expense_digest_last_sent_at.isoformat()
        if settings.expense_digest_last_sent_at
        else None,
    }


def _expense_digest_user_overrides_allowed(db: Session) -> bool:
    from core.models.models_per_tenant import Settings
    from core.services.expense_digest_service import DEFAULT_EXPENSE_SETTINGS

    record = db.query(Settings).filter(Settings.key == "expense_settings").first()
    raw = record.value if record and isinstance(record.value, dict) else {}
    digest_cfg = {
        **DEFAULT_EXPENSE_SETTINGS["digest"],
        **raw.get("digest", {}),
    }
    return bool(digest_cfg.get("allow_user_overrides", True))


def _build_email_service(db: Session):
    """Create tenant email service from stored email_config settings."""
    from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider
    from core.models.models_per_tenant import Settings

    email_settings = db.query(Settings).filter(Settings.key == "email_config").first()
    if not email_settings or not email_settings.value:
        return None

    email_config_data = email_settings.value
    if not email_config_data.get("enabled", False):
        return None

    config = EmailProviderConfig(
        provider=EmailProvider(email_config_data["provider"]),
        from_email=email_config_data.get("from_email"),
        from_name=email_config_data.get("from_name"),
        aws_access_key_id=email_config_data.get("aws_access_key_id"),
        aws_secret_access_key=email_config_data.get("aws_secret_access_key"),
        aws_region=email_config_data.get("aws_region"),
        azure_connection_string=email_config_data.get("azure_connection_string"),
        mailgun_api_key=email_config_data.get("mailgun_api_key"),
        mailgun_domain=email_config_data.get("mailgun_domain")
    )
    return EmailService(config)

@router.get("/settings", response_model=EmailNotificationSettingsSchema)
async def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get current user's notification settings"""
    try:
        # Look for existing tenant user by ID (not email to avoid duplicates)
        tenant_user = db.query(User).filter(User.id == current_user.id).first()
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in tenant database"
            )
        
        settings = db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == tenant_user.id
        ).first()
        
        if not settings:
            # Create default settings
            settings = EmailNotificationSettings(user_id=tenant_user.id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        
        return settings
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting notification settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification settings"
        )
    
@router.put("/settings", response_model=EmailNotificationSettingsSchema)
async def update_notification_settings(
    settings_update: EmailNotificationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update current user's notification settings"""
    try:
        settings = db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == current_user.id
        ).first()
        
        if not settings:
            # Create new settings
            settings = EmailNotificationSettings(
                user_id=current_user.id,
                **settings_update.model_dump()
            )
            db.add(settings)
        else:
            # Update existing settings
            for field, value in settings_update.model_dump().items():
                setattr(settings, field, value)
        
        db.commit()
        db.refresh(settings)
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="notification_settings",
            resource_id=str(settings.id),
            resource_name="Email Notification Settings",
            details=settings_update.model_dump(),
            status="success"
        )
        
        return settings
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating notification settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification settings"
        )

@router.post("/test")
async def test_notification(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Send a test notification to verify settings"""
    try:
        from core.services.notification_service import NotificationService
        from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider
        from core.models.models_per_tenant import Settings
        
        # Get email configuration
        email_settings = db.query(Settings).filter(
            Settings.key == "email_config"
        ).first()
        
        if not email_settings or not email_settings.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email service not configured"
            )
        
        # Create email service
        email_config_data = email_settings.value
        config = EmailProviderConfig(
            provider=EmailProvider(email_config_data['provider']),
            from_email=email_config_data.get('from_email'),
            from_name=email_config_data.get('from_name'),
            aws_access_key_id=email_config_data.get('aws_access_key_id'),
            aws_secret_access_key=email_config_data.get('aws_secret_access_key'),
            aws_region=email_config_data.get('aws_region'),
            azure_connection_string=email_config_data.get('azure_connection_string'),
            mailgun_api_key=email_config_data.get('mailgun_api_key'),
            mailgun_domain=email_config_data.get('mailgun_domain')
        )
        email_service = EmailService(config)

        # Create notification service
        notification_service = NotificationService(db, email_service)

        # Look for existing tenant user by ID
        tenant_user = db.query(User).filter(User.id == current_user.id).first()
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in tenant database"
            )

        # Send test notification
        success = notification_service.send_operation_notification(
            event_type="settings_updated",
            user_id=tenant_user.id,
            resource_type="notification",
            resource_id="test",
            resource_name="Test Notification",
            details={
                "message": "This is a test notification to verify your email notification settings.",
                "test_time": "now"
            }
        )

        if success:
            return {"message": "Test notification sent successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send test notification"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test notification"
        )

@router.get("/approval-preferences", response_model=dict)
async def get_approval_notification_preferences(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get current user's approval notification preferences"""
    try:
        # Look for existing tenant user by ID
        tenant_user = db.query(User).filter(User.id == current_user.id).first()
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in tenant database"
            )

        settings = db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == tenant_user.id
        ).first()

        if not settings:
            # Create default settings
            settings = EmailNotificationSettings(user_id=tenant_user.id)
            db.add(settings)
            db.commit()
            db.refresh(settings)

        # Return approval-specific preferences
        return {
            "approval_notification_frequency": settings.approval_notification_frequency,
            "approval_reminder_frequency": settings.approval_reminder_frequency,
            "approval_notification_channels": settings.approval_notification_channels,
            "approval_events": {
                "expense_submitted_for_approval": settings.expense_submitted_for_approval,
                "expense_approved": settings.expense_approved,
                "expense_rejected": settings.expense_rejected,
                "expense_level_approved": settings.expense_level_approved,
                "expense_fully_approved": settings.expense_fully_approved,
                "expense_auto_approved": settings.expense_auto_approved,
                "approval_reminder": settings.approval_reminder,
                "approval_escalation": settings.approval_escalation
            }
        }
    except Exception as e:
        logger.error(f"Error getting approval notification preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get approval notification preferences"
        )

@router.put("/approval-preferences")
async def update_approval_notification_preferences(
    preferences: dict,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update current user's approval notification preferences"""
    try:
        # Look for existing tenant user by ID
        tenant_user = db.query(User).filter(User.id == current_user.id).first()
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in tenant database"
            )
        
        settings = db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == tenant_user.id
        ).first()
        
        if not settings:
            settings = EmailNotificationSettings(user_id=tenant_user.id)
            db.add(settings)
        
        # Update approval frequency preferences
        if "approval_notification_frequency" in preferences:
            frequency = preferences["approval_notification_frequency"]
            if frequency not in ["immediate", "daily_digest"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid approval_notification_frequency. Must be 'immediate' or 'daily_digest'"
                )
            settings.approval_notification_frequency = frequency
        
        if "approval_reminder_frequency" in preferences:
            frequency = preferences["approval_reminder_frequency"]
            if frequency not in ["daily", "weekly", "disabled"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid approval_reminder_frequency. Must be 'daily', 'weekly', or 'disabled'"
                )
            settings.approval_reminder_frequency = frequency
        
        # Update approval channels
        if "approval_notification_channels" in preferences:
            channels = preferences["approval_notification_channels"]
            if not isinstance(channels, list) or not channels:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="approval_notification_channels must be a non-empty list"
                )
            valid_channels = ["email", "in_app"]
            for channel in channels:
                if channel not in valid_channels:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid channel: {channel}. Must be one of {valid_channels}"
                    )
            settings.approval_notification_channels = channels
        
        # Update approval event preferences
        if "approval_events" in preferences:
            events = preferences["approval_events"]
            approval_event_fields = [
                "expense_submitted_for_approval", "expense_approved", "expense_rejected",
                "expense_level_approved", "expense_fully_approved", "expense_auto_approved",
                "approval_reminder", "approval_escalation"
            ]
            for field in approval_event_fields:
                if field in events:
                    setattr(settings, field, bool(events[field]))
        
        db.commit()
        db.refresh(settings)
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=tenant_user.id,
            user_email=tenant_user.email,
            action="UPDATE",
            resource_type="approval_notification_preferences",
            resource_id=str(settings.id),
            resource_name="Approval Notification Preferences",
            details=preferences,
            status="success"
        )
        
        return {"message": "Approval notification preferences updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating approval notification preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update approval notification preferences"
        )

@router.post("/send-digest")
async def send_approval_digest(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Send approval digest notification (for testing purposes)"""
    try:
        from core.services.notification_service import NotificationService
        from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider
        from core.models.models_per_tenant import Settings
        
        # Get email configuration
        email_settings = db.query(Settings).filter(
            Settings.key == "email_config"
        ).first()
        
        if not email_settings or not email_settings.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email service not configured"
            )
        
        # Create email service
        email_config_data = email_settings.value
        config = EmailProviderConfig(
            provider=EmailProvider(email_config_data['provider']),
            from_email=email_config_data.get('from_email'),
            from_name=email_config_data.get('from_name'),
            aws_access_key_id=email_config_data.get('aws_access_key_id'),
            aws_secret_access_key=email_config_data.get('aws_secret_access_key'),
            aws_region=email_config_data.get('aws_region'),
            azure_connection_string=email_config_data.get('azure_connection_string'),
            mailgun_api_key=email_config_data.get('mailgun_api_key'),
            mailgun_domain=email_config_data.get('mailgun_domain')
        )
        email_service = EmailService(config)

        # Create notification service
        notification_service = NotificationService(db, email_service)

        # Create sample digest data
        digest_data = {
            "total_events": 5,
            "pending_count": 2,
            "approved_count": 2,
            "rejected_count": 1,
            "pending_approvals": [
                {
                    "expense_id": "123",
                    "category": "Travel",
                    "amount": "250.00",
                    "submitted_at": "2025-01-04 10:00"
                },
                {
                    "expense_id": "124",
                    "category": "Meals",
                    "amount": "45.00",
                    "submitted_at": "2025-01-04 14:30"
                }
            ],
            "approved_expenses": [
                {
                    "expense_id": "121",
                    "category": "Office Supplies",
                    "amount": "75.00",
                    "approved_at": "2025-01-04 09:15"
                },
                {
                    "expense_id": "122",
                    "category": "Software",
                    "amount": "99.00",
                    "approved_at": "2025-01-04 11:45"
                }
            ],
            "rejected_expenses": [
                {
                    "expense_id": "120",
                    "category": "Entertainment",
                    "amount": "150.00",
                    "rejected_at": "2025-01-04 08:30",
                    "rejection_reason": "Exceeds policy limit for entertainment expenses"
                }
            ]
        }

        # Look for existing tenant user by ID
        tenant_user = db.query(User).filter(User.id == current_user.id).first()
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in tenant database"
            )

        # Send digest
        success = notification_service.send_approval_daily_digest(
            user_id=tenant_user.id,
            digest_data=digest_data
        )

        if success:
            return {"message": "Approval digest sent successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send approval digest"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending approval digest: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send approval digest"
        )


@router.post("/expense-digest/send")
async def send_expense_digest(
    force: bool = True,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Send expense digest email using tenant Expense settings (manual trigger/test)."""
    try:
        require_admin_or_superuser(current_user, "send expense digest")

        from core.services.expense_digest_service import ExpenseDigestService

        email_service = _build_email_service(db)
        if not email_service:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email service not configured"
            )

        digest_service = ExpenseDigestService(db, email_service)
        result = digest_service.process_due_digest(
            triggering_user_id=current_user.id,
            force=force
        )

        if result.get("status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send expense digest: {result.get('errors', ['unknown_error'])}"
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending expense digest: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send expense digest"
        )


@router.get("/expense-digest/preferences", response_model=ExpenseDigestPreferenceResponse)
async def get_expense_digest_preferences(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get the current user's personal expense digest preference."""
    try:
        tenant_user = db.query(User).filter(User.id == current_user.id).first()
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in tenant database",
            )

        settings = _get_or_create_notification_settings(db, tenant_user.id)
        return _serialize_expense_digest_preferences(settings)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expense digest preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get expense digest preferences",
        )


@router.put("/expense-digest/preferences", response_model=ExpenseDigestPreferenceResponse)
async def update_expense_digest_preferences(
    payload: ExpenseDigestPreferencePayload,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Update the current user's personal expense digest preference."""
    try:
        tenant_user = db.query(User).filter(User.id == current_user.id).first()
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in tenant database",
            )

        settings = _get_or_create_notification_settings(db, tenant_user.id)
        if not _expense_digest_user_overrides_allowed(db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Personal expense digest overrides are disabled by the organization.",
            )
        if payload.frequency not in {"daily", "weekly"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="frequency must be one of: daily, weekly",
            )
        previous_frequency = settings.expense_digest_frequency
        settings.expense_digest_enabled = payload.enabled
        settings.expense_digest_frequency = payload.frequency
        if previous_frequency != payload.frequency:
            settings.expense_digest_next_run_at = None

        db.commit()
        db.refresh(settings)
        return _serialize_expense_digest_preferences(settings)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating expense digest preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update expense digest preferences",
        )

@router.get("/expense-preferences", response_model=dict)
async def get_expense_notification_preferences(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get current user's expense notification preferences"""
    try:
        # Look for existing tenant user by ID
        tenant_user = db.query(User).filter(User.id == current_user.id).first()
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in tenant database"
            )
        
        settings = db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == tenant_user.id
        ).first()

        if not settings:
            # Create default settings
            settings = EmailNotificationSettings(user_id=tenant_user.id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        
        # Return expense-specific preferences
        return {
            "expense_notification_frequency": settings.expense_notification_frequency,
            "expense_reminder_frequency": settings.expense_reminder_frequency,
            "expense_notification_channels": settings.expense_notification_channels,
            "expense_events": {
                "expense_submitted": settings.expense_submitted,
                "expense_updated": settings.expense_updated,
                "expense_approved": settings.expense_approved,
                "expense_rejected": settings.expense_rejected,
                "expense_paid": settings.expense_paid,
                "expense_commented": settings.expense_commented,
                "expense_reminder": settings.expense_reminder
            }
        }
    except Exception as e:
        logger.error(f"Error getting expense notification preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get expense notification preferences"
        )
