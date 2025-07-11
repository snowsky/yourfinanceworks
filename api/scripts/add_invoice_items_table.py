#!/usr/bin/env python3
"""
Migration script to add invoice_items table to the database.
This script adds support for storing individual line items for invoices.
"""

import sys
import os
import logging
from datetime import datetime

# Add the parent directory to sys.path so we can import from the api module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker
from models.database import SQLALCHEMY_DATABASE_URL
from models.models import Base, InvoiceItem
from sqlalchemy.engine.url import make_url

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the migration to add invoice_items table"""
    
    # Get database URL
    database_url = SQLALCHEMY_DATABASE_URL
    if make_url(database_url).get_backend_name() == "sqlite":
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    try:
        logger.info("Starting migration to add invoice_items table...")
        
        # Check if table already exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='invoice_items'
            """))
            
            if result.fetchone():
                logger.info("invoice_items table already exists. Skipping migration.")
                return
        
        # Create the table
        logger.info("Creating invoice_items table...")
        InvoiceItem.__table__.create(engine, checkfirst=True)
        
        logger.info("Migration completed successfully!")
        logger.info("Created table: invoice_items")
        
        # Verify the table was created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name='invoice_items'
            """))
            
            table_def = result.fetchone()
            if table_def:
                logger.info("Table structure:")
                logger.info(table_def[0])
            else:
                logger.error("Failed to create invoice_items table")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("✅ Migration completed successfully!")
        print("The invoice_items table has been added to your database.")
        print("You can now add line items to your invoices.")
    else:
        print("❌ Migration failed!")
        print("Please check the logs above for error details.")
        sys.exit(1) 