#!/usr/bin/env python3
"""
Script to check and update user roles
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from core.models.database import get_master_db
from core.models.models import MasterUser
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager

def check_and_promote_user():
    # Get master database session
    master_db = next(get_master_db())
    
    try:
        # Get user email from input
        email = input("Enter user email to check/promote: ").strip()
        
        if not email:
            print("Email is required")
            return
        
        # Find user in master database
        user = master_db.query(MasterUser).filter(MasterUser.email == email).first()
        
        if not user:
            print(f"User {email} not found in master database")
            return
        
        print(f"User: {user.email}")
        print(f"Current role: {user.role}")
        print(f"Is superuser: {user.is_superuser}")
        print(f"Tenant ID: {user.tenant_id}")
        
        # Ask if user wants to promote to admin
        if user.role != "admin":
            promote = input(f"Promote {email} to admin? (y/n): ").strip().lower()
            
            if promote == 'y':
                # Update in master database
                user.role = "admin"
                master_db.commit()
                print(f"Updated {email} to admin in master database")
                
                # Update in tenant database
                try:
                    tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)
                    tenant_db = tenant_session()
                    
                    tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user.id).first()
                    if tenant_user:
                        tenant_user.role = "admin"
                        tenant_db.commit()
                        print(f"Updated {email} to admin in tenant database")
                    else:
                        print(f"User {email} not found in tenant database")
                    
                    tenant_db.close()
                except Exception as e:
                    print(f"Error updating tenant database: {e}")
        else:
            print(f"User {email} is already an admin")
            
    finally:
        master_db.close()

if __name__ == "__main__":
    check_and_promote_user()