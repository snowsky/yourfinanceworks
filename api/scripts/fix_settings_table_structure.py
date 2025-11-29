#!/usr/bin/env python3
"""
Migration script to add missing columns to settings table in tenant databases.
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

def fix_settings_table_structure():
    """Add missing columns to settings table in all tenant databases."""
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
                    # Define the columns that should exist in settings table
                    required_columns = [
                        ('invoice_prefix', 'VARCHAR DEFAULT \'INV-\''),
                        ('next_invoice_number', 'INTEGER DEFAULT 1'),
                        ('invoice_terms', 'TEXT DEFAULT \'Payment due within 30 days.\''),
                        ('invoice_notes', 'TEXT DEFAULT \'Thank you for your business!\''),
                        ('send_invoice_copy', 'BOOLEAN DEFAULT TRUE'),
                        ('auto_reminders', 'BOOLEAN DEFAULT TRUE')
                    ]
                    
                    # Check existing columns in settings table
                    result = connection.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'settings'
                    """))
                    
                    existing_columns = [row[0] for row in result.fetchall()]
                    logger.info(f"Tenant {tenant.id}: Existing columns in settings table: {existing_columns}")
                    
                    # Add missing columns
                    for column_name, column_type in required_columns:
                        if column_name not in existing_columns:
                            logger.info(f"Tenant {tenant.id}: Adding column {column_name} with type {column_type}")
                            connection.execute(text(f"""
                                ALTER TABLE settings 
                                ADD COLUMN {column_name} {column_type}
                            """))
                            logger.info(f"Tenant {tenant.id}: Successfully added column {column_name}")
                        else:
                            logger.info(f"Tenant {tenant.id}: Column {column_name} already exists")
                    
                    connection.commit()
                    
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.id}: {str(e)}")
                continue
        
        logger.info("Migration completed successfully")
                
    except Exception as e:
        logger.error(f"Error in migration: {str(e)}")
        raise

if __name__ == "__main__":
    fix_settings_table_structure() 