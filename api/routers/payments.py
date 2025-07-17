from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from typing import List, Dict, Any
import logging
import traceback
from datetime import datetime, date, timezone
from collections import defaultdict

from models.database import get_db
from models.models_per_tenant import Invoice, Client, User
from schemas.payment import PaymentCreate, PaymentUpdate, Payment as PaymentSchema, PaymentWithInvoice
from routers.auth import get_current_user
from services.currency_service import CurrencyService
from utils.audit import log_audit_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _prepare_payment_chart_data(payments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prepare payment data for charts"""
    try:
        # Group payments by date for timeline chart
        payments_by_date = defaultdict(float)
        payments_by_method = defaultdict(float)
        
        for payment in payments:
            # Date grouping
            if payment.get('payment_date'):
                try:
                    payment_date = payment['payment_date']
                    if isinstance(payment_date, str):
                        payment_date = datetime.fromisoformat(payment_date).strftime('%Y-%m-%d')
                    else:
                        payment_date = payment_date.strftime('%Y-%m-%d')
                    payments_by_date[payment_date] += float(payment.get('amount', 0))
                except Exception as e:
                    logger.warning(f"Error processing payment date: {e}")
                    continue
            
            # Payment method grouping
            method = payment.get('payment_method', 'unknown')
            payments_by_method[method] += float(payment.get('amount', 0))
        
        # Prepare chart datasets
        timeline_data = [
            {'date': date, 'amount': amount} 
            for date, amount in sorted(payments_by_date.items())
        ]
        
        method_data = [
            {'method': method, 'amount': amount} 
            for method, amount in payments_by_method.items()
        ]
        
        # Calculate summary stats
        total_amount = sum(float(p.get('amount', 0)) for p in payments)
        avg_amount = total_amount / len(payments) if payments else 0
        
        return {
            'timeline': timeline_data,
            'by_method': method_data,
            'summary': {
                'total_amount': total_amount,
                'total_payments': len(payments),
                'average_amount': avg_amount,
                'date_range': {
                    'earliest': min(payments_by_date.keys()) if payments_by_date else None,
                    'latest': max(payments_by_date.keys()) if payments_by_date else None
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error preparing chart data: {e}")
        return {
            'timeline': [],
            'by_method': [],
            'summary': {
                'total_amount': 0,
                'total_payments': 0,
                'average_amount': 0,
                'date_range': {
                    'earliest': None,
                    'latest': None
                }
            }
        }

# Create a simple Payment model that matches the actual database schema
Base = declarative_base()

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    payment_method = Column(String, nullable=False, default="system")
    reference_number = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

router = APIRouter(prefix="/payments", tags=["payments"])

@router.get("/")
async def read_payments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get payments with invoice and client information using ORM
        payments = db.query(
            Payment,
            Invoice.number.label('invoice_number'),
            Client.name.label('client_name')
        ).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).offset(skip).limit(limit).all()

        # Convert to response format
        result = []
        for payment, invoice_number, client_name in payments:
            # Use "Unknown User" since we're not tracking user_id in the database
            user_name = "Unknown User"
            
            payment_dict = {
                "id": payment.id,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "payment_date": payment.payment_date.date() if payment.payment_date else None,
                "payment_method": payment.payment_method,
                "reference_number": payment.reference_number,
                "notes": payment.notes,
                "invoice_id": payment.invoice_id,
                "invoice_number": invoice_number,
                "client_name": client_name,
                "created_at": payment.created_at,
                "updated_at": payment.updated_at,
                "status": "completed",
                "user_name": user_name
            }
            result.append(payment_dict)

        # Prepare chart data
        chart_data = _prepare_payment_chart_data(result)
        
        return {
            "success": True,
            "data": result,
            "count": len(result),
            "chart_data": chart_data
        }
    except Exception as e:
        logger.error(f"Error in read_payments: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch payments: {str(e)}"
        )

@router.get("/{payment_id}", response_model=PaymentWithInvoice)
async def read_payment(
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
            Payment.id == payment_id
        ).first()

        if payment_tuple is None:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )

        payment, invoice_number, client_name = payment_tuple
        
        # Use "Unknown User" since we're not tracking user_id in the database
        user_name = "Unknown User"
        
        payment_dict = {
            "id": payment.id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "payment_date": payment.payment_date.date() if payment.payment_date else None,
            "payment_method": payment.payment_method,
            "reference_number": payment.reference_number,
            "notes": payment.notes,
            "invoice_id": payment.invoice_id,
            "invoice_number": invoice_number,
            "client_name": client_name,
            "created_at": payment.created_at,
            "updated_at": payment.updated_at,
            "status": "completed",
            "user_name": user_name
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
async def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get the invoice to determine currency
        invoice = db.query(Invoice).filter(
            Invoice.id == payment.invoice_id
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
        
        # Create payment using ORM
        db_payment = Payment(
            amount=float(payment.amount),
            currency=payment_currency,
            payment_date=payment_date,
            payment_method=payment.payment_method,
            reference_number=payment.reference_number,
            notes=payment.notes,
            invoice_id=payment.invoice_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(db_payment)
        db.commit()
        db.refresh(db_payment)
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="payment",
            resource_id=str(db_payment.id),
            resource_name=f"Payment for Invoice #{db_payment.invoice.number}",
            details=payment.dict(),
            status="success"
        )
        
        return db_payment
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="payment",
            resource_id=None,
            resource_name=None,
            details=payment.dict(),
            status="error",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create payment: {str(e)}"
        )

@router.put("/{payment_id}", response_model=PaymentSchema)
async def update_payment(
    payment_id: int,
    payment: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_payment = db.query(Payment).filter(
            Payment.id == payment_id
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
        
        db_payment.updated_at = datetime.now(timezone.utc)
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
async def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_payment = db.query(Payment).filter(
            Payment.id == payment_id
        ).first()
        if db_payment is None:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )
        
        db.delete(db_payment)
        db.commit()
        return None
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