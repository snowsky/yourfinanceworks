"""Unit tests for the subscription detector.

Builds synthetic ``BankStatementTransaction`` rows in the test tenant DB,
runs ``scan_tenant``, and checks the resulting ``DetectedSubscription``
rows and ``ScanResult`` counters.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List

import pytest
from sqlalchemy.orm import Session

# Importing the model registers it on TenantBase.metadata before the
# db_session fixture's table cleanup phase runs.
from commercial.subscriptions.models import (  # noqa: F401
    DetectedSubscription,
    SubscriptionStatus,
)
from commercial.subscriptions.services.subscription_detector import (
    PRICE_CHANGE_THRESHOLD,
    scan_tenant,
)
from core.models.models_per_tenant import BankStatement, BankStatementTransaction


@pytest.fixture
def statement(db_session: Session) -> BankStatement:
    stmt = BankStatement(
        tenant_id=1,
        original_filename="test.pdf",
        stored_filename="stored.pdf",
        file_path="/tmp/stored.pdf",
        status="processed",
    )
    db_session.add(stmt)
    db_session.commit()
    db_session.refresh(stmt)
    return stmt


def _add_txn(
    db: Session,
    statement_id: int,
    *,
    when: date,
    amount: float,
    description: str,
    transaction_type: str = "debit",
    category: str | None = None,
) -> BankStatementTransaction:
    txn = BankStatementTransaction(
        statement_id=statement_id,
        date=when,
        description=description,
        amount=amount,
        transaction_type=transaction_type,
        category=category,
    )
    db.add(txn)
    return txn


def _monthly(start: date, count: int) -> List[date]:
    return [start + timedelta(days=30 * i) for i in range(count)]


@pytest.mark.unit
def test_detects_monthly_subscription(db_session: Session, statement: BankStatement):
    for day in _monthly(date.today() - timedelta(days=90), 4):
        _add_txn(
            db_session,
            statement.id,
            when=day,
            amount=15.99,
            description="NETFLIX.COM #123",
        )
    db_session.commit()

    result = scan_tenant(db_session, emit_notifications=False)

    assert result.new_subscriptions == 1
    subs = db_session.query(DetectedSubscription).all()
    assert len(subs) == 1
    sub = subs[0]
    assert sub.cadence_days == 30
    assert pytest.approx(sub.amount, rel=1e-2) == 15.99
    assert sub.charge_count == 4
    assert sub.status == SubscriptionStatus.ACTIVE.value
    assert sub.next_expected_date == sub.last_seen_date + timedelta(days=30)


@pytest.mark.unit
def test_ignores_single_charge(db_session: Session, statement: BankStatement):
    _add_txn(
        db_session,
        statement.id,
        when=date.today() - timedelta(days=5),
        amount=42.00,
        description="ONE TIME GIZMO",
    )
    db_session.commit()

    result = scan_tenant(db_session, emit_notifications=False)

    assert result.new_subscriptions == 0
    assert db_session.query(DetectedSubscription).count() == 0


@pytest.mark.unit
def test_excludes_rent_and_payroll(db_session: Session, statement: BankStatement):
    for day in _monthly(date.today() - timedelta(days=90), 4):
        _add_txn(
            db_session,
            statement.id,
            when=day,
            amount=2200.00,
            description="MONTHLY RENT XYZ APTS",
            category="Rent",
        )
        _add_txn(
            db_session,
            statement.id,
            when=day,
            amount=4500.00,
            description="ACME PAYROLL",
            transaction_type="credit",
            category="Income",
        )
    db_session.commit()

    result = scan_tenant(db_session, emit_notifications=False)

    assert result.new_subscriptions == 0
    assert db_session.query(DetectedSubscription).count() == 0


@pytest.mark.unit
def test_price_change_triggers_update(db_session: Session, statement: BankStatement):
    base_days = _monthly(date.today() - timedelta(days=120), 4)
    for day in base_days:
        _add_txn(
            db_session,
            statement.id,
            when=day,
            amount=9.99,
            description="SPOTIFY PREMIUM",
        )
    db_session.commit()

    first = scan_tenant(db_session, emit_notifications=False)
    assert first.new_subscriptions == 1
    sub = db_session.query(DetectedSubscription).one()
    original_amount = sub.amount

    # New charge ~30 days after the latest, at a clearly higher amount that
    # exceeds the PRICE_CHANGE_THRESHOLD relative to the historical median.
    bumped_amount = original_amount * (1 + PRICE_CHANGE_THRESHOLD * 4)
    _add_txn(
        db_session,
        statement.id,
        when=base_days[-1] + timedelta(days=30),
        amount=bumped_amount,
        description="SPOTIFY PREMIUM",
    )
    db_session.commit()

    second = scan_tenant(db_session, emit_notifications=False)

    assert second.new_subscriptions == 0
    assert second.price_changed_subscriptions == 1
    db_session.refresh(sub)
    assert sub.amount > original_amount
    assert sub.last_amount == pytest.approx(bumped_amount, rel=1e-3)
    assert sub.price_change_acknowledged is False


@pytest.mark.unit
def test_dismissed_status_survives_rescan(
    db_session: Session, statement: BankStatement
):
    for day in _monthly(date.today() - timedelta(days=90), 4):
        _add_txn(
            db_session,
            statement.id,
            when=day,
            amount=49.00,
            description="AWS BILLING",
        )
    db_session.commit()

    scan_tenant(db_session, emit_notifications=False)
    sub = db_session.query(DetectedSubscription).one()
    sub.status = SubscriptionStatus.DISMISSED.value
    db_session.commit()

    second = scan_tenant(db_session, emit_notifications=False)

    db_session.refresh(sub)
    assert second.new_subscriptions == 0
    assert sub.status == SubscriptionStatus.DISMISSED.value


@pytest.mark.unit
def test_different_merchants_not_grouped(
    db_session: Session, statement: BankStatement
):
    days = _monthly(date.today() - timedelta(days=90), 4)
    for day in days:
        _add_txn(
            db_session,
            statement.id,
            when=day,
            amount=9.99,
            description="NETFLIX.COM",
        )
        _add_txn(
            db_session,
            statement.id,
            when=day,
            amount=12.99,
            description="HBO MAX",
        )
    db_session.commit()

    result = scan_tenant(db_session, emit_notifications=False)

    assert result.new_subscriptions == 2
    labels = {
        s.label for s in db_session.query(DetectedSubscription).all()
    }
    assert any("netflix" in l.lower() for l in labels)
    assert any("hbo" in l.lower() for l in labels)


@pytest.mark.unit
def test_ignores_credit_transactions(
    db_session: Session, statement: BankStatement
):
    for day in _monthly(date.today() - timedelta(days=90), 4):
        _add_txn(
            db_session,
            statement.id,
            when=day,
            amount=1000.00,
            description="EMPLOYER PAYROLL",
            transaction_type="credit",
        )
    db_session.commit()

    result = scan_tenant(db_session, emit_notifications=False)

    assert result.new_subscriptions == 0
