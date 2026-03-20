"""PDF generation and email stub endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import logging

from core.models.database import get_db
from core.models.models_per_tenant import Invoice, Client
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.utils.pdf_generator import generate_invoice_pdf

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


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: int,
    template: str = 'modern',
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Download or preview the invoice PDF, respecting the invoice's show_discount_in_pdf field."""
    try:
        # Fetch invoice, client, and company/tenant info
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        client = db.query(Client).filter(Client.id == invoice.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        # Optionally fetch tenant/company info if available
        company_data = {"name": "Your Company"}
        # Prepare invoice data
        invoice_data = {
            'id': invoice.id,
            'number': invoice.number,
            'date': invoice.created_at.strftime('%Y-%m-%d') if invoice.created_at else '',
            'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else '',
            'amount': float(invoice.amount),
            'subtotal': float(invoice.subtotal) if invoice.subtotal else float(invoice.amount),
            'discount_type': invoice.discount_type,
            'discount_value': float(invoice.discount_value) if invoice.discount_value else 0,
            'paid_amount': 0,  # Optionally calculate from payments
            'status': invoice.status,
            'notes': invoice.notes or '',
            'items': [item.__dict__ for item in invoice.items] if invoice.items else []
        }
        client_data = {
            'id': client.id,
            'name': client.name,
            'email': client.email,
            'phone': client.phone or '',
            'address': client.address or ''
        }
        # Generate PDF using the invoice's show_discount_in_pdf field
        pdf_bytes = generate_invoice_pdf(
            invoice_data=invoice_data,
            client_data=client_data,
            company_data=company_data,
            items=invoice.items,
            db=db,
            show_discount=invoice.show_discount_in_pdf,
            template_name=template
        )
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=invoice-{invoice.number}.pdf"
            }
        )
    finally:
        db.close()
