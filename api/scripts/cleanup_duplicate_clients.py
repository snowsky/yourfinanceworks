#!/usr/bin/env python3

import sys
sys.path.append('./api')

from models.database import get_master_db, SessionLocal
from models.models import Tenant, MasterUser
from services.tenant_database_manager import tenant_db_manager
from models.models_per_tenant import Client, Invoice, Payment
from sqlalchemy import func
from collections import defaultdict

def cleanup_duplicate_clients():
    """Clean up duplicate clients by merging their data"""
    print("🧹 Cleaning up duplicate clients...")
    
    # Get master database session
    master_db = SessionLocal()
    
    try:
        # Get all tenants
        tenants = master_db.query(Tenant).all()
        print(f"🏢 Found {len(tenants)} tenants")
        
        total_duplicates_removed = 0
        
        for tenant in tenants:
            print(f"\n🔍 Processing tenant '{tenant.name}' (ID: {tenant.id})...")
            
            try:
                # Get tenant database session
                tenant_session_factory = tenant_db_manager.get_tenant_session(tenant.id)
                if not tenant_session_factory:
                    print(f"  ❌ Could not get tenant database session for tenant {tenant.id}")
                    continue
                
                tenant_db = tenant_session_factory()
                
                # Find duplicate clients (same name and email)
                duplicates = tenant_db.query(
                    Client.name,
                    Client.email,
                    func.count(Client.id).label('count')
                ).group_by(
                    Client.name,
                    Client.email
                ).having(
                    func.count(Client.id) > 1
                ).all()
                
                print(f"  📋 Found {len(duplicates)} sets of duplicate clients")
                
                for name, email, count in duplicates:
                    print(f"    🔍 Processing duplicates for '{name}' ({email}) - {count} duplicates")
                    
                    # Get all clients with this name and email, ordered by ID (oldest first)
                    duplicate_clients = tenant_db.query(Client).filter(
                        Client.name == name,
                        Client.email == email
                    ).order_by(Client.id).all()
                    
                    if len(duplicate_clients) <= 1:
                        continue
                    
                    # Keep the first client (oldest)
                    client_to_keep = duplicate_clients[0]
                    clients_to_remove = duplicate_clients[1:]
                    
                    print(f"      ✅ Keeping client ID {client_to_keep.id}")
                    print(f"      🗑️  Removing clients: {[c.id for c in clients_to_remove]}")
                    
                    # Update invoices and payments to point to the kept client
                    for client_to_remove in clients_to_remove:
                        # Update invoices
                        invoices_updated = tenant_db.query(Invoice).filter(
                            Invoice.client_id == client_to_remove.id
                        ).update({Invoice.client_id: client_to_keep.id})
                        
                        # Update payments (through invoices)
                        payments_updated = 0
                        invoices_for_client = tenant_db.query(Invoice).filter(
                            Invoice.client_id == client_to_remove.id
                        ).all()
                        
                        for invoice in invoices_for_client:
                            payment_count = tenant_db.query(Payment).filter(
                                Payment.invoice_id == invoice.id
                            ).count()
                            payments_updated += payment_count
                        
                        print(f"        📄 Updated {invoices_updated} invoices")
                        print(f"        💰 Will update {payments_updated} payments")
                        
                        # Merge client data if needed (take non-null values)
                        if client_to_remove.phone and not client_to_keep.phone:
                            client_to_keep.phone = client_to_remove.phone
                        if client_to_remove.address and not client_to_keep.address:
                            client_to_keep.address = client_to_remove.address
                        if client_to_remove.preferred_currency and not client_to_keep.preferred_currency:
                            client_to_keep.preferred_currency = client_to_remove.preferred_currency
                        
                        # Add balances if they exist
                        if client_to_remove.balance:
                            client_to_keep.balance = (client_to_keep.balance or 0) + client_to_remove.balance
                        if client_to_remove.paid_amount:
                            client_to_keep.paid_amount = (client_to_keep.paid_amount or 0) + client_to_remove.paid_amount
                        
                        # Delete the duplicate client
                        tenant_db.delete(client_to_remove)
                        total_duplicates_removed += 1
                    
                    # Save changes for this duplicate set
                    tenant_db.commit()
                    print(f"      ✅ Merged data and removed {len(clients_to_remove)} duplicates")
                
                tenant_db.close()
                
            except Exception as e:
                print(f"  ❌ Error processing tenant {tenant.id}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n🎉 Cleanup complete! Removed {total_duplicates_removed} duplicate clients")
        
    finally:
        master_db.close()

def preview_duplicates():
    """Preview what duplicates would be cleaned up without actually doing it"""
    print("👀 Previewing duplicate clients...")
    
    # Get master database session
    master_db = SessionLocal()
    
    try:
        # Get all tenants
        tenants = master_db.query(Tenant).all()
        print(f"🏢 Found {len(tenants)} tenants")
        
        total_duplicates_found = 0
        
        for tenant in tenants:
            print(f"\n🔍 Checking tenant '{tenant.name}' (ID: {tenant.id})...")
            
            try:
                # Get tenant database session
                tenant_session_factory = tenant_db_manager.get_tenant_session(tenant.id)
                if not tenant_session_factory:
                    print(f"  ❌ Could not get tenant database session for tenant {tenant.id}")
                    continue
                
                tenant_db = tenant_session_factory()
                
                # Find duplicate clients
                duplicates = tenant_db.query(
                    Client.name,
                    Client.email,
                    func.count(Client.id).label('count')
                ).group_by(
                    Client.name,
                    Client.email
                ).having(
                    func.count(Client.id) > 1
                ).all()
                
                print(f"  📋 Found {len(duplicates)} sets of duplicate clients")
                
                for name, email, count in duplicates:
                    print(f"    🔍 '{name}' ({email}) - {count} duplicates")
                    
                    # Get all clients with this name and email
                    duplicate_clients = tenant_db.query(Client).filter(
                        Client.name == name,
                        Client.email == email
                    ).order_by(Client.id).all()
                    
                    for client in duplicate_clients:
                        print(f"      - ID: {client.id}, Created: {client.created_at}")
                    
                    total_duplicates_found += count - 1  # subtract 1 because we keep one
                
                tenant_db.close()
                
            except Exception as e:
                print(f"  ❌ Error checking tenant {tenant.id}: {e}")
        
        print(f"\n📊 Total duplicates that would be removed: {total_duplicates_found}")
        
    finally:
        master_db.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        preview_duplicates()
    else:
        print("🚨 WARNING: This will permanently delete duplicate clients!")
        print("🚨 Run with --preview flag first to see what would be removed.")
        print("🚨 Make sure to backup your database before running this!")
        
        response = input("\nDo you want to proceed? (type 'yes' to confirm): ")
        if response.lower() == 'yes':
            cleanup_duplicate_clients()
        else:
            print("❌ Cleanup cancelled") 