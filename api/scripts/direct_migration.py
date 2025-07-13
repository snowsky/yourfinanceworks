#!/usr/bin/env python3

import psycopg2
import os
from urllib.parse import urlparse

def add_soft_delete_columns_direct():
    """Add soft delete columns directly to the tenant database"""
    print("🔄 Adding soft delete columns to Invoice table...")
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/invoice_db")
    
    # Parse the database URL to get tenant database
    # For this system, we'll assume the tenant database is the main database
    parsed = urlparse(database_url)
    
    try:
        # Connect to the database
        connection = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],  # Remove leading '/'
            user=parsed.username,
            password=parsed.password
        )
        
        cursor = connection.cursor()
        
        print(f"📋 Connected to database: {parsed.path[1:]}")
        
        # Check if invoices table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'invoices'
        """)
        
        if not cursor.fetchone():
            print("❌ Invoices table not found")
            return
        
        print("✅ Found invoices table")
        
        # Check which columns already exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'invoices' 
            AND column_name IN ('is_deleted', 'deleted_at', 'deleted_by')
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Existing soft delete columns: {existing_columns}")
        
        # Add missing columns
        columns_to_add = []
        
        if 'is_deleted' not in existing_columns:
            columns_to_add.append("ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE")
        
        if 'deleted_at' not in existing_columns:
            columns_to_add.append("ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE")
        
        if 'deleted_by' not in existing_columns:
            # Check if users table exists first
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'users'
            """)
            
            if cursor.fetchone():
                columns_to_add.append("ADD COLUMN deleted_by INTEGER REFERENCES users(id)")
            else:
                # If users table doesn't exist, add without foreign key constraint
                columns_to_add.append("ADD COLUMN deleted_by INTEGER")
        
        if columns_to_add:
            # Execute ALTER TABLE statements
            for column_def in columns_to_add:
                alter_query = f"ALTER TABLE invoices {column_def}"
                print(f"🔄 Executing: {alter_query}")
                cursor.execute(alter_query)
            
            connection.commit()
            print(f"✅ Added {len(columns_to_add)} columns to invoices table")
        else:
            print("✅ All soft delete columns already exist")
        
        cursor.close()
        connection.close()
        
        print("🎉 Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_soft_delete_columns_direct() 