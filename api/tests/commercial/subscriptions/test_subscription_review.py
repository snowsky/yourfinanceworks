"""Unit tests for subscription needs-review derivation.

Pure tests: ``evaluate_review`` reads attributes duck-typed, so we use
``SimpleNamespace`` stand-ins and never touch the database (no db_session
fixture needed).
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from commercial.subscriptions.services.subscription_review import (
    LONG_RUNNING_MIN_DAYS,
    ReviewInfo,
    build_summary,
    evaluate_review,
    to_response,
)

TODAY = date(2026, 6, 14)


def _sub(**over):
    base = dict(
        status="active",
        cadence_days=30,
        next_expected_date=TODAY,           # on-time by default
        first_seen_date=TODAY - timedelta(days=30),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_on_time_active_sub_has_no_reason():
    assert evaluate_review(_sub(), today=TODAY) == ReviewInfo()


def test_lapsed_just_within_grace_is_not_flagged():
    # monthly cadence -> grace = max(7, round(0.5*30)) = 15 days
    sub = _sub(next_expected_date=TODAY - timedelta(days=15))
    assert evaluate_review(sub, today=TODAY).reason is None


def test_lapsed_past_grace_is_flagged_with_days_overdue():
    sub = _sub(next_expected_date=TODAY - timedelta(days=16))
    info = evaluate_review(sub, today=TODAY)
    assert info.reason == "lapsed"
    assert info.days_overdue == 16


def test_long_running_below_threshold_is_not_flagged():
    sub = _sub(
        next_expected_date=TODAY,
        first_seen_date=TODAY - timedelta(days=LONG_RUNNING_MIN_DAYS - 1),
    )
    assert evaluate_review(sub, today=TODAY).reason is None


def test_long_running_at_threshold_is_flagged_with_months():
    sub = _sub(
        next_expected_date=TODAY,
        first_seen_date=TODAY - timedelta(days=LONG_RUNNING_MIN_DAYS),
    )
    info = evaluate_review(sub, today=TODAY)
    assert info.reason == "long_running"
    assert info.months_running == LONG_RUNNING_MIN_DAYS // 30  # 6


def test_lapsed_takes_precedence_over_long_running():
    sub = _sub(
        next_expected_date=TODAY - timedelta(days=60),       # very overdue
        first_seen_date=TODAY - timedelta(days=400),         # also old
    )
    assert evaluate_review(sub, today=TODAY).reason == "lapsed"


def test_non_active_status_is_never_flagged():
    sub = _sub(
        status="dismissed",
        next_expected_date=TODAY - timedelta(days=90),
        first_seen_date=TODAY - timedelta(days=400),
    )
    assert evaluate_review(sub, today=TODAY) == ReviewInfo()


def test_missing_next_expected_date_can_still_be_long_running():
    sub = _sub(
        next_expected_date=None,
        first_seen_date=TODAY - timedelta(days=400),
    )
    assert evaluate_review(sub, today=TODAY).reason == "long_running"


def test_zero_cadence_falls_back_to_min_grace_without_crashing():
    sub = _sub(cadence_days=0, next_expected_date=TODAY - timedelta(days=8))
    # grace falls back to 7 -> 8 > 7 -> lapsed
    assert evaluate_review(sub, today=TODAY).reason == "lapsed"


# Full attribute set required by SubscriptionResponse.model_validate.
def _row(**over):
    base = dict(
        id=1,
        merchant_key="netflix",
        label="Netflix",
        category=None,
        amount=15.99,
        last_amount=15.99,
        currency="USD",
        cadence_days=30,
        confidence=0.9,
        first_seen_date=TODAY - timedelta(days=400),
        last_seen_date=TODAY,
        next_expected_date=TODAY,
        charge_count=12,
        status="active",
        cancel_reminder_at=None,
        price_change_acknowledged=False,
        source_transaction_ids=None,
        notes=None,
        dismissed_at=None,
        created_at=date(2025, 1, 1),
        updated_at=date(2025, 1, 1),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_to_response_attaches_review_fields():
    row = _row(first_seen_date=TODAY - timedelta(days=400))
    resp = to_response(row, today=TODAY)
    assert resp.review_reason == "long_running"
    assert resp.months_running == 400 // 30


def test_to_response_leaves_review_none_when_healthy():
    row = _row(first_seen_date=TODAY - timedelta(days=30))
    resp = to_response(row, today=TODAY)
    assert resp.review_reason is None
    assert resp.days_overdue is None
    assert resp.months_running is None


def test_build_summary_counts_needs_review():
    rows = [
        _row(id=1, first_seen_date=TODAY - timedelta(days=400)),   # long_running
        _row(id=2, next_expected_date=TODAY - timedelta(days=60)), # lapsed
        _row(id=3, first_seen_date=TODAY - timedelta(days=10)),    # healthy
    ]
    summary = build_summary(rows, today=TODAY)
    assert summary.needs_review_count == 2
    assert summary.total_count == 3


def test_build_summary_needs_review_filter_returns_only_flagged():
    rows = [
        _row(id=1, first_seen_date=TODAY - timedelta(days=400)),   # flagged
        _row(id=3, first_seen_date=TODAY - timedelta(days=10)),    # healthy
    ]
    summary = build_summary(rows, needs_review=True, today=TODAY)
    assert [i.id for i in summary.items] == [1]
    # count is computed before filtering, so it still reflects flagged rows
    assert summary.needs_review_count == 1
