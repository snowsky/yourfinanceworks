"""Detected subscription model.

A ``DetectedSubscription`` represents a recurring charge inferred from a
tenant's bank-statement transactions (e.g. Netflix, gym, SaaS, insurance).

Rows are upserted by the detector keyed on ``merchant_key`` so user
decisions (dismiss / not_a_subscription) survive re-scans.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from core.models.models_per_tenant import Base


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    DISMISSED = "dismissed"
    CANCELED_BY_USER = "canceled_by_user"
    NOT_A_SUBSCRIPTION = "not_a_subscription"


class DetectedSubscription(Base):
    __tablename__ = "detected_subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    merchant_key = Column(String(200), nullable=False, index=True)
    label = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)

    amount = Column(Float, nullable=False)
    last_amount = Column(Float, nullable=True)
    currency = Column(String(8), nullable=False, default="USD")

    cadence_days = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)

    first_seen_date = Column(Date, nullable=False)
    last_seen_date = Column(Date, nullable=False)
    next_expected_date = Column(Date, nullable=True)
    charge_count = Column(Integer, nullable=False, default=1)

    status = Column(
        String(32),
        nullable=False,
        default=SubscriptionStatus.ACTIVE.value,
        index=True,
    )

    source_transaction_ids = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    cancel_reminder_at = Column(Date, nullable=True)
    price_change_acknowledged = Column(Boolean, nullable=False, default=False)

    dismissed_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("merchant_key", name="uq_detected_subscriptions_merchant_key"),
        Index("ix_detected_subscriptions_status_next", "status", "next_expected_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<DetectedSubscription(label='{self.label}', amount={self.amount}, "
            f"cadence_days={self.cadence_days}, status='{self.status}')>"
        )
