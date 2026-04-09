"""Shared helpers used across expense sub-routers."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List as TypingList, Literal, Optional

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.constants.expense_status import ExpenseStatus
from core.models.models import MasterUser
from core.models.models_per_tenant import Expense
from core.schemas.expense import ExpenseCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
uvicorn_logger = logging.getLogger("uvicorn.error")


def _apply_creator_fallback(expenses: list, master_db: Session) -> None:
    """
    Populate _creator_display_name on expenses whose created_by_username is None
    (tenant DB decryption failed) by falling back to the master DB where user
    names are stored as plain text.
    """
    needs = [ex for ex in expenses if ex.created_by_username is None and ex.created_by_user_id]
    if not needs:
        return
    user_ids = list({ex.created_by_user_id for ex in needs})
    from core.models.models import MasterUser as MU
    master_users = {
        mu.id: mu
        for mu in master_db.query(MU).filter(MU.id.in_(user_ids)).all()
    }
    for ex in needs:
        mu = master_users.get(ex.created_by_user_id)
        if mu:
            if mu.first_name and mu.last_name:
                ex.__dict__['_creator_display_name'] = f"{mu.first_name} {mu.last_name}"
            elif mu.first_name:
                ex.__dict__['_creator_display_name'] = mu.first_name
            elif mu.email:
                ex.__dict__['_creator_display_name'] = mu.email


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """Validate if a status transition is allowed"""
    try:
        current = ExpenseStatus(current_status)
        new = ExpenseStatus(new_status)
        return current.can_transition_to(new)
    except ValueError:
        return False


def check_expense_modification_allowed(expense: Expense) -> None:
    """Check if an expense can be modified based on its current status"""
    from fastapi import HTTPException
    if expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify expense with status '{expense.status}'. Expense is in approval workflow."
        )


def _find_potential_expense_duplicates(
    db: Session,
    amount: float,
    expense_date,
    date_window_days: int = 3,
    exclude_id: Optional[int] = None,
) -> list:
    """SQL-filter expenses by amount + date window. Vendor comparison must be done
    in Python because the vendor column uses EncryptedColumn.
    """
    window_start = expense_date - timedelta(days=date_window_days)
    window_end = expense_date + timedelta(days=date_window_days)
    candidates = (
        db.query(Expense)
        .filter(
            Expense.is_deleted == False,
            Expense.amount.isnot(None),
            sa.func.round(sa.cast(Expense.amount, sa.Numeric), 2) == round(float(amount), 2),
            Expense.expense_date >= window_start,
            Expense.expense_date <= window_end,
        )
        .all()
    )
    if exclude_id is not None:
        candidates = [e for e in candidates if e.id != exclude_id]
    return [
        {
            "id": e.id,
            "amount": e.amount,
            "expense_date": str(e.expense_date),
            "vendor": e.vendor,
            "category": e.category,
        }
        for e in candidates
    ]


class BulkLabelsRequest(BaseModel):
    expense_ids: TypingList[int]
    operation: Literal['add', 'remove']
    label: str


class BulkExpenseCreateRequest(BaseModel):
    expenses: TypingList[ExpenseCreate]


class BulkDeleteRequest(BaseModel):
    expense_ids: TypingList[int]
