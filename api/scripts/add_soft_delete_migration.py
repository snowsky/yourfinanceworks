#!/usr/bin/env python3

import sys
sys.path.append('./api')

from core.models.database import SessionLocal
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_soft_delete_columns():
    """Add soft delete columns to Invoice tables in all tenant databases"""
    print("🔄 Adding soft delete columns to Invoice tables...")
    
    # Get master database session
    master_db = SessionLocal()
    
    try:
        # Get all tenants
        tenants = master_db.query(Tenant).all()
        print(f"📋 Found {len(tenants)} tenants")
        
        for tenant in tenants:
            print(f"\n🔍 Processing tenant '{tenant.name}' (ID: {tenant.id})...")
            
            try:
                # Get tenant database session
                tenant_session_factory = tenant_db_manager.get_tenant_session(tenant.id)
                if not tenant_session_factory:
                    print(f"  ❌ Could not get tenant database session for tenant {tenant.id}")
                    continue
                
                tenant_db = tenant_session_factory()
                
                # Check if columns already exist
                check_query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'invoices' 
                AND column_name IN ('is_deleted', 'deleted_at', 'deleted_by')
                """
                
                existing_columns = tenant_db.execute(text(check_query)).fetchall()
                existing_column_names = [row[0] for row in existing_columns]
                
                print(f"  📋 Existing soft delete columns: {existing_column_names}")
                
                # Add missing columns
                columns_to_add = []
                
                if 'is_deleted' not in existing_column_names:
                    columns_to_add.append("ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE")
                
                if 'deleted_at' not in existing_column_names:
                    columns_to_add.append("ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE")
                
                if 'deleted_by' not in existing_column_names:
                    columns_to_add.append("ADD COLUMN deleted_by INTEGER REFERENCES users(id)")
                
                if columns_to_add:
                    # Execute ALTER TABLE statements
                    for column_def in columns_to_add:
                        alter_query = f"ALTER TABLE invoices {column_def}"
                        print(f"  🔄 Executing: {alter_query}")
                        tenant_db.execute(text(alter_query))
                    
                    tenant_db.commit()
                    print(f"  ✅ Added {len(columns_to_add)} columns to tenant {tenant.name}")
                else:
                    print(f"  ✅ All soft delete columns already exist for tenant {tenant.name}")
                
                tenant_db.close()
                
            except Exception as e:
                print(f"  ❌ Error processing tenant {tenant.id}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n🎉 Migration completed for all tenants!")
        
    finally:
        master_db.close()

if __name__ == "__main__":
    add_soft_delete_columns() 