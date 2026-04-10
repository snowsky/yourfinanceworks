#!/usr/bin/env python3
"""
Create inventory attachments table for all tenant databases
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add the parent directory to the path so we can import from the api module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from config import config
from core.models.database import SQLALCHEMY_DATABASE_URL
from core.services.tenant_database_manager import tenant_db_manager

def get_master_db_url():
    return SQLALCHEMY_DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_item_attachments_table():
    """Create item_attachments table in all tenant databases"""
    
    # SQL to create the item_attachments table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS item_attachments (
        id SERIAL PRIMARY KEY,
        item_id INTEGER NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
        
        -- File information
        filename VARCHAR NOT NULL,
        stored_filename VARCHAR NOT NULL,
        file_path VARCHAR NOT NULL,
        file_size INTEGER NOT NULL,
        content_type VARCHAR,
        file_hash VARCHAR,
        
        -- Attachment metadata
        attachment_type VARCHAR NOT NULL CHECK (attachment_type IN ('image', 'document')),
        document_type VARCHAR,
        description TEXT,
        alt_text VARCHAR,
        
        -- Display and organization
        is_primary BOOLEAN NOT NULL DEFAULT FALSE,
        display_order INTEGER NOT NULL DEFAULT 0,
        
        -- Image-specific fields
        image_width INTEGER,
        image_height INTEGER,
        has_thumbnail BOOLEAN NOT NULL DEFAULT FALSE,
        thumbnail_path VARCHAR,
        
        -- Upload tracking
        uploaded_by INTEGER NOT NULL REFERENCES users(id),
        upload_ip VARCHAR,
        
        -- Status
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        
        -- Timestamps
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    
    -- Create indexes for better performance
    CREATE INDEX IF NOT EXISTS idx_item_attachments_item_id ON item_attachments(item_id);
    CREATE INDEX IF NOT EXISTS idx_item_attachments_type ON item_attachments(attachment_type);
    CREATE INDEX IF NOT EXISTS idx_item_attachments_active ON item_attachments(is_active);
    CREATE INDEX IF NOT EXISTS idx_item_attachments_primary ON item_attachments(item_id, is_primary) WHERE is_primary = TRUE;
    CREATE INDEX IF NOT EXISTS idx_item_attachments_display_order ON item_attachments(item_id, display_order);
    """
    
    try:
        # Connect to master database to get list of tenant databases
        master_db_url = get_master_db_url()
        master_engine = create_engine(master_db_url)
        
        with master_engine.connect() as conn:
            # Get list of tenant databases
            result = conn.execute(text("SELECT database_name FROM tenants WHERE is_active = true"))
            tenant_databases = [row[0] for row in result.fetchall()]
            
        logger.info(f"Found {len(tenant_databases)} active tenant databases")
        
        # Create table in each tenant database
        for db_name in tenant_databases:
            try:
                # Construct tenant database URL
                tenant_db_url = master_db_url.replace('/invoice_master', f'/{db_name}')
                tenant_engine = create_engine(tenant_db_url)
                
                with tenant_engine.connect() as conn:
                    # Execute the table creation SQL
                    conn.execute(text(create_table_sql))
                    conn.commit()
                    
                logger.info(f"✓ Created item_attachments table in database: {db_name}")
                
            except SQLAlchemyError as e:
                logger.error(f"✗ Failed to create table in database {db_name}: {e}")
                continue
                
        logger.info("✓ Item attachments table creation completed")
        
    except Exception as e:
        logger.error(f"✗ Failed to create item_attachments tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_item_attachments_table()