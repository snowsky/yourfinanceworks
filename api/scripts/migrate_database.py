#!/usr/bin/env python3
"""
Database migration script to add tenant support and missing columns
"""
import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Migrate the database to add tenant support"""
    
    # Database file path
    db_path = "invoice_app.db"
    
    if not os.path.exists(db_path):
        print("Database file not found. Creating new database...")
        return create_new_database()
    
    print("Migrating existing database...")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if tenants table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'")
        if not cursor.fetchone():
            print("Creating tenants table...")
            cursor.execute("""
                CREATE TABLE tenants (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR UNIQUE,
                    subdomain VARCHAR UNIQUE,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    email VARCHAR,
                    phone VARCHAR,
                    address VARCHAR,
                    tax_id VARCHAR,
                    logo_url VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Removed creation of default tenant
            # cursor.execute("""
            #     INSERT INTO tenants (name, email, is_active) 
            #     VALUES ('Default Company', 'admin@company.com', 1)
            # """)
            # print("Created default tenant")
        
        # Check if users table has tenant_id column
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'tenant_id' not in columns:
            print("Adding tenant_id column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN tenant_id INTEGER DEFAULT 1")
            
            # Update existing users to use default tenant
            # cursor.execute("UPDATE users SET tenant_id = 1 WHERE tenant_id IS NULL")
            print("Updated existing users to use default tenant")
        
        # Check if users table has role column
        if 'role' not in columns:
            print("Adding role column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user'")
        
        # Check if users table has other missing columns
        missing_columns = {
            'first_name': 'VARCHAR',
            'last_name': 'VARCHAR', 
            'google_id': 'VARCHAR UNIQUE',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        for column, column_type in missing_columns.items():
            if column not in columns:
                print(f"Adding {column} column to users table...")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")
        
        # Check if clients table has tenant_id
        cursor.execute("PRAGMA table_info(clients)")
        client_columns = [column[1] for column in cursor.fetchall()]
        
        if 'tenant_id' not in client_columns:
            print("Adding tenant_id column to clients table...")
            cursor.execute("ALTER TABLE clients ADD COLUMN tenant_id INTEGER DEFAULT 1")
            cursor.execute("UPDATE clients SET tenant_id = 1 WHERE tenant_id IS NULL")
        
        # Check if invoices table has tenant_id
        cursor.execute("PRAGMA table_info(invoices)")
        invoice_columns = [column[1] for column in cursor.fetchall()]
        
        if 'tenant_id' not in invoice_columns:
            print("Adding tenant_id column to invoices table...")
            cursor.execute("ALTER TABLE invoices ADD COLUMN tenant_id INTEGER DEFAULT 1")
            cursor.execute("UPDATE invoices SET tenant_id = 1 WHERE tenant_id IS NULL")
        
        # Check if payments table has tenant_id
        cursor.execute("PRAGMA table_info(payments)")
        payment_columns = [column[1] for column in cursor.fetchall()]
        
        if 'tenant_id' not in payment_columns:
            print("Adding tenant_id column to payments table...")
            cursor.execute("ALTER TABLE payments ADD COLUMN tenant_id INTEGER DEFAULT 1")
            cursor.execute("UPDATE payments SET tenant_id = 1 WHERE tenant_id IS NULL")
        
        # Check if settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if not cursor.fetchone():
            print("Creating settings table...")
            cursor.execute("""
                CREATE TABLE settings (
                    id INTEGER PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    key VARCHAR,
                    value JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    enable_ai_assistant BOOLEAN DEFAULT 0 NOT NULL
                )
            """)
        else:
            # Check if enable_ai_assistant column exists in settings table
            cursor.execute("PRAGMA table_info(settings)")
            settings_columns = [column[1] for column in cursor.fetchall()]
            if 'enable_ai_assistant' not in settings_columns:
                print("Adding enable_ai_assistant column to settings table...")
                cursor.execute("ALTER TABLE settings ADD COLUMN enable_ai_assistant BOOLEAN DEFAULT 0 NOT NULL")
        
        # Commit changes
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

def create_new_database():
    """Create a new database with the full schema"""
    print("Creating new database with full schema...")
    
    # This will use the SQLAlchemy models to create the database
    try:
        from models.database import engine
        from models import models
        
        # Create all tables
        models.Base.metadata.create_all(bind=engine)
        print("New database created successfully!")
        
        # Removed creation of default tenant and user
        # from sqlalchemy.orm import sessionmaker
        # Session = sessionmaker(bind=engine)
        # session = Session()
        # try:
        #     # Create default tenant
        #     default_tenant = models.Tenant(
        #         name="Default Company",
        #         email="admin@company.com",
        #         is_active=True
        #     )
        #     session.add(default_tenant)
        #     session.commit()
        #     print("Default tenant created")
        # except Exception as e:
        #     print(f"Error creating default data: {e}")
        #     session.rollback()
        # finally:
        #     session.close()
            
    except ImportError:
        print("SQLAlchemy not available, using raw SQL...")
        
        conn = sqlite3.connect("invoice_app.db")
        cursor = conn.cursor()
        
        # Create tables manually
        cursor.execute("""
            CREATE TABLE tenants (
                id INTEGER PRIMARY KEY,
                name VARCHAR UNIQUE,
                subdomain VARCHAR UNIQUE,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                email VARCHAR,
                phone VARCHAR,
                address VARCHAR,
                tax_id VARCHAR,
                logo_url VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            INSERT INTO tenants (name, email, is_active) 
            VALUES ('Default Company', 'admin@company.com', 1)
        """)
        
        conn.commit()
        conn.close()
        print("Basic database structure created")

if __name__ == "__main__":
    migrate_database() 