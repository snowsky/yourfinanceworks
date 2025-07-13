#!/usr/bin/env python3

import sys
sys.path.append('./api')

from models.database import get_master_db, SessionLocal
from models.models import Client as MasterClient, Tenant, MasterUser
from services.tenant_database_manager import tenant_db_manager
from models.models_per_tenant import Client as TenantClient

def check_client_duplicates():
    print("🔍 Checking for duplicate clients...")
    
    # Get master database session
    master_db = SessionLocal()
    
    try:
        # Check clients in master database
        master_clients = master_db.query(MasterClient).all()
        print(f"\n📋 Clients in MASTER database: {len(master_clients)}")
        for client in master_clients:
            print(f"  - ID: {client.id}, Name: {client.name}, Email: {client.email}, Tenant: {client.tenant_id}")
        
        # Get tenants
        tenants = master_db.query(Tenant).all()
        print(f"\n🏢 Found {len(tenants)} tenants")
        
        # Check each tenant's database
        for tenant in tenants:
            print(f"\n🔍 Checking tenant '{tenant.name}' (ID: {tenant.id})...")
            
            try:
                # Get tenant database session
                tenant_session_factory = tenant_db_manager.get_tenant_session(tenant.id)
                if tenant_session_factory:
                    tenant_db = tenant_session_factory()
                    
                    # Check clients in tenant database
                    tenant_clients = tenant_db.query(TenantClient).all()
                    print(f"  📋 Clients in TENANT database: {len(tenant_clients)}")
                    for client in tenant_clients:
                        print(f"    - ID: {client.id}, Name: {client.name}, Email: {client.email}")
                    
                    tenant_db.close()
                else:
                    print(f"  ❌ Could not get tenant database session for tenant {tenant.id}")
                    
            except Exception as e:
                print(f"  ❌ Error accessing tenant database: {e}")
        
        # Check users
        print(f"\n👥 Users in MASTER database:")
        master_users = master_db.query(MasterUser).all()
        for user in master_users:
            print(f"  - ID: {user.id}, Email: {user.email}, Tenant: {user.tenant_id}")
    
    finally:
        master_db.close()

if __name__ == "__main__":
    check_client_duplicates() 