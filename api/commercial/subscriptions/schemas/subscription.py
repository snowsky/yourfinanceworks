"""Pydantic request/response models for subscription detection."""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SubscriptionStatusLiteral = Literal[
    "active", "dismissed", "canceled_by_user", "not_a_subscription"
]


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant_key: str
    label: str
    category: Optional[str] = None
    amount: float
    last_amount: Optional[float] = None
    currency: str
    cadence_days: int
    confidence: float
    first_seen_date: date
    last_seen_date: date
    next_expected_date: Optional[date] = None
    charge_count: int
    status: SubscriptionStatusLiteral
    cancel_reminder_at: Optional[date] = None
    price_change_acknowledged: bool
    source_transaction_ids: Optional[List[int]] = None
    notes: Optional[str] = None
    dismissed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Derived needs-review fields (attached by to_response; default None).
    review_reason: Optional[Literal["lapsed", "long_running"]] = None
    days_overdue: Optional[int] = None
    months_running: Optional[int] = None

    @property
    def annual_cost(self) -> float:
        if self.cadence_days <= 0:
            return 0.0
        return round(self.amount * (365.0 / self.cadence_days), 2)


class SubscriptionSummary(BaseModel):
    total_count: int
    active_count: int
    monthly_cost: float = Field(
        ..., description="Sum of amount * (30 / cadence_days) across active rows"
    )
    annual_cost: float = Field(
        ..., description="Sum of amount * (365 / cadence_days) across active rows"
    )
    next_charge_date: Optional[date] = None
    needs_review_count: int = 0
    items: List[SubscriptionResponse]


class ChargeHistoryEntry(BaseModel):
    transaction_id: int
    date: date
    amount: float
    description: str


class ChargeHistoryResponse(BaseModel):
    subscription_id: int
    entries: List[ChargeHistoryEntry]


class ScanRequest(BaseModel):
    lookback_days: int = Field(default=365, ge=30, le=365)
    emit_notifications: bool = True


class ScanResponse(BaseModel):
    scanned_transactions: int
    candidate_groups: int
    new_subscriptions: int
    updated_subscriptions: int
    price_changed_subscriptions: int
    skipped_excluded: int
    new_subscription_ids: List[int] = Field(default_factory=list)
    price_changed_subscription_ids: List[int] = Field(default_factory=list)


class StatusUpdateRequest(BaseModel):
    status: SubscriptionStatusLiteral


class CancelReminderRequest(BaseModel):
    remind_on: Optional[date] = None
