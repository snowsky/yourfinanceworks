from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, cast, String
import sqlalchemy as sa
from typing import List, Optional, Dict, Any
import logging
import traceback
from datetime import datetime, timezone, timedelta
from fastapi.responses import StreamingResponse, FileResponse
import mimetypes
from core.utils.pdf_generator import generate_invoice_pdf
import os
from pathlib import Path
import re
from pydantic import BaseModel
from typing import List as TypingList

from core.models.database import get_db
from core.models.models_per_tenant import Invoice, Client, User, InvoiceItem, DiscountRule, Settings, InvoiceAttachment
from core.models.models import MasterUser
from core.routers.payments import Payment
from core.schemas.invoice import InvoiceCreate, InvoiceUpdate, Invoice as InvoiceSchema, InvoiceWithClient, InvoiceHistory, InvoiceHistoryCreate, RecycleBinResponse, DeletedInvoice, RestoreInvoiceRequest, PaginatedInvoices, PaginatedDeletedInvoices
from core.routers.auth import get_current_user
from core.services.tenant_database_manager import tenant_db_manager
from core.services.currency_service import CurrencyService
from core.utils.invoice import generate_invoice_number
from core.utils.rbac import require_non_viewer, require_admin
from core.utils.audit import log_audit_event
from core.utils.file_deletion import delete_file_from_storage
from core.constants.error_codes import FAILED_TO_CREATE_INVOICE, FAILED_TO_FETCH_INVOICE
from core.utils.timezone import get_tenant_timezone_aware_datetime
from core.services.review_service import ReviewService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_attachment_info(invoice, new_attachments):
    """Helper function to get attachment info from modern attachment system"""
    has_attachment = len(new_attachments) > 0
    attachment_filename = new_attachments[0].filename if new_attachments else None

    # Fallback to legacy fields only if no modern attachments exist
    if not has_attachment and hasattr(invoice, 'attachment_filename') and invoice.attachment_filename:
        has_attachment = True
        attachment_filename = invoice.attachment_filename

    return has_attachment, attachment_filename

class BulkDeleteRequest(BaseModel):
    invoice_ids: TypingList[int]

router = APIRouter(prefix="/invoices", tags=["invoices"])


def make_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def normalize_to_midnight_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to naive midnight (no tzinfo) to avoid timezone shifts on clients.

    If dt is timezone-aware, its date component is used.
    If dt is naive, its date component is used.
    """
    if dt is None:
        return None
    return datetime(dt.year, dt.month, dt.day)

def normalize_to_midnight_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize to midnight UTC (tz-aware). Suitable for timestamptz columns like created_at."""
    if dt is None:
        return None
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)

@router.post("/", response_model=InvoiceWithClient, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    logger.info("Invoice create endpoint called")
    logger.info(f"Invoice data received: {invoice}")
    logger.info(f"Current user: {current_user.email if current_user else 'None'}")
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

        # Use provided invoice number or generate unique one
        # No tenant_id needed since we're in the tenant's database
        if invoice.number and invoice.number.strip():
            # Check if the provided number is already in use
            existing_invoice = db.query(Invoice).filter(
                Invoice.number == invoice.number.strip(),
                Invoice.is_deleted == False
            ).first()
            if existing_invoice:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invoice number '{invoice.number.strip()}' is already in use. Please choose a different number."
                )
            invoice_number = invoice.number.strip()
        else:
            invoice_number = generate_invoice_number(db)

        # Initialize currency service
        currency_service = CurrencyService(db)

        # Determine invoice currency
        client_preferred_currency = currency_service.get_client_preferred_currency(invoice.client_id)
        invoice_currency = client_preferred_currency if client_preferred_currency else invoice.currency

        # Validate currency
        if not currency_service.validate_currency_code(invoice_currency):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid currency code: {invoice_currency}"
            )

        # No tenant_id needed since each tenant has its own database
        logger.debug(f"[DEBUG] Received custom_fields: {invoice.custom_fields}")
        # Normalize incoming dates to avoid off-by-one issues
        incoming_due_date = normalize_to_midnight_naive(invoice.due_date) if invoice.due_date else None
        incoming_created_at = normalize_to_midnight_utc(invoice.date) if getattr(invoice, 'date', None) else None

        # Get default notes from core.settings if no notes provided
        default_notes = None
        if not invoice.notes and not invoice.description:
            try:
                invoice_settings_record = db.query(Settings).filter(Settings.key == "invoice_settings").first()
                if invoice_settings_record and invoice_settings_record.value:
                    default_notes = invoice_settings_record.value.get("notes", "")
            except Exception as e:
                logger.warning(f"Failed to retrieve default notes from core.settings: {e}")

        db_invoice = Invoice(
            number=invoice_number,
            amount=float(invoice.amount),
            currency=invoice_currency,
            due_date=incoming_due_date,
            status=invoice.status,
            # Persist description into notes field for backward compatibility, or use default notes
            notes=invoice.description or invoice.notes or default_notes,
            client_id=invoice.client_id,
            created_at=incoming_created_at or get_tenant_timezone_aware_datetime(db),
            updated_at=incoming_created_at or get_tenant_timezone_aware_datetime(db),
            is_recurring=invoice.is_recurring,
            recurring_frequency=invoice.recurring_frequency,
            custom_fields=invoice.custom_fields,
            show_discount_in_pdf=invoice.show_discount_in_pdf,
            payer=invoice.payer,
            labels=invoice.labels,
            created_by_user_id=current_user.id  # User attribution
        )

        # Calculate subtotal and amount
        items_list = invoice.items or []
        if items_list:
            calculated_subtotal = sum(
                float(item_data.quantity) * float(item_data.price) for item_data in items_list
            )
        else:
            calculated_subtotal = float(invoice.amount)
        db_invoice.subtotal = calculated_subtotal

        # Apply discount if provided; if no items were provided, keep the provided amount
        db_invoice.discount_type = invoice.discount_type or "percentage"
        db_invoice.discount_value = float(invoice.discount_value or 0)

        if items_list:
            if db_invoice.discount_value > 0:
                if db_invoice.discount_type == "percentage":
                    discount_amount = (calculated_subtotal * db_invoice.discount_value) / 100
                else:  # fixed
                    discount_amount = db_invoice.discount_value
                db_invoice.amount = calculated_subtotal - discount_amount
            else:
                db_invoice.amount = calculated_subtotal
        else:
            db_invoice.amount = float(invoice.amount)

        # Ensure due_date default if not provided
        if db_invoice.due_date is None:
            default_due = datetime.now(timezone.utc) + timedelta(days=30)
            # Store as naive midnight to avoid timezone shifts
            db_invoice.due_date = normalize_to_midnight_naive(default_due)

        db.add(db_invoice)
        db.flush()  # Get the invoice ID

        # Optionally link to a bank statement transaction to prevent duplicates
        try:
            txn_id = None
            # Support passing link via custom_fields: { bank_transaction_id: <id> }
            cf = getattr(invoice, 'custom_fields', None)
            if isinstance(cf, dict):
                txn_id = cf.get('bank_transaction_id') or cf.get('bank_statement_transaction_id') or cf.get('transaction_id')
            if txn_id:
                from core.models.models_per_tenant import BankStatementTransaction
                txn = db.query(BankStatementTransaction).filter(BankStatementTransaction.id == int(txn_id)).first()
                if txn is not None:
                    if getattr(txn, 'invoice_id', None):
                        # Already linked – treat as idempotent and return created invoice; UI should block earlier
                        logger.info(f"Bank txn {txn_id} already linked to invoice {txn.invoice_id}")
                    else:
                        txn.invoice_id = db_invoice.id
        except Exception:
            logger.warning("Failed to link bank statement transaction to invoice", exc_info=True)

        # If an initial paid_amount is provided OR status is paid, create a payment record
        initial_paid = float(getattr(invoice, 'paid_amount', 0) or 0)
        should_create_payment = initial_paid > 0 or (invoice.status == 'paid')
        payment_amount = initial_paid if initial_paid > 0 else (float(db_invoice.amount) if invoice.status == 'paid' else 0)
        if should_create_payment and payment_amount > 0:
            try:
                pay = Payment(
                    invoice_id=db_invoice.id,
                    amount=payment_amount,
                    currency=db_invoice.currency,
                    payment_date=normalize_to_midnight_utc(db_invoice.created_at) or datetime.now(timezone.utc),
                    payment_method="system",
                    reference_number=f"AUTO-{db_invoice.number}",
                    notes="Auto-created from invoice creation"
                )
                db.add(pay)
            except Exception:
                logger.warning("Failed to create auto payment on invoice creation", exc_info=True)
        logger.info(f"[DEBUG] Saved custom_fields in DB: {db_invoice.custom_fields}")

        # Create invoice items with inventory integration
        from core.services.inventory_integration_service import InventoryIntegrationService
        integration_service = InventoryIntegrationService(db)

        for item_data in items_list:
            # Handle inventory item integration
            inventory_item_id = getattr(item_data, 'inventory_item_id', None)
            unit_of_measure = getattr(item_data, 'unit_of_measure', None)

            # If inventory_item_id is provided, populate from inventory
            if inventory_item_id:
                try:
                    inventory_data = integration_service.populate_invoice_item_from_inventory(
                        inventory_item_id, float(item_data.quantity)
                    )
                    # Use inventory data to populate item
                    description = inventory_data['description']
                    price = inventory_data['unit_price'] if item_data.price == 0 else float(item_data.price)
                    unit_of_measure = inventory_data.get('unit_of_measure', unit_of_measure)
                except Exception as e:
                    logger.warning(f"Failed to populate invoice item from inventory {inventory_item_id}: {e}")
                    # Fall back to provided data
                    description = item_data.description
                    price = float(item_data.price)
            else:
                description = item_data.description
                price = float(item_data.price)

            db_item = InvoiceItem(
                invoice_id=db_invoice.id,
                inventory_item_id=inventory_item_id,
                description=description,
                quantity=float(item_data.quantity),
                price=price,
                amount=float(item_data.quantity) * price,
                unit_of_measure=unit_of_measure
            )
            db.add(db_item)

        # Create history entry for invoice creation
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        from core.utils.audit_sanitizer import sanitize_history_values

        current_values = {
            'number': db_invoice.number,
            'amount': db_invoice.amount,
            'currency': db_invoice.currency,
            'status': db_invoice.status,
            'due_date': db_invoice.due_date.isoformat() if db_invoice.due_date else None,
            'notes': db_invoice.notes  # This will be sanitized
        }

        creation_history = InvoiceHistoryModel(
            invoice_id=db_invoice.id,
            user_id=current_user.id,
            action='creation',
            details=f'Invoice {db_invoice.number} created',
            previous_values=None,
            current_values=sanitize_history_values(current_values)
        )
        db.add(creation_history)

        db.commit()
        db.refresh(db_invoice)

        # Send notification
        try:
            from core.utils.notifications import notify_invoice_created
            notify_invoice_created(db, db_invoice, current_user.id)
        except Exception as e:
            logger.warning(f"Failed to send invoice creation notification: {str(e)}")

        # Log audit event (sanitize sensitive data)
        from core.utils.audit_sanitizer import sanitize_for_context
        try:
            # Use model_dump with exclude_unset to avoid serialization issues
            invoice_data = invoice.model_dump(exclude_unset=True, exclude_none=True)
            audit_details = sanitize_for_context(invoice_data, 'invoice_creation')
        except Exception as e:
            logger.warning(f"Failed to serialize invoice data for audit: {e}")
            # Fallback to basic audit details
            audit_details = {
                'client_id': invoice.client_id,
                'amount': invoice.amount,
                'currency': invoice.currency,
                'status': invoice.status
            }

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="invoice",
            resource_id=str(db_invoice.id),
            resource_name=f"Invoice {db_invoice.number}",
            details=audit_details,
            status="success"
        )

        # Build response including description from notes and inventory information
        items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == db_invoice.id).all()
        items_data = [
            {
                "id": item.id,
                "invoice_id": item.invoice_id,
                "inventory_item_id": item.inventory_item_id,
                "description": item.description,
                "quantity": item.quantity,
                "price": item.price,
                "amount": item.amount,
                "unit_of_measure": item.unit_of_measure
            }
            for item in items
        ]

        # Get invoice with client information and payment status (same as read_invoice)
        invoice_tuple = db.query(
            Invoice,
            Client.name.label('client_name'),
            Client.company.label('client_company'),
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid')
        ).join(
            Client, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Invoice.id == Payment.invoice_id
        ).options(
            selectinload(Invoice.created_by)
        ).filter(
            Invoice.id == db_invoice.id,
            Invoice.is_deleted == False
        ).group_by(
            Invoice.id, Client.name, Client.company
        ).first()

        if invoice_tuple is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve created invoice"
            )

        invoice, client_name, client_company, total_paid = invoice_tuple

        # Force refresh of database session to ensure we get latest data
        db.expire_all()

        # Get invoice items with inventory details
        items_query = db.query(InvoiceItem).options(
            joinedload(InvoiceItem.inventory_item)
        ).filter(InvoiceItem.invoice_id == db_invoice.id).all()

        items_data = []
        for item in items_query:
            # Properly serialize inventory item data without SQLAlchemy InstanceState
            inventory_item_data = None
            if item.inventory_item:
                inventory_item_data = {
                    "id": item.inventory_item.id,
                    "name": item.inventory_item.name,
                    "sku": item.inventory_item.sku,
                    "description": item.inventory_item.description,
                    "category_id": item.inventory_item.category_id,
                    "current_stock": float(item.inventory_item.current_stock) if item.inventory_item.current_stock else 0,
                    "unit_price": float(item.inventory_item.unit_price) if item.inventory_item.unit_price else 0,
                    "currency": item.inventory_item.currency,
                    "unit_of_measure": item.inventory_item.unit_of_measure,
                    "track_stock": item.inventory_item.track_stock,
                    "is_active": item.inventory_item.is_active
                }

            item_data = {
                "id": item.id,
                "invoice_id": item.invoice_id,
                "inventory_item_id": item.inventory_item_id,
                "description": item.description,
                "quantity": item.quantity,
                "price": item.price,
                "amount": item.amount,
                "unit_of_measure": item.unit_of_measure,
                "inventory_item": inventory_item_data
            }
            items_data.append(item_data)

        # Get new-style attachments
        from core.models.models_per_tenant import InvoiceAttachment
        new_attachments = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == db_invoice.id,
            InvoiceAttachment.is_active == True
        ).all()

        logger.info(f"Invoice created successfully with ID: {invoice.id}")

        # Get creator information
        from core.services.attribution_service import AttributionService
        created_by_username = None
        created_by_email = None

        def format_user_name(user):
            if user.first_name and user.last_name:
                return f"{user.first_name} {user.last_name}"
            elif user.first_name:
                return user.first_name
            return user.email

        if invoice.created_by:
            created_by_username = format_user_name(invoice.created_by)
            created_by_email = invoice.created_by.email

        # Process gamification event for invoice creation
        try:
            from core.services.financial_event_processor import create_financial_event_processor
            event_processor = create_financial_event_processor(db)

            invoice_data = {
                "client_id": invoice.client_id,
                "invoice_number": invoice.number,
                "total": float(invoice.amount)
            }

            gamification_result = await event_processor.process_invoice_created(
                user_id=current_user.id,
                invoice_id=invoice.id,
                invoice_data=invoice_data
            )

            if gamification_result:
                logger.info(
                    f"Gamification event processed for invoice {invoice.id}: "
                    f"points={gamification_result.points_awarded}"
                )
        except Exception as e:
            logger.warning(f"Failed to process gamification event for invoice {invoice.id}: {e}")
            # Don't fail the invoice creation if gamification processing fails

        return {
            "id": invoice.id,
            "number": invoice.number,
            "amount": float(invoice.amount),
            "currency": invoice.currency,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "status": invoice.status,
            "labels": invoice.labels,
            "notes": invoice.notes,
            "description": invoice.notes,
            "client_id": invoice.client_id,
            "client_name": client_name,
            "client_company": client_company,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
            "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
            "total_paid": float(total_paid),
            "is_recurring": invoice.is_recurring,
            "recurring_frequency": invoice.recurring_frequency,
            "discount_type": invoice.discount_type,
            "discount_value": float(invoice.discount_value) if invoice.discount_value else 0,
            "subtotal": float(invoice.subtotal) if invoice.subtotal else float(invoice.amount),
            "items": items_data,
            "custom_fields": invoice.custom_fields if invoice.custom_fields is not None else {},
            "show_discount_in_pdf": invoice.show_discount_in_pdf,
            "payer": invoice.payer,
            "has_attachment": get_attachment_info(invoice, new_attachments)[0],
            "attachment_filename": get_attachment_info(invoice, new_attachments)[1],
            "attachments": [{
                "id": att.id,
                "filename": att.filename,
                "file_size": att.file_size,
                "attachment_type": att.attachment_type,
                "created_at": att.created_at.isoformat()
            } for att in new_attachments],
            "attachment_count": len(new_attachments),
            "created_by_user_id": invoice.created_by_user_id,
            "created_by_username": created_by_username,
            "created_by_email": created_by_email,
            "review_status": invoice.review_status,
            "review_result": invoice.review_result,
            "reviewed_at": invoice.reviewed_at.isoformat() if invoice.reviewed_at else None
        }
    except HTTPException as he:
        logger.error(f"HTTPException in create_invoice: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Error in create_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_CREATE_INVOICE
        )

@router.post("/{invoice_id}/clone", response_model=InvoiceSchema, status_code=status.HTTP_201_CREATED)
async def clone_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Clone an existing invoice and create a new draft with a new number and ID.

    - Copies all primitive fields and items from the source invoice
    - Generates a new invoice number
    - Resets status to 'draft'
    - Does not copy payments or attachments
    """
    # Check permissions
    require_non_viewer(current_user, "clone invoices")

    try:
        # Fetch source invoice (exclude soft-deleted)
        source_invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if source_invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Fetch items for source invoice
        source_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()

        # Always generate new invoice number for cloned invoices
        new_number = generate_invoice_number(db)

        # Build new invoice (reset status to draft, keep due_date as-is)
        cloned_invoice = Invoice(
            number=new_number,
            amount=float(source_invoice.amount),
            currency=source_invoice.currency,
            due_date=source_invoice.due_date,
            status="draft",
            notes=source_invoice.notes,
            client_id=source_invoice.client_id,
            created_at=get_tenant_timezone_aware_datetime(db),
            updated_at=get_tenant_timezone_aware_datetime(db),
            is_recurring=source_invoice.is_recurring,
            recurring_frequency=source_invoice.recurring_frequency,
            custom_fields=source_invoice.custom_fields,
            show_discount_in_pdf=source_invoice.show_discount_in_pdf,
            payer=source_invoice.payer,
            labels=source_invoice.labels
        )

        # If the original has items, recalc subtotal/amount like create endpoint
        if source_items:
            calculated_subtotal = sum(float(item.quantity) * float(item.price) for item in source_items)
        else:
            calculated_subtotal = float(source_invoice.amount)
        cloned_invoice.subtotal = calculated_subtotal

        # Copy discount fields and recalc total
        cloned_invoice.discount_type = source_invoice.discount_type or "percentage"
        cloned_invoice.discount_value = float(source_invoice.discount_value or 0)

        if source_items:
            if cloned_invoice.discount_value > 0:
                if cloned_invoice.discount_type == "percentage":
                    discount_amount = (calculated_subtotal * cloned_invoice.discount_value) / 100
                else:
                    discount_amount = cloned_invoice.discount_value
                cloned_invoice.amount = calculated_subtotal - discount_amount
            else:
                cloned_invoice.amount = calculated_subtotal
        else:
            cloned_invoice.amount = float(source_invoice.amount)

        # Default due_date if None
        if cloned_invoice.due_date is None:
            cloned_invoice.due_date = (datetime.now(timezone.utc) + timedelta(days=30))

        # Persist invoice
        db.add(cloned_invoice)
        db.flush()

        # Clone items
        for s_item in source_items:
            db_item = InvoiceItem(
                invoice_id=cloned_invoice.id,
                description=s_item.description,
                quantity=float(s_item.quantity),
                price=float(s_item.price),
                amount=float(s_item.quantity) * float(s_item.price),
                inventory_item_id=s_item.inventory_item_id,
                unit_of_measure=s_item.unit_of_measure
            )
            db.add(db_item)

        # History for clone on new invoice
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        history_entry = InvoiceHistoryModel(
            invoice_id=cloned_invoice.id,
            user_id=current_user.id,
            action='cloned',
            details=f"Invoice cloned from {source_invoice.number} (ID {source_invoice.id})",
            previous_values=None,
            current_values={
                'source_invoice_id': source_invoice.id,
                'source_invoice_number': source_invoice.number,
                'number': cloned_invoice.number,
                'amount': cloned_invoice.amount,
                'currency': cloned_invoice.currency,
                'status': cloned_invoice.status,
                'due_date': cloned_invoice.due_date.isoformat() if cloned_invoice.due_date else None,
            }
        )
        db.add(history_entry)

        db.commit()
        db.refresh(cloned_invoice)

        # Audit log
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CLONE",
            resource_type="invoice",
            resource_id=str(cloned_invoice.id),
            resource_name=f"Invoice {cloned_invoice.number}",
            details={"cloned_from": source_invoice.id},
            status="success"
        )

        # Build response
        items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == cloned_invoice.id).all()
        items_data = [
            {
                "id": item.id,
                "invoice_id": item.invoice_id,
                "inventory_item_id": item.inventory_item_id,
                "description": item.description,
                "quantity": item.quantity,
                "price": item.price,
                "amount": item.amount,
                "unit_of_measure": item.unit_of_measure
            }
            for item in items
        ]

        return {
            "id": cloned_invoice.id,
            "number": cloned_invoice.number,
            "amount": float(cloned_invoice.amount),
            "currency": cloned_invoice.currency,
            "due_date": cloned_invoice.due_date.isoformat() if cloned_invoice.due_date else None,
            "status": cloned_invoice.status,
            "notes": cloned_invoice.notes,
            "description": cloned_invoice.notes,
            "client_id": cloned_invoice.client_id,
            "created_at": cloned_invoice.created_at.isoformat() if cloned_invoice.created_at else None,
            "updated_at": cloned_invoice.updated_at.isoformat() if cloned_invoice.updated_at else None,
            "is_recurring": cloned_invoice.is_recurring,
            "recurring_frequency": cloned_invoice.recurring_frequency,
            "discount_type": cloned_invoice.discount_type,
            "discount_value": float(cloned_invoice.discount_value) if cloned_invoice.discount_value else 0,
            "subtotal": float(cloned_invoice.subtotal) if cloned_invoice.subtotal else float(cloned_invoice.amount),
            "items": items_data,
            "custom_fields": cloned_invoice.custom_fields if cloned_invoice.custom_fields is not None else {},
            "show_discount_in_pdf": cloned_invoice.show_discount_in_pdf,
            "payer": cloned_invoice.payer,
            "has_attachment": False,
            "attachment_filename": None,
            "attachments": [],
            "attachment_count": 0,
            "review_status": cloned_invoice.review_status,
            "review_result": cloned_invoice.review_result,
            "reviewed_at": cloned_invoice.reviewed_at.isoformat() if cloned_invoice.reviewed_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cloning invoice {invoice_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to clone invoice")

@router.get("/", response_model=PaginatedInvoices)
async def read_invoices(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    label: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

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
        ).options(
            selectinload(Invoice.created_by)
        ).filter(Invoice.is_deleted == False)

        # Apply label filter if provided
        if label:
            query = query.filter(sa.cast(Invoice.labels, sa.String).ilike(f"%{label}%"))

        # Calculate total count before pagination
        total_count = query.group_by(Invoice.id, Client.name).count()

        # Get invoices with client information and payment status
        invoices = query.group_by(
            Invoice.id, Client.name
        ).order_by(Invoice.created_at.desc(), Invoice.id.desc()).offset(skip).limit(limit).all()

        # Convert to response format
        result = []
        for invoice, client_name, total_paid in invoices:
            # Check for new-style attachments
            from core.models.models_per_tenant import InvoiceAttachment
            new_attachments = db.query(InvoiceAttachment).filter(
                InvoiceAttachment.invoice_id == invoice.id,
                InvoiceAttachment.is_active == True
            ).all()

            # Get creator information - explicitly load since selectinload doesn't work with tuple queries
            created_by_username = None
            created_by_email = None
            if invoice.created_by_user_id:
                creator = db.query(User).filter(User.id == invoice.created_by_user_id).first()
                if creator:
                    if creator.first_name and creator.last_name:
                        created_by_username = f"{creator.first_name} {creator.last_name}"
                    elif creator.first_name:
                        created_by_username = creator.first_name
                    else:
                        created_by_username = creator.email
                    created_by_email = creator.email

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
                "paid_amount": float(total_paid),
                "is_recurring": invoice.is_recurring,
                "recurring_frequency": invoice.recurring_frequency,
                "discount_type": invoice.discount_type,
                "discount_value": float(invoice.discount_value) if invoice.discount_value else 0,
                "subtotal": float(invoice.subtotal) if invoice.subtotal else float(invoice.amount),
                "custom_fields": invoice.custom_fields if invoice.custom_fields is not None else {},
                "show_discount_in_pdf": invoice.show_discount_in_pdf,
                "payer": invoice.payer,
                "labels": invoice.labels,
                "has_attachment": get_attachment_info(invoice, new_attachments)[0],
                "attachment_filename": get_attachment_info(invoice, new_attachments)[1],
                "created_by_user_id": invoice.created_by_user_id,
                "created_by_username": created_by_username,
                "created_by_email": created_by_email,
                "review_status": invoice.review_status,
                "review_result": invoice.review_result,
                "reviewed_at": invoice.reviewed_at.isoformat() if invoice.reviewed_at else None
            }
            result.append(invoice_dict)

        return {
            "items": result,
            "total": total_count
        }
    except Exception as e:
        logger.error(f"Error in read_invoices: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch invoices: {str(e)}"
        )# Recycle Bin Endpoints (must come before /{invoice_id} route)

@router.post("/bulk-labels")
async def bulk_labels(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Bulk add or remove labels from invoices"""
    require_non_viewer(current_user, "bulk update invoices")

    ids = payload.get("ids", [])
    action = payload.get("action") # "add" or "remove"
    label = payload.get("label", "").strip()

    if not ids or action not in ["add", "remove"] or label == "":
        raise HTTPException(status_code=400, detail="Invalid request payload")

    try:
        invoices = db.query(Invoice).filter(Invoice.id.in_(ids)).all()

        for inv in invoices:
            current_labels = list(inv.labels or [])
            if action == "add":
                if label not in current_labels:
                    current_labels.append(label)
            elif action == "remove":
                if label in current_labels:
                    current_labels.remove(label)

            inv.labels = current_labels
            inv.updated_at = get_tenant_timezone_aware_datetime(db)

        db.commit()
        return {"success": True, "count": len(invoices)}
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk_labels: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update labels")

@router.get("/recycle-bin", response_model=PaginatedDeletedInvoices)
async def get_deleted_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get all deleted invoices in the recycle bin"""
    try:
        query = db.query(Invoice).filter(
            Invoice.is_deleted == True
        )

        total_count = query.count()

        deleted_invoices = query.offset(skip).limit(limit).all()

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
                "items": [],  # Add items if needed
                "show_discount_in_pdf": invoice.show_discount_in_pdf,
                "description": invoice.notes, # Map notes to description if needed by schema
                "custom_fields": invoice.custom_fields
            }
            result.append(invoice_dict)

        return {
            "items": result,
            "total": total_count
        }

    except Exception as e:
        logger.error(f"Error getting deleted invoices: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get deleted invoices: {str(e)}"
        )

@router.post("/recycle-bin/empty", response_model=dict)
async def empty_recycle_bin(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Empty the entire recycle bin (admin only)"""
    try:
        # Only admins can empty the recycle bin
        require_admin(current_user, "empty the recycle bin")

        # Get count of deleted invoices
        count = db.query(Invoice).filter(Invoice.is_deleted == True).count()

        if count == 0:
            return {"message": "Recycle bin is already empty", "deleted_count": 0}

        # Define the background task function
        def delete_invoices_background(tenant_id: int, user_id: int, user_email: str, count: int):
            """Background task to delete all invoices in recycle bin"""
            from core.models.database import set_tenant_context
            from core.services.tenant_database_manager import tenant_db_manager

            # Set tenant context for this background task
            set_tenant_context(tenant_id)

            # Get tenant-specific session
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db_task = SessionLocal_tenant()
            try:
                # Get all deleted invoices
                deleted_invoices = db_task.query(Invoice).filter(Invoice.is_deleted == True).all()

                # Delete all attachments from storage before deleting invoices
                try:
                    from core.models.models_per_tenant import InvoiceAttachment
                    import asyncio

                    async def delete_files():
                        # Get all invoice IDs
                        invoice_ids = [inv.id for inv in deleted_invoices]

                        # Get all attachments for these invoices
                        attachments = db_task.query(InvoiceAttachment).filter(
                            InvoiceAttachment.invoice_id.in_(invoice_ids)
                        ).all()

                        # Delete attachments individually (still needed for proper cleanup)
                        for att in attachments:
                            if att.file_path:
                                try:
                                    await delete_file_from_storage(att.file_path, tenant_id, user_id, db_task)
                                except Exception as e:
                                    logger.warning(f"Failed to delete attachment {att.file_path}: {e}")

                        # Also delete legacy attachment paths
                        for invoice in deleted_invoices:
                            if invoice.attachment_path:
                                try:
                                    await delete_file_from_storage(invoice.attachment_path, tenant_id, user_id, db_task)
                                except Exception as e:
                                    logger.warning(f"Failed to delete legacy attachment {invoice.attachment_path}: {e}")

                        if attachments:
                            logger.info(f"Deleted {len(attachments)} attachment(s) from storage during recycle bin empty")

                    # Run async file deletion
                    asyncio.run(delete_files())

                except Exception as e:
                    logger.warning(f"Failed to delete attachments during recycle bin empty: {e}")

                # Delete all invoices in recycle bin
                for invoice in deleted_invoices:
                    db_task.delete(invoice)

                db_task.commit()

                # Audit log for empty recycle bin
                log_audit_event(
                    db=db_task,
                    user_id=user_id,
                    user_email=user_email,
                    action="Empty Recycle Bin",
                    resource_type="invoice",
                    resource_id=None,
                    resource_name=None,
                    details={"message": f"Recycle bin emptied, {count} invoices permanently deleted."},
                    status="success"
                )

                logger.info(f"Successfully emptied invoice recycle bin: {count} invoices deleted")

            except Exception as e:
                db_task.rollback()
                logger.error(f"Error in background task emptying invoice recycle bin: {str(e)}")
            finally:
                db_task.close()

        # Add the deletion task to background tasks
        background_tasks.add_task(
            delete_invoices_background,
            current_user.tenant_id,
            current_user.id,
            current_user.email,
            count
        )

        return {
            "message": f"Deletion of {count} invoice(s) has been initiated. You will be notified when complete.",
            "deleted_count": count,
            "status": "processing"
        }

    except HTTPException:
        raise
    except Exception as e:
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
    current_user: MasterUser = Depends(get_current_user)
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
        db_invoice.updated_at = get_tenant_timezone_aware_datetime(db)

        # Log the restoration in invoice history
        from core.models.models_per_tenant import InvoiceHistory
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

        # Audit log for restore
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="Restore",
            resource_type="invoice",
            resource_id=str(invoice_id),
            resource_name=f"Invoice {db_invoice.number}",
            details={"message": "Invoice restored from recycle bin"},
            status="success"
        )

        return RecycleBinResponse(
            message="Invoice restored successfully",
            invoice_id=invoice_id,
            action="restored"
        )

    except HTTPException:
        raise
    except Exception as e:
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
    current_user: MasterUser = Depends(get_current_user)
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

        # Check if invoice has linked expenses - prevent deletion if it does
        if db_invoice.expenses and len(db_invoice.expenses) > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot permanently delete invoice that has linked expenses. Please unlink or delete the expenses first."
            )

        # Only admins can permanently delete invoices
        require_admin(current_user, "permanently delete invoices")

        # Delete all attachments from storage before deleting the invoice
        try:
            from core.models.models_per_tenant import InvoiceAttachment
            attachments = db.query(InvoiceAttachment).filter(
                InvoiceAttachment.invoice_id == invoice_id
            ).all()

            for att in attachments:
                if att.file_path:
                    await delete_file_from_storage(att.file_path, current_user.tenant_id, current_user.id, db)

            if attachments:
                logger.info(f"Deleted {len(attachments)} attachment(s) from storage for invoice {invoice_id}")
        except Exception as e:
            logger.warning(f"Failed to delete attachments for invoice {invoice_id}: {e}")

        # Delete legacy attachment if present
        if db_invoice.attachment_path:
            await delete_file_from_storage(db_invoice.attachment_path, current_user.tenant_id, current_user.id, db)

        # Unlink any bank statement transactions that reference this invoice  
        try:
            from core.models.models_per_tenant import BankStatementTransaction
            linked_transactions = db.query(BankStatementTransaction).filter(
                BankStatementTransaction.invoice_id == invoice_id
            ).all()
            for txn in linked_transactions:
                txn.invoice_id = None
            if linked_transactions:
                logger.info(f"Unlinked {len(linked_transactions)} bank transactions from permanently deleted invoice {invoice_id}")
        except Exception as e:
            logger.warning(f"Failed to unlink bank transactions from permanently deleted invoice {invoice_id}: {e}")

        # Log the permanent deletion before deleting
        from core.models.models_per_tenant import InvoiceHistory
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

        # Audit log for permanent delete
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="Permanent Delete",
            resource_type="invoice",
            resource_id=str(invoice_id),
            resource_name=f"Invoice {db_invoice.number}",
            details={"message": "Invoice permanently deleted"},
            status="success"
        )

        return RecycleBinResponse(
            message="Invoice permanently deleted",
            invoice_id=invoice_id,
            action="permanently_deleted"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error permanently deleting invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to permanently delete invoice: {str(e)}"
        )

@router.get("/ai-status")
async def get_ai_status(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Check if AI/LLM is configured and available for PDF processing"""
    try:
        from core.models.models_per_tenant import AIConfig as AIConfigModel

        # Check if there's at least one active and tested AI configuration, prioritizing default
        active_config = db.query(AIConfigModel).filter(
            AIConfigModel.is_active == True,
            AIConfigModel.tested == True
        ).order_by(AIConfigModel.is_default.desc()).first()

        return {
            "configured": active_config is not None
        }
    except Exception as e:
        logger.error(f"Error checking AI status: {str(e)}")
        return {
            "configured": False
        }

@router.get("/{invoice_id}", response_model=InvoiceWithClient)
async def read_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    logger.info(f"🔍 READ_INVOICE ENDPOINT CALLED - invoice_id: {invoice_id}, user: {current_user.email}")
    try:
        # Get invoice with client information and payment status
        # No tenant_id filtering needed since we're in the tenant's database
        # Note: We don't load Invoice.created_by relationship here because it points to
        # the tenant DB User model which has encrypted fields. Instead, we fetch user
        # info from the master DB later.
        invoice_tuple = db.query(
            Invoice,
            Client.name.label('client_name'),
            Client.company.label('client_company'),
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid')
        ).join(
            Client, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Invoice.id == Payment.invoice_id
        ).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).group_by(
            Invoice.id, Client.name, Client.company
        ).first()

        if invoice_tuple is None:
            logger.warning(f"User {current_user.email} attempted to access invoice {invoice_id} which doesn't exist in their tenant database")
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )

        invoice, client_name, client_company, total_paid = invoice_tuple

        logger.info(f"[DEBUG] Invoice from DB - custom_fields: {invoice.custom_fields}")
        logger.info(f"[DEBUG] Invoice from DB - type of custom_fields: {type(invoice.custom_fields)}")

        # Force refresh of database session to ensure we get latest data
        db.expire_all()

        # Get invoice items with inventory details
        items_query = db.query(InvoiceItem).options(
            joinedload(InvoiceItem.inventory_item)
        ).filter(InvoiceItem.invoice_id == invoice_id).all()

        logger.info(f"Raw items from database query: {[(item.id, item.description) for item in items_query]}")

        items_data = []
        for item in items_query:
            item_data = {
                "id": item.id,
                "invoice_id": item.invoice_id,
                "description": item.description,
                "quantity": item.quantity,
                "price": item.price,
                "amount": item.amount,
                "inventory_item_id": item.inventory_item_id,
                "unit_of_measure": item.unit_of_measure
            }

            # Add inventory item details if linked
            if item.inventory_item_id and item.inventory_item:
                item_data["inventory_item"] = {
                    "id": item.inventory_item.id,
                    "name": item.inventory_item.name,
                    "description": item.inventory_item.description,
                    "sku": item.inventory_item.sku,
                    "unit_price": item.inventory_item.unit_price,
                    "cost_price": item.inventory_item.cost_price,
                    "currency": item.inventory_item.currency,
                    "track_stock": item.inventory_item.track_stock,
                    "current_stock": item.inventory_item.current_stock,
                    "minimum_stock": item.inventory_item.minimum_stock,
                    "unit_of_measure": item.inventory_item.unit_of_measure,
                    "item_type": item.inventory_item.item_type,
                    "is_active": item.inventory_item.is_active,
                    "barcode": item.inventory_item.barcode,
                    "category_id": item.inventory_item.category_id
                }
            else:
                item_data["inventory_item"] = None

            items_data.append(item_data)

        logger.info(f"Returning {len(items_data)} items for invoice {invoice_id}: {[{'id': item['id'], 'description': item['description'], 'description_length': len(item['description']) if item['description'] else 0} for item in items_data]}")

        # Get new-style attachments for read endpoint
        from core.models.models_per_tenant import InvoiceAttachment
        new_attachments = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        ).all()

        # Get creator information - explicitly load since selectinload doesn't work with tuple queries
        created_by_username = None
        created_by_email = None
        if invoice.created_by_user_id:
            creator = db.query(User).filter(User.id == invoice.created_by_user_id).first()
            if creator:
                if creator.first_name and creator.last_name:
                    created_by_username = f"{creator.first_name} {creator.last_name}"
                elif creator.first_name:
                    created_by_username = creator.first_name
                else:
                    created_by_username = creator.email
                created_by_email = creator.email

        invoice_dict = {
            "date": invoice.created_at.isoformat() if invoice.created_at else None,
            "id": invoice.id,
            "number": invoice.number,
            "amount": float(invoice.amount),
            "currency": invoice.currency,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "status": invoice.status,
            "labels": invoice.labels,
            "notes": invoice.notes,
            "client_id": invoice.client_id,
            "client_name": client_name,
            "client_company": client_company,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
            "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
            "total_paid": float(total_paid),
            "paid_amount": float(total_paid),
            "is_recurring": invoice.is_recurring,
            "recurring_frequency": invoice.recurring_frequency,
            "discount_type": invoice.discount_type,
            "discount_value": float(invoice.discount_value) if invoice.discount_value else 0,
            "subtotal": float(invoice.subtotal) if invoice.subtotal else float(invoice.amount),
            "custom_fields": invoice.custom_fields if invoice.custom_fields is not None else {},
            "items": items_data,
            "show_discount_in_pdf": invoice.show_discount_in_pdf,
            "payer": invoice.payer,
            "has_attachment": get_attachment_info(invoice, new_attachments)[0],
            "attachment_filename": get_attachment_info(invoice, new_attachments)[1],
            "attachments": [{
                "id": att.id,
                "filename": att.filename,
                "file_size": att.file_size,
                "attachment_type": att.attachment_type,
                "created_at": att.created_at.isoformat()
            } for att in new_attachments],
            "attachment_count": len(new_attachments),
            "created_by_user_id": invoice.created_by_user_id,
            "created_by_username": created_by_username,
            "created_by_email": created_by_email,
            "review_status": invoice.review_status,
            "review_result": invoice.review_result,
            "reviewed_at": invoice.reviewed_at.isoformat() if invoice.reviewed_at else None
        }

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

@router.put("/{invoice_id}", response_model=InvoiceWithClient)
async def update_invoice(
    invoice_id: int,
    invoice: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    from core.models.database import get_tenant_context
    current_tenant = get_tenant_context()
    logger.info(f"Invoice update endpoint called - User: {current_user.email}, Tenant: {current_tenant}, Invoice ID: {invoice_id}")
    logger.debug(f"[DEBUG] Received custom_fields in update: {invoice.custom_fields}")
    # Check if user has permission to update invoices
    require_non_viewer(current_user, "update invoices")

    try:
        # Query invoice in current tenant's database (exclude soft-deleted)
        db_invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()
        if db_invoice is None:
            logger.warning(f"User {current_user.email} (tenant {current_tenant}) attempted to access invoice {invoice_id} which doesn't exist in their tenant database")
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )

        # Check if invoice is paid and prevent updates except status and payment-related changes
        update_data = invoice.model_dump(exclude_unset=True)
        if db_invoice.status == "paid" and "status" in update_data:
            # If changing status from paid, allow the change
            pass
        elif db_invoice.status == "paid":
            # Allow status updates and payment-related updates for paid invoices
            non_allowed_updates = {k: v for k, v in update_data.items()
                                 if k not in ["status", "paid_amount", "total_paid"]}
            if non_allowed_updates:
                logger.warning(f"User {current_user.email} attempted to modify paid invoice {invoice_id} (fields: {list(non_allowed_updates.keys())})")
                raise HTTPException(
                    status_code=400,
                    detail="Paid invoices can only be modified for status and payment updates"
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
        old_show_discount_in_pdf = db_invoice.show_discount_in_pdf
        old_status = db_invoice.status
        old_client_id = db_invoice.client_id

        # Update invoice fields
        update_data = invoice.model_dump(exclude_unset=True)
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
                elif key == 'due_date' and value is not None:
                    # Normalize due_date to naive midnight to avoid timezone shifts
                    value = normalize_to_midnight_naive(value)
                elif key == 'date' and value is not None:
                    # Map invoice.date to created_at for persistence
                    db_invoice.created_at = normalize_to_midnight_utc(value)
                    db_invoice.updated_at = db_invoice.created_at
                    continue  # don't setattr a non-existent column 'date'
                elif key == 'attachment_filename' and value is None:
                    # Handle attachment deletion - both old and new style
                    old_filename = db_invoice.attachment_filename

                    if db_invoice.attachment_path and os.path.exists(db_invoice.attachment_path):
                        try:
                            os.remove(db_invoice.attachment_path)
                            logger.info(f"Deleted attachment file: {db_invoice.attachment_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete attachment file: {e}")
                    db_invoice.attachment_path = None
                    db_invoice.attachment_filename = None

                    # Also soft delete any new-style attachments
                    from core.models.models_per_tenant import InvoiceAttachment
                    existing_new_attachments = db.query(InvoiceAttachment).filter(
                        InvoiceAttachment.invoice_id == invoice_id,
                        InvoiceAttachment.is_active == True
                    ).all()

                    deleted_attachments = []
                    for attachment in existing_new_attachments:
                        deleted_attachments.append({
                            'id': attachment.id,
                            'filename': attachment.filename,
                            'file_size': attachment.file_size
                        })
                        attachment.is_active = False
                        attachment.updated_at = get_tenant_timezone_aware_datetime(db)
                        logger.info(f"Soft deleted new-style attachment: {attachment.filename}")

                    # Create history entry for attachment deletion
                    if old_filename or deleted_attachments:
                        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel

                        if old_filename and deleted_attachments:
                            details = f'Attachments deleted: {old_filename} and {len(deleted_attachments)} new-style attachment(s)'
                        elif old_filename:
                            details = f'Attachment deleted: {old_filename}'
                        else:
                            filenames = [att['filename'] for att in deleted_attachments]
                            details = f'Attachment(s) deleted: {", ".join(filenames)}'

                        history_entry = InvoiceHistoryModel(
                            invoice_id=invoice_id,
                            user_id=current_user.id,
                            action='attachment_deleted',
                            details=details,
                            current_values={
                                'old_filename': old_filename,
                                'deleted_attachments': deleted_attachments
                            }
                        )
                        db.add(history_entry)

                    continue
                elif key == 'paid_amount' and value is not None:
                    # Create a payment adjustment if allowed
                    # Allow payment updates for approved invoices to support partial payments
                    # Only block payment updates for invoices that are already fully paid
                    if db_invoice.status == "paid" and float(value) >= db_invoice.amount:
                        # Already fully paid invoices cannot increase payment amount; skip
                        logger.info(f"Skipping payment amount update for invoice {db_invoice.id}: invoice is already fully paid and payment amount would not increase")
                        continue

                    # Calculate current total paid from existing payments
                    from core.models.models_per_tenant import Payment as PaymentModel
                    existing_payments = db.query(PaymentModel).filter(PaymentModel.invoice_id == db_invoice.id).all()
                    current_paid = sum(p.amount for p in existing_payments) if existing_payments else 0

                    # Calculate incremental payment amount
                    new_paid_amount = float(value)
                    incremental_amount = new_paid_amount - current_paid

                    # Only create payment if there's an actual increase
                    if incremental_amount > 0:
                        try:
                            pay = PaymentModel(
                                invoice_id=db_invoice.id,
                                amount=incremental_amount,
                                currency=db_invoice.currency,
                                payment_date=datetime.now(timezone.utc),
                                payment_method="manual",
                                reference_number=f"ADJ-{db_invoice.number}-{int(datetime.now(timezone.utc).timestamp())}",
                                notes=f"Manual paid amount update via invoice API. New total: ${new_paid_amount:.2f}"
                            )
                            db.add(pay)

                            # Create history entry for payment update
                            from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
                            history_entry = InvoiceHistoryModel(
                                invoice_id=db_invoice.id,
                                user_id=current_user.id,
                                action='payment_updated',
                                details=f'Payment updated: ${current_paid:.2f} → ${new_paid_amount:.2f} (incremental: ${incremental_amount:.2f})',
                                previous_values={'paid_amount': current_paid},
                                current_values={'paid_amount': new_paid_amount, 'incremental_amount': incremental_amount}
                            )
                            db.add(history_entry)

                        except Exception:
                            logger.warning("Failed to create payment from paid_amount update", exc_info=True)
                    elif incremental_amount < 0:
                        # Handle payment decrease - remove payments from most recent to oldest
                        try:
                            amount_to_remove = abs(incremental_amount)
                            payments_to_adjust = db.query(PaymentModel).filter(
                                PaymentModel.invoice_id == db_invoice.id
                            ).order_by(PaymentModel.payment_date.desc()).all()

                            removed_payments = []
                            remaining_to_remove = amount_to_remove

                            for payment in payments_to_adjust:
                                if remaining_to_remove <= 0:
                                    break

                                if payment.amount <= remaining_to_remove:
                                    # Remove entire payment
                                    removed_payments.append(f"${payment.amount:.2f} ({payment.reference_number})")
                                    remaining_to_remove -= payment.amount
                                    db.delete(payment)
                                else:
                                    # Partially reduce this payment
                                    old_amount = payment.amount
                                    payment.amount = payment.amount - remaining_to_remove
                                    removed_payments.append(f"${remaining_to_remove:.2f} from ${old_amount:.2f} ({payment.reference_number})")
                                    remaining_to_remove = 0

                            # Create history entry for payment decrease
                            from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
                            history_entry = InvoiceHistoryModel(
                                invoice_id=db_invoice.id,
                                user_id=current_user.id,
                                action='payment_decreased',
                                details=f'Payment decreased: ${current_paid:.2f} → ${new_paid_amount:.2f} (removed: ${amount_to_remove:.2f}). Adjusted: {", ".join(removed_payments)}',
                                previous_values={'paid_amount': current_paid},
                                current_values={'paid_amount': new_paid_amount, 'amount_removed': amount_to_remove}
                            )
                            db.add(history_entry)

                            logger.info(f"Decreased payment for invoice {db_invoice.id}: removed ${amount_to_remove:.2f}")

                        except Exception as e:
                            logger.warning(f"Failed to decrease payment from paid_amount update: {e}", exc_info=True)
                    # If incremental_amount == 0, no change needed
                    continue
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
                    existing_item.updated_at = get_tenant_timezone_aware_datetime(db)
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

        # Commit all item changes (updates, creates, deletes) to the database
        db.commit()
        logger.info(f"Committed all item changes for invoice {invoice_id}")

        # Refresh the database session to ensure we see the latest changes
        db.refresh(db_invoice)
        logger.info(f"Refreshed invoice object after item changes")

        # Verify items were saved by fetching them again
        updated_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()
        logger.info(f"Verified {len(updated_items)} items in database after commit: {[(item.id, item.description[:30] + '...' if len(item.description) > 30 else item.description) for item in updated_items]}")

        # Create history entry for the update only if there are actual changes
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        changes = []
        if invoice.status is not None and old_status != invoice.status:
            changes.append(f"Status changed from {old_status} to {invoice.status}")
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
        # Only track custom fields changes if there are actual differences
        if invoice.custom_fields is not None:
            # Normalize both for comparison (handle None vs empty dict)
            old_cf = old_custom_fields or {}
            new_cf = invoice.custom_fields or {}
            if old_cf != new_cf:
                changes.append("Custom fields updated")
                logger.info(f"[DEBUG] Custom fields changed from {old_custom_fields} to {invoice.custom_fields}")
        if invoice.show_discount_in_pdf is not None and old_show_discount_in_pdf != invoice.show_discount_in_pdf:
            changes.append(f"Show discount in PDF changed from {old_show_discount_in_pdf} to {invoice.show_discount_in_pdf}")

        # Track client change
        if invoice.client_id is not None and old_client_id != invoice.client_id:
            try:
                old_client = db.query(Client).filter(Client.id == old_client_id).first()
                new_client = db.query(Client).filter(Client.id == invoice.client_id).first()

                # Format client info as "Name (email)" or fallback to ID
                if old_client:
                    old_client_info = f"{old_client.name}"
                    if old_client.email:
                        old_client_info += f" ({old_client.email})"
                else:
                    old_client_info = f"Client ID {old_client_id}"

                if new_client:
                    new_client_info = f"{new_client.name}"
                    if new_client.email:
                        new_client_info += f" ({new_client.email})"
                else:
                    new_client_info = f"Client ID {invoice.client_id}"

                changes.append(f"Client changed from {old_client_info} to {new_client_info}")
            except Exception as e:
                # Fallback to IDs if names cannot be resolved
                print(f"Error resolving client names: {e}")
                changes.append(f"Client changed from Client ID {old_client_id} to Client ID {invoice.client_id}")

        # Handle inventory stock movements for status changes
        if "status" in update_data and old_status != invoice.status:
            from core.services.inventory_integration_service import InventoryIntegrationService
            integration_service = InventoryIntegrationService(db)

            # Process stock movements when invoice becomes payable
            if invoice.status in ['paid', 'completed']:
                try:
                    logger.info(f"Triggering stock movement processing for invoice {invoice_id} with status '{invoice.status}'")
                    movements = integration_service.process_invoice_stock_movements(db_invoice, current_user.id)
                    if movements:
                        logger.info(f"Successfully processed {len(movements)} stock movements for invoice {invoice_id}")
                        changes.append(f"Processed {len(movements)} inventory stock movements")
                    else:
                        logger.info(f"No stock movements were processed for invoice {invoice_id} (no inventory items found)")
                except Exception as e:
                    logger.error(f"Failed to process stock movements for invoice {invoice_id}: {e}")
                    # Don't fail the invoice update, just log the error

            # Reverse stock movements when invoice is cancelled/refunded
            elif invoice.status in ['cancelled', 'refunded'] and old_status in ['paid', 'completed']:
                try:
                    movements = integration_service.reverse_invoice_stock_movements(db_invoice, current_user.id)
                    if movements:
                        logger.info(f"Reversed {len(movements)} stock movements for invoice {invoice_id}")
                        changes.append(f"Reversed {len(movements)} inventory stock movements")
                except Exception as e:
                    logger.error(f"Failed to reverse stock movements for invoice {invoice_id}: {e}")
                    # Don't fail the invoice update, just log the error

        # Only create history entry if there are actual changes
        if changes and len(changes) > 0:
            from core.utils.audit_sanitizer import sanitize_history_values

            previous_values = {
                'currency': old_currency,
                'discount_value': old_discount_value,
                'discount_type': old_discount_type,
                'amount': old_amount,
                'notes': old_notes,  # This will be sanitized
                'client_id': old_client_id,
                'show_discount_in_pdf': old_show_discount_in_pdf
            }

            current_values = {
                'currency': db_invoice.currency,
                'discount_value': db_invoice.discount_value,
                'discount_type': db_invoice.discount_type,
                'amount': db_invoice.amount,
                'notes': db_invoice.notes,  # This will be sanitized
                'show_discount_in_pdf': db_invoice.show_discount_in_pdf,
                'client_id': db_invoice.client_id
            }

            history_entry = InvoiceHistoryModel(
                invoice_id=invoice_id,
                user_id=current_user.id,
                action='update',
                details='; '.join(changes),
                previous_values=sanitize_history_values(previous_values),
                current_values=sanitize_history_values(current_values)
            )
            db.add(history_entry)
            # Recalculate subtotal and amount based on updated items and discount
            recalculated_subtotal = db.query(
                sa.func.coalesce(sa.func.sum(InvoiceItem.quantity * InvoiceItem.price), 0)
            ).filter(InvoiceItem.invoice_id == invoice_id).scalar()
            db_invoice.subtotal = recalculated_subtotal

            # Apply discount if provided in update or use existing
            db_invoice.discount_type = invoice.discount_type or db_invoice.discount_type or "percentage"
            db_invoice.discount_value = float(invoice.discount_value) if invoice.discount_value is not None else float(db_invoice.discount_value or 0)

            if db_invoice.discount_value > 0:
                if db_invoice.discount_type == "percentage":
                    discount_amount = (recalculated_subtotal * db_invoice.discount_value) / 100
                else: # fixed
                    discount_amount = db_invoice.discount_value
                db_invoice.amount = recalculated_subtotal - discount_amount
            else:
                db_invoice.amount = recalculated_subtotal

            db_invoice.updated_at = get_tenant_timezone_aware_datetime(db)
            db.commit()
            db.refresh(db_invoice)
            logger.info(f"[DEBUG] Saved custom_fields in DB (update): {db_invoice.custom_fields}")

            # Add audit log for invoice update
            log_audit_event(
                db=db,
                user_id=current_user.id,
                user_email=current_user.email,
                action="UPDATE",
                resource_type="invoice",
                resource_id=str(db_invoice.id),
                resource_name=f"Invoice {db_invoice.number}",
                details={"changes": changes},
                status="success"
            )

            # Get updated items to include in response with inventory information
            items = db.query(InvoiceItem).options(
                joinedload(InvoiceItem.inventory_item)
            ).filter(InvoiceItem.invoice_id == invoice_id).all()

            items_data = []
            for item in items:
                item_data = {
                    "id": item.id,
                    "invoice_id": item.invoice_id,
                    "inventory_item_id": item.inventory_item_id,
                    "description": item.description,
                    "quantity": item.quantity,
                    "price": item.price,
                    "amount": item.amount,
                    "unit_of_measure": item.unit_of_measure
                }

                # Add inventory item details if linked
                if item.inventory_item_id and item.inventory_item:
                    item_data["inventory_item"] = {
                        "id": item.inventory_item.id,
                        "name": item.inventory_item.name,
                        "description": item.inventory_item.description,
                        "sku": item.inventory_item.sku,
                        "unit_price": item.inventory_item.unit_price,
                        "cost_price": item.inventory_item.cost_price,
                        "currency": item.inventory_item.currency,
                        "track_stock": item.inventory_item.track_stock,
                        "current_stock": item.inventory_item.current_stock,
                        "minimum_stock": item.inventory_item.minimum_stock,
                        "unit_of_measure": item.inventory_item.unit_of_measure,
                        "item_type": item.inventory_item.item_type,
                        "is_active": item.inventory_item.is_active,
                        "barcode": item.inventory_item.barcode,
                        "category_id": item.inventory_item.category_id
                    }
                else:
                    item_data["inventory_item"] = None

                items_data.append(item_data)

            logger.info(f"Returning {len(items_data)} items in response: {[{'id': item['id'], 'description': item['description'], 'description_length': len(item['description']) if item['description'] else 0} for item in items_data]}")

            # Get client name and total paid for response
            client = db.query(Client).filter(Client.id == db_invoice.client_id).first()
            total_paid = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.invoice_id == invoice_id).scalar() or 0

            # Convert to response format
            # Get new-style attachments for update endpoint
            from core.models.models_per_tenant import InvoiceAttachment
            new_attachments = db.query(InvoiceAttachment).filter(
                InvoiceAttachment.invoice_id == invoice_id,
                InvoiceAttachment.is_active == True
            ).all()

            invoice_dict = {
                "id": db_invoice.id,
                "number": db_invoice.number,
                "amount": float(db_invoice.amount),
                "currency": db_invoice.currency,
                "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
                "status": db_invoice.status,
                "notes": db_invoice.notes,
                "client_id": db_invoice.client_id,
                "client_name": client.name if client else "Unknown",
                "total_paid": float(total_paid),
                "created_at": db_invoice.created_at.isoformat() if db_invoice.created_at else None,
                "updated_at": db_invoice.updated_at.isoformat() if db_invoice.updated_at else None,
                "is_recurring": db_invoice.is_recurring,
                "recurring_frequency": db_invoice.recurring_frequency,
                "discount_type": db_invoice.discount_type,
                "discount_value": float(db_invoice.discount_value) if db_invoice.discount_value else 0,
                "subtotal": float(db_invoice.subtotal) if db_invoice.subtotal else float(db_invoice.amount),
                "items": items_data,
                "show_discount_in_pdf": db_invoice.show_discount_in_pdf,
                "payer": db_invoice.payer,
                "has_attachment": get_attachment_info(db_invoice, new_attachments)[0],
                "attachment_filename": get_attachment_info(db_invoice, new_attachments)[1],
                "attachments": [{
                    "id": att.id,
                    "filename": att.filename,
                    "file_size": att.file_size,
                    "attachment_type": att.attachment_type,
                    "created_at": att.created_at.isoformat()
                } for att in new_attachments],
                "attachment_count": len(new_attachments)
            }
            return invoice_dict
        else:
            # If no changes, just return the current state with actual items
            items = db.query(InvoiceItem).options(
                joinedload(InvoiceItem.inventory_item)
            ).filter(InvoiceItem.invoice_id == invoice_id).all()

            items_data = []
            for item in items:
                item_data = {
                    "id": item.id,
                    "invoice_id": item.invoice_id,
                    "inventory_item_id": item.inventory_item_id,
                    "description": item.description,
                    "quantity": item.quantity,
                    "price": item.price,
                    "amount": item.amount,
                    "unit_of_measure": item.unit_of_measure
                }

                # Add inventory item details if linked
                if item.inventory_item_id and item.inventory_item:
                    item_data["inventory_item"] = {
                        "id": item.inventory_item.id,
                        "name": item.inventory_item.name,
                        "description": item.inventory_item.description,
                        "sku": item.inventory_item.sku,
                        "unit_price": item.inventory_item.unit_price,
                        "cost_price": item.inventory_item.cost_price,
                        "currency": item.inventory_item.currency,
                        "track_stock": item.inventory_item.track_stock,
                        "current_stock": item.inventory_item.current_stock,
                        "minimum_stock": item.inventory_item.minimum_stock,
                        "unit_of_measure": item.inventory_item.unit_of_measure,
                        "item_type": item.inventory_item.item_type,
                        "is_active": item.inventory_item.is_active,
                        "barcode": item.inventory_item.barcode,
                        "category_id": item.inventory_item.category_id
                    }
                else:
                    item_data["inventory_item"] = None

                items_data.append(item_data)

            # Get client name and total paid for response
            client = db.query(Client).filter(Client.id == db_invoice.client_id).first()
            total_paid = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.invoice_id == invoice_id).scalar() or 0

            # Get new-style attachments for update endpoint (no changes case)
            from core.models.models_per_tenant import InvoiceAttachment
            new_attachments = db.query(InvoiceAttachment).filter(
                InvoiceAttachment.invoice_id == invoice_id,
                InvoiceAttachment.is_active == True
            ).all()

            return {
                "id": db_invoice.id,
                "number": db_invoice.number,
                "amount": float(db_invoice.amount),
                "currency": db_invoice.currency,
                "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
                "status": db_invoice.status,
                "notes": db_invoice.notes,
                "client_id": db_invoice.client_id,
                "client_name": client.name if client else "Unknown",
                "total_paid": float(total_paid),
                "created_at": db_invoice.created_at.isoformat() if db_invoice.created_at else None,
                "updated_at": db_invoice.updated_at.isoformat() if db_invoice.updated_at else None,
                "is_recurring": db_invoice.is_recurring,
                "recurring_frequency": db_invoice.recurring_frequency,
                "discount_type": db_invoice.discount_type,
                "discount_value": float(db_invoice.discount_value) if db_invoice.discount_value else 0,
                "subtotal": float(db_invoice.subtotal) if db_invoice.subtotal else float(db_invoice.amount),
                "items": items_data,
                "show_discount_in_pdf": db_invoice.show_discount_in_pdf,
                "payer": db_invoice.payer,
                "has_attachment": get_attachment_info(db_invoice, new_attachments)[0],
                "attachment_filename": get_attachment_info(db_invoice, new_attachments)[1],
                "attachments": [{
                    "id": att.id,
                    "filename": att.filename,
                    "file_size": att.file_size,
                    "attachment_type": att.attachment_type,
                    "created_at": att.created_at.isoformat()
                } for att in new_attachments],
                "attachment_count": len(new_attachments)
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update invoice: {str(e)}"
        )

@router.delete("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_invoices(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Bulk delete invoices (move to recycle bin)"""
    require_non_viewer(current_user, "bulk delete invoices")

    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        if not payload.invoice_ids:
            raise HTTPException(status_code=400, detail="No invoice IDs provided")

        # Limit bulk delete to prevent performance issues
        if len(payload.invoice_ids) > 100:
            raise HTTPException(status_code=400, detail="Cannot delete more than 100 invoices at once")

        # Get all invoices to delete
        invoices_to_delete = db.query(Invoice).filter(
            Invoice.id.in_(payload.invoice_ids),
            Invoice.is_deleted == False
        ).all()

        if not invoices_to_delete:
            raise HTTPException(status_code=404, detail="No invoices found")

        # Check if any invoices cannot be deleted
        for invoice in invoices_to_delete:
            # Prevent deleting an invoice that has linked expenses
            if invoice.expenses and len(invoice.expenses) > 0:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot delete invoice #{invoice.id} that has linked expenses. Please unlink or delete expenses first."
                )

        # Process each invoice for deletion
        deleted_count = 0
        for invoice in invoices_to_delete:
            try:
                # Unlink any bank statement transactions that reference this invoice
                try:
                    from core.models.models_per_tenant import BankStatementTransaction
                    linked_transactions = db.query(BankStatementTransaction).filter(
                        BankStatementTransaction.invoice_id == invoice.id
                    ).all()
                    for txn in linked_transactions:
                        txn.invoice_id = None
                    if linked_transactions:
                        logger.info(f"Unlinked {len(linked_transactions)} bank transactions from deleted invoice {invoice.id}")
                except Exception as e:
                    logger.warning(f"Failed to unlink bank transactions from invoice {invoice.id}: {e}")

                # Soft delete invoice
                invoice.is_deleted = True
                invoice.deleted_at = get_tenant_timezone_aware_datetime(db)
                invoice.deleted_by = current_user.id

                # Log deletion in invoice history
                from core.models.models_per_tenant import InvoiceHistory
                history_entry = InvoiceHistory(
                    invoice_id=invoice.id,
                    user_id=current_user.id,
                    action="moved_to_recycle",
                    details=f"Invoice moved to recycle bin via bulk delete"
                )
                db.add(history_entry)

                # Log audit event
                log_audit_event(
                    db=db,
                    user_id=current_user.id,
                    user_email=current_user.email,
                    action="Bulk Delete",
                    resource_type="invoice",
                    resource_id=str(invoice.id),
                    resource_name=f"Invoice {invoice.number}",
                    details={"message": "Invoice moved to recycle bin via bulk delete"},
                    status="success"
                )

                deleted_count += 1

            except Exception as e:
                logger.error(f"Failed to delete invoice {invoice.id}: {e}")
                db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete invoice #{invoice.id}: {str(e)}"
                )

        db.commit()
        logger.info(f"Successfully moved {deleted_count} invoices to recycle bin")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk delete invoices: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="Failed to bulk delete invoices"
        )

@router.delete("/{invoice_id}", response_model=RecycleBinResponse)
async def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
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

        # Check if invoice has linked expenses - prevent deletion if it does
        if db_invoice.expenses and len(db_invoice.expenses) > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete invoice that has linked expenses. Please unlink or delete the expenses first."
            )

        # Unlink any bank statement transactions that reference this invoice
        try:
            from core.models.models_per_tenant import BankStatementTransaction
            linked_transactions = db.query(BankStatementTransaction).filter(
                BankStatementTransaction.invoice_id == invoice_id
            ).all()
            for txn in linked_transactions:
                txn.invoice_id = None
            if linked_transactions:
                logger.info(f"Unlinked {len(linked_transactions)} bank transactions from deleted invoice {invoice_id}")
        except Exception as e:
            logger.warning(f"Failed to unlink bank transactions from invoice {invoice_id}: {e}")

        # Soft delete the invoice
        db_invoice.is_deleted = True
        db_invoice.deleted_at = get_tenant_timezone_aware_datetime(db)
        db_invoice.deleted_by = current_user.id

        # Log the deletion in invoice history
        from core.models.models_per_tenant import InvoiceHistory
        history_entry = InvoiceHistory(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action="moved_to_recycle",
            details=f"Invoice moved to recycle bin by {current_user.email}",
            current_values={"is_deleted": True, "deleted_at": db_invoice.deleted_at.isoformat()}
        )
        db.add(history_entry)
        db.commit()

        # Audit log for soft delete
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="Soft Delete",
            resource_type="invoice",
            resource_id=str(invoice_id),
            resource_name=f"Invoice {db_invoice.number}",
            details={"message": "Invoice moved to recycle bin"},
            status="success"
        )

        return RecycleBinResponse(
            message="Invoice moved to recycle bin successfully",
            invoice_id=invoice_id,
            action="moved_to_recycle"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_invoice: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to move invoice to recycle bin: {str(e)}"
        )

@router.post("/{invoice_id}/send-email")
async def send_invoice_email(
    invoice_id: int,
    current_user: MasterUser = Depends(get_current_user)
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
    current_user: MasterUser = Depends(get_current_user)
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

@router.get("/stats/comprehensive", response_model=dict)
async def get_comprehensive_stats(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get comprehensive invoice statistics including counts and financial data"""
    try:
        # Get all invoices (exclude soft-deleted)
        total_invoices_query = db.query(Invoice).filter(Invoice.is_deleted == False)
        total_invoices = total_invoices_query.count()

        # Count by status
        paid_invoices = total_invoices_query.filter(Invoice.status == 'paid').count()
        unpaid_invoices = total_invoices_query.filter(Invoice.status.in_(['pending', 'draft'])).count()
        overdue_invoices = total_invoices_query.filter(Invoice.status == 'overdue').count()

        # Calculate total revenue from paid invoices
        total_revenue = db.query(
            func.coalesce(func.sum(Invoice.amount), 0)
        ).filter(
            Invoice.status == 'paid',
            Invoice.is_deleted == False
        ).scalar()

        # Calculate average invoice amount
        average_invoice_amount = float(total_revenue / paid_invoices) if paid_invoices > 0 else 0.0

        return {
            "total_invoices": total_invoices,
            "total_revenue": float(total_revenue) if total_revenue is not None else 0.0,
            "average_invoice_amount": average_invoice_amount,
            "paid_invoices": paid_invoices,
            "unpaid_invoices": unpaid_invoices,
            "overdue_invoices": overdue_invoices
        }
    except Exception as e:
        logger.error(f"Error in get_comprehensive_stats: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate comprehensive statistics: {str(e)}"
        )

@router.post("/calculate-discount")
async def calculate_discount(
    subtotal: float,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
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
    current_user: MasterUser = Depends(get_current_user)
):
    """Get update history for a specific invoice, including user name"""
    # Set tenant context for proper decryption of user names
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel

        # Verify invoice exists (allow access to history for deleted invoices)
        # No tenant_id filtering needed since we're in the tenant's database
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id
        ).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Get history entries first
        history_entries = (
            db.query(InvoiceHistoryModel)
            .filter(InvoiceHistoryModel.invoice_id == invoice_id)
            .order_by(InvoiceHistoryModel.created_at.desc())
            .all()
        )

        # Get unique user IDs from history
        user_ids = list(set(h.user_id for h in history_entries))

        # Fetch users separately to ensure proper decryption
        users = {}
        if user_ids:
            user_records = db.query(User).filter(User.id.in_(user_ids)).all()
            for user in user_records:
                # Access the encrypted fields to trigger decryption
                first_name = user.first_name or ''
                last_name = user.last_name or ''
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    # Fallback to email if no name
                    full_name = user.email or f"User {user.id}"
                users[user.id] = full_name

        # Return as list of dicts with user_name
        result = []
        for h in history_entries:
            entry = h.__dict__.copy()
            entry["user_name"] = users.get(h.user_id, f"User {h.user_id}")
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
    current_user: MasterUser = Depends(get_current_user)
):
    """Create a new history entry for an invoice"""
    try:
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel

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

@router.post("/{invoice_id}/upload-attachment")
async def upload_invoice_attachment(
    invoice_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Upload an attachment for an invoice using cloud storage with local fallback"""
    logger.info(f"🔍 UPLOAD ENDPOINT CALLED - invoice_id: {invoice_id}, filename: {file.filename}, content_type: {file.content_type}")
    try:
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Validate file type
        allowed_types = {
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'image/jpeg': '.jpg',
            'image/png': '.png'
        }

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail="File type not allowed. Supported types: PDF, DOC, DOCX, JPG, PNG"
            )

        # Enforce max file size (e.g., 10 MB)
        MAX_BYTES = 10 * 1024 * 1024
        contents = await file.read()
        if len(contents) > MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 10 MB"
            )

        # Basic content sniffing for PDFs (starts with %PDF)
        if file.content_type == 'application/pdf':
            header_bytes = contents[:4]
            if header_bytes != b'%PDF':
                raise HTTPException(status_code=400, detail="Invalid PDF file")

        # Get tenant context
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
        if not tenant_id:
            raise HTTPException(status_code=500, detail="Tenant context not available")

        # Sanitize filename
        original_name = file.filename or "attachment"
        base_name = os.path.basename(original_name)
        base_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)

        # Get tenant context
        try:
            try:
                from commercial.cloud_storage.service import CloudStorageService
                from commercial.cloud_storage.config import get_cloud_storage_config

                cloud_config = get_cloud_storage_config()
                cloud_storage_service = CloudStorageService(db, cloud_config)

                # Store file using cloud storage with automatic fallback
                storage_result = await cloud_storage_service.store_file(
                    file_content=contents,
                    tenant_id=str(tenant_id),
                    item_id=invoice_id,
                    attachment_type="invoices",
                    original_filename=base_name,
                    user_id=current_user.id,
                    metadata={
                        'content_type': file.content_type,
                        'invoice_id': invoice_id
                    }
                )

                if not storage_result.success:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to store file: {storage_result.error_message}"
                    )

                # Determine storage location and file path
                if storage_result.file_url:
                    # Cloud storage - use file_key as path
                    file_path = storage_result.file_key
                    stored_filename = storage_result.file_key
                    is_cloud_stored = True
                else:
                    # Local storage fallback - construct traditional path
                    tenant_folder = f"tenant_{tenant_id}"
                    attachments_dir = Path("attachments") / tenant_folder / "invoices"
                    name_without_ext = os.path.splitext(base_name)[0][:100]
                    ext_from_ct = allowed_types[file.content_type]
                    filename = f"invoice_{invoice_id}_{name_without_ext}{ext_from_ct}"
                    file_path = str(attachments_dir / filename)
                    stored_filename = filename
                    is_cloud_stored = False

                logger.info(f"File stored successfully: {file_path} (cloud: {is_cloud_stored})")
            except ImportError:
                logger.info("Commercial CloudStorageService not found, falling back to local storage")
                raise Exception("Commercial module not found")

        except Exception as e:
            if "Commercial module not found" not in str(e):
                logger.error(f"Cloud storage service error: {e}")
            # Fallback to local storage
            tenant_folder = f"tenant_{tenant_id}"
            attachments_dir = Path("attachments") / tenant_folder / "invoices"
            attachments_dir.mkdir(parents=True, exist_ok=True)

            name_without_ext = os.path.splitext(base_name)[0][:100]
            ext_from_ct = allowed_types[file.content_type]
            filename = f"invoice_{invoice_id}_{name_without_ext}{ext_from_ct}"
            file_path = attachments_dir / filename

            # Validate file path before any file operations
            from core.utils.file_validation import validate_file_path
            validated_path = validate_file_path(str(file_path), must_exist=False)

            # Remove old attachment if exists
            if invoice.attachment_path and os.path.exists(invoice.attachment_path):
                try:
                    old_validated_path = validate_file_path(invoice.attachment_path)
                    os.remove(old_validated_path)
                    logger.info(f"Removed old attachment: {invoice.attachment_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove old attachment: {e}")

            # Save file locally
            with open(validated_path, "wb") as buffer:
                buffer.write(contents)

            file_path = str(file_path)
            stored_filename = filename
            is_cloud_stored = False
            logger.info(f"File stored locally as fallback: {file_path}")

        # Update invoice with attachment info (old system for backward compatibility)
        invoice.attachment_path = file_path
        invoice.attachment_filename = file.filename
        invoice.updated_at = get_tenant_timezone_aware_datetime(db)

        # Create new-style attachment record
        import hashlib
        file_hash = hashlib.sha256(contents).hexdigest()

        new_attachment = InvoiceAttachment(
            invoice_id=invoice_id,
            filename=file.filename or "attachment",
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=len(contents),
            content_type=file.content_type,
            file_hash=file_hash,
            attachment_type="document",  # Default type for old endpoint
            uploaded_by=current_user.id,
            is_active=True
        )
        db.add(new_attachment)

        # Create history entry for attachment upload
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        history_entry = InvoiceHistoryModel(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action='attachment_uploaded',
            details=f'Attachment uploaded: {file.filename}',
            current_values={
                'attachment_filename': file.filename,
                'file_size': len(contents),
                'content_type': file.content_type
            }
        )
        db.add(history_entry)

        logger.info(f"🔍 BEFORE COMMIT - invoice {invoice_id}: path={file_path}, filename={file.filename}")
        logger.info(f"🔍 BEFORE COMMIT - invoice object: attachment_path={invoice.attachment_path}, attachment_filename={invoice.attachment_filename}")

        try:
            db.commit()
            logger.info(f"✅ DATABASE COMMIT SUCCESSFUL for invoice {invoice_id}")
        except Exception as commit_error:
            logger.error(f"❌ DATABASE COMMIT FAILED for invoice {invoice_id}: {commit_error}")
            raise

        db.refresh(invoice)

        logger.info(f"✅ AFTER COMMIT - invoice {invoice_id}: attachment_path={invoice.attachment_path}, attachment_filename={invoice.attachment_filename}")

        # Verify the data was saved by querying again
        verification_invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        logger.info(f"🔍 VERIFICATION QUERY - invoice {invoice_id}: attachment_path={verification_invoice.attachment_path}, attachment_filename={verification_invoice.attachment_filename}")
        logger.info(f"🔍 VERIFICATION QUERY - has_attachment would be: {bool(verification_invoice.attachment_filename)}")

        # Check new-style attachments for consistent response
        new_attachments = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        ).all()

        api_has_attachment, api_attachment_filename = get_attachment_info(invoice, new_attachments)

        logger.info(f"🔍 API RESPONSE CHECK - has_attachment: {api_has_attachment}, attachment_filename: '{api_attachment_filename}'")

        logger.info(f"✅ UPLOAD ENDPOINT SUCCESS - Returning response for invoice {invoice_id}")
        return {
            "message": "Attachment uploaded successfully",
            "filename": file.filename,
            "size": len(contents),
            "attachment_path": str(file_path),
            "attachment_filename": api_attachment_filename,
            "has_attachment": api_has_attachment
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading attachment: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload attachment: {str(e)}"
        )

@router.get("/{invoice_id}/download-attachment")
async def download_invoice_attachment(
    invoice_id: int,
    attachment_id: Optional[int] = Query(None, description="Specific attachment ID to download"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Download an invoice attachment (supports both cloud and local storage)"""
    try:
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Try new-style attachments first
        from core.models.models_per_tenant import InvoiceAttachment
        query = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        )

        if attachment_id:
            new_attachment = query.filter(InvoiceAttachment.id == attachment_id).first()
        else:
            new_attachment = query.order_by(InvoiceAttachment.created_at.desc()).first()

        if new_attachment:
            # Check if this is a cloud storage file (file_path doesn't start with local path)
            if not new_attachment.file_path.startswith('/') and not new_attachment.file_path.startswith('attachments'):
                # This is likely a cloud storage file key - download and serve directly
                try:
                    try:
                        from commercial.cloud_storage.service import CloudStorageService
                        from commercial.cloud_storage.config import get_cloud_storage_config
                        from core.models.database import get_tenant_context
                        from fastapi.responses import StreamingResponse
                        import io

                        tenant_id = get_tenant_context()
                        if tenant_id:
                            cloud_config = get_cloud_storage_config()
                            cloud_storage_service = CloudStorageService(db, cloud_config)

                            # Download file content from cloud storage
                            storage_result = await cloud_storage_service.retrieve_file(
                                file_key=new_attachment.file_path,
                                tenant_id=str(tenant_id),
                                user_id=current_user.id,
                                generate_url=False,  # Download content instead of URL
                                expiry_seconds=3600
                            )

                            if storage_result.success and storage_result.file_content:
                                # Return file content as streaming response with attachment disposition
                                headers = {
                                    "Content-Disposition": f"attachment; filename={new_attachment.filename or 'attachment'}",
                                    # Add CORS headers for browser access
                                    "Access-Control-Allow-Origin": "*",
                                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                                    "Access-Control-Allow-Headers": "*"
                                }

                                return StreamingResponse(
                                    io.BytesIO(storage_result.file_content),
                                    media_type=new_attachment.content_type or 'application/octet-stream',
                                    headers=headers
                                )
                            else:
                                logger.warning(f"Failed to download from cloud storage: {storage_result.error_message}")
                    except ImportError:
                        logger.info("Commercial CloudStorageService not found, cannot download from cloud")
                except Exception as e:
                    logger.warning(f"Cloud storage retrieval failed, falling back to local: {e}")

            # Local file or cloud storage fallback - serve directly
            try:
                from core.utils.file_validation import validate_file_path
                validated_path = validate_file_path(new_attachment.file_path)
                return FileResponse(
                    path=validated_path,
                    filename=new_attachment.filename,
                    media_type=new_attachment.content_type or 'application/octet-stream'
                )
            except Exception as e:
                logger.error(f"Failed to serve local file: {e}")
                raise HTTPException(status_code=404, detail="Attachment file not accessible")

        # Fall back to old-style attachment
        if invoice.attachment_path and invoice.attachment_filename:
            # Check if this is a cloud storage file
            if not invoice.attachment_path.startswith('/') and not invoice.attachment_path.startswith('attachments'):
                # This is likely a cloud storage file key - download and serve directly
                try:
                    try:
                        from commercial.cloud_storage.service import CloudStorageService
                        from commercial.cloud_storage.config import get_cloud_storage_config
                        from core.models.database import get_tenant_context
                        from fastapi.responses import StreamingResponse
                        import io

                        tenant_id = get_tenant_context()
                        if tenant_id:
                            cloud_config = get_cloud_storage_config()
                            cloud_storage_service = CloudStorageService(db, cloud_config)

                            # Download file content from cloud storage
                            storage_result = await cloud_storage_service.retrieve_file(
                                file_key=invoice.attachment_path,
                                tenant_id=str(tenant_id),
                                user_id=current_user.id,
                                generate_url=False,  # Download content instead of URL
                                expiry_seconds=3600
                            )

                            if storage_result.success and storage_result.file_content:
                                # Return file content as streaming response with attachment disposition
                                headers = {
                                    "Content-Disposition": f"attachment; filename={invoice.attachment_filename or 'attachment'}",
                                    # Add CORS headers for browser access
                                    "Access-Control-Allow-Origin": "*",
                                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                                    "Access-Control-Allow-Headers": "*"
                                }

                                return StreamingResponse(
                                    io.BytesIO(storage_result.file_content),
                                    media_type='application/octet-stream',
                                    headers=headers
                                )
                            else:
                                logger.warning(f"Failed to download from cloud storage: {storage_result.error_message}")
                    except ImportError:
                        logger.info("Commercial CloudStorageService not found, cannot download from cloud")
                except Exception as e:
                    logger.warning(f"Cloud storage retrieval failed, falling back to local: {e}")

            # Local file - serve directly
            try:
                from core.utils.file_validation import validate_file_path
                validated_path = validate_file_path(invoice.attachment_path)
                return FileResponse(
                    path=validated_path,
                    filename=invoice.attachment_filename,
                    media_type='application/octet-stream'
                )
            except Exception as e:
                logger.error(f"Failed to serve local file: {e}")
                raise HTTPException(status_code=404, detail="Attachment file not accessible")

        # No attachment found
        raise HTTPException(status_code=404, detail="No attachment found for this invoice")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading attachment: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download attachment: {str(e)}"
        )


@router.get("/{invoice_id}/attachment-info")
async def get_invoice_attachment_info(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Return metadata for the invoice attachment so the UI can decide to preview or download."""
    try:
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        has_attachment = bool(getattr(invoice, "attachment_path", None) and os.path.exists(invoice.attachment_path))
        content_type, _ = (mimetypes.guess_type(invoice.attachment_filename or "") if has_attachment else (None, None))
        size_bytes = os.path.getsize(invoice.attachment_path) if has_attachment else None
        return {
            "has_attachment": has_attachment,
            "filename": invoice.attachment_filename,
            "content_type": content_type or "application/octet-stream",
            "file_size": size_bytes,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting attachment info for invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get attachment info")


@router.get("/{invoice_id}/preview-attachment")
async def preview_invoice_attachment(
    invoice_id: int,
    attachment_id: Optional[int] = Query(None, description="Specific attachment ID to preview"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Serve the invoice attachment with inline Content-Disposition for browser preview (PDF/images)."""
    try:
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Try new-style attachments first
        from core.models.models_per_tenant import InvoiceAttachment
        query = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        )

        if attachment_id:
            new_attachment = query.filter(InvoiceAttachment.id == attachment_id).first()
        else:
            new_attachment = query.order_by(InvoiceAttachment.created_at.desc()).first()

        if new_attachment:
            # Check if this is a cloud storage file
            if not new_attachment.file_path.startswith('/') and not new_attachment.file_path.startswith('attachments'):
                # Cloud storage logic
                try:
                    try:
                        from commercial.cloud_storage.service import CloudStorageService
                        from commercial.cloud_storage.config import get_cloud_storage_config
                        from core.models.database import get_tenant_context
                        from fastapi.responses import StreamingResponse
                        import io

                        tenant_id = get_tenant_context()
                        if tenant_id:
                            cloud_config = get_cloud_storage_config()
                            cloud_storage_service = CloudStorageService(db, cloud_config)
                            storage_result = await cloud_storage_service.retrieve_file(
                                file_key=new_attachment.file_path,
                                tenant_id=str(tenant_id),
                                user_id=current_user.id,
                                generate_url=False,
                                expiry_seconds=3600
                            )

                            if storage_result.success and storage_result.file_content:
                                media_type = new_attachment.content_type or mimetypes.guess_type(new_attachment.filename)[0] or "application/octet-stream"
                                headers = {
                                    "Content-Disposition": f"inline; filename={new_attachment.filename}",
                                    "Access-Control-Allow-Origin": "*",
                                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                                    "Access-Control-Allow-Headers": "*"
                                }
                                return StreamingResponse(io.BytesIO(storage_result.file_content), media_type=media_type, headers=headers)
                    except ImportError: pass
                except Exception as e: logger.warning(f"Cloud preview failed: {e}")

            # Local fallback
            try:
                from core.utils.file_validation import validate_file_path
                validated_path = validate_file_path(new_attachment.file_path)
                media_type = new_attachment.content_type or mimetypes.guess_type(new_attachment.filename)[0] or "application/octet-stream"
                return FileResponse(path=validated_path, filename=new_attachment.filename, media_type=media_type, headers={"Content-Disposition": f"inline; filename={new_attachment.filename}"})
            except Exception as e:
                logger.error(f"Failed to serve local file: {e}")
                raise HTTPException(status_code=404, detail="Attachment file not accessible")

        # Fallback to old-style attachment
        if invoice.attachment_path:
            # (Keep existing legacy fallback logic basically, but adapted)
            if not invoice.attachment_path.startswith('/') and not invoice.attachment_path.startswith('attachments'):
                # Cloud storage legacy...
                try:
                    from commercial.cloud_storage.service import CloudStorageService
                    from commercial.cloud_storage.config import get_cloud_storage_config
                    from core.models.database import get_tenant_context
                    from fastapi.responses import StreamingResponse
                    import io
                    tenant_id = get_tenant_context()
                    if tenant_id:
                        cloud_config = get_cloud_storage_config()
                        cloud_storage_service = CloudStorageService(db, cloud_config)
                        storage_result = await cloud_storage_service.retrieve_file(file_key=invoice.attachment_path, tenant_id=str(tenant_id), user_id=current_user.id, generate_url=False, expiry_seconds=3600)
                        if storage_result.success and storage_result.file_content:
                            media_type, _ = mimetypes.guess_type(invoice.attachment_filename or "")
                            media_type = media_type or "application/octet-stream"
                            return StreamingResponse(io.BytesIO(storage_result.file_content), media_type=media_type, headers={"Content-Disposition": f"inline; filename={invoice.attachment_filename or 'attachment'}", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, OPTIONS"})
                except: pass

            try:
                from core.utils.file_validation import validate_file_path
                validated_path = validate_file_path(invoice.attachment_path)
                media_type, _ = mimetypes.guess_type(invoice.attachment_filename or "")
                media_type = media_type or "application/octet-stream"
                return FileResponse(path=validated_path, filename=invoice.attachment_filename, media_type=media_type, headers={"Content-Disposition": f"inline; filename={invoice.attachment_filename or 'attachment'}"})
            except: pass

        raise HTTPException(status_code=404, detail="No attachment found")

    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error previewing attachment for invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview attachment")


# === Invoice Attachments Endpoints ===

@router.post("/{invoice_id}/attachments/")
@router.post("/{invoice_id}/attachments")
async def upload_invoice_attachment_new(
    invoice_id: int,
    file: UploadFile = File(...),
    attachment_type: Optional[str] = Query("document", description="Attachment type: 'image' or 'document'"),
    document_type: Optional[str] = Query(None, description="Document type (for documents)"),
    description: Optional[str] = Query(None, description="Optional description"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Upload a new attachment for an invoice (using new attachment system)
    """
    try:
        # Check if user has permission
        require_non_viewer(current_user, "upload attachments")

        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Basic validation
        if attachment_type and attachment_type not in ['image', 'document']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="attachment_type must be 'image' or 'document'"
            )

        # Default to document if not specified
        if not attachment_type:
            attachment_type = "document"

        # Validate file type before reading
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        file_ext = os.path.splitext(file.filename.lower())[1]
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv'}
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(allowed_extensions)}")

        # Read file content for validation
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file provided"
            )

        # Validate file size (max 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is 10MB")

        # Import the InvoiceAttachment model
        from core.models.models_per_tenant import InvoiceAttachment
        import uuid
        import hashlib
        from pathlib import Path

        # Create attachments directory
        from core.models.database import get_tenant_context
        from core.utils.file_validation import validate_file_path

        tenant_id = get_tenant_context()
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context not available")

        tenant_folder = f"tenant_{tenant_id}"
        attachments_dir = Path("attachments") / tenant_folder / "invoices"
        attachments_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename with validated extension
        file_extension = Path(file.filename or "attachment").suffix
        if file_extension not in allowed_extensions:
            file_extension = ".txt"  # Safe fallback

        stored_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = attachments_dir / stored_filename

        # Validate file path before saving
        validated_path = validate_file_path(str(file_path))

        # Save file to disk
        with open(validated_path, "wb") as f:
            f.write(file_content)

        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Create attachment record
        attachment = InvoiceAttachment(
            invoice_id=invoice_id,
            filename=file.filename or "attachment",
            stored_filename=stored_filename,
            file_path=str(file_path),
            file_size=len(file_content),
            content_type=file.content_type,
            file_hash=file_hash,
            attachment_type=attachment_type,
            document_type=document_type,
            description=description,
            uploaded_by=current_user.id,
            is_active=True
        )

        db.add(attachment)
        db.commit()
        db.refresh(attachment)

        # Queue invoice for async OCR processing if it's a document that could contain invoice data
        ocr_queued = False
        task_id = None
        if attachment_type == "document" and file_ext in {'.pdf', '.jpg', '.jpeg', '.png'}:
            try:
                from commercial.ai.services.ocr_service import publish_invoice_task
                import uuid

                # Generate task ID for tracking
                task_id = str(uuid.uuid4())

                # Queue the OCR task
                message = {
                    "tenant_id": tenant_id,
                    "task_id": task_id,
                    "file_path": str(file_path),
                    "filename": file.filename,
                    "user_id": current_user.id,
                    "invoice_id": invoice_id,
                    "attachment_id": attachment.id,
                    "attempt": 0
                }

                success = publish_invoice_task(message)

                if success:
                    ocr_queued = True
                    logger.info(f"Invoice attachment queued for OCR: task_id={task_id}, attachment_id={attachment.id}")
                else:
                    logger.warning(f"Failed to queue invoice attachment for OCR: attachment_id={attachment.id}")

            except Exception as e:
                logger.error(f"Failed to queue invoice OCR: {e}")

        response = {
            "id": attachment.id,
            "invoice_id": invoice_id,
            "filename": attachment.filename,
            "file_size": attachment.file_size,
            "attachment_type": attachment.attachment_type,
            "document_type": attachment.document_type,
            "description": attachment.description,
            "created_at": attachment.created_at.isoformat(),
            "status": "success",
            "message": "Attachment uploaded successfully"
        }

        # Include OCR task info if queued
        if ocr_queued and task_id:
            response["ocr_status"] = "queued"
            response["ocr_task_id"] = task_id
            response["message"] = "Attachment uploaded and queued for OCR processing"

        # Release processing lock for invoice if it was used
        try:
            from commercial.ai.services.ocr_service import release_processing_lock
            invoice_id_for_lock = invoice_id
            released = release_processing_lock("invoice", invoice_id_for_lock)
            if released:
                logger.info(f"Released processing lock for invoice {invoice_id_for_lock}")
        except Exception as lock_error:
            logger.warning(f"Failed to release processing lock for invoice {invoice_id}: {lock_error}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process invoice attachment upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process file upload"
        )


@router.delete("/{invoice_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice_attachment(
    invoice_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Delete an invoice attachment (soft delete by marking as inactive)
    """
    try:
        # Check if user has permission
        require_non_viewer(current_user, "delete attachments")

        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Import the InvoiceAttachment model
        from core.models.models_per_tenant import InvoiceAttachment

        # Find the attachment
        attachment = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.id == attachment_id,
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        ).first()

        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")

        # Allow deletion regardless of whether the file can be previewed
        # This handles cases where files are missing or corrupted

        # Soft delete the attachment (mark as inactive)
        attachment.is_active = False
        attachment.updated_at = get_tenant_timezone_aware_datetime(db)

        # Clear old-style attachment fields on the invoice if no active attachments remain
        remaining_attachments = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True,
            InvoiceAttachment.id != attachment_id  # Exclude the one we're deleting
        ).count()

        if remaining_attachments == 0:
            # No active attachments left, clear old fields
            invoice.attachment_filename = None
            invoice.attachment_path = None

        # Delete the physical file from storage (cloud and/or local)
        if attachment.file_path:
            await delete_file_from_storage(attachment.file_path, current_user.tenant_id, current_user.id, db)

        # Create history entry for attachment deletion
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        history_entry = InvoiceHistoryModel(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action='attachment_deleted',
            details=f'Attachment deleted: {attachment.filename}',
            current_values={
                'attachment_id': attachment.id,
                'filename': attachment.filename,
                'file_size': attachment.file_size
            }
        )
        db.add(history_entry)
        db.commit()

        return

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete invoice attachment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment"
        )


@router.get("/{invoice_id}/attachments/")
@router.get("/{invoice_id}/attachments")
async def get_invoice_attachments(
    invoice_id: int,
    attachment_type: Optional[str] = Query(None, description="Filter by attachment type"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get all attachments for an invoice
    """
    try:
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Import the InvoiceAttachment model
        from core.models.models_per_tenant import InvoiceAttachment

        # Query attachments
        query = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        )

        if attachment_type:
            query = query.filter(InvoiceAttachment.attachment_type == attachment_type)

        attachments = query.order_by(InvoiceAttachment.created_at.desc()).all()

        # Format response
        attachment_list = []
        for attachment in attachments:
            attachment_list.append({
                "id": attachment.id,
                "filename": attachment.filename,
                "file_size": attachment.file_size,
                "content_type": attachment.content_type,
                "attachment_type": attachment.attachment_type,
                "document_type": attachment.document_type,
                "description": attachment.description,
                "created_at": attachment.created_at.isoformat(),
                "uploaded_by": attachment.uploaded_by
            })

        return {
            "invoice_id": invoice_id,
            "attachments": attachment_list,
            "total_count": len(attachment_list)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get invoice attachments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve attachments"
        )

@router.post("/{invoice_id}/accept-review", response_model=InvoiceSchema)
async def accept_review(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "review invoices")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    review_service = ReviewService(db)
    success = review_service.accept_review(invoice)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to accept review or no review available")

    db.commit()
    db.refresh(invoice)

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_ACCEPT_INVOICE",
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=getattr(invoice, "number", None),
        details={"invoice_id": invoice.id, "review_status": invoice.review_status}
    )

    return invoice

@router.post("/{invoice_id}/reject-review", response_model=InvoiceSchema)
async def reject_review(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_non_viewer(current_user, "review invoices")

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    review_service = ReviewService(db)
    success = review_service.reject_review(invoice)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject review")

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_REJECT_INVOICE",
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=getattr(invoice, "number", None),
        details={"invoice_id": invoice.id, "review_status": invoice.review_status}
    )

    return invoice

@router.post("/{invoice_id}/review", response_model=InvoiceSchema)
async def run_review(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Trigger a full re-review (reset status to not_started for the worker to pick up)"""
    require_non_viewer(current_user, "review invoices")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check if review worker is enabled
    from commercial.ai.services.ai_config_service import AIConfigService
    if not AIConfigService.is_review_worker_enabled(db):
        raise HTTPException(
            status_code=400,
            detail="Review worker is currently disabled. Please enable it in Settings > AI Configuration before triggering a review."
        )

    # Reset review status to pending so it shows immediately in UI
    # The worker will pick it up and process it
    invoice.review_status = "pending"
    invoice.review_result = None
    invoice.reviewed_at = None

    db.commit()
    db.refresh(invoice)

    # Publish Kafka event to trigger review
    try:
        from core.services.review_event_service import get_review_event_service
        from core.models.database import get_tenant_context

        tenant_id = get_tenant_context()
        if tenant_id:
            event_service = get_review_event_service()
            event_service.publish_single_review_trigger(
                tenant_id=tenant_id,
                entity_type="invoice",
                entity_id=invoice_id
            )
            logger.info(f"Published Kafka event to trigger review for invoice {invoice_id}")
    except Exception as e:
        logger.warning(f"Failed to publish Kafka event for invoice review trigger: {e}")

    # Poll for completion with timeout
    import asyncio
    max_wait_time = 30  # Maximum 30 seconds
    poll_interval = 0.5  # Check every 500ms
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval

        # Refresh to get latest status
        db.refresh(invoice)

        # Check if worker has processed the invoice
        if invoice.review_status in ["reviewed", "failed", "diff_found"]:
            logger.info(f"Review processing completed for invoice {invoice_id}. Final status: {invoice.review_status}")
            break

    if invoice.review_status == "pending":
        logger.warning(f"Review processing timed out for invoice {invoice_id} after {max_wait_time} seconds")

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_TRIGGER_INVOICE",
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=getattr(invoice, "number", None),
        details={"invoice_id": invoice.id, "review_status": invoice.review_status}
    )

    return invoice


@router.post("/{invoice_id:int}/cancel-review", response_model=InvoiceSchema)
async def cancel_invoice_review(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Cancel an in-progress review for an invoice"""
    require_non_viewer(current_user, "review invoices")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Can only cancel if review is pending, not_started, rejected, or failed
    if invoice.review_status not in ["pending", "not_started", "rejected", "failed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel review with status '{invoice.review_status}'. Only pending, rejected, failed, or not_started reviews can be cancelled."
        )

    # Cancel the review
    invoice.review_status = "not_started"
    invoice.review_result = None
    invoice.reviewed_at = None

    db.commit()
    db.refresh(invoice)

    logger.info(f"Cancelled review for invoice {invoice_id}")

    return invoice
