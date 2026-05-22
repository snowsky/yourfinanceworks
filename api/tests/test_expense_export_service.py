"""Tests for the single-expense PDF + CSV export builders."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pypdf
import pytest


def _pdf_text(raw: bytes) -> str:
    """Extract concatenated text from a PDF byte string for assertions."""
    reader = pypdf.PdfReader(io.BytesIO(raw))
    return "\n".join((page.extract_text() or "") for page in reader.pages)

from core.models.models_per_tenant import Expense, ExpenseAttachment
from core.services.expense_export_service import (
    CSV_COLUMNS,
    build_expense_csv_row,
    build_expense_pdf,
)


def _parse_csv(raw: bytes):
    """Return (header_row, data_row) parsed via the csv module (handles embedded newlines)."""
    reader = csv.reader(io.StringIO(raw.decode("utf-8")))
    rows = list(reader)
    assert len(rows) >= 2, f"expected header + 1 data row, got {len(rows)}: {rows!r}"
    return rows[0], rows[1]


@pytest.fixture(autouse=True)
def _cleanup(db_session):
    yield
    db_session.query(ExpenseAttachment).delete()
    db_session.query(Expense).delete()
    db_session.commit()


def _mk(db_session, sample_user, **overrides) -> Expense:
    now = datetime.now(timezone.utc)
    defaults = dict(
        amount=42.50,
        currency="USD",
        expense_date=now,
        category="Meals",
        vendor="STARBUCKS",
        labels=["coffee", "morning"],
        status="recorded",
        notes="### Notes\n- line 1\n- line 2",
        user_id=sample_user.id,
        created_by_user_id=sample_user.id,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    e = Expense(**defaults)
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


def _attach(db_session, expense_id: int, filename: str) -> ExpenseAttachment:
    a = ExpenseAttachment(
        expense_id=expense_id,
        filename=filename,
        content_type="image/png",
        file_size=2048,
        file_path=f"/storage/{expense_id}/{filename}",
    )
    db_session.add(a)
    db_session.commit()
    return a


# ─── CSV ─────────────────────────────────────────────────────────────────────


def test_csv_has_header_and_one_data_row(db_session, sample_user):
    expense = _mk(db_session, sample_user)
    out = build_expense_csv_row(expense, attachment_count=0)
    header, data = _parse_csv(out)
    assert header == CSV_COLUMNS
    assert data[CSV_COLUMNS.index("id")] == str(expense.id)


def test_csv_attachment_count_reported(db_session, sample_user):
    e = _mk(db_session, sample_user)
    _, data = _parse_csv(build_expense_csv_row(e, attachment_count=3))
    assert data[CSV_COLUMNS.index("attachment_count")] == "3"


def test_csv_amount_formatted_to_two_decimals(db_session, sample_user):
    e = _mk(db_session, sample_user, amount=7.4)
    _, data = _parse_csv(build_expense_csv_row(e, attachment_count=0))
    assert data[CSV_COLUMNS.index("amount")] == "7.40"


def test_csv_labels_semicolon_joined(db_session, sample_user):
    e = _mk(db_session, sample_user, labels=["a", "b", "c"])
    _, data = _parse_csv(build_expense_csv_row(e, attachment_count=0))
    assert data[CSV_COLUMNS.index("labels")] == "a;b;c"


def test_csv_handles_missing_labels(db_session, sample_user):
    e = _mk(db_session, sample_user, labels=None)
    _, data = _parse_csv(build_expense_csv_row(e, attachment_count=0))
    assert data[CSV_COLUMNS.index("labels")] == ""


# ─── PDF ─────────────────────────────────────────────────────────────────────


def test_pdf_returns_nonempty_bytes(db_session, sample_user):
    e = _mk(db_session, sample_user)
    pdf = build_expense_pdf(e, attachments=[])
    assert isinstance(pdf, bytes)
    assert len(pdf) > 500
    assert pdf.startswith(b"%PDF-")


def test_pdf_includes_attachment_list_when_present(db_session, sample_user):
    e = _mk(db_session, sample_user)
    _attach(db_session, e.id, "receipt.png")
    _attach(db_session, e.id, "second.pdf")
    attachments = (
        db_session.query(ExpenseAttachment)
        .filter(ExpenseAttachment.expense_id == e.id)
        .order_by(ExpenseAttachment.id.asc())
        .all()
    )
    pdf = build_expense_pdf(e, attachments=attachments)
    text = _pdf_text(pdf)
    assert "receipt.png" in text
    assert "second.pdf" in text


def test_pdf_renders_with_zero_attachments(db_session, sample_user):
    e = _mk(db_session, sample_user)
    pdf = build_expense_pdf(e, attachments=[])
    assert pdf.startswith(b"%PDF-")
    assert "No attachments" in _pdf_text(pdf)


def test_pdf_shows_vendor_amount_and_expense_id(db_session, sample_user):
    e = _mk(db_session, sample_user, vendor="STARBUCKS", amount=42.5, currency="USD")
    text = _pdf_text(build_expense_pdf(e, attachments=[]))
    assert "STARBUCKS" in text
    assert f"#{e.id}" in text
    assert "42.50" in text and "USD" in text


def test_pdf_handles_missing_optional_fields(db_session, sample_user):
    # `category` is NOT NULL on the model, so leave it populated; everything else nullable.
    e = _mk(
        db_session,
        sample_user,
        vendor=None,
        labels=None,
        notes=None,
        payment_method=None,
        reference_number=None,
    )
    pdf = build_expense_pdf(e, attachments=[])
    assert pdf.startswith(b"%PDF-")
