#!/usr/bin/env python3
"""
Script to populate user_tenant_association table for existing users
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db
from core.models.models import MasterUser, user_tenant_association
from sqlalchemy.orm import Session

def populate_user_tenant_associations():
    """Add existing users to the user_tenant_association table"""
    master_db = next(get_master_db())
    
    try:
        # Get all users
        users = master_db.query(MasterUser).all()
        
        for user in users:
            # Check if user already has associations
            existing = master_db.execute(
                user_tenant_association.select().where(
                    user_tenant_association.c.user_id == user.id
                )
            ).fetchall()
            
            if not existing and user.tenant_id:
                # Add user to their primary tenant
                master_db.execute(
                    user_tenant_association.insert().values(
                        user_id=user.id,
                        tenant_id=user.tenant_id,
                        role=user.role or 'user'
                    )
                )
                print(f"Added user {user.email} to tenant {user.tenant_id}")
        
        master_db.commit()
        print("Successfully populated user tenant associations")
        
    except Exception as e:
        master_db.rollback()
        print(f"Error: {e}")
    finally:
        master_db.close()

if __name__ == "__main__":
    populate_user_tenant_associations()