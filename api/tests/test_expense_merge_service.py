"""Tests for the expense merge service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pytest

from core.models.models_per_tenant import Expense, ExpenseAttachment
from core.services.expense_merge_service import (
    MAX_MERGE,
    MIN_MERGE,
    MergeValidationError,
    build_merge_preview,
    merge_expenses,
)


@pytest.fixture(autouse=True)
def _cleanup_merge_tables(db_session):
    """Clear expenses + attachments before global teardown to avoid FK violations."""
    yield
    db_session.query(ExpenseAttachment).delete()
    db_session.query(Expense).delete()
    db_session.commit()


def _make_expense(
    db_session,
    sample_user,
    *,
    amount: float = 10.0,
    currency: str = "USD",
    category: Optional[str] = "Meals",
    vendor: Optional[str] = "Test Vendor",
    labels: Optional[List[str]] = None,
    when: Optional[datetime] = None,
) -> Expense:
    now = datetime.now(timezone.utc)
    e = Expense(
        amount=amount,
        currency=currency,
        expense_date=when or now,
        category=category,
        vendor=vendor,
        labels=labels,
        status="recorded",
        user_id=sample_user.id,
        created_by_user_id=sample_user.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


def _attach(db_session, expense_id: int, filename: str = "r.pdf") -> ExpenseAttachment:
    a = ExpenseAttachment(
        expense_id=expense_id,
        filename=filename,
        content_type="application/pdf",
        file_size=1024,
        file_path=f"/storage/{expense_id}/{filename}",
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


# ─── happy path ──────────────────────────────────────────────────────────────


def test_merge_sums_amount_and_keeps_currency(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user, amount=10.0)
    e2 = _make_expense(db_session, sample_user, amount=15.5)
    e3 = _make_expense(db_session, sample_user, amount=4.5)

    merged = merge_expenses(db_session, [e1.id, e2.id, e3.id], sample_user.id)

    assert merged.amount == pytest.approx(30.0)
    assert merged.currency == "USD"
    assert merged.id not in (e1.id, e2.id, e3.id)


def test_sources_are_soft_deleted(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user, amount=10)
    e2 = _make_expense(db_session, sample_user, amount=20)

    merged = merge_expenses(db_session, [e1.id, e2.id], sample_user.id)

    for src_id in (e1.id, e2.id):
        src = db_session.query(Expense).filter(Expense.id == src_id).first()
        assert src is not None  # still there
        assert src.is_deleted is True
        assert src.deleted_by == sample_user.id
        assert src.deleted_at is not None
    # Merged expense is alive
    assert merged.is_deleted is False


def test_attachments_relinked_to_merged(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user)
    e2 = _make_expense(db_session, sample_user)
    a1 = _attach(db_session, e1.id, "a.pdf")
    a2 = _attach(db_session, e2.id, "b.pdf")
    a3 = _attach(db_session, e2.id, "c.pdf")

    merged = merge_expenses(db_session, [e1.id, e2.id], sample_user.id)

    attachments = (
        db_session.query(ExpenseAttachment)
        .filter(ExpenseAttachment.expense_id == merged.id)
        .order_by(ExpenseAttachment.id)
        .all()
    )
    assert {a.id for a in attachments} == {a1.id, a2.id, a3.id}


def test_labels_unioned_deduped_capped(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user, labels=["travel", "Q1"])
    e2 = _make_expense(db_session, sample_user, labels=["TRAVEL", "client-x"])  # case dup
    e3 = _make_expense(db_session, sample_user, labels=[f"t{i}" for i in range(20)])

    merged = merge_expenses(
        db_session, [e1.id, e2.id, e3.id], sample_user.id, user_tags=["q1-trip"]
    )

    assert len(merged.labels) <= 10
    # Earlier source labels survive truncation
    assert "travel" in [l.lower() for l in merged.labels]
    assert "Q1" in merged.labels


def test_category_mode_with_tiebreak_to_first(db_session, sample_user):
    e_meals_1 = _make_expense(db_session, sample_user, category="Meals")
    e_transport = _make_expense(db_session, sample_user, category="Transportation")
    e_meals_2 = _make_expense(db_session, sample_user, category="Meals")

    merged = merge_expenses(
        db_session, [e_meals_1.id, e_transport.id, e_meals_2.id], sample_user.id
    )
    # Meals appears twice → mode
    assert merged.category == "Meals"


def test_category_mode_tiebreak_prefers_earlier_selection(db_session, sample_user):
    e_a = _make_expense(db_session, sample_user, category="A")
    e_b = _make_expense(db_session, sample_user, category="B")

    merged = merge_expenses(db_session, [e_b.id, e_a.id], sample_user.id)
    # 1-1 tie → first by selection order (e_b was first)
    assert merged.category == "B"


def test_latest_date_used(db_session, sample_user):
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = datetime(2026, 3, 15, tzinfo=timezone.utc)
    e1 = _make_expense(db_session, sample_user, when=earlier)
    e2 = _make_expense(db_session, sample_user, when=later)

    merged = merge_expenses(db_session, [e1.id, e2.id], sample_user.id)
    assert merged.expense_date == later


# ─── notes ────────────────────────────────────────────────────────────────────


def test_notes_contain_markdown_table_with_backlinks(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user, amount=7.40, vendor="STARBUCKS")
    e2 = _make_expense(db_session, sample_user, amount=12.00, vendor="UBER")

    merged = merge_expenses(
        db_session,
        [e1.id, e2.id],
        sample_user.id,
        notes_prefix="Lunch + ride back",
    )
    notes = merged.notes
    assert notes.startswith("### Merged expense")
    assert "Lunch + ride back" in notes
    assert "| Source | Date | Vendor | Amount |" in notes
    assert f"[Expense #{e1.id}](/expenses?id={e1.id})" in notes
    assert f"[Expense #{e2.id}](/expenses?id={e2.id})" in notes
    # Amounts rendered at 2dp
    assert "7.40" in notes
    assert "12.00" in notes


def test_pipe_in_vendor_is_escaped(db_session, sample_user):
    weird = _make_expense(db_session, sample_user, vendor="A|B Inc.")
    other = _make_expense(db_session, sample_user)
    merged = merge_expenses(db_session, [weird.id, other.id], sample_user.id)
    assert "A\\|B Inc." in merged.notes


# ─── validation ──────────────────────────────────────────────────────────────


def test_currency_mismatch_blocks(db_session, sample_user):
    usd = _make_expense(db_session, sample_user, currency="USD")
    cad = _make_expense(db_session, sample_user, currency="CAD")
    with pytest.raises(MergeValidationError) as exc:
        merge_expenses(db_session, [usd.id, cad.id], sample_user.id)
    assert exc.value.code == "currency_mismatch"


def test_too_few_blocks(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user)
    with pytest.raises(MergeValidationError) as exc:
        merge_expenses(db_session, [e1.id], sample_user.id)
    assert exc.value.code == "too_few"


def test_too_many_blocks(db_session, sample_user):
    ids = [_make_expense(db_session, sample_user, amount=1).id for _ in range(MAX_MERGE + 1)]
    with pytest.raises(MergeValidationError) as exc:
        merge_expenses(db_session, ids, sample_user.id)
    assert exc.value.code == "too_many"


def test_duplicate_ids_blocks(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user)
    e2 = _make_expense(db_session, sample_user)
    with pytest.raises(MergeValidationError) as exc:
        merge_expenses(db_session, [e1.id, e2.id, e1.id], sample_user.id)
    assert exc.value.code == "duplicate_ids"


def test_missing_or_deleted_source_blocks(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user)
    e2 = _make_expense(db_session, sample_user)
    # Soft-delete e2 before attempting the merge
    e2.is_deleted = True
    db_session.commit()

    with pytest.raises(MergeValidationError) as exc:
        merge_expenses(db_session, [e1.id, e2.id], sample_user.id)
    assert exc.value.code == "not_found"


# ─── preview (no persistence) ────────────────────────────────────────────────


def test_preview_does_not_persist(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user, amount=10)
    e2 = _make_expense(db_session, sample_user, amount=15)
    initial_count = db_session.query(Expense).count()

    preview = build_merge_preview(db_session, [e1.id, e2.id])

    assert preview.total == pytest.approx(25.0)
    assert len(preview.sources) == 2
    # Same count after preview
    assert db_session.query(Expense).count() == initial_count
    # Neither source is soft-deleted
    db_session.refresh(e1)
    db_session.refresh(e2)
    assert e1.is_deleted is False
    assert e2.is_deleted is False


def test_min_merge_constant():
    assert MIN_MERGE == 2


# ─── keep_sources mode ────────────────────────────────────────────────────────


def test_keep_sources_leaves_originals_alive(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user, amount=10)
    e2 = _make_expense(db_session, sample_user, amount=20)

    merged = merge_expenses(
        db_session, [e1.id, e2.id], sample_user.id, keep_sources=True
    )

    # Sources still alive
    for src_id in (e1.id, e2.id):
        src = db_session.query(Expense).filter(Expense.id == src_id).first()
        assert src is not None
        assert src.is_deleted is False
        assert src.deleted_at is None
        assert src.deleted_by is None
    # Merged is also alive (and is a different row)
    assert merged.is_deleted is False
    assert merged.id not in (e1.id, e2.id)
    # Amount still summed
    assert merged.amount == pytest.approx(30.0)


def test_keep_sources_duplicates_attachments(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user)
    e2 = _make_expense(db_session, sample_user)
    _attach(db_session, e1.id, "a.pdf")
    _attach(db_session, e2.id, "b.pdf")
    _attach(db_session, e2.id, "c.pdf")
    assert db_session.query(ExpenseAttachment).count() == 3

    merged = merge_expenses(
        db_session, [e1.id, e2.id], sample_user.id, keep_sources=True
    )

    # 3 source rows + 3 duplicated rows on the merged expense = 6 total
    total = db_session.query(ExpenseAttachment).count()
    assert total == 6

    # Sources keep their attachments
    src_attachments = (
        db_session.query(ExpenseAttachment)
        .filter(ExpenseAttachment.expense_id.in_([e1.id, e2.id]))
        .all()
    )
    assert len(src_attachments) == 3

    # Merged expense has the duplicates
    merged_attachments = (
        db_session.query(ExpenseAttachment)
        .filter(ExpenseAttachment.expense_id == merged.id)
        .order_by(ExpenseAttachment.filename.asc())
        .all()
    )
    assert [a.filename for a in merged_attachments] == ["a.pdf", "b.pdf", "c.pdf"]
    # file_path is shared with the originals (no file copy)
    src_paths = {a.file_path for a in src_attachments}
    merged_paths = {a.file_path for a in merged_attachments}
    assert merged_paths == src_paths


def test_keep_sources_notes_reflect_disposition(db_session, sample_user):
    e1 = _make_expense(db_session, sample_user, amount=10)
    e2 = _make_expense(db_session, sample_user, amount=20)

    kept = merge_expenses(
        db_session, [e1.id, e2.id], sample_user.id, keep_sources=True
    )
    assert "kept (visible alongside this expense)" in kept.notes

    # Reset for the consolidate variant
    db_session.query(ExpenseAttachment).delete()
    db_session.query(Expense).delete()
    db_session.commit()

    e3 = _make_expense(db_session, sample_user, amount=10)
    e4 = _make_expense(db_session, sample_user, amount=20)
    consolidated = merge_expenses(db_session, [e3.id, e4.id], sample_user.id)
    assert "moved to the recycle bin" in consolidated.notes


def test_default_still_consolidates(db_session, sample_user):
    """Regression: keep_sources defaults False, behavior unchanged from PR-1."""
    e1 = _make_expense(db_session, sample_user)
    _attach(db_session, e1.id, "only.pdf")
    e2 = _make_expense(db_session, sample_user)

    merged = merge_expenses(db_session, [e1.id, e2.id], sample_user.id)

    # Sources soft-deleted
    db_session.refresh(e1)
    assert e1.is_deleted is True
    # Attachment moved (not duplicated) — total still 1
    assert db_session.query(ExpenseAttachment).count() == 1
    sole = db_session.query(ExpenseAttachment).first()
    assert sole.expense_id == merged.id
