#!/usr/bin/env python3
"""
Promote a user with a specific email to super admin.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import SessionLocal
from models.models import MasterUser

def promote_to_super_admin(email: str):
    db = SessionLocal()
    try:
        user = db.query(MasterUser).filter(MasterUser.email == email).first()
        if not user:
            print(f"❌ User with email '{email}' not found.")
            return
        if user.is_superuser:
            print(f"✅ User '{email}' is already a super admin.")
            return
        user.is_superuser = True
        user.role = 'admin'
        db.commit()
        print(f"✅ User '{email}' has been promoted to super admin.")
    except Exception as e:
        print(f"❌ Error promoting user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python promote_to_super_admin.py user@example.com")
        sys.exit(1)
    promote_to_super_admin(sys.argv[1]) 