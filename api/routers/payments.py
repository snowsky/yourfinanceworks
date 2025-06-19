from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging
import traceback
from datetime import datetime, date

from models.database import get_db
from models.models import Payment, Invoice, Client, User
from schemas.payment import PaymentCreate, PaymentUpdate, Payment as PaymentSchema, PaymentWithInvoice
from routers.auth import get_current_user
from services.currency_service import CurrencyService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

@router.get("/", response_model=List[PaymentWithInvoice])
def read_payments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get payments with invoice and client information
        payments = db.query(
            Payment,
            Invoice.number.label('invoice_number'),
            Client.name.label('client_name')
        ).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).filter(
            Payment.tenant_id == current_user.tenant_id
        ).offset(skip).limit(limit).all()

        # Convert to response format
        result = []
        for payment, invoice_number, client_name in payments:
            payment_dict = {
                "id": payment.id,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "payment_date": payment.payment_date.date(),  # Convert to date
                "payment_method": payment.payment_method,
                "reference_number": payment.reference_number,
                "notes": payment.notes,
                "invoice_id": payment.invoice_id,
                "invoice_number": invoice_number,
                "client_name": client_name,
                "tenant_id": payment.tenant_id,
                "created_at": payment.created_at,
                "updated_at": payment.updated_at
            }
            result.append(payment_dict)

        return result
    except Exception as e:
        logger.error(f"Error in read_payments: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch payments: {str(e)}"
        )

@router.get("/{payment_id}", response_model=PaymentWithInvoice)
def read_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get payment with invoice and client information
        payment_tuple = db.query(
            Payment,
            Invoice.number.label('invoice_number'),
            Client.name.label('client_name')
        ).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).filter(
            Payment.id == payment_id,
            Payment.tenant_id == current_user.tenant_id
        ).first()

        if payment_tuple is None:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )

        payment, invoice_number, client_name = payment_tuple
        payment_dict = {
            "id": payment.id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "payment_date": payment.payment_date.date(),  # Convert to date
            "payment_method": payment.payment_method,
            "reference_number": payment.reference_number,
            "notes": payment.notes,
            "invoice_id": payment.invoice_id,
            "invoice_number": invoice_number,
            "client_name": client_name,
            "tenant_id": payment.tenant_id,
            "created_at": payment.created_at,
            "updated_at": payment.updated_at
        }
        return payment_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in read_payment: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch payment: {str(e)}"
        )

@router.post("/", response_model=PaymentSchema)
def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get the invoice to determine currency
        invoice = db.query(Invoice).filter(
            Invoice.id == payment.invoice_id,
            Invoice.tenant_id == current_user.tenant_id
        ).first()
        
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )
        
        # Initialize currency service
        currency_service = CurrencyService(db)
        
        # Determine payment currency
        payment_currency = payment.currency
        if not payment_currency or payment_currency == "USD":
            # Use invoice currency by default
            payment_currency = invoice.currency
        
        # Validate currency
        if not currency_service.validate_currency_code(payment_currency):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid currency code: {payment_currency}"
            )
        
        # Convert payment_date to datetime if it's a date
        payment_date = payment.payment_date
        if isinstance(payment_date, date):
            payment_date = datetime.combine(payment_date, datetime.min.time())
        
        db_payment = Payment(
            amount=float(payment.amount),
            currency=payment_currency,
            payment_date=payment_date,
            payment_method=payment.payment_method,
            reference_number=payment.reference_number,
            notes=payment.notes,
            invoice_id=payment.invoice_id,
            tenant_id=current_user.tenant_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(db_payment)
        db.commit()
        db.refresh(db_payment)
        return db_payment
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in create_payment: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create payment: {str(e)}"
        )

@router.put("/{payment_id}", response_model=PaymentSchema)
def update_payment(
    payment_id: int,
    payment: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.tenant_id == current_user.tenant_id
        ).first()
        if db_payment is None:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )
        
        # Initialize currency service for validation
        currency_service = CurrencyService(db)
        
        # Update payment fields
        for field, value in payment.dict(exclude_unset=True).items():
            if field == 'amount':
                value = float(value)
            elif field == 'payment_date' and isinstance(value, date):
                value = datetime.combine(value, datetime.min.time())
            elif field == 'currency':
                # Validate currency code
                if not currency_service.validate_currency_code(value):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid currency code: {value}"
                    )
            setattr(db_payment, field, value)
        
        db_payment.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_payment)
        return db_payment
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in update_payment: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update payment: {str(e)}"
        )

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.tenant_id == current_user.tenant_id
        ).first()
        if db_payment is None:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )
        
        db.delete(db_payment)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in delete_payment: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete payment: {str(e)}"
        ) 