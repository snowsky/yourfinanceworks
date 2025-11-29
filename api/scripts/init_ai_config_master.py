#!/usr/bin/env python3
"""
Script to initialize AI config table in master database.
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

def init_ai_config_master():
    """Initialize AI config table in master database"""
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Check if table already exists
            result = connection.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'ai_configs'
            """))
            
            if result.fetchone():
                logger.info("AI configs table already exists in master database")
                
                # Check if tested column exists
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'ai_configs' AND column_name = 'tested'
                """))
                
                if result.fetchone():
                    logger.info("tested column already exists in master database ai_configs table")
                else:
                    logger.info("Adding tested column to master database ai_configs table")
                    connection.execute(text("""
                        ALTER TABLE ai_configs 
                        ADD COLUMN tested BOOLEAN DEFAULT FALSE
                    """))
                    logger.info("Successfully added tested column to master database")
            else:
                logger.info("Creating ai_configs table in master database")
                # Create the ai_configs table with tested field
                connection.execute(text("""
                    CREATE TABLE ai_configs (
                        id SERIAL PRIMARY KEY,
                        tenant_id INTEGER NOT NULL,
                        provider_name VARCHAR NOT NULL,
                        provider_url VARCHAR,
                        api_key VARCHAR,
                        model_name VARCHAR NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_default BOOLEAN DEFAULT FALSE,
                        tested BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes
                connection.execute(text("""
                    CREATE INDEX idx_ai_configs_tenant_id ON ai_configs (tenant_id)
                """))
                
                connection.execute(text("""
                    CREATE INDEX idx_ai_configs_provider_name ON ai_configs (provider_name)
                """))
                
                connection.execute(text("""
                    CREATE INDEX idx_ai_configs_tested ON ai_configs (tested)
                """))
                
                logger.info("Successfully created ai_configs table in master database")
            
            connection.commit()
            
    except Exception as e:
        logger.error(f"Error initializing AI config table in master database: {e}")
        raise

if __name__ == "__main__":
    init_ai_config_master() 