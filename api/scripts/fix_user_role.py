#!/usr/bin/env python3
"""
Fix the admin user role
"""
import os
import sys

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import get_db
from models.models import User

def fix_user_role():
    """Fix the admin user role"""
    db = next(get_db())
    
    try:
        # Find the admin user
        admin_user = db.query(User).filter(User.email == "admin@example.com").first()
        
        if admin_user:
            # Update the role to admin
            admin_user.role = "admin"
            db.commit()
            print(f"✅ Updated admin user role to: {admin_user.role}")
            print(f"Email: {admin_user.email}")
            print(f"Is superuser: {admin_user.is_superuser}")
        else:
            print("❌ Admin user not found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_user_role() 