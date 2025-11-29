#!/usr/bin/env python3
"""
Fix script to ensure tenant_keys table exists and is properly initialized.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import engine, Base, get_master_db
from core.models.models import TenantKey, Tenant
from core.services.key_management_service import KeyManagementService
from sqlalchemy import inspect, text
import traceback


def fix_tenant_keys_table():
    """Ensure tenant_keys table exists and all tenants have keys."""
    
    print(f"\n{'='*60}")
    print(f"🔧 Fixing Tenant Keys Table")
    print(f"{'='*60}\n")
    
    # Step 1: Check if table exists
    print("📋 Step 1: Checking if tenant_keys table exists")
    print("-" * 60)
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if "tenant_keys" in tables:
        print(f"✅ tenant_keys table exists")
    else:
        print(f"❌ tenant_keys table does NOT exist")
        print(f"🔨 Creating tenant_keys table...")
        try:
            # Create the table
            Base.metadata.create_all(bind=engine, tables=[TenantKey.__table__])
            print(f"✅ tenant_keys table created successfully")
        except Exception as e:
            print(f"❌ Failed to create tenant_keys table: {e}")
            traceback.print_exc()
            return False
    
    # Step 2: Check existing keys
    print(f"\n📋 Step 2: Checking existing tenant keys")
    print("-" * 60)
    
    db = next(get_master_db())
    try:
        existing_keys = db.query(TenantKey).all()
        print(f"Found {len(existing_keys)} existing tenant keys:")
        for key in existing_keys:
            print(f"   - Tenant {key.tenant_id}: {key.key_id} (active: {key.is_active})")
        
        # Step 3: Get all tenants
        print(f"\n📋 Step 3: Checking all tenants")
        print("-" * 60)
        
        tenants = db.query(Tenant).all()
        print(f"Found {len(tenants)} tenants")
        
        # Step 4: Generate keys for tenants without keys
        print(f"\n📋 Step 4: Generating missing keys")
        print("-" * 60)
        
        key_service = KeyManagementService()
        existing_tenant_ids = {key.tenant_id for key in existing_keys}
        
        for tenant in tenants:
            if tenant.id not in existing_tenant_ids:
                print(f"🔑 Generating key for tenant {tenant.id}...")
                try:
                    key_service.generate_tenant_key(tenant.id)
                    print(f"✅ Generated key for tenant {tenant.id}")
                except Exception as e:
                    print(f"❌ Failed to generate key for tenant {tenant.id}: {e}")
                    traceback.print_exc()
            else:
                print(f"✅ Tenant {tenant.id} already has a key")
        
        # Step 5: Verify all keys can be retrieved
        print(f"\n📋 Step 5: Verifying key retrieval")
        print("-" * 60)
        
        for tenant in tenants:
            try:
                key_material = key_service.retrieve_tenant_key(tenant.id)
                print(f"✅ Successfully retrieved key for tenant {tenant.id}")
            except Exception as e:
                print(f"❌ Failed to retrieve key for tenant {tenant.id}: {e}")
        
        print(f"\n{'='*60}")
        print(f"✅ Tenant Keys Table Fix Complete")
        print(f"{'='*60}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during fix: {e}")
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = fix_tenant_keys_table()
    sys.exit(0 if success else 1)
