#!/usr/bin/env python3

import psycopg2
import os

def add_soft_delete_columns_postgres():
    """Add soft delete columns to the tenant database"""
    print("🔄 Adding soft delete columns to Invoice table...")
    
    # Based on the docker-compose.yml, the tenant database should be on localhost:5432
    # The tenant database name is likely "tenant_testcompany" based on previous patterns
    
    # Try connecting to the tenant database
    tenant_db_name = "tenant_3"  # Migrating the other tenant database
    
    try:
        # Connect to the tenant database
        connection = psycopg2.connect(
            host="localhost",
            port=5432,
            database=tenant_db_name,
            user="postgres",
            password="password"
        )
        
        cursor = connection.cursor()
        
        print(f"📋 Connected to tenant database: {tenant_db_name}")
        
        # Check if invoices table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'invoices'
        """)
        
        if not cursor.fetchone():
            print("❌ Invoices table not found in tenant database")
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
        
        # Show current columns
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'invoices' 
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        print("\n📋 Current invoices table structure:")
        for col_name, data_type, is_nullable in columns:
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"  - {col_name}: {data_type} {nullable}")
        
        cursor.close()
        connection.close()
        
        print("\n🎉 Migration completed successfully!")
        
    except psycopg2.OperationalError as e:
        if "does not exist" in str(e):
            print(f"❌ Database '{tenant_db_name}' does not exist")
            print("💡 Available options:")
            print("   1. The tenant database might have a different name")
            print("   2. Run the per-tenant migration first")
            print("   3. Create a test tenant first")
        else:
            print(f"❌ Connection error: {e}")
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_soft_delete_columns_postgres() 