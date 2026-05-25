"""Read/update helpers used by the subscriptions router.

Detection-related logic lives in ``subscription_detector``; this module
covers the listing and per-row actions exposed to the frontend.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from commercial.subscriptions.models import DetectedSubscription, SubscriptionStatus


def list_subscriptions(
    db: Session,
    *,
    status: Optional[str] = None,
    include_low_confidence: bool = False,
    min_confidence: float = 0.6,
) -> List[DetectedSubscription]:
    """Return subscriptions sorted by next expected charge.

    ``status`` defaults to all non-dismissed rows. ``min_confidence``
    filters out weak detections unless ``include_low_confidence`` is set.
    """
    query = db.query(DetectedSubscription)
    if status is not None:
        query = query.filter(DetectedSubscription.status == status)
    else:
        query = query.filter(
            DetectedSubscription.status != SubscriptionStatus.NOT_A_SUBSCRIPTION.value
        )
    if not include_low_confidence:
        query = query.filter(DetectedSubscription.confidence >= min_confidence)
    return (
        query
        .order_by(
            DetectedSubscription.next_expected_date.is_(None),
            DetectedSubscription.next_expected_date.asc(),
            DetectedSubscription.amount.desc(),
        )
        .all()
    )


def get_subscription(db: Session, subscription_id: int) -> Optional[DetectedSubscription]:
    return (
        db.query(DetectedSubscription)
        .filter(DetectedSubscription.id == subscription_id)
        .first()
    )


def update_status(
    db: Session,
    subscription: DetectedSubscription,
    *,
    status: SubscriptionStatus,
    user_id: Optional[int] = None,
) -> DetectedSubscription:
    """Transition status and stamp ``dismissed_by`` / ``dismissed_at`` for
    transitions that represent user intent to suppress the row."""
    subscription.status = status.value
    if status in (
        SubscriptionStatus.DISMISSED,
        SubscriptionStatus.CANCELED_BY_USER,
        SubscriptionStatus.NOT_A_SUBSCRIPTION,
    ):
        subscription.dismissed_by_user_id = user_id
        subscription.dismissed_at = datetime.now(timezone.utc)
    else:
        subscription.dismissed_by_user_id = None
        subscription.dismissed_at = None
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def set_cancel_reminder(
    db: Session,
    subscription: DetectedSubscription,
    *,
    remind_on: Optional[date],
) -> DetectedSubscription:
    subscription.cancel_reminder_at = remind_on
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def acknowledge_price_change(
    db: Session, subscription: DetectedSubscription
) -> DetectedSubscription:
    subscription.price_change_acknowledged = True
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription
