#!/usr/bin/env python3
"""
Migration script to add tenant_id column to settings table in tenant databases.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import get_master_db
from core.models.models import Tenant
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_settings_tenant_id():
    """Add tenant_id column to settings table in all tenant databases."""
    try:
        # Use PostgreSQL connection for master database
        master_db_url = "postgresql://postgres:password@postgres-master:5432/invoice_master"
        master_engine = create_engine(master_db_url)
        
        from sqlalchemy.orm import sessionmaker
        MasterSession = sessionmaker(bind=master_engine)
        master_db = MasterSession()
        
        # Get all tenants
        tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        logger.info(f"Found {len(tenants)} active tenants")
        
        for tenant in tenants:
            try:
                logger.info(f"Processing tenant: {tenant.name} (ID: {tenant.id})")
                
                # Connect to tenant database
                tenant_db_url = f"postgresql://postgres:password@postgres-master:5432/tenant_{tenant.id}"
                tenant_engine = create_engine(tenant_db_url)
                
                with tenant_engine.connect() as connection:
                    # Check if tenant_id column exists in settings table
                    result = connection.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'settings' AND column_name = 'tenant_id'
                    """))
                    
                    if result.fetchone():
                        logger.info(f"Tenant {tenant.id}: tenant_id column already exists in settings table")
                    else:
                        logger.info(f"Tenant {tenant.id}: Adding tenant_id column to settings table")
                        
                        # Add tenant_id column
                        connection.execute(text(f"""
                            ALTER TABLE settings 
                            ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT {tenant.id}
                        """))
                        
                        # Update existing settings records with the correct tenant_id
                        connection.execute(text(f"""
                            UPDATE settings 
                            SET tenant_id = {tenant.id} 
                            WHERE tenant_id IS NULL OR tenant_id = 0
                        """))
                        
                        # Add unique constraint
                        connection.execute(text("""
                            ALTER TABLE settings 
                            ADD CONSTRAINT settings_tenant_id_unique UNIQUE (tenant_id)
                        """))
                        
                        logger.info(f"Tenant {tenant.id}: Successfully added tenant_id column")
                    
                    connection.commit()
                    
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.id}: {str(e)}")
                continue
        
        logger.info("Migration completed successfully")
                
    except Exception as e:
        logger.error(f"Error in migration: {str(e)}")
        raise

if __name__ == "__main__":
    fix_settings_tenant_id() 