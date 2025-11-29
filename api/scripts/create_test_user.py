#!/usr/bin/env python3
"""
Create a test user for password reset testing
"""

import sys
import os
from datetime import datetime, timezone

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import SessionLocal
from core.models.models import MasterUser, Tenant
from core.utils.auth import get_password_hash
from core.services.tenant_database_manager import tenant_db_manager

def create_test_user():
    """Create a test user and tenant for password reset testing"""
    print("Creating test user for password reset testing...")
    
    db = SessionLocal()
    
    try:
        # Check if test user already exists
        existing_user = db.query(MasterUser).filter(MasterUser.email == "test.user@example.com").first()
        if existing_user:
            print("✅ Test user already exists")
            print(f"   Email: {existing_user.email}")
            print(f"   Name: {existing_user.first_name} {existing_user.last_name}")
            print(f"   Tenant ID: {existing_user.tenant_id}")
            return
        
        # Create test tenant
        test_tenant = Tenant(
            name="Test Organization",
            email="test.user@example.com",
            is_active=True
        )
        db.add(test_tenant)
        db.commit()
        db.refresh(test_tenant)
        
        print(f"✅ Test tenant created: {test_tenant.name} (ID: {test_tenant.id})")
        
        # Create tenant database
        success = tenant_db_manager.create_tenant_database(test_tenant.id, test_tenant.name)
        if success:
            print(f"✅ Tenant database created successfully")
        else:
            print(f"⚠️  Tenant database creation may have failed")
        
        # Create test user
        test_user = MasterUser(
            email="test.user@example.com",
            hashed_password=get_password_hash("testpassword123"),
            first_name="Test",
            last_name="User",
            tenant_id=test_tenant.id,
            role="admin",
            is_active=True,
            is_verified=True
        )
        
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print(f"✅ Test user created successfully")
        print(f"   Email: {test_user.email}")
        print(f"   Name: {test_user.first_name} {test_user.last_name}")
        print(f"   Tenant ID: {test_user.tenant_id}")
        print(f"   Role: {test_user.role}")
        
        # Create user in tenant database
        try:
            from core.models.database import set_tenant_context
            from core.models.models_per_tenant import User as TenantUser
            
            set_tenant_context(test_tenant.id)
            
            tenant_session = tenant_db_manager.get_tenant_session(test_tenant.id)
            tenant_db = tenant_session()
            
            try:
                tenant_user = TenantUser(
                    id=test_user.id,
                    email=test_user.email,
                    hashed_password=test_user.hashed_password,
                    first_name=test_user.first_name,
                    last_name=test_user.last_name,
                    role=test_user.role,
                    is_active=test_user.is_active,
                    is_verified=test_user.is_verified
                )
                
                tenant_db.add(tenant_user)
                tenant_db.commit()
                
                print(f"✅ Tenant user created successfully")
                
            finally:
                tenant_db.close()
                
        except Exception as e:
            print(f"⚠️  Warning: Failed to create tenant user: {str(e)}")
        
    except Exception as e:
        print(f"❌ Error creating test user: {str(e)}")
        db.rollback()
        
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user() 