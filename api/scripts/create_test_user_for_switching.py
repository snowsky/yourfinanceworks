#!/usr/bin/env python3
"""
Script to create a test user for organization switching
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant, user_tenant_association
from core.utils.auth import get_password_hash
from sqlalchemy.orm import joinedload

def create_test_user():
    """Create a test user with access to multiple organizations"""
    master_db = next(get_master_db())
    
    try:
        # Check if test user already exists
        test_email = "test@example.com"
        existing_user = master_db.query(MasterUser).filter(MasterUser.email == test_email).first()
        
        if existing_user:
            print(f"Test user {test_email} already exists (ID: {existing_user.id})")
            user = existing_user
        else:
            # Get the first tenant as primary
            first_tenant = master_db.query(Tenant).first()
            if not first_tenant:
                print("No tenants found in the system")
                return
            
            # Create test user
            hashed_password = get_password_hash("testpass123")
            user = MasterUser(
                email=test_email,
                hashed_password=hashed_password,
                first_name="Test",
                last_name="User",
                tenant_id=first_tenant.id,
                role="admin",
                is_active=True,
                is_superuser=False,
                is_verified=True
            )
            
            master_db.add(user)
            master_db.commit()
            master_db.refresh(user)
            print(f"Created test user {test_email} (ID: {user.id})")
        
        # Get all tenants
        all_tenants = master_db.query(Tenant).all()
        print(f"Found {len(all_tenants)} tenants in the system")
        
        # Add user to all tenants (for testing purposes)
        for tenant in all_tenants:
            # Check if association already exists
            existing_association = master_db.execute(
                user_tenant_association.select().where(
                    user_tenant_association.c.user_id == user.id,
                    user_tenant_association.c.tenant_id == tenant.id
                )
            ).first()
            
            if not existing_association:
                # Insert new association
                master_db.execute(
                    user_tenant_association.insert().values(
                        user_id=user.id,
                        tenant_id=tenant.id,
                        role="admin",
                        is_active=True
                    )
                )
                print(f"Added user to tenant {tenant.name} (ID: {tenant.id})")
            else:
                print(f"User already associated with tenant {tenant.name} (ID: {tenant.id})")
        
        master_db.commit()
        
        # Verify associations
        tenant_memberships = master_db.execute(
            user_tenant_association.select().where(
                user_tenant_association.c.user_id == user.id
            )
        ).fetchall()
        
        print(f"\nTest user {test_email} now has access to {len(tenant_memberships)} organizations:")
        for membership in tenant_memberships:
            tenant = master_db.query(Tenant).filter(Tenant.id == membership.tenant_id).first()
            print(f"  - {tenant.name} (ID: {tenant.id}) - Role: {membership.role}")
        
        print(f"\nYou can now test organization switching with:")
        print(f"  Email: {test_email}")
        print(f"  Password: testpass123")
        
    finally:
        master_db.close()

if __name__ == "__main__":
    create_test_user()