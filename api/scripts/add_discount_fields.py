#!/usr/bin/env python3
"""
Migration script to add discount fields to invoices table
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import get_database_url

def migrate_database():
    """Add discount fields to invoices table"""
    engine = create_engine(get_database_url())
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("PRAGMA table_info(invoices)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'discount_type' not in columns:
            print("Adding discount_type column...")
            conn.execute(text("ALTER TABLE invoices ADD COLUMN discount_type TEXT DEFAULT 'percentage' NOT NULL"))
        
        if 'discount_value' not in columns:
            print("Adding discount_value column...")
            conn.execute(text("ALTER TABLE invoices ADD COLUMN discount_value REAL DEFAULT 0.0 NOT NULL"))
        
        if 'subtotal' not in columns:
            print("Adding subtotal column...")
            conn.execute(text("ALTER TABLE invoices ADD COLUMN subtotal REAL"))
            
            # Initialize subtotal with current amount for existing invoices
            print("Initializing subtotal for existing invoices...")
            conn.execute(text("UPDATE invoices SET subtotal = amount WHERE subtotal IS NULL"))
        
        conn.commit()
        print("Migration completed successfully!")

if __name__ == "__main__":
    migrate_database() 