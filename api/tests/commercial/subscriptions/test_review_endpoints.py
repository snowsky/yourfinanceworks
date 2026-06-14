"""Integration tests for the subscription list/summary review path.

Seeds real ``DetectedSubscription`` rows in the test tenant DB and exercises
``list_subscriptions`` + ``build_summary`` (the same calls the list endpoint
makes), verifying needs-review derivation and the needs_review filter on real
ORM rows.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from commercial.subscriptions.models import DetectedSubscription  # noqa: F401
from commercial.subscriptions.services import build_summary, list_subscriptions

TODAY = date(2026, 6, 14)


def _add_sub(db: Session, *, merchant_key, status="active",
             next_expected_offset_days=0, first_seen_offset_days=30):
    sub = DetectedSubscription(
        merchant_key=merchant_key,
        label=merchant_key.title(),
        amount=15.99,
        currency="USD",
        cadence_days=30,
        confidence=0.9,
        first_seen_date=TODAY - timedelta(days=first_seen_offset_days),
        last_seen_date=TODAY,
        next_expected_date=TODAY - timedelta(days=-next_expected_offset_days)
        if next_expected_offset_days is not None
        else None,
        charge_count=12,
        status=status,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@pytest.fixture
def seeded(db_session: Session):
    # lapsed: 60 days overdue, active
    _add_sub(db_session, merchant_key="lapsedco",
             next_expected_offset_days=-60, first_seen_offset_days=400)
    # long_running: on-time, but first seen 400 days ago
    _add_sub(db_session, merchant_key="longco",
             next_expected_offset_days=0, first_seen_offset_days=400)
    # healthy: on-time, recently first seen
    _add_sub(db_session, merchant_key="healthyco",
             next_expected_offset_days=0, first_seen_offset_days=30)
    # dismissed + overdue: must NOT be flagged (not active)
    _add_sub(db_session, merchant_key="dismissedco", status="dismissed",
             next_expected_offset_days=-90, first_seen_offset_days=400)
    return db_session


def test_summary_counts_needs_review_on_real_rows(seeded):
    rows = list_subscriptions(seeded)
    summary = build_summary(rows, today=TODAY)
    # lapsedco + longco are flagged; healthyco and dismissedco are not
    assert summary.needs_review_count == 2
    by_key = {i.merchant_key: i for i in summary.items}
    assert by_key["lapsedco"].review_reason == "lapsed"
    assert by_key["lapsedco"].days_overdue == 60
    assert by_key["longco"].review_reason == "long_running"
    assert by_key["healthyco"].review_reason is None


def test_needs_review_filter_returns_only_flagged(seeded):
    rows = list_subscriptions(seeded)
    summary = build_summary(rows, needs_review=True, today=TODAY)
    keys = sorted(i.merchant_key for i in summary.items)
    assert keys == ["lapsedco", "longco"]
    assert summary.needs_review_count == 2
