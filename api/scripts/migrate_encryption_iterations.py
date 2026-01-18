
import os
import sys
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add the API directory to Python path
sys.path.insert(0, '/app')

from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from core.models.database import DATABASE_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IterationMigrator:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.key_management = KeyManagementService()
        self.encryption_service = EncryptionService(self.key_management)
        self.master_engine = create_engine(DATABASE_URL)
        
        self.stats = {
            'checked': 0,
            'upgraded': 0,
            'errors': 0,
            'skipped': 0
        }

    def get_tenants(self) -> List[int]:
        with self.master_engine.connect() as conn:
            res = conn.execute(text("SELECT id FROM tenants")).fetchall()
            return [r[0] for r in res]

    def migrate_tenant(self, tenant_id: int):
        logger.info(f"Starting migration for tenant {tenant_id}")
        tenant_db_url = f"postgresql://postgres:password@postgres-master:5432/tenant_{tenant_id}"
        engine = create_engine(tenant_db_url)
        
        # Define tables and their encrypted columns
        # We can also dynamically discover them, but let's use a known list first
        tables_config = [
            ('invoices', ['notes', 'custom_fields', 'attachment_filename', 'review_result']),
            ('expenses', ['vendor', 'notes', 'receipt_filename', 'inventory_items', 'consumption_items', 'analysis_result', 'review_result']),
            ('bank_statements', ['review_result']),
            ('users', ['email', 'first_name', 'last_name']),
            ('clients', ['name', 'email', 'phone', 'address', 'company']),
            ('client_notes', ['note']),
            ('ai_configs', ['provider_url', 'api_key']),
            ('audit_logs', ['user_email', 'ip_address', 'user_agent'])
        ]

        primary_iters = self.encryption_service.config.KEY_DERIVATION_ITERATIONS
        
        for table_name, columns in tables_config:
            try:
                with engine.connect() as conn:
                    # Check if table and columns exist
                    inspector = inspect(engine)
                    if table_name not in inspector.get_table_names():
                        continue
                    
                    table_columns = [col['name'] for col in inspector.get_columns(table_name)]
                    existing_columns = [col for col in columns if col in table_columns]
                    
                    if not existing_columns:
                        continue
                        
                    # Fetch records
                    query = text(f"SELECT id, {', '.join(existing_columns)} FROM {table_name}")
                    results = conn.execute(query).fetchall()
                    
                    for row in results:
                        record_id = row[0]
                        updates = {}
                        
                        for i, col_name in enumerate(existing_columns):
                            val = row[i+1]
                            if val and isinstance(val, str) and len(val) > 20:
                                self.stats['checked'] += 1
                                try:
                                    # Attempt decryption
                                    # If it uses fallback iters, decrypt_data will log it (or we can check it)
                                    # To be sure, we check if it decrypts with standard key
                                    primary_key = self.encryption_service.get_tenant_key(tenant_id, iterations=primary_iters)
                                    
                                    # Check if already using primary
                                    try:
                                        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                                        import base64
                                        combined = base64.b64decode(val.encode('ascii'))
                                        nonce = combined[:12]
                                        ciphertext = combined[12:]
                                        AESGCM(primary_key).decrypt(nonce, ciphertext, None)
                                        # Success with primary, no need to upgrade
                                        self.stats['skipped'] += 1
                                        continue
                                    except:
                                        # Tag verification failed for primary, try fallback via service
                                        decrypted = self.encryption_service.decrypt_data(val, tenant_id)
                                        # If we're here, it decrypted with a fallback!
                                        
                                        # Re-encrypt with primary iters (which service uses by default)
                                        new_val = self.encryption_service.encrypt_data(decrypted, tenant_id)
                                        updates[col_name] = new_val
                                except Exception as e:
                                    logger.error(f"Failed to process {table_name}.{col_name} ID={record_id} for tenant {tenant_id}: {e}")
                                    self.stats['errors'] += 1
                        
                        if updates:
                            if not self.dry_run:
                                update_expr = ", ".join([f"{c} = :{c}" for c in updates.keys()])
                                update_query = text(f"UPDATE {table_name} SET {update_expr} WHERE id = :record_id")
                                updates['record_id'] = record_id
                                conn.execute(update_query, updates)
                                conn.commit()
                                self.stats['upgraded'] += 1
                                logger.info(f"Upgraded {table_name} ID={record_id} for tenant {tenant_id}")
                            else:
                                self.stats['upgraded'] += 1
                                logger.info(f"DRY RUN: Would upgrade {table_name} ID={record_id} ({list(updates.keys())}) for tenant {tenant_id}")
            except Exception as table_err:
                logger.error(f"Error migrating table {table_name} for tenant {tenant_id}: {table_err}")

    def run(self):
        tenants = self.get_tenants()
        for t_id in tenants:
            self.migrate_tenant(t_id)
        
        logger.info(f"Migration Finished. Stats: {self.stats}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually execute the migration")
    args = parser.parse_args()
    
    migrator = IterationMigrator(dry_run=not args.execute)
    migrator.run()
