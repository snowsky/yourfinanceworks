#!/usr/bin/env python3
""
Migration script to add tenant_id column to audit_logs table
""
import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine.url import make_url

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import SQLALCHEMY_DATABASE_URL, get_master_db
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager

def fix_audit_logs_schema():
  d tenant_id column to audit_logs table if it doesn't exist 
    # Fix master database
    print("Fixing master database...")
    master_engine = create_engine(SQLALCHEMY_DATABASE_URL)
    inspector = inspect(master_engine)
    
    if 'audit_logs' in inspector.get_table_names():
        columns = [col[0] for col in inspector.get_columns('audit_logs')]
        if 'tenant_id' not in columns:
            print("Adding tenant_id column to master audit_logs table...")
            with master_engine.connect() as conn:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN tenant_id INTEGER"))
                conn.execute(text("ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)"))
                conn.commit()
            print("✓ Added tenant_id column to master audit_logs table")
        else:
            print("✓ Master audit_logs table already has tenant_id column")
    else:
        print("Master audit_logs table doesn't exist, will be created on next init")
    
    # Fix tenant databases
    print("\nFixing tenant databases...")
    master_db = next(get_master_db())
    try:
        tenants = master_db.query(Tenant).all()
        for tenant in tenants:
            print(f"Checking tenant {tenant.id}...")
            
            # Get tenant database URL
            db_url_template = os.environ.get("TENANT_DB_URL_TEMPLATE", "postgresql://postgres:password@postgres-master:5432/tenant_{tenant_id}")
            tenant_db_url = db_url_template.format(tenant_id=tenant.id)
            
            try:
                tenant_engine = create_engine(tenant_db_url)
                inspector = inspect(tenant_engine)
                
                if 'audit_logs' in inspector.get_table_names():
                    columns = [col[0] for col in inspector.get_columns('audit_logs')]
                    if 'tenant_id' not in columns:                   print(f"  Adding tenant_id column to tenant {tenant.id} audit_logs table...")
                        with tenant_engine.connect() as conn:
                            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN tenant_id INTEGER"))
                            conn.execute(text("ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)"))
                            conn.commit()
                        print(f"  ✓ Added tenant_id column to tenant {tenant.id} audit_logs table")
                    else:
                        print(f"  ✓ Tenant {tenant.id} audit_logs table already has tenant_id column")              else:
                    print(f"  Tenant {tenant.id} audit_logs table doesn't exist, will be created on next init")
                    
            except Exception as e:
                print(f"  ✗ Error fixing tenant {tenant.id}: {str(e)}")
                
    finally:
        master_db.close()
    
    print("\nMigration completed!")
if __name__ == "__main__":
    fix_audit_logs_schema() 