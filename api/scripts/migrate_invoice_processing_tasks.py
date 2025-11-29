#!/usr/bin/env python3
"""
Migration script to add invoice_processing_tasks table to all tenant databases.
Run this after updating the models to support async invoice OCR processing.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.models.database import SessionLocal
from core.services.tenant_database_manager import tenant_db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run the migration on all tenant databases."""
    
    migration_sql = """
    -- Add invoice_processing_tasks table for async invoice OCR processing
    CREATE TABLE IF NOT EXISTS invoice_processing_tasks (
        id SERIAL PRIMARY KEY,
        task_id VARCHAR(255) UNIQUE NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        filename VARCHAR(255) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'queued',
        error_message TEXT,
        result_data JSONB,
        user_id INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        completed_at TIMESTAMP WITH TIME ZONE
    );

    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_invoice_processing_tasks_task_id ON invoice_processing_tasks(task_id);
    CREATE INDEX IF NOT EXISTS idx_invoice_processing_tasks_user_id ON invoice_processing_tasks(user_id);
    CREATE INDEX IF NOT EXISTS idx_invoice_processing_tasks_status ON invoice_processing_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_invoice_processing_tasks_created_at ON invoice_processing_tasks(created_at);
    """
    
    try:
        # Get all tenant IDs
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()
        logger.info(f"Found {len(tenant_ids)} tenants to migrate")
        
        success_count = 0
        error_count = 0
        
        for tenant_id in tenant_ids:
            try:
                logger.info(f"Migrating tenant {tenant_id}...")
                
                # Get tenant session
                SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
                db = SessionLocalTenant()
                
                try:
                    # Execute migration
                    db.execute(text(migration_sql))
                    db.commit()
                    logger.info(f"✅ Successfully migrated tenant {tenant_id}")
                    success_count += 1
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"❌ Failed to migrate tenant {tenant_id}: {e}")
                    error_count += 1
                    
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"❌ Failed to get session for tenant {tenant_id}: {e}")
                error_count += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Migration complete!")
        logger.info(f"  Success: {success_count} tenants")
        logger.info(f"  Errors:  {error_count} tenants")
        logger.info(f"{'='*60}\n")
        
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
