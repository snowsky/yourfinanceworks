#!/usr/bin/env python3
"""
Script to reindex all search data for all tenants
"""

import os
import sys
import logging
from pathlib import Path

# Add the parent directory to the path so we can import from the API
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import get_master_db_url, get_tenant_db_url, set_tenant_context
from models.models import Tenant
from services.search_service import search_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reindex_tenant_data(tenant_id: int):
    """Reindex all data for a specific tenant"""
    try:
        # Set tenant context
        set_tenant_context(tenant_id)
        
        # Create tenant database session
        tenant_db_url = get_tenant_db_url(tenant_id)
        engine = create_engine(tenant_db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        with SessionLocal() as db:
            logger.info(f"Reindexing data for tenant {tenant_id}")
            search_service.reindex_all(db)
            logger.info(f"Successfully reindexed data for tenant {tenant_id}")
            
    except Exception as e:
        logger.error(f"Error reindexing tenant {tenant_id}: {e}")
        raise

def main():
    """Main function to reindex all tenants"""
    try:
        # Get all tenants from master database
        master_db_url = get_master_db_url()
        master_engine = create_engine(master_db_url)
        MasterSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=master_engine)
        
        with MasterSessionLocal() as master_db:
            tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
            
            if not tenants:
                logger.info("No active tenants found")
                return
            
            logger.info(f"Found {len(tenants)} active tenants")
            
            for tenant in tenants:
                logger.info(f"Processing tenant: {tenant.name} (ID: {tenant.id})")
                try:
                    reindex_tenant_data(tenant.id)
                except Exception as e:
                    logger.error(f"Failed to reindex tenant {tenant.id}: {e}")
                    continue
            
            logger.info("Reindexing completed for all tenants")
            
    except Exception as e:
        logger.error(f"Error in main reindexing process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()