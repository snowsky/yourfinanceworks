#!/usr/bin/env python3
"""
Migration script to add company_logo_url column to tenants table.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import DATABASE_URL
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_company_logo_url_column():
    """Add company_logo_url column to tenants table if it doesn't exist."""
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Check if column already exists (SQLite compatible)
            try:
                result = connection.execute(text("PRAGMA table_info(tenants)"))
                columns = [row[1] for row in result.fetchall()]
                
                if 'company_logo_url' in columns:
                    logger.info("Column company_logo_url already exists in tenants table")
                    return
                
                # Add the column
                connection.execute(text("""
                    ALTER TABLE tenants 
                    ADD COLUMN company_logo_url TEXT
                """))
                
                connection.commit()
                logger.info("Successfully added company_logo_url column to tenants table")
                
            except Exception as e:
                logger.error(f"Error checking/adding column: {str(e)}")
                raise
            
    except Exception as e:
        logger.error(f"Error adding company_logo_url column: {str(e)}")
        raise

if __name__ == "__main__":
    add_company_logo_url_column() 