#!/usr/bin/env python3
"""
Script to fix installation records that have business usage type but no trial dates
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.models.models_per_tenant import InstallationInfo
from core.services.tenant_database_manager import tenant_db_manager
from core.models.database import get_master_db, set_tenant_context

def fix_installation_trial_dates():
    """Fix installation records with business usage but no trial dates"""
    
    print("=" * 70)
    print("Fixing Installation Trial Dates")
    print("=" * 70)
    print()
    
    # Get all tenants
    master_db = next(get_master_db())
    
    try:
        from core.models.models import Tenant
        tenants = master_db.query(Tenant).all()
        
        if not tenants:
            print("No tenants found")
            return
        
        print(f"Found {len(tenants)} tenant(s)")
        print()
        
        for tenant in tenants:
            print(f"Checking tenant {tenant.id}...")
            
            # Set tenant context
            set_tenant_context(tenant.id)
            
            # Get tenant database session
            SessionLocal = tenant_db_manager.get_tenant_session(tenant.id)
            db = SessionLocal()
            
            try:
                # Get installation record
                installation = db.query(InstallationInfo).first()
                
                if not installation:
                    print(f"  No installation record found for tenant {tenant.id}")
                    continue
                
                print(f"  Installation ID: {installation.installation_id}")
                print(f"  License Status: {installation.license_status}")
                print(f"  Usage Type: {installation.usage_type}")
                print(f"  Trial Start: {installation.trial_start_date}")
                print(f"  Trial End: {installation.trial_end_date}")
                
                # Check if needs fixing
                needs_fix = False
                
                # Fix 1: Business usage type but no trial dates
                if installation.usage_type == "business" and not installation.trial_start_date:
                    print(f"  ⚠️  Business usage but no trial dates - FIXING")
                    now = datetime.now(timezone.utc)
                    installation.trial_start_date = now
                    installation.trial_end_date = now + timedelta(days=30)
                    installation.license_status = "trial"
                    needs_fix = True
                
                # Fix 2: Trial status but no trial dates
                if installation.license_status == "trial" and not installation.trial_start_date:
                    print(f"  ⚠️  Trial status but no trial dates - FIXING")
                    now = datetime.now(timezone.utc)
                    installation.trial_start_date = now
                    installation.trial_end_date = now + timedelta(days=30)
                    needs_fix = True
                
                # Fix 3: Invalid status but has usage type
                if installation.license_status == "invalid" and installation.usage_type:
                    print(f"  ⚠️  Invalid status but has usage type - FIXING")
                    if installation.usage_type == "business":
                        now = datetime.now(timezone.utc)
                        installation.trial_start_date = now
                        installation.trial_end_date = now + timedelta(days=30)
                        installation.license_status = "trial"
                    elif installation.usage_type == "personal":
                        installation.license_status = "personal"
                    needs_fix = True
                
                if needs_fix:
                    db.commit()
                    db.refresh(installation)
                    print(f"  ✓ Fixed!")
                    print(f"    New Trial Start: {installation.trial_start_date}")
                    print(f"    New Trial End: {installation.trial_end_date}")
                    print(f"    New Status: {installation.license_status}")
                else:
                    print(f"  ✓ No fixes needed")
                
                print()
                
            finally:
                db.close()
        
        print("=" * 70)
        print("✓ All installations checked and fixed")
        print("=" * 70)
        
    finally:
        master_db.close()


if __name__ == '__main__':
    try:
        fix_installation_trial_dates()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
