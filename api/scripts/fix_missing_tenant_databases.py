#!/usr/bin/env python3
"""
Script to fix missing tenant databases.
This script checks if all tenants in the master database have corresponding tenant databases,
and creates missing ones.
"""

import os
import sys
import logging
from datetime import datetime, timezone

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_and_fix_tenant_databases():
    """Check for missing tenant databases and create them"""
    master_db = next(get_master_db())
    
    try:
        print("🔍 Checking for missing tenant databases...")
        print("=" * 50)
        
        # Get all tenants from master database
        tenants = master_db.query(Tenant).all()
        print(f"Found {len(tenants)} tenants in master database")
        
        missing_databases = []
        existing_databases = []
        
        for tenant in tenants:
            print(f"\nChecking tenant {tenant.id}: {tenant.name}")
            
            try:
                # Try to connect to tenant database
                tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()
                
                # Test connection with a simple query
                tenant_session.execute(text("SELECT 1"))
                tenant_session.close()
                
                print(f"  ✅ Database exists: tenant_{tenant.id}")
                existing_databases.append(tenant)
                
            except Exception as e:
                print(f"  ❌ Database missing: tenant_{tenant.id} - {str(e)}")
                missing_databases.append(tenant)
        
        print(f"\n📊 Summary:")
        print(f"  Existing databases: {len(existing_databases)}")
        print(f"  Missing databases: {len(missing_databases)}")
        
        if missing_databases:
            print(f"\n🔧 Creating missing tenant databases:")
            print("-" * 30)
            
            for tenant in missing_databases:
                try:
                    print(f"Creating database for tenant {tenant.id}: {tenant.name}")
                    
                    success = tenant_db_manager.create_tenant_database(tenant.id, tenant.name)
                    
                    if success:
                        print(f"  ✅ Successfully created tenant_{tenant.id}")
                    else:
                        print(f"  ❌ Failed to create tenant_{tenant.id}")
                        
                except Exception as e:
                    print(f"  ❌ Error creating tenant_{tenant.id}: {str(e)}")
                    
        else:
            print("✅ All tenant databases exist - no action needed")
            
    except Exception as e:
        print(f"❌ Error checking tenant databases: {e}")
        logger.error(f"Error checking tenant databases: {e}")
    finally:
        master_db.close()

def list_tenant_databases():
    """List all tenant databases and their status"""
    master_db = next(get_master_db())
    
    try:
        print("📋 Tenant Database Status Report")
        print("=" * 50)
        
        # Get all tenants from master database
        tenants = master_db.query(Tenant).all()
        
        print(f"{'ID':<5} {'Name':<30} {'Database':<20} {'Status':<10}")
        print("-" * 70)
        
        for tenant in tenants:
            database_name = f"tenant_{tenant.id}"
            
            try:
                # Try to connect to tenant database
                tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()
                tenant_session.execute(text("SELECT 1"))
                tenant_session.close()
                
                status = "✅ OK"
                
            except Exception as e:
                status = "❌ MISSING"
            
            print(f"{tenant.id:<5} {tenant.name[:28]:<30} {database_name:<20} {status:<10}")
            
    except Exception as e:
        print(f"❌ Error listing tenant databases: {e}")
        logger.error(f"Error listing tenant databases: {e}")
    finally:
        master_db.close()

def recreate_tenant_database(tenant_id: int):
    """Recreate a specific tenant database"""
    master_db = next(get_master_db())
    
    try:
        # Get tenant info
        tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
        
        if not tenant:
            print(f"❌ Tenant {tenant_id} not found in master database")
            return
        
        print(f"🔄 Recreating database for tenant {tenant_id}: {tenant.name}")
        print("⚠️  WARNING: This will DELETE ALL DATA in the tenant database!")
        
        confirm = input("Are you sure you want to continue? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("Operation cancelled")
            return
        
        success = tenant_db_manager.recreate_tenant_database(tenant_id, tenant.name)
        
        if success:
            print(f"✅ Successfully recreated tenant_{tenant_id}")
        else:
            print(f"❌ Failed to recreate tenant_{tenant_id}")
            
    except Exception as e:
        print(f"❌ Error recreating tenant database: {e}")
        logger.error(f"Error recreating tenant database: {e}")
    finally:
        master_db.close()

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fix_missing_tenant_databases.py check    # Check and fix missing databases")
        print("  python fix_missing_tenant_databases.py list     # List all tenant databases")
        print("  python fix_missing_tenant_databases.py recreate <tenant_id>  # Recreate specific database")
        return
    
    command = sys.argv[1]
    
    if command == "check":
        check_and_fix_tenant_databases()
    elif command == "list":
        list_tenant_databases()
    elif command == "recreate":
        if len(sys.argv) < 3:
            print("Error: tenant_id required for recreate command")
            return
        
        try:
            tenant_id = int(sys.argv[2])
            recreate_tenant_database(tenant_id)
        except ValueError:
            print("Error: tenant_id must be a number")
    else:
        print(f"Unknown command: {command}")
        print("Use 'check', 'list', or 'recreate <tenant_id>'")

if __name__ == "__main__":
    main() 