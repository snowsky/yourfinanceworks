#!/usr/bin/env python3
"""
Migration script to add missing columns to tenants table (PostgreSQL).
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from models.database import DATABASE_URL
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_missing_tenant_columns():
    """Add missing columns to tenants table if they don't exist."""
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Define the columns that should exist
            required_columns = [
                ('company_logo_url', 'VARCHAR'),
                ('enable_ai_assistant', 'BOOLEAN DEFAULT FALSE'),
                ('default_currency', 'VARCHAR DEFAULT \'USD\'')
            ]
            
            # Check existing columns
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'tenants'
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            logger.info(f"Existing columns: {existing_columns}")
            
            # Add missing columns
            for column_name, column_type in required_columns:
                if column_name not in existing_columns:
                    logger.info(f"Adding column {column_name} with type {column_type}")
                    connection.execute(text(f"""
                        ALTER TABLE tenants 
                        ADD COLUMN {column_name} {column_type}
                    """))
                    logger.info(f"Successfully added column {column_name}")
                else:
                    logger.info(f"Column {column_name} already exists")
            
            connection.commit()
            logger.info("Migration completed successfully")
                
    except Exception as e:
        logger.error(f"Error adding columns: {str(e)}")
        raise

if __name__ == "__main__":
    add_missing_tenant_columns() 