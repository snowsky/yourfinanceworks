from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import logging
import traceback
from datetime import datetime, timedelta

from models.database import get_db
from models.models import Invoice, Client, User, Payment
from schemas.invoice import InvoiceCreate, InvoiceUpdate, Invoice as InvoiceSchema, InvoiceWithClient
from routers.auth import get_current_user
from utils.invoice import generate_invoice_number

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])

@router.post("/", response_model=InvoiceSchema)
def create_invoice(
    invoice: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Generate unique invoice number
        invoice_number = generate_invoice_number(db, current_user.tenant_id)
        
        db_invoice = Invoice(
            number=invoice_number,
            amount=float(invoice.amount),
            due_date=invoice.due_date,
            status=invoice.status,
            notes=invoice.notes,
            client_id=invoice.client_id,
            tenant_id=current_user.tenant_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_recurring=invoice.is_recurring,
            recurring_frequency=invoice.recurring_frequency
        )
        db.add(db_invoice)
        db.commit()
        db.refresh(db_invoice)
        return db_invoice
    except Exception as e:
        db.rollback()
        logger.error(f"Error in create_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create invoice: {str(e)}"
        )

@router.get("/", response_model=List[InvoiceWithClient])
def read_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get invoices with client information and payment status
        invoices = db.query(
            Invoice,
            Client.name.label('client_name'),
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid')
        ).join(
            Client, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Invoice.id == Payment.invoice_id
        ).filter(
            Invoice.tenant_id == current_user.tenant_id
        ).group_by(
            Invoice.id
        ).offset(skip).limit(limit).all()

        # Convert to response format
        result = []
        for invoice, client_name, total_paid in invoices:
            invoice_dict = {
                "id": invoice.id,
                "number": invoice.number,
                "amount": float(invoice.amount),
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "status": invoice.status,
                "notes": invoice.notes,
                "client_id": invoice.client_id,
                "client_name": client_name,
                "tenant_id": invoice.tenant_id,
                "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
                "total_paid": float(total_paid),
                "is_recurring": invoice.is_recurring,
                "recurring_frequency": invoice.recurring_frequency
            }
            result.append(invoice_dict)

        return result
    except Exception as e:
        logger.error(f"Error in read_invoices: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch invoices: {str(e)}"
        )

@router.get("/{invoice_id}", response_model=InvoiceWithClient)
def read_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get invoice with client information and payment status
        invoice_tuple = db.query(
            Invoice,
            Client.name.label('client_name'),
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid')
        ).join(
            Client, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Invoice.id == Payment.invoice_id
        ).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == current_user.tenant_id
        ).group_by(
            Invoice.id
        ).first()

        if invoice_tuple is None:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )

        invoice, client_name, total_paid = invoice_tuple
        invoice_dict = {
            "id": invoice.id,
            "number": invoice.number,
            "amount": float(invoice.amount),
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "status": invoice.status,
            "notes": invoice.notes,
            "client_id": invoice.client_id,
            "client_name": client_name,
            "tenant_id": invoice.tenant_id,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
            "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
            "total_paid": float(total_paid),
            "is_recurring": invoice.is_recurring,
            "recurring_frequency": invoice.recurring_frequency
        }
        return invoice_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in read_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch invoice: {str(e)}"
        )

@router.put("/{invoice_id}", response_model=InvoiceSchema)
def update_invoice(
    invoice_id: int,
    invoice: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == current_user.tenant_id
        ).first()
        if db_invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )
        
        # Update invoice fields
        update_data = invoice.dict(exclude_unset=True)
        for key, value in update_data.items():
            if key != "items":
                if key == 'amount':
                    value = float(value)
                setattr(db_invoice, key, value)
        
        db_invoice.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_invoice)
        
        # Convert to response format
        invoice_dict = {
            "id": db_invoice.id,
            "number": db_invoice.number,
            "amount": float(db_invoice.amount),
            "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
            "status": db_invoice.status,
            "notes": db_invoice.notes,
            "client_id": db_invoice.client_id,
            "tenant_id": db_invoice.tenant_id,
            "created_at": db_invoice.created_at.isoformat() if db_invoice.created_at else None,
            "updated_at": db_invoice.updated_at.isoformat() if db_invoice.updated_at else None,
            "is_recurring": db_invoice.is_recurring,
            "recurring_frequency": db_invoice.recurring_frequency
        }
        return invoice_dict
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in update_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update invoice: {str(e)}"
        )

@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == current_user.tenant_id
        ).first()
        if db_invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )
        
        db.delete(db_invoice)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in delete_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete invoice: {str(e)}"
        )

@router.post("/{invoice_id}/send-email")
def send_invoice_email(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send invoice via email - redirect to email service"""
    from fastapi import Request
    from fastapi.responses import RedirectResponse
    
    # This endpoint redirects to the email service
    # In a real application, you might want to handle this differently
    return {
        "message": "Please use the /api/email/send-invoice endpoint",
        "invoice_id": invoice_id,
        "redirect_url": f"/api/email/send-invoice"
    }

@router.get("/stats/total-income", response_model=dict)
def get_total_income(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Calculate total income from all paid invoices
        total_income = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).filter(
            Invoice.tenant_id == current_user.tenant_id
        ).scalar()

        return {
            "total_income": float(total_income) if total_income is not None else 0.0
        }
    except Exception as e:
        logger.error(f"Error in get_total_income: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate total income: {str(e)}"
        ) 