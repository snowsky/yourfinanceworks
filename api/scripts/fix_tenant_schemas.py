#!/usr/bin/env python3
"""
Utility script to fix existing tenant databases that have incorrect schema.

This script will:
1. Identify tenant databases with old schema (containing tenant_id columns)
2. Recreate them with the correct schema (without tenant_id columns)
3. Preserve any existing data if possible

Run this script after updating to database-per-tenant architecture.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.models.database import SQLALCHEMY_DATABASE_URL, get_master_db
from core.models.models import Tenant, MasterUser
from core.services.tenant_database_manager import tenant_db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_tenant_database_schema(tenant_id: int) -> bool:
    """Check if a tenant database has the correct schema (without tenant_id columns)"""
    try:
        tenant_engine = tenant_db_manager.get_tenant_engine(tenant_id)
        inspector = inspect(tenant_engine)
        
        # Check if users table has tenant_id column (it shouldn't in new schema)
        if inspector.has_table("users"):
            columns = [col['name'] for col in inspector.get_columns("users")]
            if 'tenant_id' in columns:
                logger.info(f"❌ Tenant {tenant_id} database has old schema (contains tenant_id)")
                return False
            else:
                logger.info(f"✅ Tenant {tenant_id} database has correct schema")
                return True
        else:
            logger.info(f"⚠️ Tenant {tenant_id} database missing users table")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error checking tenant {tenant_id} schema: {e}")
        return False

def fix_tenant_database_schema(tenant_id: int, tenant_name: str) -> bool:
    """Fix a tenant database schema by recreating it"""
    try:
        logger.info(f"🔧 Fixing schema for tenant {tenant_id}: {tenant_name}")
        
        # Recreate the database with correct schema
        success = tenant_db_manager.recreate_tenant_database(tenant_id, tenant_name)
        
        if success:
            logger.info(f"✅ Fixed schema for tenant {tenant_id}")
            return True
        else:
            logger.error(f"❌ Failed to fix schema for tenant {tenant_id}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error fixing tenant {tenant_id} schema: {e}")
        return False

def get_all_tenants():
    """Get all tenants from master database"""
    try:
        master_db = next(get_master_db())
        try:
            tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
            return tenants
        finally:
            master_db.close()
    except Exception as e:
        logger.error(f"Error getting tenants: {e}")
        return []

def check_and_fix_all_tenant_schemas(fix_mode: bool = False):
    """Check all tenant database schemas and optionally fix them"""
    logger.info("🔍 Checking tenant database schemas...")
    
    tenants = get_all_tenants()
    logger.info(f"Found {len(tenants)} active tenants")
    
    issues_found = []
    
    for tenant in tenants:
        logger.info(f"\n📋 Checking tenant: {tenant.name} (ID: {tenant.id})")
        
        # Check if tenant database exists
        tenant_databases = tenant_db_manager.get_all_tenant_databases()
        tenant_db_name = f"tenant_{tenant.id}"
        
        if tenant_db_name not in tenant_databases:
            logger.warning(f"⚠️ Tenant database {tenant_db_name} does not exist")
            if fix_mode:
                logger.info(f"🔧 Creating missing database for tenant {tenant.id}")
                success = tenant_db_manager.create_tenant_database(tenant.id, tenant.name)
                if success:
                    logger.info(f"✅ Created database for tenant {tenant.id}")
                else:
                    logger.error(f"❌ Failed to create database for tenant {tenant.id}")
                    issues_found.append(f"Failed to create database for tenant {tenant.id}")
            else:
                issues_found.append(f"Missing database for tenant {tenant.id}")
            continue
        
        # Check schema
        schema_correct = check_tenant_database_schema(tenant.id)
        
        if not schema_correct:
            issues_found.append(f"Incorrect schema for tenant {tenant.id}")
            
            if fix_mode:
                # Fix the schema
                success = fix_tenant_database_schema(tenant.id, tenant.name)
                if not success:
                    issues_found.append(f"Failed to fix schema for tenant {tenant.id}")
            else:
                logger.info(f"🔧 Run with --fix to repair schema for tenant {tenant.id}")
    
    return issues_found

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check and fix tenant database schemas')
    parser.add_argument('--fix', action='store_true', help='Actually fix the schemas (not just check)')
    parser.add_argument('--tenant-id', type=int, help='Fix specific tenant ID only')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🚀 Tenant Database Schema Checker/Fixer")
    logger.info("=" * 50)
    
    if args.tenant_id:
        # Fix specific tenant
        logger.info(f"Checking specific tenant: {args.tenant_id}")
        
        # Get tenant info
        master_db = next(get_master_db())
        try:
            tenant = master_db.query(Tenant).filter(Tenant.id == args.tenant_id).first()
            if not tenant:
                logger.error(f"Tenant {args.tenant_id} not found")
                sys.exit(1)
        finally:
            master_db.close()
        
        schema_correct = check_tenant_database_schema(args.tenant_id)
        
        if not schema_correct and args.fix:
            success = fix_tenant_database_schema(args.tenant_id, tenant.name)
            if success:
                logger.info(f"✅ Fixed tenant {args.tenant_id}")
            else:
                logger.error(f"❌ Failed to fix tenant {args.tenant_id}")
                sys.exit(1)
        elif not schema_correct:
            logger.info(f"🔧 Run with --fix to repair schema for tenant {args.tenant_id}")
    else:
        # Check all tenants
        issues = check_and_fix_all_tenant_schemas(fix_mode=args.fix)
        
        logger.info("\n" + "=" * 50)
        if issues:
            logger.info(f"❌ Found {len(issues)} issues:")
            for issue in issues:
                logger.info(f"  - {issue}")
            
            if not args.fix:
                logger.info("\n🔧 Run with --fix to automatically repair these issues")
        else:
            logger.info("✅ All tenant databases have correct schema!")

if __name__ == "__main__":
    main() 