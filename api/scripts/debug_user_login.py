#!/usr/bin/env python3
"""
Script to debug user login issues
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant
from core.utils.auth import verify_password
from core.services.tenant_database_manager import tenant_db_manager

def debug_user_login(email: str):
    """Debug user login issues"""
    master_db = next(get_master_db())
    
    try:
        print(f"Debugging login for user: {email}")
        print("-" * 50)
        
        # Check if user exists in master database
        user = master_db.query(MasterUser).filter(MasterUser.email == email).first()
        if not user:
            print(f"❌ User {email} not found in master database")
            return
        
        print(f"✅ User found in master database:")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Active: {user.is_active}")
        print(f"   Verified: {user.is_verified}")
        print(f"   Tenant ID: {user.tenant_id}")
        print(f"   Role: {user.role}")
        print(f"   Superuser: {user.is_superuser}")
        
        # Check tenant
        tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            print(f"❌ Tenant {user.tenant_id} not found")
            return
        
        print(f"✅ Tenant found:")
        print(f"   ID: {tenant.id}")
        print(f"   Name: {tenant.name}")
        print(f"   Active: {tenant.is_active}")
        
        # Check if tenant database exists
        try:
            tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)
            tenant_db = tenant_session()
            from sqlalchemy import text
            result = tenant_db.execute(text("SELECT 1")).fetchone()
            tenant_db.close()
            print(f"✅ Tenant database accessible")
        except Exception as e:
            print(f"❌ Tenant database error: {e}")
            
            # Try to create tenant database
            print("Attempting to create tenant database...")
            success = tenant_db_manager.create_tenant_database(user.tenant_id, tenant.name)
            if success:
                print("✅ Tenant database created successfully")
            else:
                print("❌ Failed to create tenant database")
        
        # Check if user exists in tenant database
        try:
            from core.models.models_per_tenant import User as TenantUser
            tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)
            tenant_db = tenant_session()
            
            tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user.id).first()
            if tenant_user:
                print(f"✅ User found in tenant database")
                print(f"   ID: {tenant_user.id}")
                print(f"   Email: {tenant_user.email}")
                print(f"   Active: {tenant_user.is_active}")
                print(f"   Role: {tenant_user.role}")
            else:
                print(f"❌ User not found in tenant database")
                
                # Create user in tenant database
                print("Creating user in tenant database...")
                tenant_user = TenantUser(
                    id=user.id,
                    email=user.email,
                    hashed_password=user.hashed_password,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    role=user.role,
                    is_active=user.is_active,
                    is_superuser=user.is_superuser,
                    is_verified=user.is_verified
                )
                tenant_db.add(tenant_user)
                tenant_db.commit()
                print("✅ User created in tenant database")
            
            tenant_db.close()
        except Exception as e:
            print(f"❌ Tenant user check error: {e}")
        
    finally:
        master_db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_user_login.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    debug_user_login(email)