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
    BankStatement, BankStatementTransaction, AuditLog, AIChatHistory
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
    def package_data(db: Session, tenant_id: int, include_attachments: bool = True) -> bytes:
        """
        Packages database records and attachment files into a single ZIP file.
        Returns the ZIP file content as bytes.
        """
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
            # We use the existing import logic pattern
            from core.services.tenant_database_manager import tenant_db_manager
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db = SessionLocal_tenant()
            try:
                SyncService._import_from_sqlite(sqlite_file, db, tenant_id)
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
                AuditLog, AIChatHistory
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
            # This is a bit risky but requested. We try to be careful.
            models_to_clear = [
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

            # Users
            source_users = source_db.query(TenantUser).all()
            for u in source_users:
                if u.is_superuser: continue
                # check if exists by email
                existing = target_db.query(TenantUser).filter(TenantUser.email == u.email).first()
                if existing:
                    user_map[u.id] = existing.id
                else:
                    new_u = TenantUser(**{c.name: getattr(u, c.name) for c in TenantUser.__table__.columns if c.name != 'id'})
                    target_db.add(new_u)
                    target_db.flush()
                    user_map[u.id] = new_u.id

            # Clients
            for c in source_db.query(Client).all():
                new_c = Client(**{col.name: getattr(c, col.name) for col in Client.__table__.columns if col.name != 'id'})
                target_db.add(new_c)
                target_db.flush()
                client_map[c.id] = new_c.id

            # Invoices
            for i in source_db.query(Invoice).all():
                data = {col.name: getattr(i, col.name) for col in Invoice.__table__.columns if col.name != 'id'}
                data['client_id'] = client_map.get(i.client_id)
                new_i = Invoice(**data)
                target_db.add(new_i)
                target_db.flush()
                invoice_map[i.id] = new_i.id

            # Payments
            for p in source_db.query(Payment).all():
                data = {col.name: getattr(p, col.name) for col in Payment.__table__.columns if col.name != 'id'}
                data['invoice_id'] = invoice_map.get(p.invoice_id)
                data['user_id'] = user_map.get(p.user_id) if hasattr(p, 'user_id') else None
                target_db.add(Payment(**data))

            # Expenses
            for e in source_db.query(Expense).all():
                data = {col.name: getattr(e, col.name) for col in Expense.__table__.columns if col.name != 'id'}
                data['user_id'] = user_map.get(e.user_id)
                data['invoice_id'] = invoice_map.get(e.invoice_id)
                new_e = Expense(**data)
                target_db.add(new_e)
                target_db.flush()
                expense_map[e.id] = new_e.id

            # Expense Attachments
            for ea in source_db.query(ExpenseAttachment).all():
                data = {col.name: getattr(ea, col.name) for col in ExpenseAttachment.__table__.columns if col.name != 'id'}
                data['expense_id'] = expense_map.get(ea.expense_id)
                target_db.add(ExpenseAttachment(**data))

            # Bank Statements
            for bs in source_db.query(BankStatement).all():
                data = {col.name: getattr(bs, col.name) for col in BankStatement.__table__.columns if col.name != 'id'}
                new_bs = BankStatement(**data)
                target_db.add(new_bs)
                target_db.flush()
                statement_map[bs.id] = new_bs.id

            # Bank Transactions
            for bt in source_db.query(BankStatementTransaction).all():
                data = {col.name: getattr(bt, col.name) for col in BankStatementTransaction.__table__.columns if col.name != 'id'}
                data['statement_id'] = statement_map.get(bt.statement_id)
                target_db.add(BankStatementTransaction(**data))

            # Remaining simple tables
            simple_models = [
                (Settings, {}),
                (DiscountRule, {}),
                (SupportedCurrency, {}),
                (CurrencyRate, {}),
                (InvoiceItem, {'invoice_id': invoice_map}),
                (InvoiceHistory, {'invoice_id': invoice_map, 'user_id': user_map}),
                (AIConfig, {}),
                (AuditLog, {}),
                (AIChatHistory, {'user_id': user_map})
            ]

            for model, mapping in simple_models:
                for obj in source_db.query(model).all():
                    data = {col.name: getattr(obj, col.name) for col in model.__table__.columns if col.name != 'id'}
                    for field, map_dict in mapping.items():
                        if field in data:
                            data[field] = map_dict.get(data[field])
                    target_db.add(model(**data))

            target_db.commit()

        except Exception as e:
            target_db.rollback()
            logger.error(f"Failed to import synchronization data: {e}")
            raise e
        finally:
            source_db.close()
