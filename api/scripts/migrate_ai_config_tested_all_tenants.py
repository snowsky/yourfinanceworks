#!/usr/bin/env python3
"""
Script to add tested field to AI config table for all tenant databases.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import get_master_db
from core.models.models import Tenant
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_tested_field_to_all_tenant_databases():
    """Add tested field to AI config table for all tenant databases."""
    try:
        # Get master database session
        master_db = next(get_master_db())
        
        # Get all active tenants
        tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        
        logger.info(f"Found {len(tenants)} active tenants")
        
        for tenant in tenants:
            try:
                # Construct tenant database URL
                tenant_db_url = f"postgresql://postgres:password@postgres-master:5432/tenant_{tenant.id}"
                tenant_engine = create_engine(tenant_db_url)
                
                with tenant_engine.connect() as connection:
                    # Check if tested column already exists
                    result = connection.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'ai_configs' AND column_name = 'tested'
                    """))
                    
                    if result.fetchone():
                        logger.info(f"tested column already exists in tenant_{tenant.id} database")
                        continue
                    
                    # Add the tested column
                    connection.execute(text("""
                        ALTER TABLE ai_configs 
                        ADD COLUMN tested BOOLEAN DEFAULT FALSE
                    """))
                    
                    logger.info(f"Successfully added tested column to tenant_{tenant.id} database")
                    
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.id}: {e}")
                continue
        
        logger.info("Migration completed for all tenant databases")
        
    except Exception as e:
        logger.error(f"Error in migration: {e}")
        raise

if __name__ == "__main__":
    add_tested_field_to_all_tenant_databases() 