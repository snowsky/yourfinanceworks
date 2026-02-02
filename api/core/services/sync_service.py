import os
import shutil
import tempfile
import zipfile
import logging
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import sqlalchemy
from sqlalchemy.orm import Session, sessionmaker
from fastapi import HTTPException

from core.models.database import set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from commercial.cloud_storage.config import get_cloud_storage_config
from core.models.models_per_tenant import (
    Base as TenantBase, User, Client, ClientNote, Invoice, Payment,
    Settings, DiscountRule, SupportedCurrency, CurrencyRate,
    InvoiceItem, InvoiceHistory, AIConfig, Expense, ExpenseAttachment,
    BankStatement, BankStatementTransaction, AuditLog, AIChatHistory,
    BankStatementAttachment, RawEmail, ReportTemplate, ScheduledReport,
    ReportHistory, InventoryCategory, InventoryItem, StockMovement,
    Warehouse, InventoryLevel, ItemAttachment, InvoiceAttachment,
    InvoiceProcessingTask, ExpenseApproval, InvoiceApproval, ApprovalRule,
    ApprovalDelegate, Reminder, ReminderNotification, CloudStorageConfiguration,
    StorageOperationLog, BatchProcessingJob, BatchFileProcessing,
    ExportDestinationConfig, Anomaly, InstallationInfo, LicenseValidationLog
)

logger = logging.getLogger(__name__)

class SyncService:
    @staticmethod
    def get_data_fingerprint(db: Session) -> str:
        """
        Generates a unique fingerprint for the current tenant's data.
        This includes counts and latest update timestamps of major tables.
        """
        tables = [
            Client, Invoice, Payment, Expense,
            BankStatement, AuditLog, AIChatHistory
        ]

        fingerprint_data = {}
        for table in tables:
            count = db.query(table).count()
            # Try to get the latest updated_at or created_at
            latest = None
            if hasattr(table, 'updated_at'):
                latest = db.query(sqlalchemy.func.max(table.updated_at)).scalar()
            elif hasattr(table, 'created_at'):
                latest = db.query(sqlalchemy.func.max(table.created_at)).scalar()

            fingerprint_data[table.__tablename__] = {
                "count": count,
                "latest": latest.isoformat() if latest else None
            }

        # Add hash of settings values that are important
        settings_data = db.query(Settings).all()
        settings_hash = hashlib.md5(
            json.dumps({s.key: str(s.value) for s in settings_data}, sort_keys=True).encode()
        ).hexdigest()
        fingerprint_data["settings_hash"] = settings_hash

        return hashlib.sha256(
            json.dumps(fingerprint_data, sort_keys=True).encode()
        ).hexdigest()

    @staticmethod
    def get_storage_identity() -> Dict[str, Any]:
        """
        Returns an identity object for the current cloud storage configuration.
        Used to determine if two instances share the same storage.
        """
        config = get_cloud_storage_config()
        primary = config.get_primary_provider().value

        identity = {"provider": primary}

        if primary == "aws_s3":
            identity.update({
                "bucket": config.AWS_S3_BUCKET_NAME,
                "region": config.AWS_S3_REGION,
                "endpoint": config.AWS_S3_ENDPOINT_URL
            })
        elif primary == "azure_blob":
            identity.update({
                "container": config.AZURE_CONTAINER_NAME,
                "account": config.AZURE_STORAGE_ACCOUNT_NAME
            })
        elif primary == "gcp_storage":
            identity.update({
                "bucket": config.GCP_BUCKET_NAME,
                "project": config.GCP_PROJECT_ID
            })
        else:
            identity["path"] = os.path.abspath(config.LOCAL_STORAGE_PATH)

        return identity

    @staticmethod
    async def package_data(db: Session, tenant_id: int, include_attachments: bool = True) -> bytes:
        """
        Packages database records and attachment files into a single ZIP file.
        Returns the ZIP file content as bytes.
        """
        if include_attachments:
            # Pre-fetch cloud attachments to local disk before zipping
            await SyncService._ensure_attachments_on_disk(db, tenant_id)

        temp_dir = tempfile.mkdtemp()
        try:
            # 1. Export database to SQLite
            sqlite_file = os.path.join(temp_dir, "database.sqlite")
            SyncService._export_to_sqlite(db, sqlite_file)

            # 2. Package attachments
            attachments_dir = Path("attachments") / f"tenant_{tenant_id}"

            # 3. Create ZIP package
            package_path = os.path.join(temp_dir, "sync_package.zip")
            with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add database
                zipf.write(sqlite_file, "database.sqlite")

                # Add attachments if they exist and requested
                if include_attachments and attachments_dir.exists():
                    for root, dirs, files in os.walk(attachments_dir):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(attachments_dir.parent)
                            zipf.write(file_path, arcname)

                # Include a manifest
                manifest = {
                    "tenant_id": tenant_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "include_attachments": include_attachments
                }
                zipf.writestr("manifest.json", json.dumps(manifest))

            with open(package_path, 'rb') as f:
                return f.read()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    async def _ensure_attachments_on_disk(db: Session, tenant_id: int):
        """
        Ensures that all attachments for the tenant are present on the local disk.
        If a file is missing locally but registered in the database, it attempts
        to download it from cloud storage.
        """
        try:
            from commercial.cloud_storage.service import CloudStorageService
            from commercial.cloud_storage.config import get_cloud_storage_config
            cloud_config = get_cloud_storage_config()
            cloud_service = CloudStorageService(db, cloud_config)
        except (ImportError, Exception) as e:
            logger.info(f"Cloud storage service not available for attachment pre-fetching: {e}")
            return

        # List of models and their path fields
        attachment_models = [
            (ExpenseAttachment, ['file_path']),
            (BankStatementAttachment, ['file_path']),
            (ItemAttachment, ['file_path', 'thumbnail_path']),
            (InvoiceAttachment, ['file_path']),
            (BankStatement, ['file_path']),
            (ReportHistory, ['file_path']),
            (InvoiceProcessingTask, ['file_path']),
            (BatchFileProcessing, ['file_path'])
        ]

        for model, fields in attachment_models:
            records = db.query(model).all()
            for record in records:
                for field in fields:
                    file_key = getattr(record, field)
                    if not file_key:
                        continue

                    # Target local path
                    if '/' in file_key:
                        # Cloud keys are usually tenant_X/type/filename
                        local_path = Path("attachments") / file_key
                    else:
                        # Non-path keys are likely local filenames in tenant root
                        local_path = Path("attachments") / f"tenant_{tenant_id}" / file_key

                    if local_path.exists():
                        continue

                    logger.info(f"Downloading missing attachment for sync: {file_key}")
                    try:
                        # Fetch from cloud (user_id=0 for system)
                        result = await cloud_service.retrieve_file(
                            file_key=file_key,
                            tenant_id=str(tenant_id),
                            user_id=0,
                            generate_url=False
                        )
                        if result.success and result.file_content:
                            local_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(local_path, 'wb') as f:
                                f.write(result.file_content)
                            logger.info(f"Successfully pre-fetched {file_key}")
                    except Exception as e:
                        logger.warning(f"Failed to pre-fetch {file_key}: {e}")

    @staticmethod
    def apply_package(package_bytes: bytes, tenant_id: int):
        """
        Unpacks a sync package and applies it to the tenant database and file system.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            package_path = os.path.join(temp_dir, "sync_package.zip")
            with open(package_path, 'wb') as f:
                f.write(package_bytes)

            with zipfile.ZipFile(package_path, 'r') as zipf:
                zipf.extractall(temp_dir)

            sqlite_file = os.path.join(temp_dir, "database.sqlite")
            if not os.path.exists(sqlite_file):
                raise Exception("Invalid sync package: missing database.sqlite")

            # 1. Apply database changes
            from core.services.tenant_database_manager import tenant_db_manager
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db = SessionLocal_tenant()
            try:
                SyncService._import_from_sqlite(sqlite_file, db, tenant_id)
                # Ensure users exist in master database so they can log in
                SyncService._align_master_users(db, tenant_id)
            finally:
                db.close()

            # 2. Apply attachments
            # The structure in ZIP is tenant_{id}/...
            tenant_folder_name = f"tenant_{tenant_id}"
            extracted_attachments = Path(temp_dir) / tenant_folder_name
            if extracted_attachments.exists():
                target_attachments = Path("attachments") / tenant_folder_name
                # Ensure target exists
                target_attachments.mkdir(parents=True, exist_ok=True)
                # Copy files (overwrite existing)
                for root, dirs, files in os.walk(extracted_attachments):
                    for file in files:
                        src = Path(root) / file
                        rel_path = src.relative_to(extracted_attachments)
                        dst = target_attachments / rel_path
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _export_to_sqlite(source_db: Session, target_path: str):
        """Internal helper to copy data to a new SQLite file"""
        sqlite_url = f"sqlite:///{target_path}"
        engine = sqlalchemy.create_engine(sqlite_url)
        TenantBase.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        target_session = SessionLocal()

        try:
            # List of all models (per tenant)
            models = [
                User, Client, ClientNote, Invoice, Payment, Settings, 
                DiscountRule, SupportedCurrency, CurrencyRate, 
                InvoiceItem, InvoiceHistory, AIConfig, Expense, 
                ExpenseAttachment, BankStatement, BankStatementTransaction, 
                AuditLog, AIChatHistory, BankStatementAttachment, RawEmail,
                ReportTemplate, ScheduledReport, ReportHistory,
                InventoryCategory, InventoryItem, StockMovement, Warehouse,
                InventoryLevel, ItemAttachment, InvoiceAttachment,
                InvoiceProcessingTask, ExpenseApproval, InvoiceApproval,
                ApprovalRule, ApprovalDelegate, Reminder, ReminderNotification,
                CloudStorageConfiguration, StorageOperationLog, BatchProcessingJob,
                BatchFileProcessing, ExportDestinationConfig, Anomaly
            ]

            for model in models:
                # Query all from source and add to target
                # We use attribute copying to avoid session conflicts
                for obj in source_db.query(model).all():
                    data = {c.name: getattr(obj, c.name) for c in model.__table__.columns}
                    target_session.add(model(**data))
                target_session.flush()

            target_session.commit()
        except Exception as e:
            target_session.rollback()
            raise e
        finally:
            target_session.close()

    @staticmethod
    def _import_from_sqlite(sqlite_path: str, target_db: Session, tenant_id: int):
        """Internal helper to import data from a SQLite file (replacing current data)"""
        engine = sqlalchemy.create_engine(f"sqlite:///{sqlite_path}")
        SessionLocal = sessionmaker(bind=engine)
        source_db = SessionLocal()

        try:
            # 1. Clear existing data (in reverse order of FK dependencies)
            models_to_clear = [
                Anomaly,
                ExportDestinationConfig, BatchFileProcessing, BatchProcessingJob,
                StorageOperationLog, CloudStorageConfiguration,
                ReminderNotification, Reminder, ApprovalDelegate,
                ApprovalRule, InvoiceApproval, ExpenseApproval,
                InvoiceProcessingTask, InvoiceAttachment, ItemAttachment,
                InventoryLevel, Warehouse, StockMovement, InventoryItem,
                InventoryCategory, ReportHistory, ScheduledReport,
                ReportTemplate, RawEmail, BankStatementAttachment,
                AIChatHistory, AuditLog, BankStatementTransaction, BankStatement,
                ExpenseAttachment, Expense, InvoiceItem, InvoiceHistory, 
                Payment, Invoice, ClientNote, Client, Settings, DiscountRule,
                CurrencyRate, SupportedCurrency, AIConfig
            ]

            for model in models_to_clear:
                target_db.query(model).delete()

            # Don't delete all users, maybe just non-superusers or keep current
            # In the settings.py import logic, it deletes regular users
            from core.models.models_per_tenant import User as TenantUser
            target_db.query(TenantUser).filter(TenantUser.is_superuser == False).delete()

            target_db.flush()

            # 2. Re-import data
            # Note: We need to handle ID mapping if IDs are not stable, 
            # but for a full sync between identical schemas, we can try to keep IDs.
            # The settings.py import logic handles ID mapping, which is safer.
            # I'll implement a simplified version of that mapping here.

            # Mapping tables for FKs
            user_map = {}
            client_map = {}
            invoice_map = {}
            expense_map = {}
            statement_map = {}
            category_map = {}
            item_map = {}
            warehouse_map = {}
            template_map = {}
            rule_map = {}
            job_map = {}

            # 2. Users - Smart mapping
            # First, map superusers by role if they exist, then others by email
            source_users = source_db.query(TenantUser).all()
            target_users = target_db.query(TenantUser).all()

            # Map superusers first (assume the primary admin is the same person)
            source_superusers = [u for u in source_users if u.is_superuser]
            target_superusers = [u for u in target_users if u.is_superuser]

            if source_superusers and target_superusers:
                # Map first source superuser to first target superuser
                user_map[source_superusers[0].id] = target_superusers[0].id
                # Remove them from further direct matching if we have multiples
                remaining_source = [u for u in source_users if u.id != source_superusers[0].id]
            else:
                remaining_source = source_users

            for u in remaining_source:
                # check if exists by email
                existing = target_db.query(TenantUser).filter(TenantUser.email == u.email).first()
                if existing:
                    user_map[u.id] = existing.id
                else:
                    new_u = TenantUser(**{c.name: getattr(u, c.name) for c in TenantUser.__table__.columns if c.name != 'id'})
                    target_db.add(new_u)
                    target_db.flush()
                    user_map[u.id] = new_u.id

            # 3. Clients
            for c in source_db.query(Client).all():
                new_c = Client(**{col.name: getattr(c, col.name) for col in Client.__table__.columns if col.name != 'id'})
                target_db.add(new_c)
                target_db.flush()
                client_map[c.id] = new_c.id

            # 4. Invoices
            for i in source_db.query(Invoice).all():
                data = {col.name: getattr(i, col.name) for col in Invoice.__table__.columns if col.name != 'id'}
                data['client_id'] = client_map.get(i.client_id)
                data['created_by_user_id'] = user_map.get(i.created_by_user_id)
                data['deleted_by'] = user_map.get(i.deleted_by)
                new_i = Invoice(**data)
                target_db.add(new_i)
                target_db.flush()
                invoice_map[i.id] = new_i.id

            # 5. Payments
            for p in source_db.query(Payment).all():
                data = {col.name: getattr(p, col.name) for col in Payment.__table__.columns if col.name != 'id'}
                data['invoice_id'] = invoice_map.get(p.invoice_id)
                data['user_id'] = user_map.get(p.user_id)
                target_db.add(Payment(**data))

            # 6. Expenses
            for e in source_db.query(Expense).all():
                data = {col.name: getattr(e, col.name) for col in Expense.__table__.columns if col.name != 'id'}
                data['user_id'] = user_map.get(e.user_id)
                data['invoice_id'] = invoice_map.get(e.invoice_id)
                data['created_by_user_id'] = user_map.get(e.created_by_user_id)
                data['deleted_by'] = user_map.get(e.deleted_by)
                new_e = Expense(**data)
                target_db.add(new_e)
                target_db.flush()
                expense_map[e.id] = new_e.id

            # 7. Expense Attachments
            for ea in source_db.query(ExpenseAttachment).all():
                data = {col.name: getattr(ea, col.name) for col in ExpenseAttachment.__table__.columns if col.name != 'id'}
                data['expense_id'] = expense_map.get(ea.expense_id)
                data['uploaded_by'] = user_map.get(ea.uploaded_by)
                target_db.add(ExpenseAttachment(**data))

            # 8. Bank Statements
            for bs in source_db.query(BankStatement).all():
                data = {col.name: getattr(bs, col.name) for col in BankStatement.__table__.columns if col.name != 'id'}
                data['created_by_user_id'] = user_map.get(bs.created_by_user_id)
                data['deleted_by'] = user_map.get(bs.deleted_by)
                new_bs = BankStatement(**data)
                target_db.add(new_bs)
                target_db.flush()
                statement_map[bs.id] = new_bs.id

            # 9. Bank Transactions
            for bt in source_db.query(BankStatementTransaction).all():
                data = {col.name: getattr(bt, col.name) for col in BankStatementTransaction.__table__.columns if col.name != 'id'}
                data['statement_id'] = statement_map.get(bt.statement_id)
                data['invoice_id'] = invoice_map.get(bt.invoice_id)
                data['expense_id'] = expense_map.get(bt.expense_id)
                target_db.add(BankStatementTransaction(**data))

            # 10. Inventory Parents
            for ic in source_db.query(InventoryCategory).all():
                new_ic = InventoryCategory(**{col.name: getattr(ic, col.name) for col in InventoryCategory.__table__.columns if col.name != 'id'})
                target_db.add(new_ic)
                target_db.flush()
                category_map[ic.id] = new_ic.id

            for ii in source_db.query(InventoryItem).all():
                data = {col.name: getattr(ii, col.name) for col in InventoryItem.__table__.columns if col.name != 'id'}
                data['category_id'] = category_map.get(ii.category_id)
                new_ii = InventoryItem(**data)
                target_db.add(new_ii)
                target_db.flush()
                item_map[ii.id] = new_ii.id

            for wh in source_db.query(Warehouse).all():
                data = {col.name: getattr(wh, col.name) for col in Warehouse.__table__.columns if col.name != 'id'}
                data['manager_id'] = user_map.get(wh.manager_id)
                new_wh = Warehouse(**data)
                target_db.add(new_wh)
                target_db.flush()
                warehouse_map[wh.id] = new_wh.id

            # 11. Report/Approval/Batch Parents
            for rt in source_db.query(ReportTemplate).all():
                data = {col.name: getattr(rt, col.name) for col in ReportTemplate.__table__.columns if col.name != 'id'}
                data['user_id'] = user_map.get(rt.user_id)
                new_rt = ReportTemplate(**data)
                target_db.add(new_rt)
                target_db.flush()
                template_map[rt.id] = new_rt.id

            for ar in source_db.query(ApprovalRule).all():
                data = {col.name: getattr(ar, col.name) for col in ApprovalRule.__table__.columns if col.name != 'id'}
                data['created_by'] = user_map.get(ar.created_by)
                new_ar = ApprovalRule(**data)
                target_db.add(new_ar)
                target_db.flush()
                rule_map[ar.id] = new_ar.id

            for bpj in source_db.query(BatchProcessingJob).all():
                data = {col.name: getattr(bpj, col.name) for col in BatchProcessingJob.__table__.columns if col.name != 'id'}
                data['user_id'] = user_map.get(bpj.user_id)
                new_bpj = BatchProcessingJob(**data)
                target_db.add(new_bpj)
                target_db.flush()
                job_map[bpj.id] = new_bpj.id

            # 12. Remaining models with various FKs
            # (Model, attribute_mapping_dict)
            simple_models = [
                (Settings, {}),
                (DiscountRule, {}),
                (SupportedCurrency, {}),
                (CurrencyRate, {}),
                (InvoiceItem, {'invoice_id': invoice_map}),
                (InvoiceHistory, {'invoice_id': invoice_map, 'user_id': user_map}),
                (AIConfig, {}),
                (AuditLog, {'user_id': user_map}),
                (AIChatHistory, {'user_id': user_map}),
                (ReportHistory, {'generated_by': user_map, 'template_id': template_map}),
                (StockMovement, {'user_id': user_map, 'item_id': item_map, 'warehouse_id': warehouse_map}),
                (BankStatementAttachment, {'statement_id': statement_map}),
                (ScheduledReport, {'template_id': template_map}),
                (InventoryLevel, {'item_id': item_map, 'warehouse_id': warehouse_map}),
                (ItemAttachment, {'item_id': item_map}),
                (InvoiceAttachment, {'invoice_id': invoice_map}),
                (InvoiceProcessingTask, {'invoice_id': invoice_map}),
                (ExpenseApproval, {'expense_id': expense_map, 'approver_id': user_map}),
                (InvoiceApproval, {'invoice_id': invoice_map, 'approver_id': user_map}),
                (ApprovalDelegate, {'delegate_id': user_map, 'original_approver_id': user_map}),
                (Reminder, {'user_id': user_map}),
                (ReminderNotification, {}),
                (CloudStorageConfiguration, {}),
                (StorageOperationLog, {}),
                (BatchFileProcessing, {'job_id': job_map}),
                (ExportDestinationConfig, {}),
                (Anomaly, {})
            ]

            for model, mapping in simple_models:
                for obj in source_db.query(model).all():
                    data = {col.name: getattr(obj, col.name) for col in model.__table__.columns if col.name != 'id'}
                    for field, map_dict in mapping.items():
                        if field in data:
                            data[field] = map_dict.get(data[field])
                    target_db.add(model(**data))

            target_db.commit()

            # 11. Final Step: Sync Postgres sequences
            from core.services.tenant_database_manager import tenant_db_manager
            tenant_db_manager.sync_postgres_sequences(target_db)

        except Exception as e:
            target_db.rollback()
            logger.error(f"Failed to import synchronization data: {e}")
            raise e

    @staticmethod
    def _align_master_users(tenant_db: Session, tenant_id: int):
        """
        Ensures all users in the tenant database exist in the master database 
        and have appropriate permissions to log in.
        """
        from core.models.database import SessionLocal as MasterSessionLocal
        from core.models.models import MasterUser, user_tenant_association
        from core.models.models_per_tenant import User as TenantUser

        master_db = MasterSessionLocal()
        try:
            tenant_users = tenant_db.query(TenantUser).all()
            for tu in tenant_users:
                # Check if user exists in master
                mu = master_db.query(MasterUser).filter(MasterUser.email == tu.email).first()

                if not mu:
                    # Create missing master user
                    logger.info(f"Sync: Creating missing MasterUser for {tu.email}")
                    mu = MasterUser(
                        email=tu.email,
                        hashed_password=tu.hashed_password,
                        tenant_id=tenant_id,
                        role=tu.role,
                        is_active=tu.is_active,
                        is_superuser=tu.is_superuser,
                        is_verified=tu.is_verified,
                        first_name=tu.first_name,
                        last_name=tu.last_name,
                        theme=tu.theme
                    )
                    master_db.add(mu)
                    master_db.flush() # Get ID
                else:
                    # User exists, ensure they have membership record for this tenant
                    # and update password if it changed (mirror behavior)
                    mu.hashed_password = tu.hashed_password
                    mu.role = tu.role
                    mu.is_active = tu.is_active

                # Ensure membership association exists
                membership = master_db.execute(
                    sqlalchemy.text("SELECT 1 FROM user_tenant_memberships WHERE user_id = :u_id AND tenant_id = :t_id"),
                    {"u_id": mu.id, "t_id": tenant_id}
                ).fetchone()

                if not membership:
                    logger.info(f"Sync: Adding tenant membership for {tu.email} to tenant {tenant_id}")
                    master_db.execute(
                        user_tenant_association.insert().values(
                            user_id=mu.id,
                            tenant_id=tenant_id,
                            role=tu.role,
                            is_active=tu.is_active
                        )
                    )

            master_db.commit()
            logger.info(f"Successfully aligned {len(tenant_users)} master users for tenant {tenant_id}")
        except Exception as e:
            master_db.rollback()
            logger.error(f"Failed to align master users: {e}")
            # We don't raise here to avoid failing the whole sync just because of auth mirroring,
            # though it's important. Actually, let's keep it failing for now to be safe.
            raise e
        finally:
            master_db.close()
