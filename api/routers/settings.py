from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from typing import Dict, Any
import tempfile
import os
import shutil
from datetime import datetime, timezone, date
import logging

from models.database import get_db, get_master_db
from models.models_per_tenant import User, Client, Invoice, Payment, Settings, ClientNote, InvoiceItem
from models.models import Tenant, MasterUser
from routers.auth import get_current_user
from utils.invoice import generate_invoice_number

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/")
def get_settings(
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get tenant settings (using tenant info as settings)"""
    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Return tenant info formatted as settings
    return {
        "company_info": {
            "name": tenant.name,
            "email": tenant.email or "",
            "phone": tenant.phone or "",
            "address": tenant.address or "",
            "tax_id": tenant.tax_id or "",
            "logo": tenant.company_logo_url or ""
        },
        "invoice_settings": {
            "prefix": "INV-",
            "next_number": "0001",
            "terms": "Payment due within 30 days from the date of invoice.\nLate payments are subject to a 1.5% monthly finance charge.",
            "notes": "Thank you for your business!",
            "send_copy": True,
            "auto_reminders": True
        },
        "enable_ai_assistant": tenant.enable_ai_assistant or False
    }

@router.put("/")
def update_settings(
    settings: Dict[str, Any],
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update tenant settings"""
    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Update tenant info from company_info
    company_info = settings.get("company_info", {})
    if company_info:
        tenant.name = company_info.get("name", tenant.name)
        tenant.email = company_info.get("email", tenant.email)
        tenant.phone = company_info.get("phone", tenant.phone)
        tenant.address = company_info.get("address", tenant.address)
        tenant.tax_id = company_info.get("tax_id", tenant.tax_id)
        tenant.company_logo_url = company_info.get("logo", tenant.company_logo_url)
    
    # Update AI assistant setting
    if "enable_ai_assistant" in settings:
        tenant.enable_ai_assistant = settings["enable_ai_assistant"]
    
    master_db.commit()
    master_db.refresh(tenant)
    
    return {"message": "Settings updated successfully"}

@router.get("/export-data")
def export_tenant_data(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """Export tenant data to a JSON file"""
    try:
        # Get tenant record from master database
        tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
        
        try:
            # Export tenant data from the tenant database
            tenant_data = {
                'tenant': [tenant] if tenant else [],
                'clients': db.query(Client).all(),
                'invoices': db.query(Invoice).all(),
                'payments': db.query(Payment).all(),
                'settings': db.query(Settings).all(),
                'client_notes': db.query(ClientNote).all(),
                'invoice_items': db.query(InvoiceItem).join(Invoice).all(),
            }
            
            # Convert to JSON-serializable format
            export_data = {}
            for key, value in tenant_data.items():
                if isinstance(value, list):
                    export_data[key] = []
                    for item in value:
                        if hasattr(item, '__dict__'):
                            item_dict = {}
                            for attr_key, attr_value in item.__dict__.items():
                                if not attr_key.startswith('_'):
                                    if isinstance(attr_value, (datetime, date)):
                                        item_dict[attr_key] = attr_value.isoformat()
                                    else:
                                        item_dict[attr_key] = attr_value
                            export_data[key].append(item_dict)
                        else:
                            export_data[key].append(str(item))
                else:
                    export_data[key] = str(value)
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
                import json
                json.dump(export_data, tmp_file, indent=2, default=str)
                tmp_file_path = tmp_file.name
            
            # Return the file
            return FileResponse(
                path=tmp_file_path,
                filename=f"tenant_data_{current_user.tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                media_type="application/json"
            )
            
        except Exception as e:
            logger.error(f"Error exporting tenant data: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error exporting data: {str(e)}"
            )
    
    except Exception as e:
        logger.error(f"Error in export_tenant_data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error in data export: {str(e)}"
        )

@router.post("/import-data")
async def import_tenant_data(
    file: UploadFile = File(...),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import data from an uploaded SQLite file"""
    try:
        # Only tenant admins can import data
        if current_user.role != "admin":
            raise HTTPException(
                status_code=403, 
                detail="Only tenant admins can import data"
            )
        
        # Validate file type
        if not file.filename or not file.filename.endswith('.sqlite'):
            raise HTTPException(
                status_code=400,
                detail="File must be a SQLite database (.sqlite extension)"
            )
        
        # Create temporary directory for import file
        temp_dir = tempfile.mkdtemp()
        import_file = os.path.join(temp_dir, "import.sqlite")
        
        try:
            # Save uploaded file
            with open(import_file, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Connect to import database
            import_engine = create_engine(f"sqlite:///{import_file}")
            from sqlalchemy.orm import sessionmaker
            ImportSession = sessionmaker(bind=import_engine)
            import_db = ImportSession()
            
            try:
                # Verify the database structure
                from sqlalchemy import inspect
                inspector = inspect(import_engine)
                tables = inspector.get_table_names()
                
                required_tables = ['clients', 'invoices', 'payments']
                if not all(table in tables for table in required_tables):
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid database structure. Missing required tables."
                    )
                
                # Import data (replace existing data for this tenant)
                imported_counts = {}
                
                try:
                    # Delete existing data for this tenant
                    db.query(ClientNote).filter(ClientNote.tenant_id == current_user.tenant_id).delete()
                    db.query(InvoiceItem).filter(InvoiceItem.invoice_id.in_(
                        db.query(Invoice.id).filter(Invoice.tenant_id == current_user.tenant_id)
                    )).delete(synchronize_session=False)
                    db.query(Payment).filter(Payment.tenant_id == current_user.tenant_id).delete()
                    db.query(Invoice).filter(Invoice.tenant_id == current_user.tenant_id).delete()
                    db.query(Client).filter(Client.tenant_id == current_user.tenant_id).delete()
                    db.query(Settings).filter(Settings.tenant_id == current_user.tenant_id).delete()
                    
                    # Import clients
                    if 'clients' in tables:
                        clients = import_db.query(Client).all()
                        for client in clients:
                            new_client = Client(
                                name=client.name,
                                email=client.email,
                                phone=client.phone,
                                address=client.address,
                                balance=client.balance,
                                paid_amount=client.paid_amount,
                                preferred_currency=client.preferred_currency,
                                tenant_id=current_user.tenant_id,  # Override with current tenant
                                created_at=client.created_at,
                                updated_at=datetime.now(timezone.utc)
                            )
                            db.add(new_client)
                        db.flush()  # Get IDs for clients
                        imported_counts['clients'] = len(clients)
                    
                    # Create mapping of old client IDs to new client IDs
                    old_to_new_client_ids = {}
                    if 'clients' in tables:
                        old_clients = import_db.query(Client).all()
                        new_clients = db.query(Client).filter(Client.tenant_id == current_user.tenant_id).all()
                        for old_client, new_client in zip(old_clients, new_clients):
                            old_to_new_client_ids[old_client.id] = new_client.id
                    
                    # Import invoices
                    if 'invoices' in tables:
                        invoices = import_db.query(Invoice).all()
                        old_to_new_invoice_ids = {}
                        
                        # Generate unique invoice numbers for all invoices first
                        date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
                        
                        # Find the latest invoice number for today
                        latest_invoice = db.query(Invoice).filter(
                            Invoice.tenant_id == current_user.tenant_id,
                            Invoice.number.like(f"INV-{date_prefix}-%")
                        ).order_by(Invoice.number.desc()).first()
                        
                        if latest_invoice:
                            try:
                                start_sequence = int(latest_invoice.number.split("-")[-1])
                            except (ValueError, IndexError):
                                start_sequence = 0
                        else:
                            start_sequence = 0
                        
                        # Create invoices with sequential numbers
                        valid_invoices = [inv for inv in invoices if old_to_new_client_ids.get(inv.client_id)]
                        for i, invoice in enumerate(valid_invoices):
                            new_sequence = start_sequence + i + 1
                            new_invoice_number = f"INV-{date_prefix}-{new_sequence:04d}"
                            
                            # Calculate subtotal (same as amount if no discount applied)
                            subtotal = getattr(invoice, 'subtotal', None)
                            if subtotal is None:
                                subtotal = invoice.amount
                            
                            new_invoice = Invoice(
                                number=new_invoice_number,  # Use generated number instead of original
                                amount=invoice.amount,
                                currency=invoice.currency,
                                due_date=invoice.due_date,
                                status=invoice.status,
                                notes=invoice.notes,
                                client_id=old_to_new_client_ids.get(invoice.client_id),
                                tenant_id=current_user.tenant_id,
                                created_at=invoice.created_at,
                                updated_at=datetime.now(timezone.utc),
                                is_recurring=getattr(invoice, 'is_recurring', False),
                                recurring_frequency=getattr(invoice, 'recurring_frequency', None),
                                discount_type=getattr(invoice, 'discount_type', 'percentage'),
                                discount_value=getattr(invoice, 'discount_value', 0.0),
                                subtotal=subtotal
                            )
                            db.add(new_invoice)
                            old_to_new_invoice_ids[invoice.id] = new_invoice
                        
                        db.flush()  # Get IDs for invoices
                        imported_counts['invoices'] = len(valid_invoices)
                    
                    # Update invoice ID mapping with actual database IDs
                    actual_invoice_mapping = {}
                    if 'invoices' in tables:
                        new_invoices = db.query(Invoice).filter(Invoice.tenant_id == current_user.tenant_id).all()
                        for old_id, temp_invoice in old_to_new_invoice_ids.items():
                            for new_invoice in new_invoices:
                                if (new_invoice.number == temp_invoice.number and 
                                    new_invoice.amount == temp_invoice.amount):
                                    actual_invoice_mapping[old_id] = new_invoice.id
                                    break
                    
                    # Import payments
                    if 'payments' in tables:
                        payments = import_db.query(Payment).all()
                        payment_count = 0
                        for payment in payments:
                            new_invoice_id = actual_invoice_mapping.get(payment.invoice_id)
                            if new_invoice_id:
                                new_payment = Payment(
                                    invoice_id=new_invoice_id,
                                    amount=payment.amount,
                                    currency=payment.currency,
                                    payment_date=payment.payment_date,
                                    payment_method=payment.payment_method,
                                    reference_number=payment.reference_number,
                                    notes=payment.notes,
                                    tenant_id=current_user.tenant_id,
                                    created_at=payment.created_at,
                                    updated_at=datetime.now(timezone.utc)
                                )
                                db.add(new_payment)
                                payment_count += 1
                        imported_counts['payments'] = payment_count
                    
                    # Import invoice items
                    if 'invoice_items' in tables:
                        invoice_items = import_db.query(InvoiceItem).all()
                        item_count = 0
                        for item in invoice_items:
                            new_invoice_id = actual_invoice_mapping.get(item.invoice_id)
                            if new_invoice_id:
                                new_item = InvoiceItem(
                                    invoice_id=new_invoice_id,
                                    description=item.description,
                                    quantity=item.quantity,
                                    price=item.price,
                                    amount=item.amount,
                                    created_at=item.created_at,
                                    updated_at=datetime.now(timezone.utc)
                                )
                                db.add(new_item)
                                item_count += 1
                        imported_counts['invoice_items'] = item_count
                    
                    # Import client notes
                    if 'client_notes' in tables:
                        client_notes = import_db.query(ClientNote).all()
                        note_count = 0
                        for note in client_notes:
                            new_client_id = old_to_new_client_ids.get(note.client_id)
                            if new_client_id:
                                new_note = ClientNote(
                                    note=note.note,
                                    client_id=new_client_id,
                                    user_id=current_user.id,  # Assign to current user
                                    tenant_id=current_user.tenant_id,
                                    created_at=note.created_at,
                                    updated_at=datetime.now(timezone.utc)
                                )
                                db.add(new_note)
                                note_count += 1
                        imported_counts['client_notes'] = note_count
                    
                    db.commit()
                    
                    logger.info(f"Successfully imported data for tenant {current_user.tenant_id}: {imported_counts}")
                    
                    return {
                        "success": True,
                        "message": "Data imported successfully",
                        "imported_counts": imported_counts
                    }
                    
                except Exception as import_error:
                    db.rollback()
                    logger.error(f"Error during import for tenant {current_user.tenant_id}: {str(import_error)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to import data: {str(import_error)}"
                    )
                
            finally:
                import_db.close()
                
        finally:
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing data for tenant {current_user.tenant_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import data: {str(e)}"
        )