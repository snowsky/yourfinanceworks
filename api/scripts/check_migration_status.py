#!/usr/bin/env python3
"""
Script to check migration status of all databases.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import get_master_db, DATABASE_URL
from core.models.models import Tenant
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_master_database():
    """Check migration status of master database"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Check if tested column exists in ai_configs table
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'ai_configs' AND column_name = 'tested'
            """))
            
            if result.fetchone():
                logger.info("✅ Master database: tested column exists in ai_configs table")
                return True
            else:
                logger.warning("❌ Master database: tested column missing from ai_configs table")
                return False
                
    except Exception as e:
        logger.error(f"Error checking master database: {e}")
        return False

def check_tenant_databases():
    """Check migration status of all tenant databases"""
    try:
        # Get master database session
        master_db = next(get_master_db())
        
        # Get all active tenants
        tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        
        logger.info(f"Found {len(tenants)} active tenants")
        
        all_good = True
        
        for tenant in tenants:
            try:
                # Construct tenant database URL
                tenant_db_url = f"postgresql://postgres:password@postgres-master:5432/tenant_{tenant.id}"
                tenant_engine = create_engine(tenant_db_url)
                
                with tenant_engine.connect() as connection:
                    # Check if tested column exists
                    result = connection.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'ai_configs' AND column_name = 'tested'
                    """))
                    
                    if result.fetchone():
                        logger.info(f"✅ Tenant {tenant.id}: tested column exists in ai_configs table")
                    else:
                        logger.warning(f"❌ Tenant {tenant.id}: tested column missing from ai_configs table")
                        all_good = False
                        
            except Exception as e:
                logger.error(f"Error checking tenant {tenant.id}: {e}")
                all_good = False
                continue
        
        return all_good
        
    except Exception as e:
        logger.error(f"Error checking tenant databases: {e}")
        return False

def check_migration_status():
    """Check migration status of all databases"""
    logger.info("Checking migration status...")
    
    master_ok = check_master_database()
    tenants_ok = check_tenant_databases()
    
    if master_ok and tenants_ok:
        logger.info("🎉 All databases are up to date!")
        return True
    else:
        logger.warning("⚠️  Some databases need migration")
        return False

if __name__ == "__main__":
    check_migration_status() 