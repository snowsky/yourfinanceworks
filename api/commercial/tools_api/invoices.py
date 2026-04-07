"""
Tools API — Invoice endpoints.
Exposes read+write invoice operations for agent consumption.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.models.database import get_master_db
from core.utils.invoice import generate_invoice_number

from .deps import (
    AuthContext,
    ToolResponse,
    _check_domain_access,
    get_api_auth_context,
    get_tenant_db,
    require_write,
)

router = APIRouter(prefix="/tools/invoices", tags=["tools-invoices"])
logger = logging.getLogger(__name__)

DOMAIN = "invoice"


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CreateInvoiceBody(BaseModel):
    client_id: int
    amount: float
    due_date: str  # ISO date YYYY-MM-DD
    currency: str = "USD"
    status: str = "draft"
    notes: Optional[str] = None
    description: Optional[str] = None
    number: Optional[str] = None  # auto-generated if omitted


class UpdateInvoiceStatusBody(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def list_invoices(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List invoices with optional status filter. Requires 'invoice' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    from core.models.models_per_tenant import Invoice

    q = tenant_db.query(Invoice).filter(Invoice.is_deleted == False)
    if status:
        q = q.filter(Invoice.status == status)
    invoices = q.order_by(Invoice.created_at.desc()).offset(skip).limit(min(limit, 500)).all()
    data = [_serialize_invoice(inv) for inv in invoices]
    return ToolResponse(success=True, data=data, count=len(data))


@router.get("/overdue")
async def list_overdue_invoices(
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """List invoices past their due date that are not paid. Requires 'invoice' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    from core.models.models_per_tenant import Invoice

    now = datetime.now(timezone.utc)
    invoices = (
        tenant_db.query(Invoice)
        .filter(
            Invoice.is_deleted == False,
            Invoice.due_date < now,
            Invoice.status.notin_(["paid", "cancelled"]),
        )
        .order_by(Invoice.due_date.asc())
        .all()
    )
    data = [_serialize_invoice(inv) for inv in invoices]
    return ToolResponse(success=True, data=data, count=len(data))


@router.get("/stats")
async def invoice_stats(
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Aggregated invoice counts and amounts by status. Requires 'invoice' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    from core.models.models_per_tenant import Invoice

    rows = (
        tenant_db.query(Invoice.status, func.count(Invoice.id), func.sum(Invoice.amount))
        .filter(Invoice.is_deleted == False)
        .group_by(Invoice.status)
        .all()
    )
    stats = [{"status": r[0], "count": r[1], "total_amount": float(r[2] or 0)} for r in rows]
    return ToolResponse(success=True, data=stats)


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Get a single invoice by ID. Requires 'invoice' domain access."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    inv = _get_or_404(tenant_db, invoice_id)
    return ToolResponse(success=True, data=_serialize_invoice(inv))


@router.post("/")
async def create_invoice(
    body: CreateInvoiceBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Create a new invoice. Requires 'invoice' domain + write permission."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    from core.models.models_per_tenant import Client, Invoice

    # Validate client exists
    client = tenant_db.query(Client).filter(Client.id == body.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {body.client_id} not found")

    # Parse due_date
    try:
        due_date = datetime.fromisoformat(body.due_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="due_date must be ISO format YYYY-MM-DD")

    number = body.number.strip() if body.number else generate_invoice_number(tenant_db)

    user_id = int(auth_context.user_id) if auth_context.user_id else None
    inv = Invoice(
        number=number,
        client_id=body.client_id,
        amount=body.amount,
        subtotal=body.amount,
        currency=body.currency,
        due_date=due_date,
        status=body.status,
        notes=body.notes,
        description=body.description,
        created_by_user_id=user_id,
    )
    tenant_db.add(inv)
    tenant_db.commit()
    tenant_db.refresh(inv)
    logger.info("Tools API: created invoice %s (api_key=%s)", inv.number, auth_context.api_key_id)
    return ToolResponse(success=True, data=_serialize_invoice(inv), message="Invoice created")


@router.patch("/{invoice_id}/status")
async def update_invoice_status(
    invoice_id: int,
    body: UpdateInvoiceStatusBody,
    tenant_db: Session = Depends(get_tenant_db),
    auth_context: AuthContext = Depends(get_api_auth_context),
    master_db: Session = Depends(get_master_db),
):
    """Update invoice status. Requires 'invoice' domain + write permission."""
    _check_domain_access(master_db, auth_context, DOMAIN)
    require_write(auth_context)

    inv = _get_or_404(tenant_db, invoice_id)
    inv.status = body.status
    inv.updated_at = datetime.now(timezone.utc)
    tenant_db.commit()
    tenant_db.refresh(inv)
    return ToolResponse(success=True, data=_serialize_invoice(inv), message="Status updated")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, invoice_id: int):
    from core.models.models_per_tenant import Invoice
    inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


def _serialize_invoice(inv) -> dict:
    return {
        "id": inv.id,
        "number": inv.number,
        "client_id": inv.client_id,
        "amount": inv.amount,
        "currency": inv.currency,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "status": inv.status,
        "notes": inv.notes,
        "description": inv.description,
        "paid_amount": inv.paid_amount,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
    }
