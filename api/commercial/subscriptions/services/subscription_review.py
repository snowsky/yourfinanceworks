"""Derive a 'needs review' reason for a detected subscription.

Pure, deterministic helpers. ``evaluate_review`` reads only attributes that
already exist on ``DetectedSubscription`` (status, next_expected_date,
cadence_days, first_seen_date), so it can be unit-tested against lightweight
stand-ins without a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

# "active" status string. Kept as a literal to keep this module import-light
# and DB-free; it mirrors ``SubscriptionStatus.ACTIVE.value``.
ACTIVE_STATUS = "active"

LONG_RUNNING_MIN_DAYS = 180
LAPSED_MIN_GRACE_DAYS = 7
LAPSED_GRACE_CADENCE_FRACTION = 0.5


@dataclass(frozen=True)
class ReviewInfo:
    reason: Optional[str] = None            # "lapsed" | "long_running" | None
    days_overdue: Optional[int] = None
    months_running: Optional[int] = None


def _lapsed_grace_days(cadence_days: int) -> int:
    if cadence_days and cadence_days > 0:
        return max(
            LAPSED_MIN_GRACE_DAYS,
            round(LAPSED_GRACE_CADENCE_FRACTION * cadence_days),
        )
    return LAPSED_MIN_GRACE_DAYS


def evaluate_review(sub, *, today: date) -> ReviewInfo:
    """Return the needs-review reason for ``sub`` as of ``today``.

    Only ``active`` subscriptions are eligible. ``lapsed`` (charges stopped)
    takes precedence over ``long_running`` (still charging but old). At most
    one reason is returned.
    """
    if sub.status != ACTIVE_STATUS:
        return ReviewInfo()

    next_expected = sub.next_expected_date
    if next_expected is not None:
        grace = _lapsed_grace_days(sub.cadence_days)
        days_overdue = (today - next_expected).days
        if days_overdue > grace:
            return ReviewInfo(reason="lapsed", days_overdue=days_overdue)

    first_seen = sub.first_seen_date
    if first_seen is not None:
        age_days = (today - first_seen).days
        if age_days >= LONG_RUNNING_MIN_DAYS:
            return ReviewInfo(
                reason="long_running", months_running=age_days // 30
            )

    return ReviewInfo()
