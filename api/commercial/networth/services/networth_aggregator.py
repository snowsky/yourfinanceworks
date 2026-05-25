"""Net-worth aggregation service.

Collects current balances from three sources:
- Bank: latest non-null balance per ``BankStatement.bank_name`` from
  ``BankStatementTransaction``.
- Investment: sum of ``InvestmentHolding.current_value`` per
  ``InvestmentPortfolio`` (skipped silently if the investments plugin is
  not installed).
- Liability: the stored balance on each ``FinancialLiability``.

A snapshot run writes one row per account into ``net_worth_snapshots`` keyed
by today's date. The summary endpoint reads the most recent snapshot date;
the history endpoint reads one row per month-end.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from commercial.networth.models import (
    AccountKind,
    FinancialLiability,
    NetWorthSnapshot,
)
from core.models.models_per_tenant import BankStatement, BankStatementTransaction

logger = logging.getLogger(__name__)


@dataclass
class AccountBalance:
    """One account's contribution to net worth at a point in time."""

    account_kind: str
    label: str
    balance: float
    currency: str
    account_ref: Optional[int] = None


@dataclass
class NetWorthSummary:
    """Net-worth rollup returned to the dashboard widget."""

    snapshot_date: Optional[date]
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    net_worth: float = 0.0
    bank_total: float = 0.0
    investment_total: float = 0.0
    liability_total: float = 0.0
    accounts: List[AccountBalance] = field(default_factory=list)


@dataclass
class SnapshotResult:
    """Outcome of a capture_snapshot run."""

    snapshot_date: date
    rows_written: int
    summary: NetWorthSummary


@dataclass
class HistoryPoint:
    """One month-end data point for the history chart."""

    snapshot_date: date
    total_assets: float
    total_liabilities: float
    net_worth: float


# ---------------------------------------------------------------------------
# Snapshot capture
# ---------------------------------------------------------------------------


def capture_snapshot(
    db: Session, *, user_id: Optional[int] = None
) -> SnapshotResult:
    """Compute current balances and persist them as a new snapshot run."""
    today = date.today()
    balances = _collect_current_balances(db)

    # Replace any rows already written today so the manual button is
    # idempotent within a single day.
    db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.snapshot_date == today
    ).delete(synchronize_session=False)

    for bal in balances:
        db.add(
            NetWorthSnapshot(
                snapshot_date=today,
                account_kind=bal.account_kind,
                account_ref=bal.account_ref,
                label=bal.label,
                balance=bal.balance,
                currency=bal.currency,
            )
        )

    db.commit()
    summary = _summarize(today, balances)
    return SnapshotResult(
        snapshot_date=today, rows_written=len(balances), summary=summary
    )


def capture_snapshot_after_statement_import(
    db: Session, *, user_id: Optional[int] = None
) -> Optional[SnapshotResult]:
    """Auto-trigger entry point for the bank-statement import flow.

    Swallows exceptions so detection failures never break ingestion.
    """
    try:
        return capture_snapshot(db, user_id=user_id)
    except Exception:  # noqa: BLE001
        logger.exception("Net-worth auto-snapshot failed after statement import")
        return None


# ---------------------------------------------------------------------------
# Read-side helpers
# ---------------------------------------------------------------------------


def build_summary(db: Session) -> NetWorthSummary:
    """Return the most recent snapshot as a summary. Returns an empty
    summary if no snapshot has been captured yet."""
    latest_date = (
        db.query(NetWorthSnapshot.snapshot_date)
        .order_by(desc(NetWorthSnapshot.snapshot_date))
        .limit(1)
        .scalar()
    )
    if latest_date is None:
        return NetWorthSummary(snapshot_date=None)

    rows = (
        db.query(NetWorthSnapshot)
        .filter(NetWorthSnapshot.snapshot_date == latest_date)
        .all()
    )
    balances = [
        AccountBalance(
            account_kind=r.account_kind,
            label=r.label,
            balance=float(r.balance or 0.0),
            currency=r.currency or "USD",
            account_ref=r.account_ref,
        )
        for r in rows
    ]
    return _summarize(latest_date, balances)


def history_by_month(db: Session, *, months: int = 12) -> List[HistoryPoint]:
    """Return one HistoryPoint per snapshot_date, newest last, capped at
    ``months`` most-recent distinct dates."""
    rows = (
        db.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.snapshot_date.asc())
        .all()
    )
    by_date: dict[date, list[NetWorthSnapshot]] = {}
    for r in rows:
        by_date.setdefault(r.snapshot_date, []).append(r)

    points: List[HistoryPoint] = []
    for snap_date in sorted(by_date.keys()):
        rs = by_date[snap_date]
        assets = sum(
            float(r.balance or 0.0)
            for r in rs
            if r.account_kind in (AccountKind.BANK.value, AccountKind.INVESTMENT.value)
        )
        liabilities = sum(
            float(r.balance or 0.0)
            for r in rs
            if r.account_kind == AccountKind.LIABILITY.value
        )
        points.append(
            HistoryPoint(
                snapshot_date=snap_date,
                total_assets=round(assets, 2),
                total_liabilities=round(liabilities, 2),
                net_worth=round(assets - liabilities, 2),
            )
        )

    if months > 0:
        points = points[-months:]
    return points


# ---------------------------------------------------------------------------
# Internal balance collection
# ---------------------------------------------------------------------------


def _collect_current_balances(db: Session) -> List[AccountBalance]:
    out: List[AccountBalance] = []
    out.extend(_bank_balances(db))
    out.extend(_investment_balances(db))
    out.extend(_liability_balances(db))
    return out


def _bank_balances(db: Session) -> List[AccountBalance]:
    """Latest non-null balance per ``BankStatement.bank_name``.

    Why bank_name and not statement_id: BankStatement is one upload, but a
    user has many statements from the same physical account over time. The
    bank_name string is the closest stable handle we have for "an account".
    """
    rows = (
        db.query(
            BankStatement.bank_name,
            BankStatementTransaction.balance,
            BankStatementTransaction.date,
        )
        .join(
            BankStatementTransaction,
            BankStatementTransaction.statement_id == BankStatement.id,
        )
        .filter(
            BankStatement.is_deleted.is_(False),
            BankStatementTransaction.balance.isnot(None),
        )
        .order_by(BankStatementTransaction.date.desc())
        .all()
    )

    latest: dict[str, float] = {}
    for bank_name, balance, _txn_date in rows:
        key = (bank_name or "Unknown Bank").strip() or "Unknown Bank"
        if key in latest:
            continue
        latest[key] = float(balance or 0.0)

    return [
        AccountBalance(
            account_kind=AccountKind.BANK.value,
            label=label,
            balance=round(bal, 2),
            currency="USD",
        )
        for label, bal in latest.items()
    ]


def _investment_balances(db: Session) -> List[AccountBalance]:
    """Sum InvestmentHolding.current_value per non-archived portfolio.

    Returns empty list if the investments plugin is not installed.
    """
    try:
        from plugins.investments.models import InvestmentPortfolio
    except ImportError:
        return []

    portfolios = (
        db.query(InvestmentPortfolio)
        .filter(InvestmentPortfolio.is_archived.is_(False))
        .all()
    )
    out: List[AccountBalance] = []
    for portfolio in portfolios:
        total = 0.0
        for holding in portfolio.holdings:
            try:
                total += float(holding.current_value)
            except (TypeError, ValueError):
                continue
        out.append(
            AccountBalance(
                account_kind=AccountKind.INVESTMENT.value,
                label=str(portfolio.name) if portfolio.name else f"Portfolio {portfolio.id}",
                balance=round(total, 2),
                currency=portfolio.currency or "USD",
                account_ref=portfolio.id,
            )
        )
    return out


def _liability_balances(db: Session) -> List[AccountBalance]:
    rows = db.query(FinancialLiability).all()
    return [
        AccountBalance(
            account_kind=AccountKind.LIABILITY.value,
            label=row.name,
            balance=round(float(row.balance or 0.0), 2),
            currency=row.currency or "USD",
            account_ref=row.id,
        )
        for row in rows
    ]


def _summarize(snap_date: date, balances: List[AccountBalance]) -> NetWorthSummary:
    bank_total = sum(
        b.balance for b in balances if b.account_kind == AccountKind.BANK.value
    )
    investment_total = sum(
        b.balance
        for b in balances
        if b.account_kind == AccountKind.INVESTMENT.value
    )
    liability_total = sum(
        b.balance
        for b in balances
        if b.account_kind == AccountKind.LIABILITY.value
    )
    total_assets = bank_total + investment_total
    return NetWorthSummary(
        snapshot_date=snap_date,
        total_assets=round(total_assets, 2),
        total_liabilities=round(liability_total, 2),
        net_worth=round(total_assets - liability_total, 2),
        bank_total=round(bank_total, 2),
        investment_total=round(investment_total, 2),
        liability_total=round(liability_total, 2),
        accounts=balances,
    )


__all__ = [
    "AccountBalance",
    "HistoryPoint",
    "NetWorthSummary",
    "SnapshotResult",
    "build_summary",
    "capture_snapshot",
    "capture_snapshot_after_statement_import",
    "history_by_month",
]
