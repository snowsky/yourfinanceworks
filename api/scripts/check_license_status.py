#!/usr/bin/env python3
"""
Check License Status

This script checks the current license status and enabled features.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.services.license_service import LicenseService


def get_tenant_db_session(tenant_id: int):
    """Get database session for tenant database."""
    from core.services.tenant_database_manager import tenant_db_manager
    SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
    return SessionLocal_tenant()


def check_license_status(tenant_id: int = 1):
    """Check license status for a tenant."""
    print(f"\n🔍 Checking license status for tenant {tenant_id}...")
    
    db = get_tenant_db_session(tenant_id)
    
    try:
        license_service = LicenseService(db)
        
        # Get license status
        license_status = license_service.get_license_status()
        print(f"\n📋 License Status:")
        print(f"   Status: {license_status.get('license_status')}")
        print(f"   Is Licensed: {license_status.get('is_licensed')}")
        print(f"   Is Personal: {license_status.get('is_personal')}")
        print(f"   Is Trial: {license_status.get('is_trial')}")
        
        # Get trial status
        trial_status = license_service.get_trial_status()
        print(f"\n📋 Trial Status:")
        print(f"   Is Trial: {trial_status.get('is_trial')}")
        print(f"   Trial Active: {trial_status.get('trial_active')}")
        print(f"   In Grace Period: {trial_status.get('in_grace_period')}")
        
        # Get enabled features
        enabled_features = license_service.get_enabled_features()
        print(f"\n📋 Enabled Features:")
        if "all" in enabled_features:
            print(f"   ✅ ALL FEATURES ENABLED (trial or grace period)")
        elif "core" in enabled_features:
            print(f"   ✅ Core features enabled")
            for feature in enabled_features:
                if feature != "core":
                    print(f"   ✅ {feature}")
        else:
            print(f"   ❌ No features enabled")
        
        # Check specific feature
        has_batch = license_service.has_feature("batch_processing")
        print(f"\n📋 Batch Processing Feature:")
        print(f"   Enabled: {'✅ Yes' if has_batch else '❌ No'}")
        
        # Get full status
        full_status = license_service.get_full_status()
        print(f"\n📋 Full Status:")
        import json
        print(json.dumps(full_status, indent=2, default=str))
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Check license status'
    )
    
    parser.add_argument(
        '--tenant-id',
        type=int,
        default=1,
        help='Tenant ID (default: 1)'
    )
    
    args = parser.parse_args()
    
    check_license_status(args.tenant_id)


if __name__ == '__main__':
    main()
