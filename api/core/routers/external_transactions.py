"""
External transactions API for API clients to submit financial data.
"""

import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models.database import get_master_db
from core.models.models import MasterUser
from core.models.api_models import APIClient, ExternalTransaction
from core.schemas.api_schemas import (
    ExternalTransactionCreate, ExternalTransactionResponse, 
    ExternalTransactionUpdate, ExternalTransactionList
)
from core.services.external_api_auth_service import ExternalAPIAuthService, AuthContext
from core.routers.auth import get_current_user


router = APIRouter(prefix="/external-transactions", tags=["external-transactions"])
auth_service = ExternalAPIAuthService()


def get_api_auth_context(request: Request) -> Optional[AuthContext]:
    """Get API authentication context from request state."""
    return getattr(request.state, 'auth', None)


def require_api_auth(request: Request) -> AuthContext:
    """Require API authentication."""
    auth_context = get_api_auth_context(request)
    if not auth_context or not auth_context.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API authentication required"
        )
    return auth_context


def _generate_duplicate_hash(
    amount: float, 
    currency: str, 
    date: datetime, 
    description: str, 
    external_reference_id: Optional[str] = None
) -> str:
    """Generate a hash for duplicate detection."""
    hash_input = f"{amount}:{currency}:{date.isoformat()}:{description}"
    if external_reference_id:
        hash_input += f":{external_reference_id}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


@router.post("/transactions", response_model=ExternalTransactionResponse)
async def create_external_transaction(
    transaction_data: ExternalTransactionCreate,
    request: Request,
    db: Session = Depends(get_master_db)
):
    """Create a new external transaction via API."""
    
    # Require API authentication
    auth_context = require_api_auth(request)
    
    # Get API client
    api_client = db.query(APIClient).filter(
        APIClient.client_id == auth_context.api_key_id,
        APIClient.is_active == True
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API client"
        )
    
    # Check permissions
    allowed, error_msg = await auth_service.check_api_client_permissions(
        db, api_client, transaction_data.transaction_type, 
        float(transaction_data.amount), transaction_data.currency
    )
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    
    # Generate duplicate check hash
    duplicate_hash = _generate_duplicate_hash(
        float(transaction_data.amount),
        transaction_data.currency,
        transaction_data.date,
        transaction_data.description,
        transaction_data.external_reference_id
    )
    
    # Check for duplicates
    existing_transaction = db.query(ExternalTransaction).filter(
        and_(
            ExternalTransaction.duplicate_check_hash == duplicate_hash,
            ExternalTransaction.external_client_id == api_client.id,
            ExternalTransaction.tenant_id == api_client.tenant_id
        )
    ).first()
    
    if existing_transaction:
        # Mark as duplicate and return existing transaction
        new_transaction = ExternalTransaction(
            user_id=api_client.user_id,
            tenant_id=api_client.tenant_id,
            external_client_id=api_client.id,
            external_reference_id=transaction_data.external_reference_id,
            transaction_type=transaction_data.transaction_type,
            amount=transaction_data.amount,
            currency=transaction_data.currency,
            date=transaction_data.date,
            description=transaction_data.description,
            original_amount=transaction_data.original_amount,
            original_currency=transaction_data.original_currency,
            exchange_rate=transaction_data.exchange_rate,
            conversion_date=transaction_data.conversion_date,
            category=transaction_data.category,
            subcategory=transaction_data.subcategory,
            source_system=transaction_data.source_system,
            invoice_reference=transaction_data.invoice_reference,
            payment_method=transaction_data.payment_method,
            sales_tax_amount=transaction_data.sales_tax_amount,
            vat_amount=transaction_data.vat_amount,
            other_tax_amount=transaction_data.other_tax_amount,
            business_purpose=transaction_data.business_purpose,
            receipt_url=transaction_data.receipt_url,
            vendor_name=transaction_data.vendor_name,
            duplicate_check_hash=duplicate_hash,
            is_duplicate=True,
            original_transaction_id=existing_transaction.external_transaction_id,
            submission_metadata=transaction_data.submission_metadata,
            api_version="1.0",
            client_ip_address=request.client.host if request.client else None,
            disable_ai_recognition=transaction_data.disable_ai_recognition
        )
        
        db.add(new_transaction)
        api_client.total_transactions_submitted += 1
        db.commit()
        db.refresh(new_transaction)
        
        return ExternalTransactionResponse.from_orm(new_transaction)
    
    # Create new transaction
    new_transaction = ExternalTransaction(
        user_id=api_client.user_id,
        tenant_id=api_client.tenant_id,
        external_client_id=api_client.id,
        external_reference_id=transaction_data.external_reference_id,
        transaction_type=transaction_data.transaction_type,
        amount=transaction_data.amount,
        currency=transaction_data.currency,
        date=transaction_data.date,
        description=transaction_data.description,
        original_amount=transaction_data.original_amount,
        original_currency=transaction_data.original_currency,
        exchange_rate=transaction_data.exchange_rate,
        conversion_date=transaction_data.conversion_date,
        category=transaction_data.category,
        subcategory=transaction_data.subcategory,
        source_system=transaction_data.source_system,
        invoice_reference=transaction_data.invoice_reference,
        payment_method=transaction_data.payment_method,
        sales_tax_amount=transaction_data.sales_tax_amount,
        vat_amount=transaction_data.vat_amount,
        other_tax_amount=transaction_data.other_tax_amount,
        business_purpose=transaction_data.business_purpose,
        receipt_url=transaction_data.receipt_url,
        vendor_name=transaction_data.vendor_name,
        duplicate_check_hash=duplicate_hash,
        submission_metadata=transaction_data.submission_metadata,
        api_version="1.0",
        client_ip_address=request.client.host if request.client else None,
        disable_ai_recognition=transaction_data.disable_ai_recognition
    )
    
    db.add(new_transaction)
    api_client.total_transactions_submitted += 1
    db.commit()
    db.refresh(new_transaction)
    
    # Send webhook notification if configured
    if api_client.webhook_url:
        try:
            await auth_service.send_webhook_notification(
                webhook_url=api_client.webhook_url,
                webhook_secret=api_client.webhook_secret,
                event_type="transaction.created",
                data={
                    "transaction_id": new_transaction.external_transaction_id,
                    "type": new_transaction.transaction_type,
                    "amount": float(new_transaction.amount),
                    "currency": new_transaction.currency,
                    "status": new_transaction.status
                }
            )
        except Exception:
            # Don't fail the transaction if webhook fails
            pass
    
    return ExternalTransactionResponse.from_orm(new_transaction)


@router.get("/transactions", response_model=ExternalTransactionList)
async def list_external_transactions(
    request: Request,
    db: Session = Depends(get_master_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    transaction_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    """List external transactions for the authenticated API client."""
    
    # Require API authentication
    auth_context = require_api_auth(request)
    
    # Get API client
    api_client = db.query(APIClient).filter(
        APIClient.client_id == auth_context.api_key_id,
        APIClient.is_active == True
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API client"
        )
    
    # Build query
    query = db.query(ExternalTransaction).filter(
        ExternalTransaction.external_client_id == api_client.id,
        ExternalTransaction.tenant_id == api_client.tenant_id
    )
    
    # Apply filters
    if transaction_type:
        query = query.filter(ExternalTransaction.transaction_type == transaction_type)
    
    if status:
        query = query.filter(ExternalTransaction.status == status)
    
    if start_date:
        query = query.filter(ExternalTransaction.date >= start_date)
    
    if end_date:
        query = query.filter(ExternalTransaction.date <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    transactions = query.order_by(ExternalTransaction.created_at.desc()).offset(offset).limit(per_page).all()
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page
    
    return ExternalTransactionList(
        transactions=[ExternalTransactionResponse.from_orm(t) for t in transactions],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/transactions/{transaction_id}", response_model=ExternalTransactionResponse)
async def get_external_transaction(
    transaction_id: str,
    request: Request,
    db: Session = Depends(get_master_db)
):
    """Get a specific external transaction."""
    
    # Require API authentication
    auth_context = require_api_auth(request)
    
    # Get API client
    api_client = db.query(APIClient).filter(
        APIClient.client_id == auth_context.api_key_id,
        APIClient.is_active == True
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API client"
        )
    
    # Find transaction
    transaction = db.query(ExternalTransaction).filter(
        and_(
            ExternalTransaction.external_transaction_id == transaction_id,
            ExternalTransaction.external_client_id == api_client.id,
            ExternalTransaction.tenant_id == api_client.tenant_id
        )
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return ExternalTransactionResponse.from_orm(transaction)


@router.put("/transactions/{transaction_id}", response_model=ExternalTransactionResponse)
async def update_external_transaction(
    transaction_id: str,
    update_data: ExternalTransactionUpdate,
    request: Request,
    db: Session = Depends(get_master_db)
):
    """Update an external transaction."""
    
    # Require API authentication
    auth_context = require_api_auth(request)
    
    # Get API client
    api_client = db.query(APIClient).filter(
        APIClient.client_id == auth_context.api_key_id,
        APIClient.is_active == True
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API client"
        )
    
    # Find transaction
    transaction = db.query(ExternalTransaction).filter(
        and_(
            ExternalTransaction.external_transaction_id == transaction_id,
            ExternalTransaction.external_client_id == api_client.id,
            ExternalTransaction.tenant_id == api_client.tenant_id
        )
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Check if transaction can be updated
    if transaction.status in ["approved", "rejected"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update approved or rejected transactions"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(transaction, field, value)
    
    transaction.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(transaction)
    
    # Send webhook notification if configured
    if api_client.webhook_url:
        try:
            await auth_service.send_webhook_notification(
                webhook_url=api_client.webhook_url,
                webhook_secret=api_client.webhook_secret,
                event_type="transaction.updated",
                data={
                    "transaction_id": transaction.external_transaction_id,
                    "type": transaction.transaction_type,
                    "amount": float(transaction.amount),
                    "currency": transaction.currency,
                    "status": transaction.status
                }
            )
        except Exception:
            # Don't fail the update if webhook fails
            pass
    
    return ExternalTransactionResponse.from_orm(transaction)


# UI endpoints for managing external transactions (requires JWT auth)
@router.get("/ui/transactions", response_model=ExternalTransactionList)
async def ui_list_external_transactions(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    transaction_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    client_id: Optional[str] = Query(None)
):
    """List external transactions for UI (admin view)."""
    
    # Build query
    query = db.query(ExternalTransaction).filter(
        ExternalTransaction.tenant_id == current_user.tenant_id
    )
    
    # Filter by client if specified
    if client_id:
        api_client = db.query(APIClient).filter(
            APIClient.client_id == client_id,
            APIClient.tenant_id == current_user.tenant_id
        ).first()
        if api_client:
            query = query.filter(ExternalTransaction.external_client_id == api_client.id)
    
    # Apply filters
    if transaction_type:
        query = query.filter(ExternalTransaction.transaction_type == transaction_type)
    
    if status:
        query = query.filter(ExternalTransaction.status == status)
    
    if start_date:
        query = query.filter(ExternalTransaction.date >= start_date)
    
    if end_date:
        query = query.filter(ExternalTransaction.date <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    transactions = query.order_by(ExternalTransaction.created_at.desc()).offset(offset).limit(per_page).all()
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page
    
    return ExternalTransactionList(
        transactions=[ExternalTransactionResponse.from_orm(t) for t in transactions],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.put("/ui/transactions/{transaction_id}/review", response_model=ExternalTransactionResponse)
async def ui_review_external_transaction(
    transaction_id: str,
    review_data: ExternalTransactionUpdate,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db)
):
    """Review and approve/reject an external transaction (UI)."""
    
    # Find transaction
    transaction = db.query(ExternalTransaction).filter(
        and_(
            ExternalTransaction.external_transaction_id == transaction_id,
            ExternalTransaction.tenant_id == current_user.tenant_id
        )
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Update review fields
    if review_data.status:
        transaction.status = review_data.status
    
    if review_data.review_notes:
        transaction.review_notes = review_data.review_notes
    
    transaction.reviewed_by = current_user.id
    transaction.reviewed_at = datetime.now(timezone.utc)
    transaction.requires_review = False
    transaction.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(transaction)
    
    # Send webhook notification if configured
    api_client = db.query(APIClient).filter(APIClient.id == transaction.external_client_id).first()
    if api_client and api_client.webhook_url:
        try:
            await auth_service.send_webhook_notification(
                webhook_url=api_client.webhook_url,
                webhook_secret=api_client.webhook_secret,
                event_type="transaction.reviewed",
                data={
                    "transaction_id": transaction.external_transaction_id,
                    "type": transaction.transaction_type,
                    "amount": float(transaction.amount),
                    "currency": transaction.currency,
                    "status": transaction.status,
                    "reviewed_by": current_user.email
                }
            )
        except Exception:
            # Don't fail the review if webhook fails
            pass
    
    return ExternalTransactionResponse.from_orm(transaction)
