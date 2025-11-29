#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db
from core.models.models import Tenant
from core.models.models_per_tenant import SupportedCurrency
from core.services.tenant_database_manager import tenant_db_manager
from datetime import datetime, timezone

# Basic currencies to seed
CURRENCIES = [
    {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2},
    {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2},
    {"code": "GBP", "name": "British Pound", "symbol": "£", "decimal_places": 2},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimal_places": 0},
    {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$", "decimal_places": 2},
    {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "decimal_places": 2},
    {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF", "decimal_places": 2},
    {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥", "decimal_places": 2},
    {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "decimal_places": 2},
    {"code": "BRL", "name": "Brazilian Real", "symbol": "R$", "decimal_places": 2},
]

def seed_currencies_for_tenant(tenant_id: int):
    """Seed currencies for a specific tenant"""
    try:
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        db = tenant_session()
        
        for currency_data in CURRENCIES:
            # Check if currency already exists
            existing = db.query(SupportedCurrency).filter(
                SupportedCurrency.code == currency_data["code"]
            ).first()
            
            if not existing:
                currency = SupportedCurrency(
                    code=currency_data["code"],
                    name=currency_data["name"],
                    symbol=currency_data["symbol"],
                    decimal_places=currency_data["decimal_places"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(currency)
                print(f"Added currency: {currency_data['code']} - {currency_data['name']}")
        
        db.commit()
        print(f"✅ Successfully seeded currencies for tenant {tenant_id}")
        
    except Exception as e:
        print(f"❌ Error seeding currencies for tenant {tenant_id}: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Seed currencies for all tenants"""
    master_db = next(get_master_db())
    
    try:
        # Get all tenants
        tenants = master_db.query(Tenant).all()
        
        if not tenants:
            print("No tenants found. Please create a tenant first.")
            return
        
        print(f"Found {len(tenants)} tenants. Seeding currencies...")
        
        for tenant in tenants:
            print(f"\nSeeding currencies for tenant: {tenant.name} (ID: {tenant.id})")
            seed_currencies_for_tenant(tenant.id)
        
        print(f"\n✅ Currency seeding completed for all tenants!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        master_db.close()

if __name__ == "__main__":
    main()