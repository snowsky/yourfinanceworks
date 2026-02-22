from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum

# Import the enums from core.models
class RecurrencePattern(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class ReminderStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SNOOZED = "snoozed"
    CANCELLED = "cancelled"

class ReminderPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Base schemas
class ReminderBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Reminder title")
    description: Optional[str] = Field(None, max_length=1000, description="Detailed description")
    due_date: datetime = Field(..., description="When the reminder is due")
    recurrence_pattern: RecurrencePattern = Field(RecurrencePattern.NONE, description="How often to repeat")
    recurrence_interval: int = Field(1, ge=1, le=365, description="Repeat every N units")
    recurrence_end_date: Optional[datetime] = Field(None, description="When to stop recurring")
    priority: ReminderPriority = Field(ReminderPriority.MEDIUM, description="Priority level")
    assigned_to_id: int = Field(..., description="User ID to assign this reminder to")
    position: int = Field(0, description="Order position")
    is_pinned: bool = Field(False, description="Whether the reminder is pinned to top")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator('recurrence_end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        if v and info.data.get('due_date') and v <= info.data['due_date']:
            raise ValueError('Recurrence end date must be after due date')
        return v

    @field_validator('recurrence_interval')
    @classmethod
    def validate_recurrence_interval(cls, v, info):
        pattern = info.data.get('recurrence_pattern')
        if pattern == RecurrencePattern.NONE and v != 1:
            raise ValueError('Recurrence interval must be 1 for non-recurring reminders')
        return v

class ReminderCreate(ReminderBase):
    """Schema for creating a new reminder"""
    pass

class ReminderUpdate(BaseModel):
    """Schema for updating an existing reminder"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    due_date: Optional[datetime] = None
    recurrence_pattern: Optional[RecurrencePattern] = None
    recurrence_interval: Optional[int] = Field(None, ge=1, le=365)
    recurrence_end_date: Optional[datetime] = None
    priority: Optional[ReminderPriority] = None
    assigned_to_id: Optional[int] = None
    position: Optional[int] = None
    is_pinned: Optional[bool] = None
    tags: Optional[List[str]] = None
    extra_metadata: Optional[Dict[str, Any]] = None

class ReminderStatusUpdate(BaseModel):
    """Schema for updating reminder status"""
    status: ReminderStatus = Field(..., description="New status")
    completion_notes: Optional[str] = Field(None, max_length=500, description="Notes about completion")
    snoozed_until: Optional[datetime] = Field(None, description="Snooze until this time")

class ReminderResponse(ReminderBase):
    """Schema for reminder responses"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ReminderStatus
    created_by_id: int
    position: int
    is_pinned: bool
    next_due_date: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    snooze_count: int = 0
    completed_at: Optional[datetime] = None
    completed_by_id: Optional[int] = None
    completion_notes: Optional[str] = None
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime
    # User attribution fields (for consistency with other entities)
    created_by_username: Optional[str] = None
    created_by_email: Optional[str] = None

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Override model_validate to populate attribution fields from relationship"""
        instance = super().model_validate(obj, **kwargs)

        # Populate flat attribution fields from relationship if available
        if hasattr(obj, 'created_by') and obj.created_by:
            from core.services.attribution_service import AttributionService
            instance.created_by_username = AttributionService.get_display_name(obj.created_by)
            instance.created_by_email = obj.created_by.email if hasattr(obj.created_by, 'email') else None
        else:
            # Handle missing attribution gracefully
            instance.created_by_username = "Unknown"
            instance.created_by_email = None

        return instance

class ReminderWithUsers(ReminderResponse):
    """Schema for reminder responses with user information"""
    created_by: Optional["UserBasic"] = None
    assigned_to: Optional["UserBasic"] = None
    completed_by: Optional["UserBasic"] = None

# User schema for relationship
class UserBasic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.email

# Notification schemas
class ReminderNotificationBase(BaseModel):
    notification_type: str = Field(..., description="Type of notification")
    channel: str = Field(..., description="Notification channel")
    scheduled_for: datetime = Field(..., description="When to send")
    subject: Optional[str] = Field(None, max_length=200)
    message: Optional[str] = Field(None, max_length=1000)

class ReminderNotificationCreate(ReminderNotificationBase):
    reminder_id: int
    user_id: int

class ReminderNotificationResponse(ReminderNotificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reminder_id: int
    user_id: int
    sent_at: Optional[datetime] = None
    is_sent: bool = False
    is_read: bool = False
    send_attempts: int = 0
    last_attempt_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# List and filter schemas
class ReminderFilter(BaseModel):
    """Schema for filtering reminders"""
    status: Optional[List[ReminderStatus]] = None
    priority: Optional[List[ReminderPriority]] = None
    assigned_to_id: Optional[int] = None
    created_by_id: Optional[int] = None
    due_date_from: Optional[datetime] = None
    due_date_to: Optional[datetime] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = Field(None, max_length=100, description="Search in title and description")

class ReminderList(BaseModel):
    """Schema for paginated reminder list"""
    items: List[ReminderWithUsers]
    total: int
    page: int
    per_page: int
    pages: int

# Bulk operations
class BulkReminderUpdate(BaseModel):
    """Schema for bulk reminder updates"""
    reminder_ids: List[int] = Field(..., min_length=1, max_length=100)
    status: Optional[ReminderStatus] = None
    priority: Optional[ReminderPriority] = None
    assigned_to_id: Optional[int] = None
    position: Optional[int] = None

class ReorderReminders(BaseModel):
    """Schema for reordering reminders"""
    reminder_ids: List[int] = Field(..., min_length=1, max_length=100)

class BulkReminderResponse(BaseModel):
    """Schema for bulk operation responses"""
    updated_count: int
    failed_count: int
    errors: List[str] = []

# Update the forward reference
ReminderWithUsers.model_rebuild()
