#!/usr/bin/env python3
"""
Migration script to move legacy attachment fields to modern attachment system.

Legacy system:
- Invoices: attachment_path, attachment_filename
- Expenses: receipt_path, receipt_filename
- Bank Statements: file_path (handled separately)

Modern system:
- ItemAttachment: for inventory items
- InvoiceAttachment: for invoices
- ExpenseAttachment: for expenses

This script migrates existing legacy attachments to the modern system.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from core.models.models_per_tenant import (
    Invoice, Expense, InvoiceAttachment, ExpenseAttachment,
    Base as TenantBase
)
from core.models.models import Base as MasterBase
from core.services.tenant_database_manager import TenantDatabaseManager
from core.services.attachment_service import AttachmentService
from commercial.cloud_storage.service import CloudStorageService
from core.services.file_storage_service import FileStorageService
# from core.utils.column_encryptor import decrypt_value  # Not needed for this migration
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LegacyAttachmentMigrator:
    """Handles migration of legacy attachment fields to modern attachment system."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_engine(db_url)
        self.tenant_manager = TenantDatabaseManager()
        self.attachment_service = None
        # Initialize services later when we have a database session
        self.cloud_storage_service = None
        self.file_storage_service = None

    def get_tenant_databases(self) -> List[str]:
        """Get all tenant database names."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT datname FROM pg_database WHERE datname LIKE 'tenant_%'"))
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to get tenant databases: {e}")
            return []

    def migrate_tenant_attachments(self, tenant_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Migrate legacy attachments for a specific tenant.

        Args:
            tenant_id: Tenant identifier (e.g., 'tenant_1')
            dry_run: If True, only simulate migration without making changes

        Returns:
            Migration statistics
        """
        logger.info(f"Starting migration for tenant {tenant_id} (dry_run={dry_run})")

        stats = {
            'tenant_id': tenant_id,
            'invoices_migrated': 0,
            'expenses_migrated': 0,
            'errors': [],
            'skipped': 0
        }

        try:
            # Get tenant database session factory
            tenant_session_factory = self.tenant_manager.get_tenant_session(tenant_id)
            if not tenant_session_factory:
                raise Exception(f"Could not get session factory for tenant {tenant_id}")

            # Create actual session
            tenant_session = tenant_session_factory()

            # Initialize services for this tenant
            self.attachment_service = AttachmentService(tenant_session)
            if not self.cloud_storage_service:
                self.cloud_storage_service = CloudStorageService(tenant_session)
            if not self.file_storage_service:
                self.file_storage_service = FileStorageService()

            # Migrate invoice attachments
            invoice_stats = self._migrate_invoice_attachments(tenant_session, tenant_id, dry_run)
            stats['invoices_migrated'] = invoice_stats['migrated']
            stats['errors'].extend(invoice_stats['errors'])

            # Migrate expense attachments
            expense_stats = self._migrate_expense_attachments(tenant_session, tenant_id, dry_run)
            stats['expenses_migrated'] = expense_stats['migrated']
            stats['errors'].extend(expense_stats['errors'])

            tenant_session.close()

        except Exception as e:
            logger.error(f"Failed to migrate tenant {tenant_id}: {e}")
            stats['errors'].append(str(e))

        logger.info(f"Completed migration for tenant {tenant_id}: {stats}")
        return stats

    def _migrate_invoice_attachments(self, session: Session, tenant_id: str, dry_run: bool) -> Dict[str, Any]:
        """Migrate legacy invoice attachments."""
        stats = {'migrated': 0, 'errors': []}

        try:
            # Find invoices with legacy attachments
            legacy_invoices = session.query(Invoice).filter(
                Invoice.attachment_path.isnot(None),
                Invoice.attachment_filename.isnot(None),
                Invoice.is_deleted == False
            ).all()

            logger.info(f"Found {len(legacy_invoices)} invoices with legacy attachments")

            for invoice in legacy_invoices:
                try:
                    # Check if modern attachment already exists
                    existing_attachment = session.query(InvoiceAttachment).filter(
                        InvoiceAttachment.invoice_id == invoice.id,
                        InvoiceAttachment.filename == invoice.attachment_filename,
                        InvoiceAttachment.is_active == True
                    ).first()

                    if existing_attachment:
                        logger.info(f"Invoice {invoice.id}: modern attachment already exists, skipping")
                        stats['skipped'] += 1
                        continue

                    # Create modern attachment record
                    attachment_data = {
                        'invoice_id': invoice.id,
                        'filename': invoice.attachment_filename,
                        'stored_filename': self._generate_stored_filename(invoice.attachment_filename),
                        'file_path': invoice.attachment_path,
                        'file_size': self._get_file_size(invoice.attachment_path),
                        'content_type': self._guess_content_type(invoice.attachment_filename),
                        'attachment_type': 'document',  # Default to document
                        'document_type': 'invoice_attachment',
                        'uploaded_by': 1,  # System user
                        'is_active': True
                    }

                    if not dry_run:
                        new_attachment = InvoiceAttachment(**attachment_data)
                        session.add(new_attachment)
                        session.commit()

                        # Clear legacy fields
                        invoice.attachment_path = None
                        invoice.attachment_filename = None
                        session.commit()

                        logger.info(f"Migrated invoice attachment: {invoice.id} -> {new_attachment.id}")

                    stats['migrated'] += 1

                except Exception as e:
                    logger.error(f"Failed to migrate invoice {invoice.id}: {e}")
                    stats['errors'].append(f"Invoice {invoice.id}: {str(e)}")
                    session.rollback()

        except Exception as e:
            logger.error(f"Failed to migrate invoice attachments: {e}")
            stats['errors'].append(str(e))

        return stats

    def _migrate_expense_attachments(self, session: Session, tenant_id: str, dry_run: bool) -> Dict[str, Any]:
        """Migrate legacy expense attachments."""
        stats = {'migrated': 0, 'errors': []}

        try:
            # Find expenses with legacy attachments
            legacy_expenses = session.query(Expense).filter(
                Expense.receipt_path.isnot(None),
                Expense.receipt_filename.isnot(None)
            ).all()

            logger.info(f"Found {len(legacy_expenses)} expenses with legacy attachments")

            for expense in legacy_expenses:
                try:
                    # Check if modern attachment already exists
                    existing_attachment = session.query(ExpenseAttachment).filter(
                        ExpenseAttachment.expense_id == expense.id,
                        ExpenseAttachment.filename == expense.receipt_filename,
                        ExpenseAttachment.uploaded_at.isnot(None)  # Basic check
                    ).first()

                    if existing_attachment:
                        logger.info(f"Expense {expense.id}: modern attachment already exists, skipping")
                        stats['skipped'] += 1
                        continue

                    # Create modern attachment record
                    attachment_data = {
                        'expense_id': expense.id,
                        'filename': expense.receipt_filename,
                        'content_type': self._guess_content_type(expense.receipt_filename),
                        'size_bytes': self._get_file_size(expense.receipt_path),
                        'file_path': expense.receipt_path,
                        'uploaded_by': expense.user_id or 1,
                        'uploaded_at': expense.created_at or datetime.now(timezone.utc)
                    }

                    if not dry_run:
                        new_attachment = ExpenseAttachment(**attachment_data)
                        session.add(new_attachment)
                        session.commit()

                        # Clear legacy fields
                        expense.receipt_path = None
                        expense.receipt_filename = None
                        session.commit()

                        logger.info(f"Migrated expense attachment: {expense.id} -> {new_attachment.id}")

                    stats['migrated'] += 1

                except Exception as e:
                    logger.error(f"Failed to migrate expense {expense.id}: {e}")
                    stats['errors'].append(f"Expense {expense.id}: {str(e)}")
                    session.rollback()

        except Exception as e:
            logger.error(f"Failed to migrate expense attachments: {e}")
            stats['errors'].append(str(e))

        return stats

    def _generate_stored_filename(self, original_filename: str) -> str:
        """Generate a stored filename with timestamp."""
        import uuid
        timestamp = int(datetime.now(timezone.utc).timestamp())
        return f"{uuid.uuid4()}_{timestamp}_{original_filename}"

    def _get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size if file exists."""
        if not file_path:
            return None

        try:
            # Handle both absolute paths and relative paths
            if file_path.startswith('/'):
                path = Path(file_path)
            else:
                # Assume it's relative to upload path
                path = Path(config.UPLOAD_PATH) / file_path

            if path.exists():
                return path.stat().st_size
        except Exception:
            pass
        return None

    def _guess_content_type(self, filename: str) -> Optional[str]:
        """Guess content type from filename."""
        if not filename:
            return None

        import mimetypes
        content_type, _ = mimetypes.guess_type(filename)
        return content_type

    def run_migration(self, dry_run: bool = True, tenant_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run migration for all tenants or filtered tenants.

        Args:
            dry_run: If True, only simulate migration
            tenant_filter: List of tenant IDs to migrate, None for all

        Returns:
            Overall migration statistics
        """
        logger.info(f"Starting legacy attachment migration (dry_run={dry_run})")

        overall_stats = {
            'total_tenants': 0,
            'tenants_processed': 0,
            'total_invoices_migrated': 0,
            'total_expenses_migrated': 0,
            'total_errors': 0,
            'tenant_stats': []
        }

        # Get tenant databases
        tenant_dbs = self.get_tenant_databases()
        if tenant_filter:
            tenant_dbs = [db for db in tenant_dbs if db in tenant_filter]

        overall_stats['total_tenants'] = len(tenant_dbs)

        for tenant_db in tenant_dbs:
            # Extract tenant ID from database name (e.g., 'tenant_1' -> '1')
            tenant_id = tenant_db.replace('tenant_', '')

            try:
                stats = self.migrate_tenant_attachments(tenant_id, dry_run)
                overall_stats['tenant_stats'].append(stats)
                overall_stats['tenants_processed'] += 1
                overall_stats['total_invoices_migrated'] += stats['invoices_migrated']
                overall_stats['total_expenses_migrated'] += stats['expenses_migrated']
                overall_stats['total_errors'] += len(stats['errors'])

            except Exception as e:
                logger.error(f"Failed to process tenant {tenant_db}: {e}")
                overall_stats['tenant_stats'].append({
                    'tenant_id': tenant_id,
                    'error': str(e)
                })

        logger.info(f"Migration completed: {overall_stats}")
        return overall_stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Migrate legacy attachments to modern system')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (no changes made)')
    parser.add_argument('--tenants', nargs='*', help='Specific tenant IDs to migrate (e.g., 1 2 3)')
    parser.add_argument('--db-url', help='Database URL (defaults to config.DB_URL)')

    args = parser.parse_args()

    # Get database URL
    db_url = args.db_url or config.DATABASE_URL
    if not db_url:
        logger.error("No database URL provided")
        sys.exit(1)

    # Initialize migrator
    migrator = LegacyAttachmentMigrator(db_url)

    # Convert tenant IDs to database names
    tenant_filter = None
    if args.tenants:
        tenant_filter = [f"tenant_{tid}" for tid in args.tenants]

    # Run migration
    try:
        stats = migrator.run_migration(dry_run=args.dry_run, tenant_filter=tenant_filter)

        print("\n=== Migration Summary ===")
        print(f"Tenants processed: {stats['tenants_processed']}/{stats['total_tenants']}")
        print(f"Invoices migrated: {stats['total_invoices_migrated']}")
        print(f"Expenses migrated: {stats['total_expenses_migrated']}")
        print(f"Total errors: {stats['total_errors']}")

        if args.dry_run:
            print("\nThis was a DRY RUN - no changes were made.")
            print("Run without --dry-run to perform actual migration.")

        if stats['total_errors'] > 0:
            print(f"\nErrors occurred: {stats['total_errors']}")
            for tenant_stat in stats['tenant_stats']:
                if 'errors' in tenant_stat and tenant_stat['errors']:
                    print(f"Tenant {tenant_stat['tenant_id']}: {len(tenant_stat['errors'])} errors")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()