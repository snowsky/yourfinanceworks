#!/usr/bin/env python3
"""
Script to initialize AI config table in all tenant databases.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from models.database import get_master_db
from models.models import Tenant
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_ai_config_tenants():
    """Initialize AI config table in all tenant databases"""
    try:
        # Get master database session
        master_db = next(get_master_db())
        
        # Get all active tenants
        tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        
        logger.info(f"Found {len(tenants)} active tenants")

        for tenant in tenants:
            try:
                # Construct tenant database URL
                tenant_db_url = f"postgresql://postgres:password@postgres-master:5432/tenant_{tenant.id}"
                tenant_engine = create_engine(tenant_db_url)
                
                with tenant_engine.connect() as connection:
                    # Check if table already exists
                    result = connection.execute(text("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'ai_configs'
                    """))
                    
                    if result.fetchone():
                        logger.info(f"AI configs table already exists in tenant_{tenant.id} database")
                        
                        # Check if tested column exists
                        result = connection.execute(text("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'ai_configs' AND column_name = 'tested'
                        """))
                        
                        if result.fetchone():
                            logger.info(f"tested column already exists in tenant_{tenant.id} database")
                        else:
                            logger.info(f"Adding tested column to tenant_{tenant.id} database")
                            connection.execute(text("""
                                ALTER TABLE ai_configs 
                                ADD COLUMN tested BOOLEAN DEFAULT FALSE
                            """))
                            logger.info(f"Successfully added tested column to tenant_{tenant.id} database")
                    else:
                        logger.info(f"Creating ai_configs table in tenant_{tenant.id} database")
                        # Create the ai_configs table with tested field
                        connection.execute(text("""
                            CREATE TABLE ai_configs (
                                id SERIAL PRIMARY KEY,
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
                            CREATE INDEX idx_ai_configs_provider_name ON ai_configs (provider_name)
                        """))
                        
                        connection.execute(text("""
                            CREATE INDEX idx_ai_configs_is_active ON ai_configs (is_active)
                        """))
                        
                        connection.execute(text("""
                            CREATE INDEX idx_ai_configs_is_default ON ai_configs (is_default)
                        """))
                        
                        connection.execute(text("""
                            CREATE INDEX idx_ai_configs_tested ON ai_configs (tested)
                        """))
                        
                        logger.info(f"Successfully created ai_configs table in tenant_{tenant.id} database")
                    
                    connection.commit()
                    
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.id}: {e}")
                continue
        
        logger.info("AI config table initialization completed for all tenant databases")
        
    except Exception as e:
        logger.error(f"Error initializing AI config tables: {e}")
        raise

if __name__ == "__main__":
    init_ai_config_tenants() 