#!/usr/bin/env python3
"""
Force database initialization script.
This script will delete any existing database and create a fresh one with the correct schema.
"""

import os
import sys
import logging
from pathlib import Path

# Add the parent directory (api) to Python path so we can import modules
api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, api_dir)

from core.models.database import SQLALCHEMY_DATABASE_URL
from db_init import init_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def force_init_database():
    """Force initialize the database by removing existing file and creating fresh."""
    
    # Extract database file path from URL
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
        db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
        if db_path.startswith("./"):
            db_path = db_path[2:]  # Remove leading ./
        
        # Convert to absolute path relative to api directory
        if not os.path.isabs(db_path):
            db_path = os.path.join(api_dir, db_path)
        
        logger.info(f"Database path: {db_path}")
        
        # Remove existing database file if it exists
        if os.path.exists(db_path):
            logger.info(f"Removing existing database file: {db_path}")
            os.remove(db_path)
        else:
            logger.info("No existing database file found.")
    
    # Initialize the database
    try:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialization completed successfully!")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    force_init_database() 