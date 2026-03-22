"""
Tools API — Payment endpoints.
Exposes read+write payment operations for agent consumption.
Creating a payment automatically syncs the parent invoice status.
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

router = APIRouter(prefix="/api/v1/tools/payments", tags=["tools-payments"])
logger = logging.getLogger(__name__)

# Payments are tied to invoices — use "invoice" domain gate.
DOMAIN = "invoice"


# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------

class CreatePaymentBody(BaseModel):
    invoice_id: int
    amount: float
    currency: str = "USD"
    payment_date: Optional[str] = None  # ISO; defaults to now
    payment_method: str = "other"
    reference_number: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def list_payments(
    skip: int = 0,
    limit: int = 100,
    invoice_id: Optional[int] = None,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List payments with optional invoice filter. Requires 'invoice' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    from core.models.models_per_tenant import Invoice, Payment

    q = tenant_db.query(Payment)
    if invoice_id is not None:
        q = q.filter(Payment.invoice_id == invoice_id)
    payments = q.order_by(Payment.payment_date.desc()).offset(skip).limit(min(limit, 500)).all()
    data = [_serialize_payment(p) for p in payments]
    return ToolResponse(success=True, data=data, count=len(data))


@router.get("/{payment_id}")
async def get_payment(
    payment_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Get a single payment by ID. Requires 'invoice' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    return ToolResponse(success=True, data=_serialize_payment(_get_or_404(tenant_db, payment_id)))


@router.post("/")
async def create_payment(
    body: CreatePaymentBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """
    Record a payment against an invoice.
    Automatically syncs invoice status (draft→paid when fully paid).
    Requires 'invoice' domain + write permission.
    """
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    from core.models.models_per_tenant import Invoice, Payment
    from core.routers.payments import sync_invoice_status

    # Validate invoice exists
    invoice = tenant_db.query(Invoice).filter(
        Invoice.id == body.invoice_id, Invoice.is_deleted == False
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {body.invoice_id} not found")

    payment_date = datetime.now(timezone.utc)
    if body.payment_date:
        try:
            payment_date = datetime.fromisoformat(body.payment_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="payment_date must be ISO format")

    user_id = int(auth_context.user_id) if auth_context.user_id else None
    payment = Payment(
        invoice_id=body.invoice_id,
        amount=body.amount,
        currency=body.currency,
        payment_date=payment_date,
        payment_method=body.payment_method,
        reference_number=body.reference_number,
        notes=body.notes,
        user_id=user_id,
    )
    tenant_db.add(payment)
    tenant_db.commit()
    tenant_db.refresh(payment)

    # Sync invoice status (may flip to "paid" if fully covered)
    sync_invoice_status(tenant_db, body.invoice_id)

    logger.info(
        "Tools API: created payment id=%s for invoice %s (api_key=%s)",
        payment.id, body.invoice_id, auth_context.api_key_id,
    )
    return ToolResponse(success=True, data=_serialize_payment(payment), message="Payment recorded")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, payment_id: int):
    from core.models.models_per_tenant import Payment
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p


def _serialize_payment(p) -> dict:
    return {
        "id": p.id,
        "invoice_id": p.invoice_id,
        "amount": p.amount,
        "currency": p.currency,
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "payment_method": p.payment_method,
        "reference_number": p.reference_number,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
