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
    
    # Expense operation notifications
    expense_created: bool = True
    expense_updated: bool = False
    expense_deleted: bool = True
    expense_approved: bool = True
    expense_rejected: bool = True
    expense_submitted: bool = True
    expense_imported: bool = True
    expense_analysis_completed: bool = True
    expense_analysis_failed: bool = True
    
    # Inventory operation notifications
    inventory_created: bool = True
    inventory_updated: bool = False
    inventory_deleted: bool = True
    inventory_low_stock: bool = True
    inventory_out_of_stock: bool = True
    inventory_stock_movement: bool = False
    inventory_category_created: bool = False
    inventory_category_updated: bool = False
    inventory_category_deleted: bool = True
    
    # Statement operation notifications
    statement_generated: bool = True
    statement_sent: bool = True
    statement_overdue: bool = True
    statement_uploaded: bool = True
    statement_processed: bool = True
    statement_processing_failed: bool = True
    statement_transaction_created: bool = False
    
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
    
    # Reminder notifications
    reminder_created: bool = True
    reminder_sent: bool = True
    reminder_overdue: bool = True
    reminder_due: bool = True
    reminder_upcoming: bool = True
    reminder_assigned: bool = True
    reminder_completed: bool = False
    
    # Reminder notification preferences
    reminder_advance_days: int = 1
    reminder_notification_frequency: str = "immediate"  # immediate, daily_digest
    
    # Additional notification preferences
    notification_email: Optional[str] = None
    daily_summary: bool = False
    weekly_summary: bool = False

    # Personal expense digest preferences
    expense_digest_enabled: bool = False
    expense_digest_frequency: str = "weekly"
    expense_digest_next_run_at: Optional[datetime] = None
    expense_digest_last_sent_at: Optional[datetime] = None
    
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
    
    @field_validator('reminder_notification_frequency')
    @classmethod
    def validate_reminder_notification_frequency(cls, v):
        valid_frequencies = ["immediate", "daily_digest"]
        if v not in valid_frequencies:
            raise ValueError(f'reminder_notification_frequency must be one of {valid_frequencies}')
        return v

    @field_validator('expense_digest_frequency')
    @classmethod
    def validate_expense_digest_frequency(cls, v):
        valid_frequencies = ["daily", "weekly"]
        if v not in valid_frequencies:
            raise ValueError(f'expense_digest_frequency must be one of {valid_frequencies}')
        return v
    
    @field_validator('reminder_advance_days')
    @classmethod
    def validate_reminder_advance_days(cls, v):
        if v < 0 or v > 30:
            raise ValueError('reminder_advance_days must be between 0 and 30')
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
