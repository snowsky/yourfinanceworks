"""
Tools API — Expense endpoints.
Exposes read+write expense operations for agent consumption.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.models.database import get_master_db

from .deps import (
    AuthContext,
    ToolResponse,
    _check_domain_access,
    get_api_auth_context,
    get_tenant_db,
    require_write,
)

router = APIRouter(prefix="/tools/expenses", tags=["tools-expenses"])
logger = logging.getLogger(__name__)

DOMAIN = "expense"


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CreateExpenseBody(BaseModel):
    amount: float
    category: str
    expense_date: Optional[str] = None  # ISO date; defaults to now
    currency: str = "USD"
    vendor: Optional[str] = None
    notes: Optional[str] = None
    invoice_id: Optional[int] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    status: str = "recorded"


class UpdateExpenseBody(BaseModel):
    amount: Optional[float] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    invoice_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def list_expenses(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    invoice_id: Optional[int] = None,
    unlinked_only: bool = False,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List expenses with optional filters. Requires 'expense' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    from core.models.models_per_tenant import Expense

    q = tenant_db.query(Expense).filter(Expense.is_deleted == False)
    if category:
        q = q.filter(Expense.category == category)
    if invoice_id is not None:
        q = q.filter(Expense.invoice_id == invoice_id)
    if unlinked_only:
        q = q.filter(Expense.invoice_id == None)

    expenses = q.order_by(Expense.expense_date.desc()).offset(skip).limit(min(limit, 500)).all()
    data = [_serialize_expense(e) for e in expenses]
    return ToolResponse(success=True, data=data, count=len(data))


@router.get("/{expense_id}")
async def get_expense(
    expense_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Get a single expense by ID. Requires 'expense' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    return ToolResponse(success=True, data=_serialize_expense(_get_or_404(tenant_db, expense_id)))


@router.post("/")
async def create_expense(
    body: CreateExpenseBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Create a new expense. Requires 'expense' domain + write permission."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    from core.models.models_per_tenant import Expense

    expense_date = datetime.now(timezone.utc)
    if body.expense_date:
        try:
            expense_date = datetime.fromisoformat(body.expense_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="expense_date must be ISO format")

    user_id = int(auth_context.user_id) if auth_context.user_id else None
    expense = Expense(
        amount=body.amount,
        category=body.category,
        expense_date=expense_date,
        currency=body.currency,
        vendor=body.vendor,
        notes=body.notes,
        invoice_id=body.invoice_id,
        payment_method=body.payment_method,
        reference_number=body.reference_number,
        status=body.status,
        created_by_user_id=user_id,
        user_id=user_id,
    )
    tenant_db.add(expense)
    tenant_db.commit()
    tenant_db.refresh(expense)
    logger.info("Tools API: created expense id=%s (api_key=%s)", expense.id, auth_context.api_key_id)
    return ToolResponse(success=True, data=_serialize_expense(expense), message="Expense created")


@router.patch("/{expense_id}")
async def update_expense(
    expense_id: int,
    body: UpdateExpenseBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Update an expense. Requires 'expense' domain + write permission."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    expense = _get_or_404(tenant_db, expense_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    expense.updated_at = datetime.now(timezone.utc)
    tenant_db.commit()
    tenant_db.refresh(expense)
    return ToolResponse(success=True, data=_serialize_expense(expense), message="Expense updated")


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Soft-delete an expense. Requires 'expense' domain + write permission."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    expense = _get_or_404(tenant_db, expense_id)
    expense.is_deleted = True
    expense.deleted_at = datetime.now(timezone.utc)
    tenant_db.commit()
    return ToolResponse(success=True, message=f"Expense {expense_id} deleted")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, expense_id: int):
    from core.models.models_per_tenant import Expense
    e = db.query(Expense).filter(Expense.id == expense_id, Expense.is_deleted == False).first()
    if not e:
        raise HTTPException(status_code=404, detail="Expense not found")
    return e


def _serialize_expense(e) -> dict:
    return {
        "id": e.id,
        "amount": e.amount,
        "currency": e.currency,
        "category": e.category,
        "vendor": e.vendor,
        "expense_date": e.expense_date.isoformat() if e.expense_date else None,
        "status": e.status,
        "notes": e.notes,
        "invoice_id": e.invoice_id,
        "payment_method": e.payment_method,
        "reference_number": e.reference_number,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
