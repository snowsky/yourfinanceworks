"""
Pydantic schemas for Scheduled Job Alerts.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertOperator(str, Enum):
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    EQUAL = "eq"
    NOT_EQUAL = "neq"
    CONTAINS = "contains"
    STATUS_IS = "status_is"


class AlertCondition(BaseModel):
    """Defines a condition that triggers an alert."""
    field: str = Field(..., description="Field from the report output to evaluate (e.g., 'total_records', 'total_amount', 'status')")
    operator: AlertOperator = Field(..., description="Comparison operator")
    threshold: Any = Field(..., description="Value to compare against")


class AlertNotificationChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


# --- Create / Update schemas ---

class ScheduledJobAlertCreate(BaseModel):
    scheduled_report_id: int = Field(..., description="ID of the scheduled report to monitor")
    name: str = Field(..., description="Alert name", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Alert description")
    condition: AlertCondition = Field(..., description="Condition that triggers the alert")
    notification_channels: List[AlertNotificationChannel] = Field(
        default=[AlertNotificationChannel.EMAIL],
        description="Channels to send notifications through"
    )
    recipients: List[str] = Field(..., description="Recipients for the alert notification", min_length=1)
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM, description="Alert severity level")
    is_active: Optional[bool] = Field(default=True, description="Whether the alert is active")
    cooldown_minutes: Optional[int] = Field(default=60, ge=1, le=1440, description="Cooldown period in minutes between alerts")


class ScheduledJobAlertUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Alert name", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Alert description")
    condition: Optional[AlertCondition] = Field(None, description="Condition that triggers the alert")
    notification_channels: Optional[List[AlertNotificationChannel]] = Field(None, description="Notification channels")
    recipients: Optional[List[str]] = Field(None, description="Recipients for the alert notification")
    severity: Optional[AlertSeverity] = Field(None, description="Alert severity level")
    is_active: Optional[bool] = Field(None, description="Whether the alert is active")
    cooldown_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Cooldown period in minutes")


# --- Response schemas ---

class ScheduledJobAlertResponse(BaseModel):
    id: int
    scheduled_report_id: int
    name: str
    description: Optional[str]
    condition: AlertCondition
    notification_channels: List[str]
    recipients: List[str]
    severity: str
    is_active: bool
    cooldown_minutes: int
    last_triggered_at: Optional[datetime]
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduledJobAlertListResponse(BaseModel):
    alerts: List[ScheduledJobAlertResponse]
    total: int


class ScheduledJobAlertHistoryResponse(BaseModel):
    id: int
    alert_id: int
    triggered_at: datetime
    condition_result: Optional[Dict[str, Any]]
    notification_sent: bool
    notification_error: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ScheduledJobAlertHistoryListResponse(BaseModel):
    history: List[ScheduledJobAlertHistoryResponse]
    total: int
