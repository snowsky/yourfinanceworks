#!/usr/bin/env python3
"""
Script to add tested field to AI config table.
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

def add_tested_field_to_ai_config():
    """Add tested field to AI config table."""
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Check if tested column already exists (PostgreSQL syntax)
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'ai_configs' AND column_name = 'tested'
            """))
            
            if result.fetchone():
                logger.info("tested column already exists in ai_configs table")
                return
            
            # Add the tested column
            connection.execute(text("""
                ALTER TABLE ai_configs 
                ADD COLUMN tested BOOLEAN DEFAULT FALSE
            """))
            
            logger.info("Successfully added tested column to ai_configs table")
            
    except Exception as e:
        logger.error(f"Error adding tested field to AI config table: {e}")
        raise

if __name__ == "__main__":
    add_tested_field_to_ai_config() 