#!/usr/bin/env python3
"""
Enable Batch Processing Feature

This script enables batch processing for your installation.
It can either:
1. Start a trial (enables all features)
2. Add batch_processing to your licensed features
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager


def get_master_db_session():
    """Get database session for master database."""
    db_host = os.getenv('POSTGRES_HOST', 'postgres')
    db_port = os.getenv('POSTGRES_PORT', '5432')
    db_name = os.getenv('POSTGRES_DB', 'invoice_app')
    db_user = os.getenv('POSTGRES_USER', 'postgres')
    db_password = os.getenv('POSTGRES_PASSWORD', 'password')
    
    db_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def get_tenant_db_session(tenant_id: int):
    """Get database session for tenant database."""
    SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
    return SessionLocal_tenant()


def enable_batch_processing_via_trial(tenant_id: int = 1):
    """Enable batch processing by starting a trial."""
    print(f"\n🚀 Starting trial to enable batch processing...")
    
    db = get_tenant_db_session(tenant_id)
    
    try:
        from core.services.license_service import LicenseService
        license_service = LicenseService(db)
        
        # Start trial
        result = license_service.start_trial(user_id=1)
        
        if result.get("success"):
            print(f"✅ Trial started successfully!")
            print(f"   Message: {result.get('message')}")
            
            # Check if batch processing is now enabled
            has_batch = license_service.has_feature("batch_processing")
            print(f"\n📋 Batch Processing Feature:")
            print(f"   Enabled: {'✅ Yes' if has_batch else '❌ No'}")
            
            return True
        else:
            print(f"❌ Failed to start trial: {result.get('message')}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def enable_batch_processing_via_license(tenant_id: int = 1):
    """Enable batch processing by adding it to licensed features."""
    print(f"\n🔧 Adding batch_processing to licensed features...")
    
    db = get_tenant_db_session(tenant_id)
    
    try:
        from core.models.models_per_tenant import InstallationInfo
        
        # Get installation info
        installation = db.query(InstallationInfo).filter(
            InstallationInfo.tenant_id == tenant_id
        ).first()
        
        if not installation:
            print(f"❌ Installation info not found for tenant {tenant_id}")
            return False
        
        # Get current licensed features
        current_features = installation.licensed_features or []
        print(f"   Current features: {current_features}")
        
        # Add batch_processing if not already present
        if "batch_processing" not in current_features:
            current_features.append("batch_processing")
            installation.licensed_features = current_features
            db.commit()
            print(f"   ✅ Added batch_processing to licensed features")
        else:
            print(f"   ℹ️  batch_processing already in licensed features")
        
        # Verify
        from core.services.license_service import LicenseService
        license_service = LicenseService(db)
        has_batch = license_service.has_feature("batch_processing")
        print(f"\n📋 Batch Processing Feature:")
        print(f"   Enabled: {'✅ Yes' if has_batch else '❌ No'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Enable batch processing feature'
    )
    
    parser.add_argument(
        '--tenant-id',
        type=int,
        default=1,
        help='Tenant ID (default: 1)'
    )
    
    parser.add_argument(
        '--method',
        choices=['trial', 'license'],
        default='trial',
        help='Method to enable batch processing (default: trial)'
    )
    
    args = parser.parse_args()
    
    if args.method == 'trial':
        success = enable_batch_processing_via_trial(args.tenant_id)
    else:
        success = enable_batch_processing_via_license(args.tenant_id)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
