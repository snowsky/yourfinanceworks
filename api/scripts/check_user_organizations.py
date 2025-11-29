#!/usr/bin/env python3
"""
Script to check user organizations and tenant associations
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant, user_tenant_association
from sqlalchemy.orm import joinedload

def check_user_organizations():
    """Check user organizations and tenant associations"""
    master_db = next(get_master_db())
    
    try:
        # Get all users
        users = master_db.query(MasterUser).options(joinedload(MasterUser.tenants)).all()
        
        print(f"Found {len(users)} users in the system:")
        print("-" * 50)
        
        for user in users:
            print(f"User: {user.email} (ID: {user.id})")
            print(f"  Primary Tenant ID: {user.tenant_id}")
            print(f"  Role: {user.role}")
            print(f"  Is Superuser: {user.is_superuser}")
            
            # Get tenant memberships from association table
            tenant_memberships = master_db.execute(
                user_tenant_association.select().where(
                    user_tenant_association.c.user_id == user.id
                )
            ).fetchall()
            
            # Get all tenant IDs user has access to (including primary tenant)
            tenant_ids = [membership.tenant_id for membership in tenant_memberships]
            if user.tenant_id and user.tenant_id not in tenant_ids:
                tenant_ids.append(user.tenant_id)
            
            print(f"  Tenant Memberships: {len(tenant_memberships)}")
            for membership in tenant_memberships:
                tenant = master_db.query(Tenant).filter(Tenant.id == membership.tenant_id).first()
                print(f"    - Tenant {membership.tenant_id}: {tenant.name if tenant else 'Unknown'} (Role: {membership.role})")
            
            # Get tenant details for all accessible tenants
            if tenant_ids:
                tenants = master_db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
                print(f"  Accessible Organizations: {len(tenants)}")
                for tenant in tenants:
                    is_primary = tenant.id == user.tenant_id
                    print(f"    - {tenant.name} (ID: {tenant.id}){' [PRIMARY]' if is_primary else ''}")
            else:
                print("  No accessible organizations found")
            
            print()
        
        # Show all tenants in the system
        all_tenants = master_db.query(Tenant).all()
        print(f"All tenants in the system ({len(all_tenants)}):")
        print("-" * 50)
        for tenant in all_tenants:
            print(f"  - {tenant.name} (ID: {tenant.id}) - Active: {tenant.is_active}")
        
    finally:
        master_db.close()

if __name__ == "__main__":
    check_user_organizations()