"""Expense merge service.

Consolidates 2..50 selected expenses into one new Expense whose amount is the
sum of the sources. Source expenses are soft-deleted (visible in the recycle
bin, restorable). Source attachments are re-linked to the merged expense.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from core.constants.expense_status import ExpenseStatus
from core.models.models_per_tenant import Expense, ExpenseAttachment
from core.utils.timezone import get_tenant_timezone_aware_datetime

MIN_MERGE = 2
MAX_MERGE = 50
MAX_LABELS = 10


class MergeValidationError(Exception):
    """Raised when the requested merge cannot proceed (4xx)."""

    def __init__(self, message: str, *, code: str = "merge_invalid"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SourceRow:
    id: int
    expense_date: datetime
    vendor: Optional[str]
    amount: float
    category: Optional[str]
    currency: str
    labels: List[str]
    notes: Optional[str]


@dataclass(frozen=True)
class MergePreview:
    sources: List[SourceRow]
    total: float
    currency: str
    latest_date: datetime
    category: Optional[str]
    vendor: Optional[str]
    labels: List[str]
    notes: str


def _normalize_labels(raw: List[str]) -> List[str]:
    """Trim, drop blanks, case-insensitive dedupe, cap at MAX_LABELS."""
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


def _mode_with_tiebreak(values: List[Tuple[int, Optional[str]]]) -> Optional[str]:
    """Return the most-frequent non-empty value. On ties, the first by source order.

    `values` is a list of (source_id_order_index, value) — already ordered by selection.
    """
    counter: Counter[str] = Counter()
    first_index: dict[str, int] = {}
    for idx, val in values:
        if not val:
            continue
        counter[val] += 1
        first_index.setdefault(val, idx)
    if not counter:
        return None
    # Highest count, tie -> earliest first_index
    return max(counter.items(), key=lambda kv: (kv[1], -first_index[kv[0]]))[0]


def _escape_md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def _build_notes(
    sources: List[SourceRow],
    user_prefix: Optional[str],
    keep_sources: bool = False,
) -> str:
    header_block = "### Merged expense\n"
    if user_prefix and user_prefix.strip():
        header_block += f"\n{user_prefix.strip()}\n"
    disposition = (
        "kept (visible alongside this expense)"
        if keep_sources
        else "moved to the recycle bin"
    )
    summary_lines = [
        "",
        f"- **Source expenses merged:** {len(sources)}",
        f"- **Currency:** {sources[0].currency}",
        f"- **Sources:** {disposition}",
        "",
    ]
    table_rows = [
        "| Source | Date | Vendor | Amount |",
        "|---|---|---|---:|",
    ]
    for s in sources:
        vendor = _escape_md_cell(s.vendor or "—")
        date_str = s.expense_date.strftime("%Y-%m-%d") if s.expense_date else "—"
        table_rows.append(
            f"| [Expense #{s.id}](/expenses?id={s.id}) "
            f"| {date_str} "
            f"| {vendor} "
            f"| {s.amount:.2f} |"
        )
    return header_block + "\n".join(summary_lines + table_rows)


def _load_sources(db: Session, expense_ids: List[int]) -> List[SourceRow]:
    """Fetch sources in the user-supplied order and validate they all exist + are alive."""
    if len(expense_ids) < MIN_MERGE:
        raise MergeValidationError(
            f"At least {MIN_MERGE} expenses are required to merge.",
            code="too_few",
        )
    if len(expense_ids) > MAX_MERGE:
        raise MergeValidationError(
            f"At most {MAX_MERGE} expenses can be merged at once.",
            code="too_many",
        )
    if len(set(expense_ids)) != len(expense_ids):
        raise MergeValidationError("Duplicate expense ids in request.", code="duplicate_ids")

    rows = (
        db.query(Expense)
        .filter(Expense.id.in_(expense_ids), Expense.is_deleted.is_(False))
        .all()
    )
    by_id = {r.id: r for r in rows}
    missing = [eid for eid in expense_ids if eid not in by_id]
    if missing:
        raise MergeValidationError(
            f"Expenses not found or already deleted: {missing}",
            code="not_found",
        )

    sources: List[SourceRow] = []
    for eid in expense_ids:
        e = by_id[eid]
        sources.append(
            SourceRow(
                id=e.id,
                expense_date=e.expense_date,
                vendor=e.vendor,
                amount=float(e.amount or 0),
                category=e.category,
                currency=e.currency or "USD",
                labels=list(e.labels) if isinstance(e.labels, list) else [],
                notes=e.notes,
            )
        )
    return sources


def build_merge_preview(
    db: Session,
    expense_ids: List[int],
    user_tags: Optional[List[str]] = None,
    notes_prefix: Optional[str] = None,
    keep_sources: bool = False,
) -> MergePreview:
    """Validate selection and compute the merged record. Does not persist."""
    sources = _load_sources(db, expense_ids)

    currencies = {s.currency for s in sources}
    if len(currencies) > 1:
        raise MergeValidationError(
            f"Cannot merge expenses with different currencies: {sorted(currencies)}",
            code="currency_mismatch",
        )
    currency = sources[0].currency

    total = sum(s.amount for s in sources)
    latest_date = max(s.expense_date for s in sources)

    indexed_categories = [(i, s.category) for i, s in enumerate(sources)]
    indexed_vendors = [(i, s.vendor) for i, s in enumerate(sources)]
    category = _mode_with_tiebreak(indexed_categories)
    vendor = _mode_with_tiebreak(indexed_vendors)

    union_labels: List[str] = []
    for s in sources:
        union_labels.extend(s.labels)
    if user_tags:
        union_labels.extend(user_tags)
    labels = _normalize_labels(union_labels)

    notes = _build_notes(sources, notes_prefix, keep_sources=keep_sources)

    return MergePreview(
        sources=sources,
        total=total,
        currency=currency,
        latest_date=latest_date,
        category=category,
        vendor=vendor,
        labels=labels,
        notes=notes,
    )


def merge_expenses(
    db: Session,
    expense_ids: List[int],
    user_id: int,
    user_tags: Optional[List[str]] = None,
    notes_prefix: Optional[str] = None,
    keep_sources: bool = False,
) -> Expense:
    """Create the merged Expense.

    When `keep_sources` is False (default), source expenses are soft-deleted and
    their attachments are re-pointed at the merged expense.

    When `keep_sources` is True, sources stay alive and their attachments are
    DUPLICATED at the row level — new ExpenseAttachment rows pointing at the
    same `file_path` — so both sources and merged surface the same receipts.

    Raises MergeValidationError on any precondition failure (caller maps to 400).
    """
    preview = build_merge_preview(
        db, expense_ids, user_tags, notes_prefix, keep_sources=keep_sources
    )
    now = get_tenant_timezone_aware_datetime(db)

    merged = Expense(
        amount=preview.total,
        currency=preview.currency,
        expense_date=preview.latest_date,
        category=preview.category or "Merged",
        vendor=preview.vendor,
        labels=preview.labels,
        status=ExpenseStatus.RECORDED.value,
        notes=preview.notes,
        user_id=user_id,
        created_by_user_id=user_id,
        imported_from_attachment=False,
        analysis_status="not_started",
        created_at=now,
        updated_at=now,
    )
    db.add(merged)
    db.flush()  # need merged.id

    source_ids = [s.id for s in preview.sources]

    if keep_sources:
        # Duplicate attachment rows so the merged expense surfaces the same
        # receipts the sources still show. No file copy — both rows point at
        # the same file_path.
        source_attachments = (
            db.query(ExpenseAttachment)
            .filter(ExpenseAttachment.expense_id.in_(source_ids))
            .all()
        )
        for src in source_attachments:
            db.add(
                ExpenseAttachment(
                    expense_id=merged.id,
                    filename=src.filename,
                    content_type=src.content_type,
                    file_size=src.file_size,
                    file_path=src.file_path,
                    uploaded_at=src.uploaded_at,
                    uploaded_by=src.uploaded_by,
                    analysis_status=src.analysis_status,
                    analysis_result=src.analysis_result,
                )
            )
    else:
        # Re-link every attachment on the sources to the merged expense.
        db.query(ExpenseAttachment).filter(
            ExpenseAttachment.expense_id.in_(source_ids)
        ).update({ExpenseAttachment.expense_id: merged.id}, synchronize_session=False)

        # Soft-delete the sources.
        db.query(Expense).filter(Expense.id.in_(source_ids)).update(
            {
                Expense.is_deleted: True,
                Expense.deleted_at: now,
                Expense.deleted_by: user_id,
            },
            synchronize_session=False,
        )

    db.commit()
    db.refresh(merged)
    return merged
