#!/usr/bin/env python3
"""
Simple migration: Add user_id column to payments table in current tenant database.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import create_engine, text
from models.database import SQLALCHEMY_DATABASE_URL

def add_user_id_column():
    """Add user_id column to payments table"""
    print(f"Migrating database: {SQLALCHEMY_DATABASE_URL}")
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if column already exists (Postgres syntax)
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'payments' AND column_name = 'user_id'
        """))
        if result.fetchone():
            print("  - user_id column already exists, skipping.")
            return
        
        # Add the column (Postgres syntax)
        print("  - Adding user_id column...")
        conn.execute(text("ALTER TABLE payments ADD COLUMN user_id INTEGER REFERENCES users(id)"))
        conn.commit()
        print("  - Done.")

if __name__ == "__main__":
    add_user_id_column() 