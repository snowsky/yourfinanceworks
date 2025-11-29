#!/usr/bin/env python3
"""
Create Export Destination for Batch Processing

This script creates an export destination configuration for batch processing.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.services.tenant_database_manager import tenant_db_manager


def get_tenant_db_session(tenant_id: int):
    """Get database session for tenant database."""
    SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
    return SessionLocal_tenant()


def create_export_destination(tenant_id: int = 1):
    """Create a default export destination."""
    print(f"\n📝 Creating export destination for tenant {tenant_id}...")
    
    db = get_tenant_db_session(tenant_id)
    
    try:
        from core.models.models_per_tenant import ExportDestinationConfig
        from datetime import datetime, timezone
        
        # Check if default destination already exists
        existing = db.query(ExportDestinationConfig).filter(
            ExportDestinationConfig.tenant_id == tenant_id,
            ExportDestinationConfig.is_default == True
        ).first()
        
        if existing:
            print(f"✅ Default export destination already exists:")
            print(f"   ID: {existing.id}")
            print(f"   Name: {existing.name}")
            print(f"   Type: {existing.destination_type}")
            return existing.id
        
        # Create new export destination
        destination = ExportDestinationConfig(
            tenant_id=tenant_id,
            name="Default Export",
            description="Default export destination for batch processing",
            destination_type="local",  # local, s3, azure, etc.
            is_active=True,
            is_default=True,
            config={
                "path": "/exports",
                "format": "csv"
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add(destination)
        db.commit()
        db.refresh(destination)
        
        print(f"✅ Export destination created successfully!")
        print(f"   ID: {destination.id}")
        print(f"   Name: {destination.name}")
        print(f"   Type: {destination.destination_type}")
        print(f"   Is Default: {destination.is_default}")
        
        return destination.id
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Create export destination for batch processing'
    )
    
    parser.add_argument(
        '--tenant-id',
        type=int,
        default=1,
        help='Tenant ID (default: 1)'
    )
    
    args = parser.parse_args()
    
    destination_id = create_export_destination(args.tenant_id)
    sys.exit(0 if destination_id else 1)


if __name__ == '__main__':
    main()
