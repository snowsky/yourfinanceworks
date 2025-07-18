from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, distinct
from typing import List, Optional
import logging
import traceback
from datetime import datetime, date, timezone
from decimal import Decimal

from models.database import get_db
from models.models_per_tenant import Invoice, Client, User, InvoiceItem, DiscountRule
from routers.payments import Payment
from schemas.invoice import InvoiceCreate, InvoiceUpdate, Invoice as InvoiceSchema, InvoiceWithClient, InvoiceHistory, InvoiceHistoryCreate, RecycleBinResponse, DeletedInvoice, RestoreInvoiceRequest
from routers.auth import get_current_user
from services.currency_service import CurrencyService
from utils.invoice import generate_invoice_number
from utils.rbac import require_non_viewer, require_admin
from utils.audit import log_audit_event
from constants.error_codes import FAILED_TO_CREATE_INVOICE, FAILED_TO_FETCH_INVOICE

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])

def make_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

@router.post("/", response_model=InvoiceSchema)
async def create_invoice(
    invoice: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info("Invoice create endpoint called")
    # Check if user has permission to create invoices
    require_non_viewer(current_user, "create invoices")
    
    try:
        # Validate that the client exists
        client = db.query(Client).filter(Client.id == invoice.client_id).first()
        if not client:
            raise HTTPException(
                status_code=404,
                detail=f"Client with ID {invoice.client_id} not found. Please create a client first."
            )
        
        # Generate unique invoice number
        # No tenant_id needed since we're in the tenant's database
        invoice_number = generate_invoice_number(db)
        
        # Initialize currency service
        currency_service = CurrencyService(db)
        
        # Determine invoice currency
        invoice_currency = invoice.currency
        if not invoice_currency or invoice_currency == "USD":
            # Use client's preferred currency or tenant default
            # No tenant_id needed since we're in the tenant's database
            invoice_currency = currency_service.get_client_preferred_currency(
                invoice.client_id
            )
        
        # Validate currency
        if not currency_service.validate_currency_code(invoice_currency):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid currency code: {invoice_currency}"
            )
        
        # No tenant_id needed since each tenant has its own database
        logger.info(f"[DEBUG] Received custom_fields: {invoice.custom_fields}")
        db_invoice = Invoice(
            number=invoice_number,
            amount=float(invoice.amount),
            currency=invoice_currency,
            due_date=invoice.due_date,
            status=invoice.status,
            notes=invoice.notes,
            client_id=invoice.client_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_recurring=invoice.is_recurring,
            recurring_frequency=invoice.recurring_frequency,
            discount_type=invoice.discount_type or "percentage",
            discount_value=float(invoice.discount_value or 0),
            subtotal=float(invoice.subtotal or invoice.amount),
            custom_fields=invoice.custom_fields
        )
        db.add(db_invoice)
        db.flush()  # Get the invoice ID
        logger.info(f"[DEBUG] Saved custom_fields in DB: {db_invoice.custom_fields}")
        
        # Create invoice items
        for item_data in invoice.items:
            db_item = InvoiceItem(
                invoice_id=db_invoice.id,
                description=item_data.description,
                quantity=float(item_data.quantity),
                price=float(item_data.price),
                amount=float(item_data.quantity) * float(item_data.price)
            )
            db.add(db_item)
        
        # Create history entry for invoice creation
        from models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        creation_history = InvoiceHistoryModel(
            invoice_id=db_invoice.id,
            user_id=current_user.id,
            action='creation',
            details=f'Invoice {db_invoice.number} created',
            previous_values=None,
            current_values={
                'number': db_invoice.number,
                'amount': db_invoice.amount,
                'currency': db_invoice.currency,
                'status': db_invoice.status,
                'due_date': db_invoice.due_date.isoformat() if db_invoice.due_date else None,
                'notes': db_invoice.notes
            }
        )
        db.add(creation_history)
        
        db.commit()
        db.refresh(db_invoice)
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="invoice",
            resource_id=str(db_invoice.id),
            resource_name=f"Invoice {db_invoice.number}",
            details=invoice.dict(),
            status="success"
        )
        
        return db_invoice
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in create_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_CREATE_INVOICE
        )

@router.get("/", response_model=List[InvoiceWithClient])
async def read_invoices(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Build base query (exclude soft-deleted invoices)
        # No tenant_id filtering needed since we're in the tenant's database
        query = db.query(
            Invoice,
            Client.name.label('client_name'),
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid')
        ).join(
            Client, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Invoice.id == Payment.invoice_id
        ).filter(Invoice.is_deleted == False)
        
        # Apply status filter if provided
        if status_filter and status_filter != "all":
            query = query.filter(Invoice.status == status_filter)
        
        # Get invoices with client information and payment status
        invoices = query.group_by(
            Invoice.id, Client.name
        ).offset(skip).limit(limit).all()

        # Convert to response format
        result = []
        for invoice, client_name, total_paid in invoices:
            invoice_dict = {
                "id": invoice.id,
                "number": invoice.number,
                "amount": float(invoice.amount),
                "currency": invoice.currency,
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "status": invoice.status,
                "notes": invoice.notes,
                "client_id": invoice.client_id,
                "client_name": client_name,
                "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
                "total_paid": float(total_paid),
                "is_recurring": invoice.is_recurring,
                "recurring_frequency": invoice.recurring_frequency,
                "discount_type": invoice.discount_type,
                "discount_value": float(invoice.discount_value) if invoice.discount_value else 0,
                "subtotal": float(invoice.subtotal) if invoice.subtotal else float(invoice.amount)
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

# Recycle Bin Endpoints (must come before /{invoice_id} route)

@router.get("/recycle-bin", response_model=List[DeletedInvoice])
async def get_deleted_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all deleted invoices in the recycle bin"""
    try:
        deleted_invoices = db.query(Invoice).filter(
            Invoice.is_deleted == True
        ).offset(skip).limit(limit).all()
        
        # Build response with additional info
        result = []
        for invoice in deleted_invoices:
            invoice_dict = {
                "id": invoice.id,
                "number": invoice.number,
                "amount": invoice.amount,
                "currency": invoice.currency,
                "due_date": invoice.due_date,
                "status": invoice.status,
                "notes": invoice.notes,
                "client_id": invoice.client_id,
                "is_recurring": invoice.is_recurring,
                "recurring_frequency": invoice.recurring_frequency,
                "discount_type": invoice.discount_type,
                "discount_value": invoice.discount_value,
                "subtotal": invoice.subtotal,
                "created_at": invoice.created_at,
                "updated_at": invoice.updated_at,
                "is_deleted": invoice.is_deleted,
                "deleted_at": invoice.deleted_at,
                "deleted_by": invoice.deleted_by,
                "deleted_by_username": invoice.deleted_by_user.email if invoice.deleted_by_user else None,
                "items": []  # Add items if needed
            }
            result.append(invoice_dict)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting deleted invoices: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get deleted invoices: {str(e)}"
        )

@router.post("/recycle-bin/empty", response_model=dict)
async def empty_recycle_bin(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Empty the entire recycle bin (admin only)"""
    try:
        # Only admins can empty the recycle bin
        require_admin(current_user, "empty the recycle bin")
        
        # Get all deleted invoices
        deleted_invoices = db.query(Invoice).filter(Invoice.is_deleted == True).all()
        count = len(deleted_invoices)
        
        if count == 0:
            return {"message": "Recycle bin is already empty", "deleted_count": 0}
        
        # Log the bulk deletion
        from models.models_per_tenant import InvoiceHistory
        history_entry = InvoiceHistory(
            invoice_id=None,  # No specific invoice
            user_id=current_user.id,
            action="recycle_bin_emptied",
            details=f"Recycle bin emptied by {current_user.email}, {count} invoices permanently deleted",
            current_values={"deleted_count": count}
        )
        db.add(history_entry)
        
        # Delete all invoices in recycle bin
        for invoice in deleted_invoices:
            db.delete(invoice)
        
        db.commit()
        
        return {
            "message": f"Recycle bin emptied successfully. {count} invoices permanently deleted.",
            "deleted_count": count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error emptying recycle bin: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to empty recycle bin: {str(e)}"
        )

@router.post("/{invoice_id}/restore", response_model=RecycleBinResponse)
async def restore_invoice(
    invoice_id: int,
    restore_request: RestoreInvoiceRequest = RestoreInvoiceRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Restore an invoice from the recycle bin"""
    try:
        # Find the deleted invoice
        db_invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == True
        ).first()
        
        if db_invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Deleted invoice not found"
            )
        
        # Restore the invoice
        db_invoice.is_deleted = False
        db_invoice.deleted_at = None
        db_invoice.deleted_by = None
        db_invoice.status = restore_request.new_status  # Set the new status
        db_invoice.updated_at = datetime.now(timezone.utc)
        
        # Log the restoration in invoice history
        from models.models_per_tenant import InvoiceHistory
        history_entry = InvoiceHistory(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action="restored_from_recycle",
            details=f"Invoice restored from recycle bin by {current_user.email}",
            current_values={
                "is_deleted": False, 
                "status": restore_request.new_status,
                "restored_at": datetime.now(timezone.utc).isoformat()
            }
        )
        db.add(history_entry)
        
        db.commit()
        
        return RecycleBinResponse(
            message="Invoice restored successfully",
            invoice_id=invoice_id,
            action="restored"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error restoring invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore invoice: {str(e)}"
        )

@router.delete("/{invoice_id}/permanent", response_model=RecycleBinResponse)
async def permanently_delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Permanently delete an invoice from the recycle bin"""
    try:
        # Find the deleted invoice
        db_invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == True
        ).first()
        
        if db_invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Deleted invoice not found"
            )
        
        # Only admins can permanently delete invoices
        require_admin(current_user, "permanently delete invoices")
        
        # Log the permanent deletion before deleting
        from models.models_per_tenant import InvoiceHistory
        history_entry = InvoiceHistory(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action="permanently_deleted",
            details=f"Invoice permanently deleted by {current_user.email}",
            previous_values={
                "number": db_invoice.number,
                "amount": float(db_invoice.amount),
                "client_id": db_invoice.client_id
            }
        )
        db.add(history_entry)
        db.commit()  # Commit the history first
        
        # Now permanently delete the invoice (this will cascade to related records)
        db.delete(db_invoice)
        db.commit()
        
        return RecycleBinResponse(
            message="Invoice permanently deleted",
            invoice_id=invoice_id,
            action="permanently_deleted"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error permanently deleting invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to permanently delete invoice: {str(e)}"
        )

@router.get("/{invoice_id}", response_model=InvoiceWithClient)
async def read_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Get invoice with client information and payment status
        # No tenant_id filtering needed since we're in the tenant's database
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
            Invoice.is_deleted == False
        ).group_by(
            Invoice.id, Client.name
        ).first()

        if invoice_tuple is None:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )

        invoice, client_name, total_paid = invoice_tuple
        
        logger.info(f"[DEBUG] Invoice from DB - custom_fields: {invoice.custom_fields}")
        logger.info(f"[DEBUG] Invoice from DB - type of custom_fields: {type(invoice.custom_fields)}")
        
        # Get invoice items
        items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()
        items_data = [
            {
                "id": item.id,
                "invoice_id": item.invoice_id,
                "description": item.description,
                "quantity": item.quantity,
                "price": item.price,
                "amount": item.amount
            }
            for item in items
        ]
        
        logger.info(f"Returning {len(items_data)} items for invoice {invoice_id}: {[{'id': item['id'], 'description': item['description'], 'description_length': len(item['description']) if item['description'] else 0} for item in items_data]}")
        
        invoice_dict = {
            "id": invoice.id,
            "number": invoice.number,
            "amount": float(invoice.amount),
            "currency": invoice.currency,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "status": invoice.status,
            "notes": invoice.notes,
            "client_id": invoice.client_id,
            "client_name": client_name,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
            "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
            "total_paid": float(total_paid),
            "is_recurring": invoice.is_recurring,
            "recurring_frequency": invoice.recurring_frequency,
            "discount_type": invoice.discount_type,
            "discount_value": float(invoice.discount_value) if invoice.discount_value else 0,
            "subtotal": float(invoice.subtotal) if invoice.subtotal else float(invoice.amount),
            "custom_fields": invoice.custom_fields,
            "items": items_data
        }
        logger.info(f"[DEBUG] Final invoice_dict response - custom_fields: {invoice_dict.get('custom_fields')}")
        logger.info(f"[DEBUG] Final invoice_dict response - custom_fields type: {type(invoice_dict.get('custom_fields'))}")
        logger.info(f"[DEBUG] Final invoice_dict response - all keys: {list(invoice_dict.keys())}")
        return invoice_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in read_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_FETCH_INVOICE
        )

@router.put("/{invoice_id}", response_model=InvoiceSchema)
async def update_invoice(
    invoice_id: int,
    invoice: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info("Invoice update endpoint called")
    logger.info(f"[DEBUG] Received custom_fields in update: {invoice.custom_fields}")
    # Check if user has permission to update invoices
    require_non_viewer(current_user, "update invoices")
    
    try:
        # No tenant_id filtering needed since we're in the tenant's database (exclude soft-deleted)
        db_invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()
        if db_invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )
        
        # Initialize currency service for validation
        currency_service = CurrencyService(db)
        
        # Capture old values before updating
        old_currency = db_invoice.currency
        old_discount_value = db_invoice.discount_value
        old_discount_type = db_invoice.discount_type
        old_amount = db_invoice.amount
        old_notes = db_invoice.notes
        old_custom_fields = db_invoice.custom_fields

        # Update invoice fields
        update_data = invoice.dict(exclude_unset=True)
        logger.info(f"[DEBUG] Update data received: {update_data}")
        for key, value in update_data.items():
            if key != "items":
                if key == 'amount':
                    value = float(value)
                elif key == 'currency':
                    # Validate currency code
                    if not currency_service.validate_currency_code(value):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid currency code: {value}"
                        )
                setattr(db_invoice, key, value)
        
        logger.info(f"[DEBUG] After setting fields, custom_fields in DB: {db_invoice.custom_fields}")
        
        # Handle items update if provided
        if invoice.items is not None:
            logger.info(f"Processing {len(invoice.items)} items for invoice {invoice_id}")
            logger.info(f"Items data: " + str([
                {
                    'id': getattr(item, 'id', None),
                    'description': getattr(item, 'description', None),
                    'description_length': len(getattr(item, 'description', '') or '')
                }
                for item in invoice.items
            ]))
            
            # Get existing items
            existing_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()
            existing_items_dict = {item.id: item for item in existing_items}
            logger.info(f"Found {len(existing_items)} existing items: {[item.id for item in existing_items]}")
            
            # Track which items are being updated
            updated_item_ids = set()
            
            # Process each item in the update request
            for item_data in invoice.items:
                logger.info(f"Processing item: id={getattr(item_data, 'id', None)}, description='{getattr(item_data, 'description', None)}', description_length={len(getattr(item_data, 'description', '') or '')}")
                
                if item_data.id and item_data.id in existing_items_dict:
                    # Update existing item
                    existing_item = existing_items_dict[item_data.id]
                    logger.info(f"Updating existing item {getattr(item_data, 'id', None)}: description from '{getattr(existing_item, 'description', None)}' to '{getattr(item_data, 'description', None)}'")
                    existing_item.description = getattr(item_data, 'description', existing_item.description)
                    existing_item.quantity = float(getattr(item_data, 'quantity', existing_item.quantity))
                    existing_item.price = float(getattr(item_data, 'price', existing_item.price))
                    existing_item.amount = float(getattr(item_data, 'quantity', existing_item.quantity)) * float(getattr(item_data, 'price', existing_item.price))
                    existing_item.updated_at = datetime.now(timezone.utc)
                    updated_item_ids.add(item_data.id)
                else:
                    # Create new item (no ID or ID not found)
                    logger.info(f"Creating new item with description: '{item_data.description}'")
                    db_item = InvoiceItem(
                        invoice_id=invoice_id,
                        description=item_data.description,
                        quantity=float(item_data.quantity),
                        price=float(item_data.price),
                        amount=float(item_data.quantity) * float(item_data.price)
                    )
                    db.add(db_item)
            
            # Remove items that are no longer in the list
            for item_id, item in existing_items_dict.items():
                if item_id not in updated_item_ids:
                    db.delete(item)
        
        # Create history entry for the update only if there are actual changes
        from models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        changes = []
        if invoice.currency and old_currency != invoice.currency:
            changes.append(f"Currency changed from {old_currency} to {invoice.currency}")
        if invoice.discount_value is not None and old_discount_value != invoice.discount_value:
            old_discount = f"{old_discount_value}{'%' if old_discount_type == 'percentage' else ' (fixed)'}"
            new_discount = f"{invoice.discount_value}{'%' if invoice.discount_type == 'percentage' else ' (fixed)'}"
            changes.append(f"Discount changed from {old_discount} to {new_discount}")
        if invoice.notes is not None and old_notes != invoice.notes:
            if not old_notes and invoice.notes:
                changes.append("Notes added")
            elif old_notes and not invoice.notes:
                changes.append("Notes removed")
            else:
                changes.append("Notes updated")
        if invoice.custom_fields is not None and old_custom_fields != invoice.custom_fields:
            changes.append("Custom fields updated")
            logger.info(f"[DEBUG] Custom fields changed from {old_custom_fields} to {invoice.custom_fields}")
        
        # Only create history entry if there are actual changes
        if changes:
            history_entry = InvoiceHistoryModel(
                invoice_id=invoice_id,
                user_id=current_user.id,
                action='update',
                details='; '.join(changes),
                previous_values={
                    'currency': old_currency,
                    'discount_value': old_discount_value,
                    'discount_type': old_discount_type,
                    'amount': old_amount,
                    'notes': old_notes
                },
                current_values={
                    'currency': db_invoice.currency,
                    'discount_value': db_invoice.discount_value,
                    'discount_type': db_invoice.discount_type,
                    'amount': db_invoice.amount,
                    'notes': db_invoice.notes
                }
            )
            db.add(history_entry)
            db_invoice.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(db_invoice)
            logger.info(f"[DEBUG] Saved custom_fields in DB (update): {db_invoice.custom_fields}")
            
            # Get updated items to include in response
            items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()
            items_data = [
                {
                    "id": item.id,
                    "invoice_id": item.invoice_id,
                    "description": item.description,
                    "quantity": item.quantity,
                    "price": item.price,
                    "amount": item.amount
                }
                for item in items
            ]
            
            logger.info(f"Returning {len(items_data)} items in response: {[{'id': item['id'], 'description': item['description'], 'description_length': len(item['description']) if item['description'] else 0} for item in items_data]}")
            
            # Convert to response format
            invoice_dict = {
                "id": db_invoice.id,
                "number": db_invoice.number,
                "amount": float(db_invoice.amount),
                "currency": db_invoice.currency,
                "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
                "status": db_invoice.status,
                "notes": db_invoice.notes,
                "client_id": db_invoice.client_id,
                "created_at": db_invoice.created_at.isoformat() if db_invoice.created_at else None,
                "updated_at": db_invoice.updated_at.isoformat() if db_invoice.updated_at else None,
                "is_recurring": db_invoice.is_recurring,
                "recurring_frequency": db_invoice.recurring_frequency,
                "discount_type": db_invoice.discount_type,
                "discount_value": float(db_invoice.discount_value) if db_invoice.discount_value else 0,
                "subtotal": float(db_invoice.subtotal) if db_invoice.subtotal else float(db_invoice.amount),
                "items": items_data
            }
            return invoice_dict
        else:
            # If no changes, just return the current state
            return {
                "id": db_invoice.id,
                "number": db_invoice.number,
                "amount": float(db_invoice.amount),
                "currency": db_invoice.currency,
                "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
                "status": db_invoice.status,
                "notes": db_invoice.notes,
                "client_id": db_invoice.client_id,
                "created_at": db_invoice.created_at.isoformat() if db_invoice.created_at else None,
                "updated_at": db_invoice.updated_at.isoformat() if db_invoice.updated_at else None,
                "is_recurring": db_invoice.is_recurring,
                "recurring_frequency": db_invoice.recurring_frequency,
                "discount_type": db_invoice.discount_type,
                "discount_value": float(db_invoice.discount_value) if db_invoice.discount_value else 0,
                "subtotal": float(db_invoice.subtotal) if db_invoice.subtotal else float(db_invoice.amount),
                "items": [] # No items if no changes
            }
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

@router.delete("/{invoice_id}", response_model=RecycleBinResponse)
async def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Move an invoice to the recycle bin (soft delete)"""
    try:
        # Find the invoice (exclude already deleted ones)
        db_invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()
        
        if db_invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found or already deleted"
            )
        
        # Soft delete the invoice
        db_invoice.is_deleted = True
        db_invoice.deleted_at = datetime.now(timezone.utc)
        db_invoice.deleted_by = current_user.id
        
        # Log the deletion in invoice history
        from models.models_per_tenant import InvoiceHistory
        history_entry = InvoiceHistory(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action="moved_to_recycle",
            details=f"Invoice moved to recycle bin by {current_user.email}",
            current_values={"is_deleted": True, "deleted_at": db_invoice.deleted_at.isoformat()}
        )
        db.add(history_entry)
        
        db.commit()
        
        return RecycleBinResponse(
            message="Invoice moved to recycle bin successfully",
            invoice_id=invoice_id,
            action="moved_to_recycle"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in delete_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to move invoice to recycle bin: {str(e)}"
        )

@router.post("/{invoice_id}/send-email")
async def send_invoice_email(
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
        "message": "Please use the /api/v1/email/send-invoice endpoint",
        "invoice_id": invoice_id,
        "redirect_url": f"/api/v1/email/send-invoice"
    }

@router.get("/stats/total-income", response_model=dict)
async def get_total_income(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Calculate total income from all paid invoices (exclude soft-deleted)
        total_income = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).filter(Invoice.is_deleted == False).scalar()

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

@router.post("/calculate-discount")
async def calculate_discount(
    subtotal: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate the applicable discount for a given subtotal using discount rules"""
    try:
        # Get all active discount rules, ordered by priority and min_amount
        discount_rules = db.query(DiscountRule).filter(
            DiscountRule.is_active == True
        ).order_by(DiscountRule.priority.desc(), DiscountRule.min_amount.desc()).all()
        
        # Find the first applicable rule
        applicable_rule = None
        for rule in discount_rules:
            if subtotal >= rule.min_amount:
                applicable_rule = rule
                break
        
        if not applicable_rule:
            return {
                "discount_type": "none",
                "discount_value": 0,
                "discount_amount": 0,
                "applied_rule": None
            }
        
        # Calculate discount amount
        if applicable_rule.discount_type == "percentage":
            discount_amount = (subtotal * applicable_rule.discount_value) / 100
        else:  # fixed amount
            discount_amount = min(applicable_rule.discount_value, subtotal)
        
        return {
            "discount_type": applicable_rule.discount_type,
            "discount_value": applicable_rule.discount_value,
            "discount_amount": discount_amount,
            "applied_rule": {
                "id": applicable_rule.id,
                "name": applicable_rule.name,
                "min_amount": applicable_rule.min_amount
            }
        }
    except Exception as e:
        logger.error(f"Error in calculate_discount: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate discount: {str(e)}"
        ) 

@router.get("/{invoice_id}/history")
async def get_invoice_history(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get update history for a specific invoice, including user name"""
    try:
        from models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel

        # Verify invoice exists (allow access to history for deleted invoices)
        # No tenant_id filtering needed since we're in the tenant's database
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id
        ).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Join with User to get user name (first_name + last_name)
        history = (
            db.query(
                InvoiceHistoryModel,
                (func.coalesce(User.first_name, '') + ' ' + func.coalesce(User.last_name, '')).label("user_name")
            )
            .join(User, InvoiceHistoryModel.user_id == User.id)
            .filter(
                InvoiceHistoryModel.invoice_id == invoice_id
            )
            .order_by(InvoiceHistoryModel.created_at.desc())
            .all()
        )

        # Return as list of dicts with user_name
        result = []
        for h, user_name in history:
            entry = h.__dict__.copy()
            entry["user_name"] = user_name
            result.append(entry)

        # Return only the actual history entries from the database
        # The invoice's updated_at is already reflected in the latest history entry
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching invoice history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch invoice history")

@router.post("/{invoice_id}/history", response_model=InvoiceHistory)
async def create_invoice_history_entry(
    invoice_id: int,
    history_entry: InvoiceHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new history entry for an invoice"""
    try:
        from models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        
        # Verify invoice exists (no tenant_id filtering needed since we're in the tenant's database)
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id
        ).first()
        
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )
        
        # Create history entry
        db_history = InvoiceHistoryModel(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action=history_entry.action,
            details=history_entry.details,
            previous_values=history_entry.previous_values,
            current_values=history_entry.current_values
        )
        
        db.add(db_history)
        db.commit()
        db.refresh(db_history)
        
        return db_history
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invoice history entry: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create invoice history entry"
        ) 