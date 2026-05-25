"""In-app notification dispatch for subscription detection events.

We piggyback on the existing ``ReminderNotification`` table (with
``reminder_id=NULL``) so the existing notifications feed renders these
without needing a parallel UI.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from core.models.models_per_tenant import ReminderNotification

if TYPE_CHECKING:
    from commercial.subscriptions.models import DetectedSubscription


logger = logging.getLogger(__name__)


EVENT_SUBSCRIPTION_DETECTED = "subscription_detected"
EVENT_SUBSCRIPTION_PRICE_CHANGED = "subscription_price_changed"
EVENT_SUBSCRIPTION_CHARGE_UPCOMING = "subscription_charge_upcoming"


def notify_subscription_detected(
    db: Session, *, user_id: int, subscription: "DetectedSubscription"
) -> None:
    cadence = _cadence_label(subscription.cadence_days)
    amount = _format_amount(subscription.amount, subscription.currency)
    subject = f"New subscription detected: {subscription.label}"
    message = (
        f"We spotted a recurring charge from {subscription.label} — "
        f"{amount} {cadence}. Review it on the Subscriptions page."
    )
    _record(
        db,
        user_id=user_id,
        notification_type=EVENT_SUBSCRIPTION_DETECTED,
        subject=subject,
        message=message,
    )


def notify_price_change(
    db: Session,
    *,
    user_id: int,
    subscription: "DetectedSubscription",
    old_amount: float,
    new_amount: float,
) -> None:
    direction = "increased" if new_amount > old_amount else "decreased"
    delta = abs(new_amount - old_amount)
    pct = (delta / old_amount * 100.0) if old_amount > 0 else 0.0
    old_fmt = _format_amount(old_amount, subscription.currency)
    new_fmt = _format_amount(new_amount, subscription.currency)
    subject = f"Price change: {subscription.label}"
    message = (
        f"{subscription.label} {direction} from {old_fmt} to {new_fmt} "
        f"({pct:.1f}%)."
    )
    _record(
        db,
        user_id=user_id,
        notification_type=EVENT_SUBSCRIPTION_PRICE_CHANGED,
        subject=subject,
        message=message,
    )


def notify_charge_upcoming(
    db: Session, *, user_id: int, subscription: "DetectedSubscription"
) -> None:
    """Optional reminder a few days before the next expected charge."""
    if not subscription.next_expected_date:
        return
    amount = _format_amount(subscription.amount, subscription.currency)
    subject = f"Upcoming charge: {subscription.label}"
    message = (
        f"{subscription.label} is expected to charge {amount} on "
        f"{subscription.next_expected_date.isoformat()}."
    )
    _record(
        db,
        user_id=user_id,
        notification_type=EVENT_SUBSCRIPTION_CHARGE_UPCOMING,
        subject=subject,
        message=message,
    )


def _record(
    db: Session,
    *,
    user_id: int,
    notification_type: str,
    subject: str,
    message: str,
) -> None:
    now = datetime.now(timezone.utc)
    try:
        notification = ReminderNotification(
            reminder_id=None,
            user_id=user_id,
            notification_type=notification_type,
            channel="in_app",
            scheduled_for=now,
            subject=subject,
            message=message,
            is_sent=True,
            sent_at=now,
        )
        db.add(notification)
        db.flush()
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to record subscription notification (user_id=%s, type=%s)",
            user_id,
            notification_type,
        )


def _cadence_label(cadence_days: int) -> str:
    if cadence_days == 7:
        return "weekly"
    if cadence_days == 14:
        return "every two weeks"
    if cadence_days == 30:
        return "monthly"
    if cadence_days == 90:
        return "quarterly"
    if cadence_days == 365:
        return "annually"
    return f"every {cadence_days} days"


def _format_amount(amount: float, currency: str) -> str:
    symbol = {"USD": "$", "CAD": "C$", "EUR": "€", "GBP": "£"}.get(currency, "")
    return f"{symbol}{amount:,.2f}" if symbol else f"{amount:,.2f} {currency}"
