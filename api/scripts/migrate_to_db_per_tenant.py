#!/usr/bin/env python3
"""
Migration script to transition from single database with tenant isolation
to database-per-tenant architecture.

This script:
1. Creates separate databases for each tenant
2. Migrates data from master database to tenant-specific databases
3. Preserves all existing data and relationships
4. Provides rollback capability
"""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy import create_engine, text, MetaData, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import SQLALCHEMY_DATABASE_URL, engine as master_engine
from models.models import Base, Tenant, User, Client, Invoice, Payment, Settings, ClientNote, InvoiceItem, InvoiceHistory, DiscountRule, CurrencyRate, AIConfig
from services.tenant_database_manager import TenantDatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TenantMigrationManager:
    """Manages the migration from single database to database-per-tenant"""
    
    def __init__(self):
        self.master_engine = master_engine
        self.master_session = sessionmaker(bind=self.master_engine)
        self.tenant_db_manager = TenantDatabaseManager()
        self.migration_log = []
        
    def run_migration(self, dry_run: bool = False):
        """Run the complete migration process"""
        try:
            logger.info("🚀 Starting migration to database-per-tenant architecture")
            
            if dry_run:
                logger.info("🔍 Running in DRY RUN mode - no actual changes will be made")
            
            # Step 1: Validate current setup
            logger.info("📋 Step 1: Validating current setup...")
            self._validate_current_setup()
            
            # Step 2: Get all tenants from master database
            logger.info("🏢 Step 2: Getting tenant information...")
            tenants = self._get_all_tenants()
            logger.info(f"Found {len(tenants)} tenants to migrate")
            
            # Step 3: Create tenant databases
            logger.info("🗄️ Step 3: Creating tenant databases...")
            for tenant in tenants:
                self._create_tenant_database(tenant, dry_run)
            
            # Step 4: Migrate data for each tenant
            logger.info("📦 Step 4: Migrating data...")
            for tenant in tenants:
                self._migrate_tenant_data(tenant, dry_run)
            
            # Step 5: Verify migration
            logger.info("✅ Step 5: Verifying migration...")
            self._verify_migration(tenants)
            
            # Step 6: Create backup information
            logger.info("💾 Step 6: Creating migration backup info...")
            self._create_migration_backup_info(tenants)
            
            if not dry_run:
                logger.info("🎉 Migration completed successfully!")
                logger.info("⚠️  Remember to:")
                logger.info("   - Update your application to use the new middleware")
                logger.info("   - Update docker-compose.yml if needed")
                logger.info("   - Test the application thoroughly")
                logger.info("   - Keep the master database as backup until you're confident")
            else:
                logger.info("🔍 Dry run completed - no actual changes were made")
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise
    
    def _validate_current_setup(self):
        """Validate that the current setup is ready for migration"""
        db = self.master_session()
        try:
            # Check if we have tenants
            tenant_count = db.query(Tenant).count()
            if tenant_count == 0:
                raise ValueError("No tenants found in master database")
            
            # Check if all users have tenant_id
            users_without_tenant = db.query(User).filter(User.tenant_id.is_(None)).count()
            if users_without_tenant > 0:
                raise ValueError(f"Found {users_without_tenant} users without tenant_id")
            
            # Check if all tenant-related tables have tenant_id
            required_tables = ['clients', 'invoices', 'payments', 'settings', 'client_notes', 'discount_rules', 'currency_rates', 'ai_configs']
            inspector = inspect(self.master_engine)
            
            for table_name in required_tables:
                if inspector.has_table(table_name):
                    columns = [col['name'] for col in inspector.get_columns(table_name)]
                    if 'tenant_id' not in columns:
                        raise ValueError(f"Table {table_name} missing tenant_id column")
            
            logger.info("✅ Current setup validation passed")
            
        finally:
            db.close()
    
    def _get_all_tenants(self) -> List[Tenant]:
        """Get all tenants from the master database"""
        db = self.master_session()
        try:
            tenants = db.query(Tenant).all()
            return tenants
        finally:
            db.close()
    
    def _create_tenant_database(self, tenant: Tenant, dry_run: bool = False):
        """Create database for a specific tenant"""
        try:
            logger.info(f"📄 Creating database for tenant: {tenant.name} (ID: {tenant.id})")
            
            if not dry_run:
                success = self.tenant_db_manager.create_tenant_database(tenant.id, tenant.name)
                if not success:
                    raise Exception(f"Failed to create database for tenant {tenant.id}")
                    
                self.migration_log.append({
                    'action': 'create_database',
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'timestamp': datetime.now().isoformat()
                })
                
                logger.info(f"✅ Database created for tenant {tenant.name}")
            else:
                logger.info(f"🔍 [DRY RUN] Would create database for tenant {tenant.name}")
                
        except Exception as e:
            logger.error(f"❌ Failed to create database for tenant {tenant.name}: {e}")
            raise
    
    def _migrate_tenant_data(self, tenant: Tenant, dry_run: bool = False):
        """Migrate all data for a specific tenant"""
        logger.info(f"📦 Migrating data for tenant: {tenant.name} (ID: {tenant.id})")
        
        # Get master database session
        master_db = self.master_session()
        
        try:
            # Get tenant database session
            if not dry_run:
                TenantSession = self.tenant_db_manager.get_tenant_session(tenant.id)
                tenant_db = TenantSession()
            else:
                tenant_db = None
            
            try:
                # Migrate data in order of dependencies
                self._migrate_users(tenant, master_db, tenant_db, dry_run)
                self._migrate_clients(tenant, master_db, tenant_db, dry_run)
                self._migrate_invoices(tenant, master_db, tenant_db, dry_run)
                self._migrate_invoice_items(tenant, master_db, tenant_db, dry_run)
                self._migrate_payments(tenant, master_db, tenant_db, dry_run)
                self._migrate_settings(tenant, master_db, tenant_db, dry_run)
                self._migrate_client_notes(tenant, master_db, tenant_db, dry_run)
                self._migrate_discount_rules(tenant, master_db, tenant_db, dry_run)
                self._migrate_currency_rates(tenant, master_db, tenant_db, dry_run)
                self._migrate_ai_configs(tenant, master_db, tenant_db, dry_run)
                self._migrate_invoice_history(tenant, master_db, tenant_db, dry_run)
                
                if not dry_run:
                    tenant_db.commit()
                    logger.info(f"✅ Data migration completed for tenant {tenant.name}")
                else:
                    logger.info(f"🔍 [DRY RUN] Would migrate data for tenant {tenant.name}")
                    
            finally:
                if tenant_db:
                    tenant_db.close()
                    
        finally:
            master_db.close()
    
    def _migrate_users(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate users for a tenant"""
        users = master_db.query(User).filter(User.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(users)} users")
        
        if not dry_run:
            for user in users:
                # Create new user without tenant_id (it's not needed in tenant database)
                new_user = User(
                    id=user.id,
                    email=user.email,
                    hashed_password=user.hashed_password,
                    is_active=user.is_active,
                    is_superuser=user.is_superuser,
                    is_verified=user.is_verified,
                    role=user.role,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    google_id=user.google_id,
                    created_at=user.created_at,
                    updated_at=user.updated_at
                )
                tenant_db.add(new_user)
    
    def _migrate_clients(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate clients for a tenant"""
        clients = master_db.query(Client).filter(Client.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(clients)} clients")
        
        if not dry_run:
            for client in clients:
                new_client = Client(
                    id=client.id,
                    name=client.name,
                    email=client.email,
                    phone=client.phone,
                    address=client.address,
                    balance=client.balance,
                    paid_amount=client.paid_amount,
                    preferred_currency=client.preferred_currency,
                    created_at=client.created_at,
                    updated_at=client.updated_at
                )
                tenant_db.add(new_client)
    
    def _migrate_invoices(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate invoices for a tenant"""
        invoices = master_db.query(Invoice).filter(Invoice.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(invoices)} invoices")
        
        if not dry_run:
            for invoice in invoices:
                new_invoice = Invoice(
                    id=invoice.id,
                    number=invoice.number,
                    amount=invoice.amount,
                    currency=invoice.currency,
                    due_date=invoice.due_date,
                    status=invoice.status,
                    notes=invoice.notes,
                    client_id=invoice.client_id,
                    is_recurring=invoice.is_recurring,
                    recurring_frequency=invoice.recurring_frequency,
                    discount_type=invoice.discount_type,
                    discount_value=invoice.discount_value,
                    subtotal=invoice.subtotal,
                    created_at=invoice.created_at,
                    updated_at=invoice.updated_at
                )
                tenant_db.add(new_invoice)
    
    def _migrate_invoice_items(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate invoice items for a tenant"""
        # Get invoice items through invoices
        invoice_items = master_db.query(InvoiceItem).join(Invoice).filter(Invoice.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(invoice_items)} invoice items")
        
        if not dry_run:
            for item in invoice_items:
                new_item = InvoiceItem(
                    id=item.id,
                    invoice_id=item.invoice_id,
                    description=item.description,
                    quantity=item.quantity,
                    price=item.price,
                    amount=item.amount,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                tenant_db.add(new_item)
    
    def _migrate_payments(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate payments for a tenant"""
        payments = master_db.query(Payment).filter(Payment.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(payments)} payments")
        
        if not dry_run:
            for payment in payments:
                new_payment = Payment(
                    id=payment.id,
                    invoice_id=payment.invoice_id,
                    amount=payment.amount,
                    currency=payment.currency,
                    payment_date=payment.payment_date,
                    payment_method=payment.payment_method,
                    reference_number=payment.reference_number,
                    notes=payment.notes,
                    created_at=payment.created_at,
                    updated_at=payment.updated_at
                )
                tenant_db.add(new_payment)
    
    def _migrate_settings(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate settings for a tenant"""
        settings = master_db.query(Settings).filter(Settings.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(settings)} settings")
        
        if not dry_run:
            for setting in settings:
                new_setting = Settings(
                    id=setting.id,
                    key=setting.key,
                    value=setting.value,
                    created_at=setting.created_at,
                    updated_at=setting.updated_at
                )
                tenant_db.add(new_setting)
    
    def _migrate_client_notes(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate client notes for a tenant"""
        notes = master_db.query(ClientNote).filter(ClientNote.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(notes)} client notes")
        
        if not dry_run:
            for note in notes:
                new_note = ClientNote(
                    id=note.id,
                    note=note.note,
                    client_id=note.client_id,
                    user_id=note.user_id,
                    created_at=note.created_at,
                    updated_at=note.updated_at
                )
                tenant_db.add(new_note)
    
    def _migrate_discount_rules(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate discount rules for a tenant"""
        rules = master_db.query(DiscountRule).filter(DiscountRule.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(rules)} discount rules")
        
        if not dry_run:
            for rule in rules:
                new_rule = DiscountRule(
                    id=rule.id,
                    name=rule.name,
                    min_amount=rule.min_amount,
                    discount_type=rule.discount_type,
                    discount_value=rule.discount_value,
                    currency=rule.currency,
                    is_active=rule.is_active,
                    priority=rule.priority,
                    created_at=rule.created_at,
                    updated_at=rule.updated_at
                )
                tenant_db.add(new_rule)
    
    def _migrate_currency_rates(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate currency rates for a tenant"""
        rates = master_db.query(CurrencyRate).filter(CurrencyRate.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(rates)} currency rates")
        
        if not dry_run:
            for rate in rates:
                new_rate = CurrencyRate(
                    id=rate.id,
                    from_currency=rate.from_currency,
                    to_currency=rate.to_currency,
                    rate=rate.rate,
                    effective_date=rate.effective_date,
                    created_at=rate.created_at,
                    updated_at=rate.updated_at
                )
                tenant_db.add(new_rate)
    
    def _migrate_ai_configs(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate AI configurations for a tenant"""
        configs = master_db.query(AIConfig).filter(AIConfig.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(configs)} AI configurations")
        
        if not dry_run:
            for config in configs:
                new_config = AIConfig(
                    id=config.id,
                    provider_name=config.provider_name,
                    provider_url=config.provider_url,
                    api_key=config.api_key,
                    model_name=config.model_name,
                    is_active=config.is_active,
                    is_default=config.is_default,
                    created_at=config.created_at,
                    updated_at=config.updated_at
                )
                tenant_db.add(new_config)
    
    def _migrate_invoice_history(self, tenant: Tenant, master_db, tenant_db, dry_run: bool):
        """Migrate invoice history for a tenant"""
        history = master_db.query(InvoiceHistory).filter(InvoiceHistory.tenant_id == tenant.id).all()
        logger.info(f"   📋 Migrating {len(history)} invoice history records")
        
        if not dry_run:
            for record in history:
                new_record = InvoiceHistory(
                    id=record.id,
                    invoice_id=record.invoice_id,
                    user_id=record.user_id,
                    action=record.action,
                    details=record.details,
                    previous_values=record.previous_values,
                    current_values=record.current_values,
                    created_at=record.created_at
                )
                tenant_db.add(new_record)
    
    def _verify_migration(self, tenants: List[Tenant]):
        """Verify that migration was successful"""
        logger.info("🔍 Verifying migration...")
        
        for tenant in tenants:
            try:
                # Get counts from master database
                master_db = self.master_session()
                master_counts = {}
                
                try:
                    master_counts['users'] = master_db.query(User).filter(User.tenant_id == tenant.id).count()
                    master_counts['clients'] = master_db.query(Client).filter(Client.tenant_id == tenant.id).count()
                    master_counts['invoices'] = master_db.query(Invoice).filter(Invoice.tenant_id == tenant.id).count()
                    master_counts['payments'] = master_db.query(Payment).filter(Payment.tenant_id == tenant.id).count()
                finally:
                    master_db.close()
                
                # Get counts from tenant database
                TenantSession = self.tenant_db_manager.get_tenant_session(tenant.id)
                tenant_db = TenantSession()
                tenant_counts = {}
                
                try:
                    tenant_counts['users'] = tenant_db.query(User).count()
                    tenant_counts['clients'] = tenant_db.query(Client).count()
                    tenant_counts['invoices'] = tenant_db.query(Invoice).count()
                    tenant_counts['payments'] = tenant_db.query(Payment).count()
                finally:
                    tenant_db.close()
                
                # Compare counts
                for table, master_count in master_counts.items():
                    tenant_count = tenant_counts.get(table, 0)
                    if master_count != tenant_count:
                        raise ValueError(f"Count mismatch for {table} in tenant {tenant.name}: master={master_count}, tenant={tenant_count}")
                
                logger.info(f"✅ Verification passed for tenant {tenant.name}: {master_counts}")
                
            except Exception as e:
                logger.error(f"❌ Verification failed for tenant {tenant.name}: {e}")
                raise
    
    def _create_migration_backup_info(self, tenants: List[Tenant]):
        """Create backup information for potential rollback"""
        backup_info = {
            'migration_date': datetime.now().isoformat(),
            'tenants_migrated': [
                {
                    'id': tenant.id,
                    'name': tenant.name,
                    'database_name': f'tenant_{tenant.id}'
                }
                for tenant in tenants
            ],
            'master_database_url': SQLALCHEMY_DATABASE_URL,
            'migration_log': self.migration_log
        }
        
        backup_file = f'migration_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(backup_file, 'w') as f:
            json.dump(backup_info, f, indent=2)
        
        logger.info(f"💾 Migration backup info saved to: {backup_file}")

def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate to database-per-tenant architecture')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (no actual changes)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        migration_manager = TenantMigrationManager()
        migration_manager.run_migration(dry_run=args.dry_run)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 