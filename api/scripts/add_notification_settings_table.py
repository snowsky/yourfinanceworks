#!/usr/bin/env python3
"""
Add email notification settings table to all tenant databases
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import SQLALCHEMY_DATABASE_URL, get_tenant_context
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager

def get_master_db_url():
    return SQLALCHEMY_DATABASE_URL

def get_tenant_db_url(tenant_id):
    return tenant_db_manager.get_tenant_database_url(tenant_id)
from core.models import EmailNotificationSettings, Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_notification_settings_table():
    """Add email notification settings table to all tenant databases"""
    
    # Connect to master database to get all tenants
    master_engine = create_engine(get_master_db_url())
    MasterSession = sessionmaker(bind=master_engine)
    master_session = MasterSession()
    
    try:
        # Get all tenants
        tenants = master_session.query(Tenant).all()
        logger.info(f"Found {len(tenants)} tenants")
        
        for tenant in tenants:
            logger.info(f"Processing tenant {tenant.id}: {tenant.name}")
            
            try:
                # Connect to tenant database
                tenant_engine = create_engine(get_tenant_db_url(tenant.id))
                inspector = inspect(tenant_engine)
                
                # Check if table already exists
                if 'email_notification_settings' in inspector.get_table_names():
                    logger.info(f"  - Table already exists for tenant {tenant.id}")
                    continue
                
                # Create the table
                EmailNotificationSettings.__table__.create(tenant_engine)
                logger.info(f"  - Created email_notification_settings table for tenant {tenant.id}")
                
            except Exception as e:
                logger.error(f"  - Error processing tenant {tenant.id}: {str(e)}")
                continue
    
    except Exception as e:
        logger.error(f"Error accessing master database: {str(e)}")
        return False
    
    finally:
        master_session.close()
    
    logger.info("Migration completed successfully")
    return True

if __name__ == "__main__":
    success = add_notification_settings_table()
    sys.exit(0 if success else 1)