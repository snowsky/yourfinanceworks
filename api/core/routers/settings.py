from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import tempfile
import os
import shutil
from datetime import datetime, timezone
import logging
from PIL import Image
import io

from core.models.database import get_db, get_master_db, set_tenant_context
from core.models.models_per_tenant import User, Client, Invoice, Settings, ClientNote, InvoiceItem
from core.models.models import Tenant, MasterUser
from core.routers.auth import get_current_user
from core.utils.rbac import require_admin, require_admin_or_superuser
from core.utils.audit import log_audit_event
from core.utils.feature_gate import feature_enabled
from core.constants.error_codes import FAILED_TO_IMPORT_DATA
from core.services.tenant_database_manager import tenant_db_manager
from core.services.expense_mobile_service import get_expense_mobile_config, save_expense_mobile_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_SHARING_SETTINGS = {
    "default_access_type": "public",
    "default_expiration_hours": 24,
    "allow_public_links": True,
    "allow_password_links": True,
    "allow_question_links": True,
    "default_one_time": False,
    "require_expiration": True,
}


def _get_sharing_settings(db: Session) -> Dict[str, Any]:
    sharing_settings_record = db.query(Settings).filter(Settings.key == "sharing_settings").first()
    if sharing_settings_record and sharing_settings_record.value:
        return {**DEFAULT_SHARING_SETTINGS, **sharing_settings_record.value}
    return DEFAULT_SHARING_SETTINGS


@router.get("/")
async def get_settings(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get tenant settings (using tenant info as settings)"""
    # Only org admins or superusers can view settings
    require_admin_or_superuser(current_user, "view settings")

    # Manually get master database
    master_db = next(get_master_db())


    try:
        tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Fetch all needed settings in a single query
        _setting_keys = {"invoice_settings", "ai_chat_history_retention_days", "timezone", "sharing_settings"}
        _settings_map = {
            s.key: s
            for s in db.query(Settings).filter(Settings.key.in_(_setting_keys)).all()
        }

        invoice_settings_record = _settings_map.get("invoice_settings")
        default_invoice_settings = {
            "prefix": "INV-",
            "next_number": "0001",
            "terms": "",
            "notes": "",
            "send_copy": True,
            "auto_reminders": True
        }
        if invoice_settings_record and invoice_settings_record.value:
            invoice_settings = {**default_invoice_settings, **invoice_settings_record.value}
        else:
            invoice_settings = default_invoice_settings

        ai_chat_history_retention_days = 7
        ai_setting = _settings_map.get("ai_chat_history_retention_days")
        if ai_setting and ai_setting.value:
            try:
                ai_chat_history_retention_days = max(1, min(30, int(ai_setting.value)))
            except (ValueError, TypeError):
                ai_chat_history_retention_days = 7

        timezone = "UTC"
        tz_setting = _settings_map.get("timezone")
        if tz_setting and tz_setting.value:
            try:
                timezone = str(tz_setting.value)
            except (ValueError, TypeError):
                timezone = "UTC"

        sharing_settings_record = _settings_map.get("sharing_settings")
        if sharing_settings_record and sharing_settings_record.value:
            sharing_settings = {**DEFAULT_SHARING_SETTINGS, **sharing_settings_record.value}
        else:
            sharing_settings = DEFAULT_SHARING_SETTINGS

        # Return tenant info formatted as settings
        settings_data = {
            "company_info": {
                "name": tenant.name,
                "email": tenant.email or "",
                "phone": tenant.phone or "",
                "address": tenant.address or "",
                "tax_id": tenant.tax_id or "",
                "logo": tenant.company_logo_url or ""
            },
            "invoice_settings": invoice_settings,
            "enable_ai_assistant": tenant.enable_ai_assistant or False,
            "ai_chat_history_retention_days": ai_chat_history_retention_days,
            "timezone": timezone,
            "allow_join_lookup": tenant.allow_join_lookup if tenant.allow_join_lookup is not None else True,
            "join_lookup_exact_match": tenant.join_lookup_exact_match if tenant.join_lookup_exact_match is not None else False,
            "expense_mobile": get_expense_mobile_config(master_db, tenant),
            "sharing_settings": sharing_settings,
        }

        # If AI assistant is enabled, validate license status
        if settings_data["enable_ai_assistant"]:
            if not feature_enabled("ai_chat", db):
                # License expired or deactivated - disable AI assistant
                settings_data["enable_ai_assistant"] = False
                settings_data["ai_assistant_license_error"] = "AI Assistant requires a valid license. Please upgrade your plan."

                # Also update tenant record to disable AI assistant
                tenant.enable_ai_assistant = False
                master_db.commit()

        return settings_data
    finally:
        master_db.close()


@router.get("/sharing")
async def get_sharing_settings(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get record sharing defaults and allowed methods for the active tenant."""
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return _get_sharing_settings(db)

@router.put("/")
async def update_settings(
    settings: Dict[str, Any],
    master_db: Session = Depends(get_master_db),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update tenant settings"""
    # Only org admins or superusers can update settings
    require_admin_or_superuser(current_user, "update settings")



    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Update tenant info from company_info
    company_info = settings.get("company_info", {})
    if company_info:
        # Validate and normalize company name consistency with signup rules (min 2 chars)
        if "name" in company_info and company_info["name"] is not None:
            new_name = str(company_info["name"]).strip()
            if len(new_name) < 2:
                raise HTTPException(status_code=400, detail="Organization name must be at least 2 characters long")
            tenant.name = new_name

        tenant.phone = company_info.get("phone", tenant.phone)
        tenant.address = company_info.get("address", tenant.address)
        tenant.tax_id = company_info.get("tax_id", tenant.tax_id)

        # Update organization join settings
        if "allow_join_lookup" in settings:
            tenant.allow_join_lookup = settings["allow_join_lookup"]
        if "join_lookup_exact_match" in settings:
            tenant.join_lookup_exact_match = settings["join_lookup_exact_match"]

        # Logo is managed separately via /upload-logo endpoint, don't update it here

    # Update AI assistant setting
    if "enable_ai_assistant" in settings:
        # Check license if enabling or keeping enabled
        if settings["enable_ai_assistant"]:
            if not feature_enabled("ai_chat", db):
                raise HTTPException(
                    status_code=402,
                    detail="AI Assistant feature requires a valid license. Please upgrade your plan."
                )
        tenant.enable_ai_assistant = settings["enable_ai_assistant"]

    # Update AI chat history retention setting
    if "ai_chat_history_retention_days" in settings:
        retention_days = settings["ai_chat_history_retention_days"]
        # Validate retention days (1-30)
        if not isinstance(retention_days, int) or retention_days < 1 or retention_days > 30:
            raise HTTPException(status_code=400, detail="AI chat history retention days must be between 1 and 30")

        # Get or create the setting record
        retention_setting = db.query(Settings).filter(Settings.key == "ai_chat_history_retention_days").first()
        if retention_setting:
            retention_setting.value = retention_days
            retention_setting.updated_at = datetime.now(timezone.utc)
        else:
            retention_setting = Settings(
                key="ai_chat_history_retention_days",
                value=retention_days,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(retention_setting)

        db.commit()

    # Update invoice settings in tenant database
    invoice_settings = settings.get("invoice_settings", {})

    if invoice_settings:
        # Get or create invoice settings record
        invoice_settings_record = db.query(Settings).filter(Settings.key == "invoice_settings").first()

        if invoice_settings_record:
            # Update existing record
            current_value = invoice_settings_record.value or {}
            updated_value = {**current_value, **invoice_settings}
            invoice_settings_record.value = updated_value
            invoice_settings_record.updated_at = datetime.now(timezone.utc)
        else:
            # Create new record
            invoice_settings_record = Settings(
                key="invoice_settings",
                value=invoice_settings,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(invoice_settings_record)

        db.commit()

        # Log audit event in tenant DB for invoice settings
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="invoice_settings",
            resource_id="1",
            resource_name="Invoice Settings",
            details=invoice_settings,
            status="success"
        )

    # Update timezone setting in tenant database
    if "timezone" in settings:
        timezone_value = settings.get("timezone")
        if timezone_value:
            # Validate timezone (basic check - should be a non-empty string)
            timezone_str = str(timezone_value).strip()
            if not timezone_str:
                raise HTTPException(status_code=400, detail="Timezone cannot be empty")

            # Get or create timezone setting record
            timezone_setting = db.query(Settings).filter(Settings.key == "timezone").first()

            if timezone_setting:
                timezone_setting.value = timezone_str
                timezone_setting.updated_at = datetime.now(timezone.utc)
            else:
                timezone_setting = Settings(
                    key="timezone",
                    value=timezone_str,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(timezone_setting)

            db.commit()

    if "sharing_settings" in settings:
        sharing_settings = settings.get("sharing_settings") or {}
        allowed_access_types = {"public", "password", "question"}
        default_access_type = sharing_settings.get("default_access_type", "public")
        if default_access_type not in allowed_access_types:
            raise HTTPException(status_code=400, detail="Invalid default sharing access type")

        expiration_hours = sharing_settings.get("default_expiration_hours", 24)
        if not isinstance(expiration_hours, int) or expiration_hours < 0 or expiration_hours > 8760:
            raise HTTPException(status_code=400, detail="Default sharing expiration must be between 0 and 8760 hours")

        if sharing_settings.get("require_expiration") and expiration_hours == 0:
            raise HTTPException(status_code=400, detail="Expiration is required when require_expiration is enabled")

        if default_access_type == "public" and not sharing_settings.get("allow_public_links", True):
            raise HTTPException(status_code=400, detail="Default access type cannot be disabled")
        if default_access_type == "password" and not sharing_settings.get("allow_password_links", True):
            raise HTTPException(status_code=400, detail="Default access type cannot be disabled")
        if default_access_type == "question" and not sharing_settings.get("allow_question_links", True):
            raise HTTPException(status_code=400, detail="Default access type cannot be disabled")

        sharing_settings_record = db.query(Settings).filter(Settings.key == "sharing_settings").first()
        if sharing_settings_record:
            current_value = sharing_settings_record.value or {}
            sharing_settings_record.value = {**current_value, **sharing_settings}
            sharing_settings_record.updated_at = datetime.now(timezone.utc)
        else:
            sharing_settings_record = Settings(
                key="sharing_settings",
                value=sharing_settings,
                category="sharing",
                description="Default record sharing controls",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(sharing_settings_record)
        db.commit()

    if "expense_mobile" in settings:
        save_expense_mobile_config(master_db, tenant, settings.get("expense_mobile"))

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
    # Manually set tenant context and get tenant database
    set_tenant_context(current_user.tenant_id)
    tenant_session = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    tenant_db = tenant_session()

    try:
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="settings",
            resource_id=str(tenant.id),
            resource_name=f"Setting: {tenant.name}",
            details=settings,
            status="success"
        )
    finally:
        tenant_db.close()

    return {"message": "Settings updated successfully"}

@router.get("/export-data")
async def export_tenant_data(
    current_user: MasterUser = Depends(get_current_user),
    master_db: Session = Depends(get_master_db)
):
    """Export tenant data to a real SQLite file"""
    require_admin_or_superuser(current_user, "export data")
    import sqlalchemy
    from sqlalchemy.orm import sessionmaker
    from core.models.models_per_tenant import (
        Base as TenantBase, User, Client, ClientNote, Invoice, Payment, Settings, DiscountRule, SupportedCurrency, CurrencyRate, InvoiceItem, InvoiceHistory, AIConfig, Expense, ExpenseAttachment, BankStatement, BankStatementTransaction, AuditLog, AIChatHistory
    )
    import atexit

    # Manually set tenant context and get tenant database
    set_tenant_context(current_user.tenant_id)
    tenant_session = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    db = tenant_session()

    # Create a temporary SQLite file
    from core.utils.file_validation import validate_file_path
    temp_dir = tempfile.mkdtemp()
    sqlite_path = os.path.join(temp_dir, f"data_export_{current_user.tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite")
    sqlite_path = os.path.abspath(sqlite_path)  # Normalize path
    sqlite_url = f"sqlite:///{sqlite_path}"
    sqlite_engine = sqlalchemy.create_engine(sqlite_url, connect_args={"check_same_thread": False})
    TenantBase.metadata.create_all(sqlite_engine)
    SqliteSession = sessionmaker(bind=sqlite_engine)
    sqlite_session = SqliteSession()

    _EXPORT_BATCH_SIZE = 500

    def _copy_table(src_query, model_cls):
        """Stream rows in batches to avoid loading entire tables into memory."""
        count = 0
        for obj in src_query.yield_per(_EXPORT_BATCH_SIZE):
            sqlite_session.add(model_cls(**{c.name: getattr(obj, c.name) for c in model_cls.__table__.columns}))
            count += 1
            if count % _EXPORT_BATCH_SIZE == 0:
                sqlite_session.flush()

    try:
        # Copy all data from the current tenant's database using streaming to avoid OOM on large tables.
        # NOTE: SQLAlchemy ORM queries are safe and automatically parameterized - not vulnerable to SQL injection
        # 1. Users
        _copy_table(db.query(User), User)
        # 2. Clients
        _copy_table(db.query(Client), Client)
        # 3. ClientNotes
        _copy_table(db.query(ClientNote), ClientNote)
        # 4. Invoices
        _copy_table(db.query(Invoice), Invoice)
        # 5. Payments
        _copy_table(db.query(Payment), Payment)
        # 6. Settings
        _copy_table(db.query(Settings), Settings)
        # 7. DiscountRules
        _copy_table(db.query(DiscountRule), DiscountRule)
        # 8. SupportedCurrencies
        _copy_table(db.query(SupportedCurrency), SupportedCurrency)
        # 9. CurrencyRates
        _copy_table(db.query(CurrencyRate), CurrencyRate)
        # 10. InvoiceItems
        _copy_table(db.query(InvoiceItem), InvoiceItem)
        # 11. InvoiceHistory
        _copy_table(db.query(InvoiceHistory), InvoiceHistory)
        # 12. AIConfig
        _copy_table(db.query(AIConfig), AIConfig)
        # 13. Expenses
        _copy_table(db.query(Expense), Expense)
        # 14. ExpenseAttachments
        _copy_table(db.query(ExpenseAttachment), ExpenseAttachment)
        # 15. BankStatements
        _copy_table(db.query(BankStatement), BankStatement)
        # 16. BankStatementTransactions
        _copy_table(db.query(BankStatementTransaction), BankStatementTransaction)
        # 17. AuditLogs
        _copy_table(db.query(AuditLog), AuditLog)
        # 18. AIChatHistory
        _copy_table(db.query(AIChatHistory), AIChatHistory)
        sqlite_session.commit()
        sqlite_session.close()

        # Return the file as a download
        validated_path = validate_file_path(sqlite_path)

        def cleanup():
            shutil.rmtree(temp_dir, ignore_errors=True)
        atexit.register(cleanup)
        return FileResponse(
            path=validated_path,
            filename=os.path.basename(validated_path),
            media_type="application/x-sqlite3",
            background=None  # atexit will handle cleanup
        )
    except Exception as e:
        sqlite_session.rollback()
        sqlite_session.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Error exporting tenant data to SQLite: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting data: {str(e)}")
    finally:
        db.close()  # Close tenant database session

@router.post("/import-data")
async def import_tenant_data(
    file: UploadFile = File(...),
    current_user: MasterUser = Depends(get_current_user)
):
    """Import data from an uploaded SQLite file (full restore, all tables)"""
    import tempfile, os
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import sessionmaker
    from core.models import (
        User, Client, ClientNote, Invoice, Payment, Settings, DiscountRule, SupportedCurrency, CurrencyRate, InvoiceItem, InvoiceHistory, AIConfig, EmailNotificationSettings, Expense, ExpenseAttachment, BankStatement, BankStatementTransaction, AuditLog, AIChatHistory
    )
    from core.services.tenant_database_manager import tenant_db_manager
    try:
        require_admin_or_superuser(current_user, "import data")

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
                'invoice_items', 'invoice_history', 'ai_configs', 'expenses', 'expense_attachments',
                'bank_statements', 'bank_statement_transactions', 'audit_logs', 'ai_chat_history'
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
                db.query(AIChatHistory).delete()
                db.query(AuditLog).delete()
                db.query(BankStatementTransaction).delete()
                db.query(BankStatement).delete()
                db.query(ExpenseAttachment).delete()
                db.query(Expense).delete()
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
                # Delete notification settings before users to avoid FK violations
                db.query(EmailNotificationSettings).delete()
                db.query(User).filter(User.is_superuser == False).delete()  # Don't delete superusers
                old_to_new_user_ids = {}
                old_to_new_client_ids = {}
                old_to_new_invoice_ids = {}
                old_to_new_expense_ids = {}
                old_to_new_statement_ids = {}
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
                # 5. Email Notification Settings (map user IDs)
                if 'email_notification_settings' in tables:
                    notif_rows = import_db.query(EmailNotificationSettings).all()
                    for row in notif_rows:
                        new_user_id = old_to_new_user_ids.get(row.user_id)
                        if not new_user_id:
                            continue
                        new_row = EmailNotificationSettings(
                            user_id=new_user_id,
                            user_created=row.user_created,
                            user_updated=row.user_updated,
                            user_deleted=row.user_deleted,
                            user_login=row.user_login,
                            client_created=row.client_created,
                            client_updated=row.client_updated,
                            client_deleted=row.client_deleted,
                            invoice_created=row.invoice_created,
                            invoice_updated=row.invoice_updated,
                            invoice_deleted=row.invoice_deleted,
                            invoice_sent=row.invoice_sent,
                            invoice_paid=row.invoice_paid,
                            invoice_overdue=row.invoice_overdue,
                            payment_created=row.payment_created,
                            payment_updated=row.payment_updated,
                            payment_deleted=row.payment_deleted,
                            settings_updated=row.settings_updated,
                            notification_email=row.notification_email,
                            daily_summary=row.daily_summary,
                            weekly_summary=row.weekly_summary,
                        )
                        db.add(new_row)
                    imported_counts['email_notification_settings'] = len(notif_rows)

                # 6. InvoiceItems
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
                        new_user_id = old_to_new_user_ids.get(note.user_id, current_user.id)
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
                        new_user_id = old_to_new_user_ids.get(hist.user_id) if hist.user_id else current_user.id
                        if new_invoice_id and new_user_id:
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

                # 13. Expenses
                if 'expenses' in tables:
                    expenses = import_db.query(Expense).all()
                    for expense in expenses:
                        new_user_id = old_to_new_user_ids.get(expense.user_id) if expense.user_id else None
                        new_invoice_id = old_to_new_invoice_ids.get(expense.invoice_id) if expense.invoice_id else None
                        new_expense = Expense(
                            amount=expense.amount,
                            currency=expense.currency,
                            expense_date=expense.expense_date,
                            category=expense.category,
                            vendor=expense.vendor,
                            label=expense.label,
                            labels=expense.labels,
                            tax_rate=expense.tax_rate,
                            tax_amount=expense.tax_amount,
                            total_amount=expense.total_amount,
                            payment_method=expense.payment_method,
                            reference_number=expense.reference_number,
                            status=expense.status,
                            notes=expense.notes,
                            receipt_path=expense.receipt_path,
                            receipt_filename=expense.receipt_filename,
                            user_id=new_user_id,
                            invoice_id=new_invoice_id,
                            imported_from_attachment=getattr(expense, 'imported_from_attachment', False),
                            analysis_status=getattr(expense, 'analysis_status', 'not_started'),
                            analysis_result=getattr(expense, 'analysis_result', None),
                            analysis_error=getattr(expense, 'analysis_error', None),
                            manual_override=getattr(expense, 'manual_override', False),
                            analysis_updated_at=getattr(expense, 'analysis_updated_at', None),
                            created_at=expense.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_expense)
                        db.flush()
                        old_to_new_expense_ids[expense.id] = new_expense.id
                    imported_counts['expenses'] = len(expenses)

                # 14. ExpenseAttachments
                if 'expense_attachments' in tables:
                    attachments = import_db.query(ExpenseAttachment).all()
                    attachment_count = 0
                    for attachment in attachments:
                        new_expense_id = old_to_new_expense_ids.get(attachment.expense_id)
                        new_user_id = old_to_new_user_ids.get(attachment.uploaded_by) if attachment.uploaded_by else None
                        if new_expense_id:
                            new_attachment = ExpenseAttachment(
                                expense_id=new_expense_id,
                                filename=attachment.filename,
                                content_type=attachment.content_type,
                                size_bytes=attachment.size_bytes,
                                file_path=attachment.file_path,
                                uploaded_at=attachment.uploaded_at,
                                uploaded_by=new_user_id
                            )
                            db.add(new_attachment)
                            attachment_count += 1
                    imported_counts['expense_attachments'] = attachment_count

                # 15. BankStatements
                if 'bank_statements' in tables:
                    statements = import_db.query(BankStatement).all()
                    for statement in statements:
                        new_statement = BankStatement(
                            tenant_id=current_user.tenant_id,
                            original_filename=statement.original_filename,
                            stored_filename=statement.stored_filename,
                            file_path=statement.file_path,
                            status=statement.status,
                            extracted_count=statement.extracted_count,
                            notes=statement.notes,
                            labels=statement.labels,
                            created_at=statement.created_at,
                            updated_at=datetime.now(timezone.utc)
                        )
                        db.add(new_statement)
                        db.flush()
                        old_to_new_statement_ids[statement.id] = new_statement.id
                    imported_counts['bank_statements'] = len(statements)

                # 16. BankStatementTransactions
                if 'bank_statement_transactions' in tables:
                    transactions = import_db.query(BankStatementTransaction).all()
                    transaction_count = 0
                    for transaction in transactions:
                        new_statement_id = old_to_new_statement_ids.get(transaction.statement_id)
                        new_invoice_id = old_to_new_invoice_ids.get(transaction.invoice_id) if transaction.invoice_id else None
                        new_expense_id = old_to_new_expense_ids.get(transaction.expense_id) if transaction.expense_id else None
                        if new_statement_id:
                            new_transaction = BankStatementTransaction(
                                statement_id=new_statement_id,
                                date=transaction.date,
                                description=transaction.description,
                                amount=transaction.amount,
                                transaction_type=transaction.transaction_type,
                                balance=transaction.balance,
                                category=transaction.category,
                                invoice_id=new_invoice_id,
                                expense_id=new_expense_id,
                                created_at=transaction.created_at,
                                updated_at=datetime.now(timezone.utc)
                            )
                            db.add(new_transaction)
                            transaction_count += 1
                    imported_counts['bank_statement_transactions'] = transaction_count

                # 17. AuditLogs
                if 'audit_logs' in tables:
                    audit_logs = import_db.query(AuditLog).all()
                    for log in audit_logs:
                        new_log = AuditLog(
                            user_id=log.user_id,
                            user_email=log.user_email,
                            action=log.action,
                            resource_type=log.resource_type,
                            resource_id=log.resource_id,
                            resource_name=log.resource_name,
                            details=log.details,
                            ip_address=log.ip_address,
                            user_agent=log.user_agent,
                            status=log.status,
                            error_message=log.error_message,
                            created_at=log.created_at
                        )
                        db.add(new_log)
                    imported_counts['audit_logs'] = len(audit_logs)

                # 18. AIChatHistory
                if 'ai_chat_history' in tables:
                    chat_history = import_db.query(AIChatHistory).all()
                    for chat in chat_history:
                        new_user_id = old_to_new_user_ids.get(chat.user_id) if chat.user_id else None
                        if new_user_id:
                            new_chat = AIChatHistory(
                                user_id=new_user_id,
                                tenant_id=current_user.tenant_id,
                                message=chat.message,
                                sender=chat.sender,
                                created_at=chat.created_at
                            )
                            db.add(new_chat)
                    imported_counts['ai_chat_history'] = len(chat_history)

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
    logger.info(f"🔍 LOGO UPLOAD ENDPOINT REACHED - user: {current_user.email}, tenant: {current_user.tenant_id}")
    logger.info(f"file: {file}")

    # Only admins can upload company logo
    require_admin(current_user, "upload company logo")

    # Debug logging to see what we're receiving
    logger.info(f"🔍 Logo upload request - filename: {file.filename}, content_type: {file.content_type}, size: {file.size if hasattr(file, 'size') else 'unknown'}")

    # Validate file extension first
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_ext = os.path.splitext(file.filename.lower())[1]
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}")

    # Validate content type
    allowed_content_types = {'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'}
    if file.content_type and file.content_type.lower() not in allowed_content_types:
        raise HTTPException(status_code=400, detail=f"Invalid content type: {file.content_type}")

    # Read and validate file content
    try:
        file_content = await file.read()
        file_size = len(file_content)
        logger.info(f"Logo file size: {file_size} bytes")

        MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5MB
        if file_size > MAX_LOGO_SIZE:
            raise HTTPException(status_code=400, detail=f"Logo file too large. Maximum size is 5MB, received {file_size} bytes")

        # Validate magic numbers (file signature) for common image types
        if len(file_content) < 4:
            raise HTTPException(status_code=400, detail="File too small to be a valid image")

        magic = file_content[:4]
        valid_magic = (
            magic[:2] == b'\xff\xd8' or  # JPEG
            magic[:3] == b'\x89PNG' or   # PNG
            magic[:3] == b'GIF' or       # GIF
            magic[:4] == b'RIFF' or      # WEBP
            magic[:2] == b'<?' or magic[:4] == b'<svg'  # SVG
        )
        if not valid_magic:
            raise HTTPException(status_code=400, detail="File content does not match image format")
    except Exception as e:
        logger.error(f"Error reading file for size check: {e}")
        raise HTTPException(status_code=400, detail="Error processing uploaded file")

    # Ensure static/logos/<tenant_id> directory exists
    from core.utils.file_validation import validate_file_path
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static", "logos")
    static_dir = os.path.abspath(static_dir)
    tenant_dir = os.path.join(static_dir, str(current_user.tenant_id))
    tenant_dir = os.path.abspath(tenant_dir)

    # Ensure tenant_dir is within static_dir
    if not tenant_dir.startswith(static_dir):
        raise HTTPException(status_code=400, detail="Invalid tenant directory")

    os.makedirs(tenant_dir, exist_ok=True)

    # Use consistent filename for each tenant (overwrites existing logo)
    ext = os.path.splitext(file.filename)[1].lower() or ".png"
    if ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
        ext = ".png"
    filename = f"logo{ext}"
    file_path = validate_file_path(os.path.join(tenant_dir, filename), must_exist=False)

    # Final validation: ensure file_path is within tenant_dir
    if not file_path.startswith(tenant_dir):
        raise HTTPException(status_code=400, detail="Invalid file path")

    print(f"Attempting to save logo to {file_path}")

    try:
        # Use the file_content we already read for size validation
        # Open and resize the image using PIL
        image = Image.open(io.BytesIO(file_content))

        # Resize to 200x200 while maintaining aspect ratio
        image.thumbnail((200, 200), Image.Resampling.LANCZOS)

        # Save the resized image
        image.save(file_path, quality=85, optimize=True)

        print(f"Logo saved successfully to {file_path}")

        # Return the public URL
        logo_url = f"/static/logos/{current_user.tenant_id}/{filename}"

        # Save logo URL to tenant record in master database using manual session
        from sqlalchemy import text
        from core.models.database import SessionLocal
        logger.info(f"Saving logo URL to tenant {current_user.tenant_id}: {logo_url}")

        db = SessionLocal()
        try:
            result = db.execute(
                text("UPDATE tenants SET company_logo_url = :logo_url WHERE id = :tenant_id"),
                {"logo_url": logo_url, "tenant_id": current_user.tenant_id}
            )
            db.commit()
            logger.info(f"Logo URL updated in database, rows affected: {result.rowcount}")

            # Verify the update
            verify = db.execute(
                text("SELECT company_logo_url FROM tenants WHERE id = :tenant_id"),
                {"tenant_id": current_user.tenant_id}
            ).fetchone()
            logger.info(f"Verification query result: {verify[0] if verify else 'NOT FOUND'}")
        except Exception as e:
            logger.error(f"Database error: {e}")
            db.rollback()
            raise
        finally:
            db.close()

        return {"url": logo_url}

    except Exception as e:
        print(f"Failed to save logo to {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save logo: {e}")


@router.get("/logo/{tenant_id}")
async def get_company_logo(
    tenant_id: str,
    master_db: Session = Depends(get_master_db)
):
    """Retrieve a company logo image by tenant ID."""
    try:
        # Manually get master database
        tenant_record = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant_record or not tenant_record.company_logo_url:
            raise HTTPException(status_code=404, detail="Logo not found for this tenant.")

        # Construct the absolute path to the logo file
        # Assuming company_logo_url is like /static/logos/<tenant_id>/logo.png
        # We need to convert this to an absolute file system path
        relative_path = tenant_record.company_logo_url.lstrip("/") # Remove leading slash

        # Validate path to prevent directory traversal
        if ".." in relative_path or not relative_path.startswith("static/logos/"):
            raise HTTPException(status_code=400, detail="Invalid logo path")

        from core.utils.file_validation import validate_file_path
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        file_path = os.path.join(base_dir, relative_path)
        validated_path = validate_file_path(file_path)

        # Ensure the resolved path is still within the expected directory
        expected_dir = os.path.abspath(os.path.join(base_dir, "static", "logos"))
        if not validated_path.startswith(expected_dir):
            raise HTTPException(status_code=400, detail="Invalid logo path")

        if not os.path.exists(validated_path):
            raise HTTPException(status_code=404, detail="Logo file not found on server.")

        return FileResponse(validated_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving logo for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while retrieving logo.")

@router.get("/value/{key}")
async def get_setting_value(
    key: str,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get a specific setting value by key"""
    # Only admins
    require_admin_or_superuser(current_user, "view settings")

    setting = db.query(Settings).filter(Settings.key == key).first()
    if not setting:
        return {"key": key, "value": None}

    return {"key": key, "value": setting.value}

@router.put("/value/{key}")
async def update_setting_value(
    key: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update a specific setting value by key"""
    require_admin_or_superuser(current_user, "update settings")

    # Expect payload to contain "value" key
    if "value" not in payload:
         # Optionally allow raw payload if it doesn't have "value"? 
         # Best to require structure: {"value": <actual_value>}
         # But if the user sends just a dict that happens to have "value"... 
         # Let's enforce {"value": ...} wrapper in frontend.
         pass

    new_value = payload.get("value")

    setting = db.query(Settings).filter(Settings.key == key).first()
    if setting:
        setting.value = new_value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        setting = Settings(
            key=key,
            value=new_value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(setting)

    db.commit()
    db.refresh(setting)

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="setting",
        resource_id=key,
        resource_name=f"Setting: {key}",
        details={"value": new_value},
        status="success"
    )

    return {"key": key, "value": setting.value}
