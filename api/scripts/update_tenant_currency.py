#!/usr/bin/env python3
"""
Update Tenant Default Currency Script

This script allows you to update the default currency for a tenant.
When users create new clients, they will use this default currency.

Usage:
    python update_tenant_currency.py

The script will prompt you for:
- Your email address (to identify your tenant)
- New default currency code (e.g., USD, EUR, GBP, CAD, JPY)
"""

import sys
import os

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_master_db
from models.models import Tenant, MasterUser

def update_tenant_currency():
    """Update tenant default currency interactively"""
    master_db = next(get_master_db())
    
    try:
        print("🏢 Tenant Default Currency Updater")
        print("=" * 40)
        
        # Get user email
        user_email = input("Enter your email address: ").strip()
        if not user_email:
            print("❌ Email is required")
            return
        
        # Find user
        user = master_db.query(MasterUser).filter(MasterUser.email == user_email).first()
        if not user:
            print(f"❌ User with email '{user_email}' not found")
            return
        
        # Find user's tenant
        tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            print("❌ Tenant not found for this user")
            return
        
        # Display current info
        print(f"\n📋 Current Information:")
        print(f"   User: {user.first_name} {user.last_name} ({user.email})")
        print(f"   Organization: {tenant.name} (ID: {tenant.id})")
        print(f"   Current Default Currency: {tenant.default_currency}")
        
        # Get new currency
        print(f"\n💱 Common Currency Codes:")
        print("   USD - US Dollar")
        print("   EUR - Euro")
        print("   GBP - British Pound")
        print("   CAD - Canadian Dollar")
        print("   JPY - Japanese Yen")
        print("   AUD - Australian Dollar")
        print("   CHF - Swiss Franc")
        print("   CNY - Chinese Yuan")
        print("   INR - Indian Rupee")
        print("   BRL - Brazilian Real")
        
        new_currency = input(f"\nEnter new default currency code (current: {tenant.default_currency}): ").strip().upper()
        
        if not new_currency:
            print("❌ Currency code is required")
            return
            
        if len(new_currency) != 3:
            print("❌ Currency code must be exactly 3 letters (e.g., USD, EUR, GBP)")
            return
        
        if new_currency == tenant.default_currency:
            print(f"ℹ️  Currency is already set to {new_currency}")
            return
        
        # Confirm change
        confirm = input(f"\n⚠️  Change default currency from {tenant.default_currency} to {new_currency}? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ Operation cancelled")
            return
        
        # Update currency
        tenant.default_currency = new_currency
        master_db.commit()
        
        print(f"\n✅ Success!")
        print(f"   Organization: {tenant.name}")
        print(f"   Default Currency: {tenant.default_currency}")
        print(f"\n💡 Note: Refresh your browser to see the new default currency in client forms")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        master_db.rollback()
    finally:
        master_db.close()

def list_all_tenants():
    """List all tenants and their current default currencies"""
    master_db = next(get_master_db())
    
    try:
        print("🏢 All Tenants and Their Default Currencies")
        print("=" * 50)
        
        tenants = master_db.query(Tenant).order_by(Tenant.id).all()
        
        if not tenants:
            print("No tenants found")
            return
        
        for tenant in tenants:
            # Count users in this tenant
            user_count = master_db.query(MasterUser).filter(MasterUser.tenant_id == tenant.id).count()
            
            print(f"   ID: {tenant.id}")
            print(f"   Name: {tenant.name}")
            print(f"   Default Currency: {tenant.default_currency}")
            print(f"   Users: {user_count}")
            print(f"   Active: {'Yes' if tenant.is_active else 'No'}")
            print("-" * 30)
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        master_db.close()

def main():
    """Main function with menu"""
    print("🏢 Tenant Currency Management")
    print("=" * 30)
    print("1. Update your tenant's default currency")
    print("2. List all tenants and their currencies")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        update_tenant_currency()
    elif choice == "2":
        list_all_tenants()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()