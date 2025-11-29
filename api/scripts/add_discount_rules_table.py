#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import SQLALCHEMY_DATABASE_URL

def add_discount_rules_table():
    """Add discount_rules table to the database"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        # Create discount_rules table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS discount_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name VARCHAR NOT NULL,
                min_amount FLOAT NOT NULL,
                discount_type VARCHAR DEFAULT 'percentage' NOT NULL,
                discount_value FLOAT NOT NULL,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                priority INTEGER DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants (id)
            )
        """))
        
        # Create index on tenant_id for better performance
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_discount_rules_tenant_id 
            ON discount_rules (tenant_id)
        """))
        
        # Create index on priority for sorting
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_discount_rules_priority 
            ON discount_rules (priority DESC)
        """))
        
        conn.commit()
        print("✅ Discount rules table created successfully!")

if __name__ == "__main__":
    add_discount_rules_table() 