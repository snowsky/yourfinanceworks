"""PDF generation and email stub endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
import logging

from core.models.database import get_db, get_master_db
from core.models.models_per_tenant import Invoice
from core.models.models import MasterUser, Tenant
from core.routers.auth import get_current_user
from core.services.invoice_render import build_view_model, load_template_config
from core.services.invoice_render.renderer import render_invoice_html, render_invoice_pdf_async

logger = logging.getLogger(__name__)

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
