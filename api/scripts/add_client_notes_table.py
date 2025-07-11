#!/usr/bin/env python3
"""
Migration script to add client_notes table to the database.
This script adds support for storing notes for clients.
"""

import sys
import os
import logging
from datetime import datetime

# Add the parent directory to sys.path so we can import from the api module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models.database import SQLALCHEMY_DATABASE_URL
from models.models import Base, ClientNote
from sqlalchemy.engine.url import make_url

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the migration to add client_notes table"""
    
    # Get database URL
    database_url = SQLALCHEMY_DATABASE_URL
    if make_url(database_url).get_backend_name() == "sqlite":
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(database_url)
    
    try:
        logger.info("Starting migration to add client_notes table...")
        
        # Check if table already exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='client_notes'
            """))
            
            if result.fetchone():
                logger.info("client_notes table already exists. Skipping migration.")
                return
        
        # Create the table
        logger.info("Creating client_notes table...")
        ClientNote.__table__.create(engine, checkfirst=True)
        
        logger.info("Migration completed successfully!")
        logger.info("Created table: client_notes")
        
        # Verify the table was created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name='client_notes'
            """))
            
            table_def = result.fetchone()
            if table_def:
                logger.info("Table structure:")
                logger.info(table_def[0])
            else:
                logger.error("Failed to create client_notes table")
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
        print("The client_notes table has been added to your database.")
        print("You can now add notes to your clients.")
    else:
        print("❌ Migration failed!")
        print("Please check the logs above for error details.")
        sys.exit(1) 