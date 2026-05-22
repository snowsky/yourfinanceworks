"""Tests for the statement rollup expense service."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

import pytest

from core.models.models_per_tenant import (
    BankStatement,
    BankStatementTransaction,
    Expense,
)
from commercial.ai_bank_statement.services.statement_rollup_service import (
    MAX_LABELS,
    NoDebitsFound,
    ROLLUP_CATEGORY,
    ROLLUP_MARKER_LABEL,
    RollupConflict,
    STATEMENT_LABEL_PREFIX,
    StatementNotFound,
    build_preview,
    create_rollup_expense,
)


@pytest.fixture(autouse=True)
def _cleanup_rollup_tables(db_session):
    """Clear bank_statements + expenses + their children before each test.

    The global conftest teardown deletes MasterBase tables first (which includes
    a 'users' Table declared in both bases that maps to the same physical table),
    so any expense persisted with user_id set would cause an FK violation during
    MasterBase's `DELETE FROM users` step. This local fixture runs first (LIFO
    teardown order) and removes the offending rows before the global cleanup.
    """
    yield
    # Order matches FK dependencies: children before parents.
    for table in (
        BankStatementTransaction,
        BankStatement,
        Expense,
    ):
        db_session.query(table).delete()
    db_session.commit()


def _make_statement(db_session, *, filename: str = "march-2026.pdf", bank_name: Optional[str] = "Test Bank") -> BankStatement:
    now = datetime.now(timezone.utc)
    statement = BankStatement(
        tenant_id=1,
        original_filename=filename,
        stored_filename=filename,
        file_path=f"/tmp/{filename}",
        status="processed",
        extracted_count=0,
        bank_name=bank_name,
        created_at=now,
        updated_at=now,
    )
    db_session.add(statement)
    db_session.commit()
    db_session.refresh(statement)
    return statement


def _add_tx(
    db_session,
    statement_id: int,
    *,
    amount: float,
    tx_type: str = "debit",
    description: str = "TX",
    category: Optional[str] = None,
    when: Optional[date] = None,
    expense_id: Optional[int] = None,
) -> BankStatementTransaction:
    now = datetime.now(timezone.utc)
    tx = BankStatementTransaction(
        statement_id=statement_id,
        date=when or date(2026, 3, 14),
        description=description,
        amount=amount,
        transaction_type=tx_type,
        category=category,
        expense_id=expense_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


def _add_linked_expense(db_session, user_id: int) -> Expense:
    now = datetime.now(timezone.utc)
    e = Expense(
        amount=7.40,
        currency="USD",
        expense_date=now,
        category="Meals",
        vendor="STARBUCKS",
        user_id=user_id,
        created_by_user_id=user_id,
        status="recorded",
        created_at=now,
        updated_at=now,
    )
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


# ─── happy path ──────────────────────────────────────────────────────────────


def test_create_rollup_sums_only_debits(db_session, sample_user):
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=10.0, tx_type="debit", description="A", category="Meals", when=date(2026, 3, 10))
    _add_tx(db_session, statement.id, amount=20.0, tx_type="debit", description="B", category="Transportation", when=date(2026, 3, 12))
    _add_tx(db_session, statement.id, amount=999.0, tx_type="credit", description="Refund", when=date(2026, 3, 14))

    result = create_rollup_expense(db_session, statement.id, sample_user.id, user_tags=[])

    assert result.expense.amount == pytest.approx(30.0)
    assert result.debit_count == 2
    assert result.expense.category == ROLLUP_CATEGORY
    assert result.expense.vendor == "Test Bank"
    # latest_date = max debit date
    assert result.expense.expense_date.date() == date(2026, 3, 12)
    # FK back-link is set
    db_session.refresh(statement)
    assert statement.rollup_expense_id == result.expense.id


def test_labels_include_marker_statement_ref_and_distinct_categories(db_session, sample_user):
    statement = _make_statement(db_session, filename="april.pdf")
    _add_tx(db_session, statement.id, amount=5, category="Meals")
    _add_tx(db_session, statement.id, amount=6, category="Meals")  # dup category
    _add_tx(db_session, statement.id, amount=7, category="Transportation")
    _add_tx(db_session, statement.id, amount=8, category=None)  # untagged

    result = create_rollup_expense(db_session, statement.id, sample_user.id, user_tags=["q1-trip"])

    labels = result.expense.labels
    assert labels[0] == ROLLUP_MARKER_LABEL
    assert f"{STATEMENT_LABEL_PREFIX}april.pdf" in labels
    assert "Meals" in labels
    assert "Transportation" in labels
    assert "q1-trip" in labels
    # category appears once even though two debits use it
    assert labels.count("Meals") == 1


def test_user_tags_deduped_case_insensitively_and_capped(db_session, sample_user):
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=1)
    many_tags = [f"tag{i}" for i in range(20)] + ["TAG1", "tag1"]  # dups
    result = create_rollup_expense(db_session, statement.id, sample_user.id, user_tags=many_tags)

    labels = result.expense.labels
    assert len(labels) <= MAX_LABELS
    # marker + statement-ref must survive truncation (they come first in raw order)
    assert ROLLUP_MARKER_LABEL in labels
    assert any(l.startswith(STATEMENT_LABEL_PREFIX) for l in labels)


# ─── notes formatting ─────────────────────────────────────────────────────────


def test_notes_list_each_debit_and_mark_already_linked(db_session, sample_user):
    statement = _make_statement(db_session)
    prior_expense = _add_linked_expense(db_session, sample_user.id)
    _add_tx(
        db_session,
        statement.id,
        amount=7.40,
        description="STARBUCKS",
        when=date(2026, 3, 14),
        expense_id=prior_expense.id,
    )
    _add_tx(db_session, statement.id, amount=12.00, description="UBER", when=date(2026, 3, 15))

    result = create_rollup_expense(db_session, statement.id, sample_user.id, user_tags=[])

    notes = result.expense.notes
    # Notes are GFM markdown — heading, summary list, then a table row per debit.
    assert notes.startswith("### Bookkeeping rollup")
    assert "| Date | Description | Amount | Linked expense |" in notes
    starbucks_line = next(line for line in notes.splitlines() if "STARBUCKS" in line)
    assert f"[Expense #{prior_expense.id}](/expenses?id={prior_expense.id})" in starbucks_line
    uber_line = next(line for line in notes.splitlines() if "UBER" in line)
    assert "Expense #" not in uber_line  # unlinked → em-dash, not a link
    assert uber_line.rstrip().endswith("— |")
    # Linked txn still counted in the total
    assert result.expense.amount == pytest.approx(19.40)
    assert result.debit_count == 2


# ─── error paths ─────────────────────────────────────────────────────────────


def test_no_debits_raises(db_session, sample_user):
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=5, tx_type="credit", description="ONLY CREDIT")

    with pytest.raises(NoDebitsFound):
        create_rollup_expense(db_session, statement.id, sample_user.id)


def test_missing_statement_raises(db_session, sample_user):
    with pytest.raises(StatementNotFound):
        create_rollup_expense(db_session, 99_999, sample_user.id)


def test_soft_deleted_statement_raises(db_session, sample_user):
    statement = _make_statement(db_session)
    statement.is_deleted = True
    db_session.commit()

    with pytest.raises(StatementNotFound):
        create_rollup_expense(db_session, statement.id, sample_user.id)


# ─── idempotency / replace ───────────────────────────────────────────────────


def test_second_call_without_replace_raises_conflict(db_session, sample_user):
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=10)

    first = create_rollup_expense(db_session, statement.id, sample_user.id)
    with pytest.raises(RollupConflict) as exc_info:
        create_rollup_expense(db_session, statement.id, sample_user.id)
    assert exc_info.value.existing_expense_id == first.expense.id


def test_replace_soft_deletes_old_and_creates_new(db_session, sample_user):
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=10)
    first = create_rollup_expense(db_session, statement.id, sample_user.id)

    _add_tx(db_session, statement.id, amount=25)  # add one more debit
    second = create_rollup_expense(db_session, statement.id, sample_user.id, replace=True)

    assert second.expense.id != first.expense.id
    assert second.expense.amount == pytest.approx(35.0)

    old = db_session.query(Expense).filter(Expense.id == first.expense.id).first()
    assert old is not None
    assert old.is_deleted is True
    assert old.deleted_by == sample_user.id

    db_session.refresh(statement)
    assert statement.rollup_expense_id == second.expense.id


def test_orphaned_rollup_link_allows_new_create(db_session, sample_user):
    """If the previously linked rollup is soft-deleted out of band, a new create should succeed."""
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=10)
    first = create_rollup_expense(db_session, statement.id, sample_user.id)

    # Simulate manual recycle-bin delete of the rollup
    old = db_session.query(Expense).filter(Expense.id == first.expense.id).first()
    old.is_deleted = True
    db_session.commit()

    # Should NOT raise — the linked expense is no longer "alive"
    second = create_rollup_expense(db_session, statement.id, sample_user.id)
    assert second.expense.id != first.expense.id


# ─── preview (no persistence) ────────────────────────────────────────────────


def test_preview_does_not_persist(db_session, sample_user):
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=10, category="Meals")
    _add_tx(db_session, statement.id, amount=15, category="Transportation")

    preview = build_preview(db_session, statement.id, user_tags=["custom"])

    assert preview.total == pytest.approx(25.0)
    assert len(preview.debits) == 2
    assert "Meals" in preview.auto_labels
    assert "custom" in preview.auto_labels
    assert preview.existing_rollup_id is None

    # No expense was persisted
    assert db_session.query(Expense).count() == 0
    db_session.refresh(statement)
    assert statement.rollup_expense_id is None


def test_preview_reports_existing_rollup_id(db_session, sample_user):
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=10)
    first = create_rollup_expense(db_session, statement.id, sample_user.id)

    preview = build_preview(db_session, statement.id, user_tags=[])
    assert preview.existing_rollup_id == first.expense.id


def test_negative_debit_amounts_produce_positive_rollup(db_session, sample_user):
    """Some banks store debits as negative on the statement.

    The Expense.amount column represents the outgoing magnitude, so the rollup
    must take abs() — sum, markdown notes, and preview payload all positive.
    """
    statement = _make_statement(db_session)
    _add_tx(db_session, statement.id, amount=-10.0, tx_type="debit", description="A")
    _add_tx(db_session, statement.id, amount=-20.0, tx_type="debit", description="B")

    result = create_rollup_expense(db_session, statement.id, sample_user.id)

    assert result.expense.amount == pytest.approx(30.0)
    # Per-row table cells should also show positive magnitude (no leading "-")
    for line in result.expense.notes.splitlines():
        if line.startswith("| 2026-") and "|" in line:
            assert "-10.00" not in line
            assert "-20.00" not in line

    # Preview also reports positive
    preview = build_preview(db_session, statement.id, user_tags=[])
    assert preview.total == pytest.approx(30.0)
    assert all(d.amount > 0 for d in preview.debits)
