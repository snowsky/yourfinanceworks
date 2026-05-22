"""Per-expense export endpoints (PDF + CSV)."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import Expense, ExpenseAttachment
from core.routers.auth import get_current_user
from core.services.expense_export_service import (
    build_expense_csv_row,
    build_expense_pdf,
)
from core.utils.audit import log_audit_event
from core.utils.rbac import require_non_viewer

logger = logging.getLogger(__name__)
router = APIRouter()


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _filename_stem(expense: Expense) -> str:
    base = expense.vendor or f"expense-{expense.id}"
    stem = _SAFE_FILENAME_RE.sub("-", base).strip("-").lower() or f"expense-{expense.id}"
    return f"{stem}-{expense.id}"


def _load_alive_expense(db: Session, expense_id: int) -> Expense:
    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.is_deleted.is_(False))
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.get("/{expense_id}/export.pdf")
async def export_expense_pdf(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """One-page receipt-style PDF of a single expense.

    Attachment filenames are listed, but attachment bytes are NOT embedded.
    The response sets `X-Export-Notice: attachments-not-embedded` so clients
    can surface a "ZIP bundle coming soon" hint.
    """
    require_non_viewer(current_user, "export expense as PDF")
    expense = _load_alive_expense(db, expense_id)
    attachments = (
        db.query(ExpenseAttachment)
        .filter(ExpenseAttachment.expense_id == expense_id)
        .order_by(ExpenseAttachment.id.asc())
        .all()
    )
    pdf_bytes = build_expense_pdf(expense, attachments)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="EXPORT",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=f"Expense #{expense.id} PDF export",
        details={"format": "pdf", "attachment_count": len(attachments)},
        status="success",
    )

    filename = f"{_filename_stem(expense)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Notice": "attachments-not-embedded",
        },
    )


@router.get("/{expense_id}/export.csv")
async def export_expense_csv(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Single-row CSV for the given expense, including an attachment_count column."""
    require_non_viewer(current_user, "export expense as CSV")
    expense = _load_alive_expense(db, expense_id)
    attachment_count = (
        db.query(ExpenseAttachment)
        .filter(ExpenseAttachment.expense_id == expense_id)
        .count()
    )
    csv_bytes = build_expense_csv_row(expense, attachment_count)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="EXPORT",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=f"Expense #{expense.id} CSV export",
        details={"format": "csv", "attachment_count": attachment_count},
        status="success",
    )

    filename = f"{_filename_stem(expense)}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Notice": "attachments-not-embedded",
        },
    )
