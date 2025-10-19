#!/usr/bin/env python3
"""
Test script to verify expense persistence issue
Run this after creating an expense to check if it's actually in the database
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/invoice_app")

def check_tenant_databases():
    """Check all tenant databases for expenses"""
    # Connect to master database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all tenants
        result = session.execute(text("SELECT id, name, database_name FROM tenants"))
        tenants = result.fetchall()
        
        print(f"\n{'='*60}")
        print(f"Found {len(tenants)} tenants")
        print(f"{'='*60}\n")
        
        for tenant in tenants:
            tenant_id, tenant_name, db_name = tenant
            print(f"\nTenant: {tenant_name} (ID: {tenant_id})")
            print(f"Database: {db_name}")
            print("-" * 60)
            
            # Connect to tenant database
            tenant_db_url = DATABASE_URL.rsplit('/', 1)[0] + f'/{db_name}'
            tenant_engine = create_engine(tenant_db_url)
            tenant_session = sessionmaker(bind=tenant_engine)()
            
            try:
                # Count expenses
                result = tenant_session.execute(text("SELECT COUNT(*) FROM expenses"))
                expense_count = result.scalar()
                print(f"Total expenses: {expense_count}")
                
                # Get recent expenses
                result = tenant_session.execute(text("""
                    SELECT id, user_id, amount, category, vendor, created_at 
                    FROM expenses 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """))
                expenses = result.fetchall()
                
                if expenses:
                    print("\nRecent expenses:")
                    for exp in expenses:
                        exp_id, user_id, amount, category, vendor, created_at = exp
                        print(f"  ID: {exp_id}, User: {user_id}, Amount: {amount}, "
                              f"Category: {category}, Vendor: {vendor}, Created: {created_at}")
                else:
                    print("No expenses found")
                    
                # Check users
                result = tenant_session.execute(text("SELECT id, email FROM users"))
                users = result.fetchall()
                print(f"\nUsers in this tenant: {len(users)}")
                for user_id, email in users:
                    print(f"  User ID: {user_id}, Email: {email}")
                    
            finally:
                tenant_session.close()
                tenant_engine.dispose()
                
    finally:
        session.close()
        engine.dispose()

if __name__ == "__main__":
    try:
        check_tenant_databases()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
