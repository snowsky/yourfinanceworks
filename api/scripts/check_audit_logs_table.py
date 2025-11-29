#!/usr/bin/env python3
"""
Script to check if the audit_logs table exists in all tenant databases.
"""
import os
from sqlalchemy import create_engine, inspect
from core.models.database import SQLALCHEMY_DATABASE_URL, get_master_db
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager

def check_audit_logs_table():
    print("Checking audit_logs table for all tenants...")
    master_db = next(get_master_db())
    tenants = master_db.query(Tenant).all()
    for tenant in tenants:
        try:
            tenant_engine = create_engine(tenant_db_manager.get_tenant_database_url(tenant.id))
            inspector = inspect(tenant_engine)
            if 'audit_logs' in inspector.get_table_names():
                print(f"✓ Tenant {tenant.id} ({tenant.name}): audit_logs table exists.")
            else:
                print(f"✗ Tenant {tenant.id} ({tenant.name}): audit_logs table MISSING!")
        except Exception as e:
            print(f"✗ Tenant {tenant.id} ({tenant.name}): ERROR - {e}")
    master_db.close()

if __name__ == "__main__":
    check_audit_logs_table() 