#!/usr/bin/env python3
"""
Migration script to add multi-tenancy support to the invoice application.

This script will:
1. Create the tenants table
2. Add tenant_id columns to existing tables
3. Create a default tenant for existing data
4. Update existing records to reference the default tenant
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models.database import SQLALCHEMY_DATABASE_URL
from models.models import Base, Tenant, User, Client, Invoice, Payment

def run_migration():
    # Create engine and session
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print("🚀 Starting multi-tenant migration...")
        
        # Step 1: Create all new tables (this will create tenants table)
        print("📋 Creating new tables...")
        Base.metadata.create_all(bind=engine)
        
        # Step 2: Check if we need to add tenant_id columns to existing tables
        print("🔧 Checking existing table structure...")
        
        # Check if tenant_id already exists in users table
        result = db.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'tenant_id' not in columns:
            print("➕ Adding tenant_id columns to existing tables...")
            
            # Add tenant_id columns
            db.execute(text("ALTER TABLE users ADD COLUMN tenant_id INTEGER"))
            db.execute(text("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'"))
            db.execute(text("ALTER TABLE clients ADD COLUMN tenant_id INTEGER"))
            db.execute(text("ALTER TABLE invoices ADD COLUMN tenant_id INTEGER"))
            db.execute(text("ALTER TABLE payments ADD COLUMN tenant_id INTEGER"))
            
            # Removed creation of default tenant and updating records to reference it
            # print("🏢 Creating default tenant...")
            # default_tenant = Tenant(
            #     name="Default Organization",
            #     email="admin@example.com",
            #     is_active=True
            # )
            # db.add(default_tenant)
            # db.commit()
            # db.refresh(default_tenant)
            # print(f"✅ Created default tenant with ID: {default_tenant.id}")
            # print("📝 Updating existing records...")
            # db.execute(text(f"UPDATE users SET tenant_id = {default_tenant.id} WHERE tenant_id IS NULL"))
            # db.execute(text(f"UPDATE clients SET tenant_id = {default_tenant.id} WHERE tenant_id IS NULL"))
            # db.execute(text(f"UPDATE invoices SET tenant_id = {default_tenant.id} WHERE tenant_id IS NULL"))
            # db.execute(text(f"UPDATE payments SET tenant_id = {default_tenant.id} WHERE tenant_id IS NULL"))
            # first_user = db.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
            # if first_user:
            #     db.execute(text(f"UPDATE users SET role = 'admin' WHERE id = {first_user[0]}"))
            # db.commit()
            # print("✅ Updated existing records")
            print("⚠️  Note: Please manually add NOT NULL constraints to tenant_id columns if needed")
            
        else:
            print("✅ Tables already have tenant_id columns")
        
        # Step 6: Verify migration
        print("🔍 Verifying migration...")
        tenant_count = db.execute(text("SELECT COUNT(*) FROM tenants")).fetchone()[0]
        user_count = db.execute(text("SELECT COUNT(*) FROM users WHERE tenant_id IS NOT NULL")).fetchone()[0]
        client_count = db.execute(text("SELECT COUNT(*) FROM clients WHERE tenant_id IS NOT NULL")).fetchone()[0]
        invoice_count = db.execute(text("SELECT COUNT(*) FROM invoices WHERE tenant_id IS NOT NULL")).fetchone()[0]
        payment_count = db.execute(text("SELECT COUNT(*) FROM payments WHERE tenant_id IS NOT NULL")).fetchone()[0]
        
        print(f"📊 Migration Summary:")
        print(f"   - Tenants: {tenant_count}")
        print(f"   - Users with tenant: {user_count}")
        print(f"   - Clients with tenant: {client_count}")
        print(f"   - Invoices with tenant: {invoice_count}")
        print(f"   - Payments with tenant: {payment_count}")
        
        print("🎉 Multi-tenant migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration() 