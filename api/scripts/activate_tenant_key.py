#!/usr/bin/env python3
"""
Activate a tenant's encryption key.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db
from core.models.models import TenantKey
import argparse


def activate_tenant_key(tenant_id: int):
    """Activate a tenant's encryption key."""
    
    print(f"\n{'='*60}")
    print(f"🔑 Activating Encryption Key for Tenant {tenant_id}")
    print(f"{'='*60}\n")
    
    db = next(get_master_db())
    try:
        # Find the tenant key
        tenant_key = db.query(TenantKey).filter(TenantKey.tenant_id == tenant_id).first()
        
        if not tenant_key:
            print(f"❌ No encryption key found for tenant {tenant_id}")
            return False
        
        print(f"📋 Current key status:")
        print(f"   Key ID: {tenant_key.key_id}")
        print(f"   Version: {tenant_key.version}")
        print(f"   Is Active: {tenant_key.is_active}")
        print(f"   Created: {tenant_key.created_at}")
        
        if tenant_key.is_active:
            print(f"\n✅ Key is already active")
            return True
        
        # Activate the key
        print(f"\n🔨 Activating key...")
        tenant_key.is_active = True
        db.commit()
        
        print(f"✅ Key activated successfully!")
        
        # Verify
        db.refresh(tenant_key)
        print(f"\n📋 Updated key status:")
        print(f"   Is Active: {tenant_key.is_active}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error activating key: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Activate a tenant's encryption key")
    parser.add_argument("--tenant-id", type=int, required=True, help="Tenant ID")
    
    args = parser.parse_args()
    
    success = activate_tenant_key(args.tenant_id)
    sys.exit(0 if success else 1)
