#!/usr/bin/env python3
"""
Script to enable AI assistant for existing tenants.
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

def enable_ai_assistant():
    """Enable AI assistant for all existing tenants."""
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Update all tenants to enable AI assistant
            result = connection.execute(text("""
                UPDATE tenants 
                SET enable_ai_assistant = TRUE 
                WHERE enable_ai_assistant IS NULL OR enable_ai_assistant = FALSE
            """))
            
            connection.commit()
            logger.info(f"Successfully enabled AI assistant for {result.rowcount} tenants")
                
    except Exception as e:
        logger.error(f"Error enabling AI assistant: {str(e)}")
        raise

if __name__ == "__main__":
    enable_ai_assistant() 