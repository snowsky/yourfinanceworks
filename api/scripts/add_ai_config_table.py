#!/usr/bin/env python3
"""
Script to add AI config table.
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

def add_ai_config_table():
    """Add AI config table to the database."""
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Check if table already exists
            result = connection.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='ai_configs'
            """))
            
            if result.fetchone():
                logger.info("AI configs table already exists")
                return
            
            # Create the ai_configs table
            connection.execute(text("""
                CREATE TABLE ai_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id INTEGER NOT NULL,
                    provider_name VARCHAR NOT NULL,
                    provider_url VARCHAR,
                    api_key VARCHAR,
                    model_name VARCHAR NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_default BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants (id)
                )
            """))
            
            # Create indexes
            connection.execute(text("""
                CREATE INDEX idx_ai_configs_tenant_id ON ai_configs (tenant_id)
            """))
            
            connection.execute(text("""
                CREATE INDEX idx_ai_configs_provider_name ON ai_configs (provider_name)
            """))
            
            connection.commit()
            logger.info("Successfully created ai_configs table")
                
    except Exception as e:
        logger.error(f"Error creating AI config table: {str(e)}")
        raise

if __name__ == "__main__":
    add_ai_config_table() 