#!/usr/bin/env python3
"""
Migration script to make client email unique and required
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from services.tenant_database_manager import tenant_db_manager
from models.database import get_master_db
from models.models import Tenant

def migrate_tenant_database(tenant_id: int, tenant_name: str):
    """Migrate a single tenant database"""
    print(f"Migrating tenant {tenant_id} ({tenant_name})...")
    
    try:
        # Get tenant database session
        tenant_session_factory = tenant_db_manager.get_tenant_session(tenant_id)
        # Create a session to get the engine
        with tenant_session_factory() as session:
            engine = session.bind
            
            with engine.connect() as conn:
                # Start transaction
                trans = conn.begin()
                
                try:
                    # 1. Update null emails to a default value
                    result = conn.execute(text("""
                        UPDATE clients 
                        SET email = CONCAT('client_', id, '@example.com')
                        WHERE email IS NULL OR email = ''
                    """))
                    print(f"  Updated {result.rowcount} clients with null/empty emails")
                    
                    # 2. Handle duplicate emails by appending a number
                    conn.execute(text("""
                        UPDATE clients 
                        SET email = email || '_' || id
                        WHERE id IN (
                            SELECT id FROM (
                                SELECT id, email, 
                                       ROW_NUMBER() OVER (PARTITION BY email ORDER BY id) as rn
                                FROM clients
                            ) t WHERE rn > 1
                        )
                    """))
                    print("  Fixed duplicate emails")
                    
                    # 3. Make email NOT NULL
                    conn.execute(text("ALTER TABLE clients ALTER COLUMN email SET NOT NULL"))
                    print("  Set email column to NOT NULL")
                    
                    # 4. Add unique constraint
                    conn.execute(text("ALTER TABLE clients ADD CONSTRAINT clients_email_unique UNIQUE (email)"))
                    print("  Added unique constraint to email")
                    
                    # Commit transaction
                    trans.commit()
                    print(f"  ✅ Successfully migrated tenant {tenant_id}")
                    
                except Exception as e:
                    trans.rollback()
                    print(f"  ❌ Error migrating tenant {tenant_id}: {e}")
                    return False
                
    except Exception as e:
        print(f"  ❌ Failed to connect to tenant {tenant_id} database: {e}")
        return False
    
    return True

def main():
    """Main migration function"""
    print("🔄 Starting client email unique migration...")
    
    # Get all tenants from master database
    master_db = next(get_master_db())
    try:
        tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        print(f"Found {len(tenants)} active tenants")
        
        success_count = 0
        for tenant in tenants:
            if migrate_tenant_database(tenant.id, tenant.name):
                success_count += 1
        
        print(f"\n✅ Migration completed: {success_count}/{len(tenants)} tenants migrated successfully")
        
    finally:
        master_db.close()

if __name__ == "__main__":
    main()