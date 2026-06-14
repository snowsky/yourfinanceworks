"""Derive a 'needs review' reason for a detected subscription.

Pure, deterministic helpers. ``evaluate_review`` reads only attributes that
already exist on ``DetectedSubscription`` (status, next_expected_date,
cadence_days, first_seen_date), so it can be unit-tested against lightweight
stand-ins without a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from commercial.subscriptions.schemas import (
    SubscriptionResponse,
    SubscriptionSummary,
)

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


def to_response(sub, *, today: Optional[date] = None) -> SubscriptionResponse:
    """Build a SubscriptionResponse and attach derived review fields."""
    if today is None:
        today = date.today()
    resp = SubscriptionResponse.model_validate(sub)
    info = evaluate_review(sub, today=today)
    resp.review_reason = info.reason
    resp.days_overdue = info.days_overdue
    resp.months_running = info.months_running
    return resp


def build_summary(
    rows: List,
    *,
    needs_review: bool = False,
    today: Optional[date] = None,
) -> SubscriptionSummary:
    """Assemble the list summary. ``needs_review_count`` is computed over the
    full row set; when ``needs_review`` is set the returned ``items`` are
    filtered to flagged rows only (totals stay over the full set)."""
    if today is None:
        today = date.today()

    items = [to_response(r, today=today) for r in rows]
    active = [r for r in rows if r.status == ACTIVE_STATUS]
    monthly = sum(
        r.amount * (30.0 / r.cadence_days) for r in active if r.cadence_days
    )
    annual = sum(
        r.amount * (365.0 / r.cadence_days) for r in active if r.cadence_days
    )
    upcoming = [r.next_expected_date for r in active if r.next_expected_date]
    next_charge = min(upcoming) if upcoming else None
    needs_review_count = sum(1 for i in items if i.review_reason is not None)

    if needs_review:
        items = [i for i in items if i.review_reason is not None]

    return SubscriptionSummary(
        total_count=len(rows),
        active_count=len(active),
        monthly_cost=round(monthly, 2),
        annual_cost=round(annual, 2),
        next_charge_date=next_charge,
        needs_review_count=needs_review_count,
        items=items,
    )
