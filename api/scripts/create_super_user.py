#!/usr/bin/env python3
"""
Script to create a super user for the invoice system.
Super users can manage all tenants and users across the system.
"""

import os
import sys
import getpass
from datetime import datetime, timezone

# Add the parent directory to the path so we can import from the core module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants.password import MIN_PASSWORD_LENGTH
from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant
from core.utils.auth import get_password_hash

def create_super_user():
    """Create a super user"""
    db = next(get_master_db())
    
    try:
        print("🔧 Creating Super User")
        print("=" * 50)
        
        # Get user input
        email = input("Enter super user email: ").strip()
        if not email:
            print("❌ Email is required")
            return
            
        # Check if user already exists
        existing_user = db.query(MasterUser).filter(MasterUser.email == email).first()
        if existing_user:
            print(f"❌ User with email {email} already exists")
            
            # Ask if they want to make existing user a super user
            make_super = input("Do you want to make this user a super user? (y/n): ").strip().lower()
            if make_super == 'y':
                existing_user.is_superuser = True
                existing_user.role = "admin"
                db.commit()
                print(f"✅ User {email} is now a super user")
            return
        
        first_name = input("Enter first name: ").strip()
        last_name = input("Enter last name: ").strip()
        
        # Get password securely
        password = getpass.getpass("Enter password: ")
        password_confirm = getpass.getpass("Confirm password: ")
        
        if password != password_confirm:
            print("❌ Passwords do not match")
            return
        
        if len(password) < 6:
            print("❌ Password must be at least 6 characters long")
            return
        
        # Create or find a default tenant for the super user
        # Super users still need to be associated with a tenant
        super_admin_tenant = db.query(Tenant).filter(Tenant.name == "Super Admin").first()
        if not super_admin_tenant:
            print("Creating 'Super Admin' tenant...")
            super_admin_tenant = Tenant(
                name="Super Admin",
                email=email,
                is_active=True,
                default_currency="USD"
            )
            db.add(super_admin_tenant)
            db.commit()
            db.refresh(super_admin_tenant)
            print("✅ Super Admin tenant created")
        
        # Create the super user
        hashed_password = get_password_hash(password)
        super_user = MasterUser(
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            tenant_id=super_admin_tenant.id,
            role="admin",
            is_active=True,
            is_superuser=True,
            is_verified=True
        )
        
        db.add(super_user)
        db.commit()
        db.refresh(super_user)
        
        print("✅ Super user created successfully!")
        print(f"   Email: {email}")
        print(f"   Name: {first_name} {last_name}")
        print(f"   Tenant: {super_admin_tenant.name}")
        print(f"   Role: {super_user.role}")
        print(f"   Superuser: {super_user.is_superuser}")
        print("\n🔐 Super user can now:")
        print("   - Access all tenant databases")
        print("   - Create/edit/delete tenants")
        print("   - Manage users across all tenants")
        print("   - Access super-admin endpoints at /api/v1/super-admin/")
        
    except Exception as e:
        print(f"❌ Error creating super user: {e}")
        db.rollback()
    finally:
        db.close()

def list_super_users():
    """List all super users"""
    db = next(get_master_db())
    
    try:
        super_users = db.query(MasterUser).filter(MasterUser.is_superuser == True).all()
        
        if not super_users:
            print("No super users found")
            return
        
        print(f"\n📋 Super Users ({len(super_users)} found):")
        print("=" * 50)
        
        for user in super_users:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_name = tenant.name if tenant else "Unknown"
            
            print(f"   Email: {user.email}")
            print(f"   Name: {user.first_name} {user.last_name}")
            print(f"   Tenant: {tenant_name}")
            print(f"   Role: {user.role}")
            print(f"   Active: {user.is_active}")
            print(f"   Verified: {user.is_verified}")
            print(f"   Created: {user.created_at}")
            print("-" * 30)
            
    except Exception as e:
        print(f"❌ Error listing super users: {e}")
    finally:
        db.close()

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_super_users()
    else:
        create_super_user()

if __name__ == "__main__":
    main() 