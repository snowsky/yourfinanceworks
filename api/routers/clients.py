from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging
import traceback
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func
from datetime import datetime

from models.database import get_db
from models.models import Client, User, Payment, Invoice
from schemas.client import ClientCreate, ClientUpdate, Client as ClientSchema
from routers.auth import get_current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])

@router.get("/", response_model=List[ClientSchema])
def read_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get clients with their total invoice amounts, total paid amounts, and calculate outstanding balance
        clients = db.query(
            Client,
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid'),
            func.coalesce(func.sum(Invoice.amount), 0).label('total_invoiced')
        ).outerjoin(
            Invoice, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Payment.invoice_id == Invoice.id
        ).filter(
            Client.tenant_id == current_user.tenant_id
        ).group_by(
            Client.id
        ).offset(skip).limit(limit).all()

        # Convert to response format
        result = []
        for client, total_paid, total_invoiced in clients:
            # Calculate outstanding balance for pending/unpaid invoices
            pending_invoices = db.query(
                func.coalesce(func.sum(Invoice.amount), 0)
            ).filter(
                Invoice.client_id == client.id,
                Invoice.status.in_(['pending', 'overdue', 'partially_paid'])
            ).scalar()
            
            pending_payments = db.query(
                func.coalesce(func.sum(Payment.amount), 0)
            ).filter(
                Payment.invoice_id.in_(
                    db.query(Invoice.id).filter(
                        Invoice.client_id == client.id,
                        Invoice.status.in_(['pending', 'overdue', 'partially_paid'])
                    )
                )
            ).scalar()
            
            outstanding_balance = float(pending_invoices or 0) - float(pending_payments or 0)
            
            client_dict = {
                "id": client.id,
                "tenant_id": client.tenant_id,
                "name": client.name,
                "email": client.email,
                "phone": client.phone,
                "address": client.address,
                "balance": max(0, outstanding_balance),  # Use calculated outstanding balance
                "paid_amount": float(total_paid),
                "preferred_currency": client.preferred_currency,
                "created_at": client.created_at,
                "updated_at": client.updated_at
            }
            result.append(client_dict)

        return result
    except Exception as e:
        logger.error(f"Error in read_clients: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch clients: {str(e)}"
        )

@router.get("/{client_id}", response_model=ClientSchema)
def read_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get client with total paid amount
        client_tuple = db.query(
            Client,
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid')
        ).outerjoin(
            Invoice, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Payment.invoice_id == Invoice.id
        ).filter(
            Client.id == client_id,
            Client.tenant_id == current_user.tenant_id
        ).group_by(
            Client.id
        ).first()

        if client_tuple is None:
            raise HTTPException(
                status_code=404,
                detail="Client not found"
            )

        client, total_paid = client_tuple
        
        # Calculate outstanding balance for pending/unpaid invoices
        pending_invoices = db.query(
            func.coalesce(func.sum(Invoice.amount), 0)
        ).filter(
            Invoice.client_id == client.id,
            Invoice.status.in_(['pending', 'overdue', 'partially_paid'])
        ).scalar()
        
        pending_payments = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.invoice_id.in_(
                db.query(Invoice.id).filter(
                    Invoice.client_id == client.id,
                    Invoice.status.in_(['pending', 'overdue', 'partially_paid'])
                )
            )
        ).scalar()
        
        outstanding_balance = float(pending_invoices or 0) - float(pending_payments or 0)
        
        client_dict = {
            "id": client.id,
            "tenant_id": client.tenant_id,
            "name": client.name,
            "email": client.email,
            "phone": client.phone,
            "address": client.address,
            "balance": max(0, outstanding_balance),  # Use calculated outstanding balance
            "paid_amount": float(total_paid),
            "preferred_currency": client.preferred_currency,
            "created_at": client.created_at,
            "updated_at": client.updated_at
        }
        return client_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in read_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch client: {str(e)}"
        )

@router.post("/", response_model=ClientSchema)
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_client = Client(
            **client.dict(),
            tenant_id=current_user.tenant_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(db_client)
        db.commit()
        db.refresh(db_client)
        return db_client
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error in create_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error in create_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create client: {str(e)}"
        )

@router.put("/{client_id}", response_model=ClientSchema)
def update_client(
    client_id: int,
    client: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_client = db.query(Client).filter(
            Client.id == client_id,
            Client.tenant_id == current_user.tenant_id
        ).first()
        if db_client is None:
            raise HTTPException(
                status_code=404,
                detail="Client not found"
            )
        
        # Update client fields
        for field, value in client.dict(exclude_unset=True).items():
            setattr(db_client, field, value)
        
        db_client.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_client)
        return db_client
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in update_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update client: {str(e)}"
        )

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Check if client exists
        db_client = db.query(Client).filter(
            Client.id == client_id,
            Client.tenant_id == current_user.tenant_id
        ).first()
        if db_client is None:
            raise HTTPException(
                status_code=404,
                detail="Client not found"
            )
        
        # Check if client has associated invoices
        has_invoices = db.query(Invoice).filter(
            Invoice.client_id == client_id,
            Invoice.tenant_id == current_user.tenant_id
        ).first() is not None
        
        if has_invoices:
            # Delete all associated invoices first
            db.query(Invoice).filter(
                Invoice.client_id == client_id,
                Invoice.tenant_id == current_user.tenant_id
            ).delete()
        
        # Now delete the client
        db.delete(db_client)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in delete_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete client: {str(e)}"
        ) 