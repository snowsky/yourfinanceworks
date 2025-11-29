import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.models import MasterUser, Tenant
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager
from core.models.database import get_master_db

# Set up master DB session
def get_master_session():
    return next(get_master_db())

def check_orphaned_users():
    master_db = get_master_session()
    users = master_db.query(MasterUser).all()
    print(f"Checking {len(users)} users in master DB...")
    for user in users:
        tenant_id = user.tenant_id
        if not tenant_id:
            print(f"User {user.email} (id={user.id}) has no tenant_id, skipping.")
            continue
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
            tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user.id).first()
            if not tenant_user:
                print(f"ORPHANED: User {user.email} (id={user.id}) exists in master DB but not in tenant DB {tenant_id}")
            tenant_session.close()
        except Exception as e:
            print(f"Error checking tenant DB {tenant_id} for user {user.email}: {e}")
    master_db.close()

if __name__ == "__main__":
    check_orphaned_users() 