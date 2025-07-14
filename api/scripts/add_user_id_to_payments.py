#!/usr/bin/env python3
"""
Migration: Add user_id column to payments table in all tenant databases.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import create_engine, text

MASTER_DB_URL = "postgresql://postgres:password@postgres-master:5432/invoice_master"

def get_all_tenant_db_urls():
    engine = create_engine(MASTER_DB_URL)
    db_urls = []
    with engine.connect() as conn:
        # Get all tenant IDs from the tenants table
        result = conn.execute(text("SELECT id FROM tenants WHERE is_active = true"))
        for row in result:
            tenant_id = row[0]
            db_name = f"tenant_{tenant_id}"
            db_url = f"postgresql://postgres:password@postgres-master:5432/{db_name}"
            db_urls.append(db_url)
    return db_urls

def add_user_id_column():
    db_urls = get_all_tenant_db_urls()
    for db_url in db_urls:
        print(f"Migrating: {db_url}")
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Check if column already exists (Postgres syntax)
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'payments' AND column_name = 'user_id'
            """))
            if result.fetchone():
                print("  - user_id column already exists, skipping.")
                continue
            # Add the column (Postgres syntax)
            print("  - Adding user_id column...")
            conn.execute(text("ALTER TABLE payments ADD COLUMN user_id INTEGER REFERENCES users(id)"))
            conn.commit()
            print("  - Done.")

if __name__ == "__main__":
    add_user_id_column() 