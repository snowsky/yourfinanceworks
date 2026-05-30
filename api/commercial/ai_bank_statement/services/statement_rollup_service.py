"""Statement rollup expense service.

Aggregates all debit transactions on a bank statement into a single bookkeeping
Expense. The rollup's amount sums every debit (including those that already have
their own per-transaction Expense link); already-linked transactions are noted
in the rollup's notes so the bookkeeper can reconcile.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from core.constants.expense_status import ExpenseStatus
from core.models.models_per_tenant import (
    BankStatement,
    BankStatementTransaction,
    Expense,
)
from core.utils.money import sum_money
from core.utils.timezone import get_tenant_timezone_aware_datetime


ROLLUP_CATEGORY = "Statement Rollup"
ROLLUP_MARKER_LABEL = "auto-imported"
STATEMENT_LABEL_PREFIX = "statement:"
MAX_LABELS = 10


class RollupConflict(Exception):
    """Raised when a rollup already exists for the statement and replace=False."""

    def __init__(self, existing_expense_id: int):
        super().__init__(f"Rollup already exists (expense {existing_expense_id})")
        self.existing_expense_id = existing_expense_id


class StatementNotFound(Exception):
    pass


class NoDebitsFound(Exception):
    pass


@dataclass(frozen=True)
class DebitRow:
    transaction_id: int
    date: datetime
    description: str
    amount: float
    category: Optional[str]
    linked_expense_id: Optional[int]


@dataclass(frozen=True)
class RollupPreview:
    statement: BankStatement
    debits: List[DebitRow]
    total: float
    currency: str
    latest_date: Optional[datetime]
    auto_labels: List[str]
    notes: str
    existing_rollup_id: Optional[int]


def _get_statement(db: Session, statement_id: int) -> BankStatement:
    statement = (
        db.query(BankStatement)
        .filter(BankStatement.id == statement_id, BankStatement.is_deleted.is_(False))
        .first()
    )
    if not statement:
        raise StatementNotFound(f"Statement {statement_id} not found")
    return statement


def _get_debit_rows(db: Session, statement_id: int) -> List[DebitRow]:
    txs = (
        db.query(BankStatementTransaction)
        .filter(
            BankStatementTransaction.statement_id == statement_id,
            BankStatementTransaction.transaction_type == "debit",
        )
        .order_by(BankStatementTransaction.date.asc(), BankStatementTransaction.id.asc())
        .all()
    )
    return [
        DebitRow(
            transaction_id=tx.id,
            date=tx.date if isinstance(tx.date, datetime) else datetime.combine(tx.date, datetime.min.time()),
            description=tx.description or "",
            # Use magnitude — some banks store debits as negative amounts on the
            # statement. The Expense.amount column represents the outgoing
            # magnitude, mirroring the per-transaction "Create expense" flow
            # which calls Math.abs() in the frontend.
            amount=abs(float(tx.amount or 0)),
            category=tx.category,
            linked_expense_id=tx.expense_id,
        )
        for tx in txs
    ]


def _normalize_labels(raw: List[str]) -> List[str]:
    """Trim, drop blanks, dedupe (case-insensitive), cap at MAX_LABELS, preserve order."""
    seen: set[str] = set()
    out: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        v = item.strip()
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
        if len(out) >= MAX_LABELS:
            break
    return out


def _build_auto_labels(
    statement: BankStatement, debits: List[DebitRow], user_tags: List[str]
) -> List[str]:
    distinct_categories = []
    seen_cats: set[str] = set()
    for d in debits:
        if d.category and d.category not in seen_cats:
            distinct_categories.append(d.category)
            seen_cats.add(d.category)
    # Order: marker, statement ref, distinct categories, user tags.
    # _normalize_labels caps + dedupes; user tags are last so the auto ones survive truncation.
    raw = [
        ROLLUP_MARKER_LABEL,
        f"{STATEMENT_LABEL_PREFIX}{statement.original_filename}",
        *distinct_categories,
        *user_tags,
    ]
    return _normalize_labels(raw)


def _escape_md_cell(value: str) -> str:
    """Make a string safe to drop into a GFM table cell — escape pipes and newlines."""
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def _build_notes(statement: BankStatement, debits: List[DebitRow]) -> str:
    """Render the rollup notes as GFM markdown.

    Heading + summary list + a table of every included debit. Already-linked
    transactions get a markdown link to their existing Expense.
    """
    header = (
        f"### Bookkeeping rollup\n"
        f"\n"
        f"- **Statement:** {_escape_md_cell(statement.original_filename)}\n"
        f"- **Statement ID:** {statement.id}\n"
        f"- **Debit transactions:** {len(debits)}\n"
    )
    if not debits:
        return f"{header}\n_No debit transactions._"

    table_rows = ["| Date | Description | Amount | Linked expense |", "|---|---|---:|---|"]
    for d in debits:
        date_str = d.date.strftime("%Y-%m-%d")
        linked_cell = (
            f"[Expense #{d.linked_expense_id}](/expenses?id={d.linked_expense_id})"
            if d.linked_expense_id is not None
            else "—"
        )
        table_rows.append(
            f"| {date_str} "
            f"| {_escape_md_cell(d.description)} "
            f"| {d.amount:.2f} "
            f"| {linked_cell} |"
        )
    return f"{header}\n" + "\n".join(table_rows)


def build_preview(
    db: Session, statement_id: int, user_tags: Optional[List[str]] = None
) -> RollupPreview:
    """Compute everything the modal needs to render — does not create anything."""
    statement = _get_statement(db, statement_id)
    debits = _get_debit_rows(db, statement_id)
    user_tags = user_tags or []

    # Decimal accumulation rounded to cents — this total is persisted to Expense.amount,
    # so float drift (0.1 + 0.2 -> 0.30000000000000004) must not leak into it.
    total = sum_money(d.amount for d in debits)
    # BankStatement has no currency column today; default USD. Override via future schema.
    currency = "USD"
    latest_date: Optional[datetime] = max((d.date for d in debits), default=None)
    auto_labels = _build_auto_labels(statement, debits, user_tags)
    notes = _build_notes(statement, debits)

    return RollupPreview(
        statement=statement,
        debits=debits,
        total=total,
        currency=currency,
        latest_date=latest_date,
        auto_labels=auto_labels,
        notes=notes,
        existing_rollup_id=statement.rollup_expense_id,
    )


@dataclass(frozen=True)
class RollupResult:
    expense: Expense
    debit_count: int


def create_rollup_expense(
    db: Session,
    statement_id: int,
    user_id: int,
    user_tags: Optional[List[str]] = None,
    replace: bool = False,
) -> RollupResult:
    """Create (or replace) the rollup Expense for a statement.

    Raises:
        StatementNotFound: statement missing or soft-deleted.
        NoDebitsFound: statement has zero debit transactions.
        RollupConflict: a rollup already exists and replace=False.
    """
    preview = build_preview(db, statement_id, user_tags)

    if not preview.debits:
        raise NoDebitsFound(f"Statement {statement_id} has no debit transactions")

    statement = preview.statement

    if statement.rollup_expense_id is not None:
        # Verify the linked rollup still exists and is not soft-deleted.
        existing = (
            db.query(Expense)
            .filter(Expense.id == statement.rollup_expense_id, Expense.is_deleted.is_(False))
            .first()
        )
        if existing is not None:
            if not replace:
                raise RollupConflict(existing_expense_id=existing.id)
            now = get_tenant_timezone_aware_datetime(db)
            existing.is_deleted = True
            existing.deleted_at = now
            existing.deleted_by = user_id
            db.flush()

    now = get_tenant_timezone_aware_datetime(db)
    rollup = Expense(
        amount=preview.total,
        currency=preview.currency,
        expense_date=preview.latest_date or now,
        category=ROLLUP_CATEGORY,
        vendor=statement.bank_name,
        labels=preview.auto_labels,
        status=ExpenseStatus.RECORDED.value,
        notes=preview.notes,
        user_id=user_id,
        created_by_user_id=user_id,
        imported_from_attachment=False,
        analysis_status="not_started",
        created_at=now,
        updated_at=now,
    )
    db.add(rollup)
    db.flush()

    statement.rollup_expense_id = rollup.id
    db.commit()
    db.refresh(rollup)
    return RollupResult(expense=rollup, debit_count=len(preview.debits))
