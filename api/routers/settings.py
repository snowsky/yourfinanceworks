from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from typing import Dict, Any
import tempfile
import os
import shutil
from datetime import datetime, timezone, date
import logging
import uuid
from PIL import Image
import io
from fastapi.concurrency import run_in_threadpool

from models.database import get_db, get_master_db
from models.models_per_tenant import User, Client, Invoice, Settings, ClientNote, InvoiceItem
from routers.payments import Payment
from models.models import Tenant, MasterUser
from routers.auth import get_current_user
from utils.invoice import generate_invoice_number
from utils.rbac import require_admin
from utils.audit import log_audit_event
from constants.error_codes import FAILED_TO_IMPORT_DATA

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/")
async def get_settings(
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get tenant settings (using tenant info as settings)"""
    # Only admins can view settings
    require_admin(current_user, "view settings")
    
    
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
async def update_settings(
    settings: Dict[str, Any],
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update tenant settings"""
    # Only admins can update settings
    require_admin(current_user, "update settings")
    
    
    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Update tenant info from company_info
    company_info = settings.get("company_info", {})
    if company_info:
        tenant.name = company_info.get("name", tenant.name)
        
        tenant.phone = company_info.get("phone", tenant.phone)
        tenant.address = company_info.get("address", tenant.address)
        tenant.tax_id = company_info.get("tax_id", tenant.tax_id)
        tenant.company_logo_url = company_info.get("logo", tenant.company_logo_url)
    
    # Update AI assistant setting
    if "enable_ai_assistant" in settings:
        tenant.enable_ai_assistant = settings["enable_ai_assistant"]
    
    master_db.commit()
    master_db.refresh(tenant)
    
    # Log audit event in master DB
    log_audit_event(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="settings",
        resource_id=str(tenant.id),
        resource_name=f"Setting: {tenant.name}",
        details=settings,
        status="success"
    )
    # Log audit event in tenant DB as well
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="settings",
        resource_id=str(tenant.id),
        resource_name=f"Setting: {tenant.name}",
        details=settings,
        status="success"
    )

    return {"message": "Settings updated successfully"}

@router.get("/export-data")
async def export_tenant_data(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """Export tenant data to a real SQLite file"""
    require_admin(current_user, "export data")
    import sqlalchemy
    import sqlite3
    from sqlalchemy.orm import sessionmaker
    from models.models_per_tenant import (
        Base as TenantBase, User, Client, ClientNote, Invoice, Payment, Settings, DiscountRule, SupportedCurrency, CurrencyRate, InvoiceItem, InvoiceHistory, AIConfig
    )
    import atexit

    # Create a temporary SQLite file
    temp_dir = tempfile.mkdtemp()
    sqlite_path = os.path.join(temp_dir, f"data_export_{current_user.tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite")
    sqlite_url = f"sqlite:///{sqlite_path}"
    sqlite_engine = sqlalchemy.create_engine(sqlite_url, connect_args={"check_same_thread": False})
    TenantBase.metadata.create_all(sqlite_engine)
    SqliteSession = sessionmaker(bind=sqlite_engine)
    sqlite_session = SqliteSession()

    try:
        # Copy all data from the current tenant's database
        # 1. Users
        for obj in db.query(User).all():
            sqlite_session.add(User(**{c.name: getattr(obj, c.name) for c in User.__table__.columns}))
        # 2. Clients
        for obj in db.query(Client).all():
            sqlite_session.add(Client(**{c.name: getattr(obj, c.name) for c in Client.__table__.columns}))
        # 3. ClientNotes
        for obj in db.query(ClientNote).all():
            sqlite_session.add(ClientNote(**{c.name: getattr(obj, c.name) for c in ClientNote.__table__.columns}))
        # 4. Invoices
        for obj in db.query(Invoice).all():
            sqlite_session.add(Invoice(**{c.name: getattr(obj, c.name) for c in Invoice.__table__.columns}))
        # 5. Payments
        for obj in db.query(Payment).all():
            sqlite_session.add(Payment(**{c.name: getattr(obj, c.name) for c in Payment.__table__.columns}))
        # 6. Settings
        for obj in db.query(Settings).all():
            sqlite_session.add(Settings(**{c.name: getattr(obj, c.name) for c in Settings.__table__.columns}))
        # 7. DiscountRules
        for obj in db.query(DiscountRule).all():
            sqlite_session.add(DiscountRule(**{c.name: getattr(obj, c.name) for c in DiscountRule.__table__.columns}))
        # 8. SupportedCurrencies
        for obj in db.query(SupportedCurrency).all():
            sqlite_session.add(SupportedCurrency(**{c.name: getattr(obj, c.name) for c in SupportedCurrency.__table__.columns}))
        # 9. CurrencyRates
        for obj in db.query(CurrencyRate).all():
            sqlite_session.add(CurrencyRate(**{c.name: getattr(obj, c.name) for c in CurrencyRate.__table__.columns}))
        # 10. InvoiceItems
        for obj in db.query(InvoiceItem).all():
            sqlite_session.add(InvoiceItem(**{c.name: getattr(obj, c.name) for c in InvoiceItem.__table__.columns}))
        # 11. InvoiceHistory
        for obj in db.query(InvoiceHistory).all():
            sqlite_session.add(InvoiceHistory(**{c.name: getattr(obj, c.name) for c in InvoiceHistory.__table__.columns}))
        # 12. AIConfig
        for obj in db.query(AIConfig).all():
            sqlite_session.add(AIConfig(**{c.name: getattr(obj, c.name) for c in AIConfig.__table__.columns}))
        sqlite_session.commit()
        sqlite_session.close()

        # Return the file as a download
        def cleanup():
            shutil.rmtree(temp_dir, ignore_errors=True)
        atexit.register(cleanup)
        return FileResponse(
            path=sqlite_path,
            filename=os.path.basename(sqlite_path),
            media_type="application/x-sqlite3",
            background=None  # atexit will handle cleanup
        )
    except Exception as e:
        sqlite_session.rollback()
        sqlite_session.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Error exporting tenant data to SQLite: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting data: {str(e)}")

@router.post("/import-data")
async def import_tenant_data(
    file: UploadFile = File(...),
    current_user: MasterUser = Depends(get_current_user)
):
    """Import data from an uploaded SQLite file (full restore, all tables)"""
    import tempfile, os
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import sessionmaker
    from models.models_per_tenant import (
        User, Client, ClientNote, Invoice, Payment, Settings, DiscountRule, SupportedCurrency, CurrencyRate, InvoiceItem, InvoiceHistory, AIConfig
    )
    from services.tenant_database_manager import tenant_db_manager
    try:
        require_admin(current_user, "import data")
        
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
                content = file.file.read()
                buffer.write(content)
            
            # Connect to import database
            import_engine = create_engine(f"sqlite:///{import_file}")
            ImportSession = sessionmaker(bind=import_engine)
            import_db = ImportSession()
            from sqlalchemy import inspect
            inspector = inspect(import_engine)
            tables = inspector.get_table_names()
            # List of all tables to import
            table_names = [
                'users', 'clients', 'client_notes', 'invoices', 'payments', 'settings',
                'discount_rules', 'supported_currencies', 'currency_rates',
                'invoice_items', 'invoice_history', 'ai_configs'
            ]
            missing = [t for t in ['clients', 'invoices', 'payments'] if t not in tables]
            if missing:
                raise HTTPException(status_code=400, detail=f"Invalid database structure. Missing required tables: {', '.join(missing)}")
            imported_counts = {}
            # Create a new session for the tenant DB directly
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(current_user.tenant_id)
            db = SessionLocal_tenant()
            try:
                # Delete all existing data for this tenant (order matters for FKs)
                db.query(ClientNote).delete()
                db.query(InvoiceItem).delete()
                db.query(Payment).delete()
                db.query(InvoiceHistory).delete()
                db.query(Invoice).delete()
                db.query(Client).delete()
                db.query(Settings).delete()
                db.query(DiscountRule).delete()
                db.query(CurrencyRate).delete()
                db.query(SupportedCurrency).delete()
                db.query(AIConfig).delete()
                db.query(User).filter(User.is_superuser == False).delete()  # Don't delete superusers
                old_to_new_user_ids = {}
                old_to_new_client_ids = {}
                old_to_new_invoice_ids = {}
                # 1. Users
                if 'users' in tables:
                    users = import_db.query(User).all()
                    user_count = 0
                    for user in users:
                        # Don't import superusers from backup, only regular users
                        if user.is_superuser:
                            continue
                        existing = db.query(User).filter(User.email == user.email).first()
                        if existing:
                            old_to_new_user_ids[user.id] = existing.id
                            continue
                        new_user = User(
                            email=user.email,
                            hashed_password=user.hashed_password,
                            is_active=user.is_active,
                            is_superuser=False,  # Never import superusers
                            is_verified=user.is_verified,
                            role=user.role,
                            first_name=user.first_name,
                            last_name=user.last_name,
                            google_id=user.google_id,
                            created_at=user.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_user)
                        db.flush()
                        old_to_new_user_ids[user.id] = new_user.id
                        user_count += 1
                    imported_counts['users'] = user_count
                # 2. Clients
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
                            created_at=client.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_client)
                        db.flush()
                        old_to_new_client_ids[client.id] = new_client.id
                    imported_counts['clients'] = len(clients)
                # 3. Invoices
                if 'invoices' in tables:
                    invoices = import_db.query(Invoice).all()
                    for invoice in invoices:
                        new_invoice = Invoice(
                            number=invoice.number,
                            amount=invoice.amount,
                            currency=invoice.currency,
                            due_date=invoice.due_date,
                            status=invoice.status,
                            notes=invoice.notes,
                            client_id=old_to_new_client_ids.get(invoice.client_id),
                            created_at=invoice.created_at,
                            updated_at=datetime.now(timezone.utc),
                            is_recurring=getattr(invoice, 'is_recurring', False),
                            recurring_frequency=getattr(invoice, 'recurring_frequency', None),
                            discount_type=getattr(invoice, 'discount_type', 'percentage'),
                            discount_value=getattr(invoice, 'discount_value', 0.0),
                            subtotal=getattr(invoice, 'subtotal', invoice.amount),
                            is_deleted=getattr(invoice, 'is_deleted', False),
                            deleted_at=getattr(invoice, 'deleted_at', None),
                            deleted_by=None
                        )
                        db.add(new_invoice)
                        db.flush()
                        old_to_new_invoice_ids[invoice.id] = new_invoice.id
                    imported_counts['invoices'] = len(invoices)
                # 4. Payments
                if 'payments' in tables:
                    payments = import_db.query(Payment).all()
                    payment_count = 0
                    for payment in payments:
                        new_invoice_id = old_to_new_invoice_ids.get(payment.invoice_id)
                        new_user_id = old_to_new_user_ids.get(payment.user_id) if hasattr(payment, 'user_id') else None
                        if new_invoice_id:
                            new_payment = Payment(
                                invoice_id=new_invoice_id,
                                amount=payment.amount,
                                currency=payment.currency,
                                payment_date=payment.payment_date,
                                payment_method=payment.payment_method,
                                reference_number=payment.reference_number,
                                notes=payment.notes,
                                created_at=payment.created_at,
                                updated_at=datetime.now(timezone.utc),
                                user_id=new_user_id
                            )
                            db.add(new_payment)
                            payment_count += 1
                    imported_counts['payments'] = payment_count
                # 5. InvoiceItems
                if 'invoice_items' in tables:
                    invoice_items = import_db.query(InvoiceItem).all()
                    item_count = 0
                    for item in invoice_items:
                        new_invoice_id = old_to_new_invoice_ids.get(item.invoice_id)
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
                # 6. ClientNotes
                if 'client_notes' in tables:
                    client_notes = import_db.query(ClientNote).all()
                    note_count = 0
                    for note in client_notes:
                        new_client_id = old_to_new_client_ids.get(note.client_id)
                        new_user_id = old_to_new_user_ids.get(note.user_id) if hasattr(note, 'user_id') else current_user.id
                        if new_client_id:
                            new_note = ClientNote(
                                note=note.note,
                                client_id=new_client_id,
                                user_id=new_user_id,
                                created_at=note.created_at,
                                updated_at=datetime.now(timezone.utc)
                            )
                            db.add(new_note)
                            note_count += 1
                    imported_counts['client_notes'] = note_count
                # 7. Settings
                if 'settings' in tables:
                    settings = import_db.query(Settings).all()
                    for setting in settings:
                        new_setting = Settings(
                            key=setting.key,
                            value=setting.value,
                            created_at=setting.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_setting)
                    imported_counts['settings'] = len(settings)
                # 8. DiscountRules
                if 'discount_rules' in tables:
                    rules = import_db.query(DiscountRule).all()
                    for rule in rules:
                        new_rule = DiscountRule(
                            name=rule.name,
                            min_amount=rule.min_amount,
                            discount_type=rule.discount_type,
                            discount_value=rule.discount_value,
                            currency=rule.currency,
                            is_active=rule.is_active,
                            priority=rule.priority,
                            created_at=rule.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_rule)
                    imported_counts['discount_rules'] = len(rules)
                # 9. SupportedCurrencies
                if 'supported_currencies' in tables:
                    currencies = import_db.query(SupportedCurrency).all()
                    for currency in currencies:
                        new_currency = SupportedCurrency(
                            code=currency.code,
                            name=currency.name,
                            symbol=currency.symbol,
                            decimal_places=currency.decimal_places,
                            is_active=currency.is_active,
                            created_at=currency.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_currency)
                    imported_counts['supported_currencies'] = len(currencies)
                # 10. CurrencyRates
                if 'currency_rates' in tables:
                    rates = import_db.query(CurrencyRate).all()
                    for rate in rates:
                        new_rate = CurrencyRate(
                            from_currency=rate.from_currency,
                            to_currency=rate.to_currency,
                            rate=rate.rate,
                            effective_date=rate.effective_date,
                            created_at=rate.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_rate)
                    imported_counts['currency_rates'] = len(rates)
                # 11. InvoiceHistory
                if 'invoice_history' in tables:
                    histories = import_db.query(InvoiceHistory).all()
                    for hist in histories:
                        new_invoice_id = old_to_new_invoice_ids.get(hist.invoice_id)
                        new_user_id = old_to_new_user_ids.get(hist.user_id) if hasattr(hist, 'user_id') else current_user.id
                        if new_invoice_id:
                            new_hist = InvoiceHistory(
                                invoice_id=new_invoice_id,
                                user_id=new_user_id,
                                action=hist.action,
                                details=hist.details,
                                previous_values=hist.previous_values,
                                current_values=hist.current_values,
                                created_at=hist.created_at
                            )
                            db.add(new_hist)
                    imported_counts['invoice_history'] = len(histories)
                # 12. AIConfig
                if 'ai_configs' in tables:
                    configs = import_db.query(AIConfig).all()
                    for config in configs:
                        new_config = AIConfig(
                            provider_name=config.provider_name,
                            provider_url=config.provider_url,
                            api_key=config.api_key,
                            model_name=config.model_name,
                            is_active=config.is_active,
                            is_default=config.is_default,
                            tested=getattr(config, 'tested', False),
                            created_at=config.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_config)
                    imported_counts['ai_configs'] = len(configs)
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
                    detail=FAILED_TO_IMPORT_DATA
                )
            finally:
                db.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing data for tenant {current_user.tenant_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_IMPORT_DATA
        )

@router.post("/upload-logo")
async def upload_company_logo(
    file: UploadFile = File(...),
    current_user: MasterUser = Depends(get_current_user)
):
    """Upload a company logo image and return its public URL (per-tenant directory)."""
    # Only admins can upload company logo
    require_admin(current_user, "upload company logo")
    
    # Only allow image files
    if not file.content_type or not file.content_type.startswith("image/"):
        logger.error(f"Rejected upload: not an image file. Content-Type: {file.content_type}")
        raise HTTPException(status_code=400, detail="Only image files are allowed.")

    # Ensure static/logos/<tenant_id> directory exists
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static", "logos")
    static_dir = os.path.abspath(static_dir)
    tenant_dir = os.path.join(static_dir, str(current_user.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)

    # Use consistent filename for each tenant (overwrites existing logo)
    ext = os.path.splitext(file.filename)[1] or ".png"
    filename = f"logo{ext}"
    file_path = os.path.join(tenant_dir, filename)
    
    print(f"Attempting to save logo to {file_path}")

    try:
        file.file.seek(0)  # Ensure pointer is at the start
        
        # Read the uploaded file
        file_content = file.file.read()
        
        # Open and resize the image using PIL
        image = Image.open(io.BytesIO(file_content))
        
        # Resize to 100x100 while maintaining aspect ratio
        image.thumbnail((200, 200), Image.Resampling.LANCZOS)
        
        # Save the resized image
        image.save(file_path, quality=85, optimize=True)
        
        print(f"Logo saved successfully to {file_path}")
        
        # Return the public URL
        logo_url = f"/static/logos/{current_user.tenant_id}/{filename}"
        return {"url": logo_url}
        
    except Exception as e:
        print(f"Failed to save logo to {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save logo: {e}")