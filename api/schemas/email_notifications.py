from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime

class EmailNotificationSettingsBase(BaseModel):
    # User operation notifications
    user_created: bool = False
    user_updated: bool = False
    user_deleted: bool = False
    user_login: bool = False
    
    # Client operation notifications
    client_created: bool = True
    client_updated: bool = False
    client_deleted: bool = True
    
    # Invoice operation notifications
    invoice_created: bool = True
    invoice_updated: bool = False
    invoice_deleted: bool = True
    invoice_sent: bool = True
    invoice_paid: bool = True
    invoice_overdue: bool = True
    
    # Payment operation notifications
    payment_created: bool = True
    payment_updated: bool = False
    payment_deleted: bool = True
    
    # Settings operation notifications
    settings_updated: bool = False
    
    # Organization join request notifications
    organization_join_request_created: bool = True
    
    # Approval operation notifications
    expense_submitted_for_approval: bool = True
    expense_approved: bool = True
    expense_rejected: bool = True
    expense_level_approved: bool = True
    expense_fully_approved: bool = True
    expense_auto_approved: bool = True
    approval_reminder: bool = True
    approval_escalation: bool = True
    
    # Approval notification frequency preferences
    approval_notification_frequency: str = "immediate"  # immediate, daily_digest
    approval_reminder_frequency: str = "daily"  # daily, weekly, disabled
    
    # Approval notification channel preferences
    approval_notification_channels: List[str] = ["email"]  # ["email", "in_app"] or ["email"] or ["in_app"]
    
    # Additional notification preferences
    notification_email: Optional[str] = None
    daily_summary: bool = False
    weekly_summary: bool = False
    
    @field_validator('approval_notification_frequency')
    @classmethod
    def validate_approval_notification_frequency(cls, v):
        valid_frequencies = ["immediate", "daily_digest"]
        if v not in valid_frequencies:
            raise ValueError(f'approval_notification_frequency must be one of {valid_frequencies}')
        return v
    
    @field_validator('approval_reminder_frequency')
    @classmethod
    def validate_approval_reminder_frequency(cls, v):
        valid_frequencies = ["daily", "weekly", "disabled"]
        if v not in valid_frequencies:
            raise ValueError(f'approval_reminder_frequency must be one of {valid_frequencies}')
        return v
    
    @field_validator('approval_notification_channels')
    @classmethod
    def validate_approval_notification_channels(cls, v):
        valid_channels = ["email", "in_app"]
        if not v or not isinstance(v, list):
            raise ValueError('approval_notification_channels must be a non-empty list')
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f'Invalid channel: {channel}. Must be one of {valid_channels}')
        return v

class EmailNotificationSettingsCreate(EmailNotificationSettingsBase):
    pass

class EmailNotificationSettingsUpdate(EmailNotificationSettingsBase):
    pass

class EmailNotificationSettings(EmailNotificationSettingsBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class NotificationEvent(BaseModel):
    event_type: str
    user_id: int
    resource_type: str
    resource_id: str
    resource_name: str
    details: dict
    timestamp: datetime