"""Unit tests for the net-worth aggregator.

Verifies bank-balance pickup, liability aggregation, snapshot persistence,
and history rollup. Investments are exercised through the import-fallback
path because the plugin's encrypted columns require app initialization.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from commercial.networth.models import (  # noqa: F401
    AccountKind,
    FinancialLiability,
    LiabilityKind,
    NetWorthSnapshot,
)
from commercial.networth.services.networth_aggregator import (
    build_summary,
    capture_snapshot,
    history_by_month,
)
from core.models.models_per_tenant import BankStatement, BankStatementTransaction


def _add_bank_balance(
    db: Session,
    *,
    bank_name: str,
    when: date,
    balance: float,
) -> None:
    stmt = BankStatement(
        tenant_id=1,
        original_filename=f"{bank_name}.pdf",
        stored_filename=f"{bank_name}.pdf",
        file_path=f"/tmp/{bank_name}.pdf",
        status="processed",
        bank_name=bank_name,
    )
    db.add(stmt)
    db.flush()
    db.add(
        BankStatementTransaction(
            statement_id=stmt.id,
            date=when,
            description="closing balance",
            amount=0.0,
            transaction_type="debit",
            balance=balance,
        )
    )
    db.commit()


@pytest.mark.unit
def test_capture_snapshot_writes_bank_and_liability_rows(db_session: Session):
    _add_bank_balance(
        db_session, bank_name="Chase Checking", when=date.today(), balance=4200.0
    )
    db_session.add(
        FinancialLiability(
            name="Visa Card",
            kind=LiabilityKind.CREDIT_CARD.value,
            balance=1500.0,
            currency="USD",
        )
    )
    db_session.commit()

    result = capture_snapshot(db_session, user_id=None)

    assert result.rows_written == 2
    assert result.summary.bank_total == pytest.approx(4200.0)
    assert result.summary.liability_total == pytest.approx(1500.0)
    assert result.summary.total_assets == pytest.approx(4200.0)
    assert result.summary.net_worth == pytest.approx(2700.0)

    rows = (
        db_session.query(NetWorthSnapshot)
        .filter(NetWorthSnapshot.snapshot_date == date.today())
        .all()
    )
    kinds = sorted(r.account_kind for r in rows)
    assert kinds == [AccountKind.BANK.value, AccountKind.LIABILITY.value]


@pytest.mark.unit
def test_capture_snapshot_is_idempotent_within_a_day(db_session: Session):
    _add_bank_balance(
        db_session, bank_name="Chase", when=date.today(), balance=1000.0
    )

    first = capture_snapshot(db_session)
    second = capture_snapshot(db_session)

    rows = (
        db_session.query(NetWorthSnapshot)
        .filter(NetWorthSnapshot.snapshot_date == date.today())
        .all()
    )
    assert len(rows) == first.rows_written == second.rows_written
    assert first.summary.bank_total == second.summary.bank_total


@pytest.mark.unit
def test_latest_bank_balance_wins_per_bank_name(db_session: Session):
    _add_bank_balance(
        db_session,
        bank_name="Chase",
        when=date.today() - timedelta(days=30),
        balance=500.0,
    )
    _add_bank_balance(
        db_session, bank_name="Chase", when=date.today(), balance=900.0
    )

    summary = capture_snapshot(db_session).summary

    bank_accounts = [
        a for a in summary.accounts if a.account_kind == AccountKind.BANK.value
    ]
    assert len(bank_accounts) == 1
    assert bank_accounts[0].balance == pytest.approx(900.0)


@pytest.mark.unit
def test_build_summary_returns_empty_without_snapshots(db_session: Session):
    summary = build_summary(db_session)
    assert summary.snapshot_date is None
    assert summary.net_worth == 0.0
    assert summary.accounts == []


@pytest.mark.unit
def test_history_returns_one_point_per_snapshot_date(db_session: Session):
    older = date.today() - timedelta(days=60)
    newer = date.today()
    db_session.add_all(
        [
            NetWorthSnapshot(
                snapshot_date=older,
                account_kind=AccountKind.BANK.value,
                label="Chase",
                balance=1000.0,
                currency="USD",
            ),
            NetWorthSnapshot(
                snapshot_date=older,
                account_kind=AccountKind.LIABILITY.value,
                label="Visa",
                balance=200.0,
                currency="USD",
            ),
            NetWorthSnapshot(
                snapshot_date=newer,
                account_kind=AccountKind.BANK.value,
                label="Chase",
                balance=1200.0,
                currency="USD",
            ),
        ]
    )
    db_session.commit()

    points = history_by_month(db_session, months=12)

    assert len(points) == 2
    assert points[0].snapshot_date == older
    assert points[0].net_worth == pytest.approx(800.0)
    assert points[1].snapshot_date == newer
    assert points[1].net_worth == pytest.approx(1200.0)


@pytest.mark.unit
def test_history_respects_months_cap(db_session: Session):
    today = date.today()
    for i in range(5):
        db_session.add(
            NetWorthSnapshot(
                snapshot_date=today - timedelta(days=30 * i),
                account_kind=AccountKind.BANK.value,
                label="Chase",
                balance=1000.0 + i,
                currency="USD",
            )
        )
    db_session.commit()

    points = history_by_month(db_session, months=3)
    assert len(points) == 3


@pytest.mark.unit
def test_deleted_bank_statements_are_skipped(db_session: Session):
    stmt = BankStatement(
        tenant_id=1,
        original_filename="deleted.pdf",
        stored_filename="deleted.pdf",
        file_path="/tmp/deleted.pdf",
        status="processed",
        bank_name="GhostBank",
        is_deleted=True,
    )
    db_session.add(stmt)
    db_session.flush()
    db_session.add(
        BankStatementTransaction(
            statement_id=stmt.id,
            date=date.today(),
            description="x",
            amount=0.0,
            transaction_type="debit",
            balance=9999.0,
        )
    )
    db_session.commit()

    summary = capture_snapshot(db_session).summary
    assert summary.bank_total == 0.0
