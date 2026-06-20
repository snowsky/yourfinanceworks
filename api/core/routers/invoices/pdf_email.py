"""PDF generation and email stub endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

from core.models.database import get_db, get_master_db
from core.models.models_per_tenant import Client, Invoice
from core.models.models import MasterUser, Tenant
from core.routers.auth import get_current_user
from core.schemas.invoice import InvoiceItemCreate
from core.services.invoice_render import assemble_view_model, build_view_model, load_template_config
from core.services.invoice_render.renderer import render_invoice_html, render_invoice_pdf_async
from datetime import datetime

logger = logging.getLogger(__name__)


class InvoicePreviewRequest(BaseModel):
    """Loose schema for rendering a draft invoice (no save needed).
    All fields are optional so in-progress forms can preview at any point."""
    number: Optional[str] = None
    date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    currency: Optional[str] = None
    amount: Optional[float] = None          # post-discount total (not used as subtotal)
    subtotal: Optional[float] = None        # pre-discount base — preferred
    paid_amount: Optional[float] = None
    client_id: Optional[int] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    show_discount_in_pdf: Optional[bool] = None
    notes: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None
    items: Optional[List[InvoiceItemCreate]] = None

router = APIRouter()


@router.post("/{invoice_id}/send-email")
async def send_invoice_email(
    invoice_id: int,
    current_user: MasterUser = Depends(get_current_user)
):
    """Send invoice via email - redirect to email service"""
    # This endpoint redirects to the email service
    # In a real application, you might want to handle this differently
    return {
        "message": "Please use the /api/v1/email/send-invoice endpoint",
        "invoice_id": invoice_id,
        "redirect_url": f"/api/v1/email/send-invoice"
    }


def _load_invoice_and_tenant(
    invoice_id: int,
    db: Session,
    master_db: Session,
    current_user: MasterUser,
):
    """Fetch the invoice (tenant-scoped) and the Tenant record (master DB)."""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.is_deleted == False
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    return invoice, tenant


@router.get("/{invoice_id}/preview", response_class=HTMLResponse)
async def preview_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return an HTML preview of the invoice using the unified WeasyPrint renderer."""
    invoice, tenant = _load_invoice_and_tenant(invoice_id, db, master_db, current_user)
    cfg = load_template_config(db)
    html = render_invoice_html(build_view_model(db, invoice, tenant, cfg), cfg)
    return HTMLResponse(content=html)


@router.post("/preview", response_class=HTMLResponse)
async def preview_invoice_from_body(
    body: InvoicePreviewRequest,
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Render the unified HTML template from posted form data (no save needed).

    Use this from the Edit screen's Live Preview so unsaved changes are rendered
    with the same server template as the View screen.
    """
    # Company — from the master Tenant record
    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    company: Dict[str, Any] = {
        "name": tenant.name if tenant else "",
        "logo_url": getattr(tenant, "company_logo_url", None),
        "address": getattr(tenant, "address", "") or "",
        "phone": getattr(tenant, "phone", "") or "",
        "email": getattr(tenant, "email", "") or "",
        "tax_id": getattr(tenant, "tax_id", "") or "",
    }

    # Meta
    issue_date = str(body.date.date()) if body.date else ""
    due_date_str = str(body.due_date.date()) if body.due_date else ""
    meta: Dict[str, Any] = {
        "number": body.number or "DRAFT",
        "issue_date": issue_date,
        "due_date": due_date_str,
        "status": body.status or "draft",
        "currency": body.currency or "USD",
        "show_discount": body.show_discount_in_pdf if body.show_discount_in_pdf is not None else True,
    }

    # Client — look up by client_id; blank if not found
    client_record: Optional[Client] = None
    if body.client_id is not None:
        client_record = db.query(Client).filter(Client.id == body.client_id).first()
    client: Dict[str, Any] = {
        "name": getattr(client_record, "name", "") or "" if client_record else "",
        "email": getattr(client_record, "email", "") or "" if client_record else "",
        "phone": getattr(client_record, "phone", "") or "" if client_record else "",
        "address": getattr(client_record, "address", "") or "" if client_record else "",
    }

    # Items
    raw_items = body.items or []
    items: List[Dict[str, Any]] = [
        {
            "description": it.description,
            "quantity": float(it.quantity),
            "unit_of_measure": getattr(it, "unit_of_measure", "") or "",
            "unit_price": float(it.price),
            "amount": float(it.quantity) * float(it.price),
        }
        for it in raw_items
    ]

    # Amount (pre-discount base) — use subtotal first; fall back to sum of item amounts
    item_sum = sum(it["amount"] for it in items)
    if body.subtotal is not None:
        base_amount = float(body.subtotal)
    elif body.amount is not None:
        # body.amount is post-discount; avoid double-discounting by using item sum
        base_amount = item_sum if item_sum else float(body.amount)
    else:
        base_amount = item_sum

    data: Dict[str, Any] = {
        "company": company,
        "meta": meta,
        "client": client,
        "items": items,
        "amount": base_amount,  # pre-discount; assemble_view_model applies discount
        "paid_amount": body.paid_amount or 0.0,
        "discount": {
            "type": body.discount_type or "percentage",
            "value": float(body.discount_value or 0.0),
        },
        "custom_fields": body.custom_fields or {},
        "notes": body.notes or "",
    }

    cfg = load_template_config(db)
    vm = assemble_view_model(data, cfg, public=False)
    return HTMLResponse(content=render_invoice_html(vm, cfg))


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Download the invoice as a PDF using the unified WeasyPrint renderer."""
    invoice, tenant = _load_invoice_and_tenant(invoice_id, db, master_db, current_user)
    cfg = load_template_config(db)
    pdf = await render_invoice_pdf_async(build_view_model(db, invoice, tenant, cfg), cfg)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=invoice-{invoice.number}.pdf"},
    )
