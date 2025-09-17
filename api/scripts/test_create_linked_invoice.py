#!/usr/bin/env python3
"""
Test to create an invoice properly linked to inventory and verify the UI shows the information
"""

import requests
import json
from uuid import uuid4

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def get_auth_headers():
    """Get authentication headers"""
    try:
        unique_email = f"test_{uuid4().hex}@example.com"
        
        # Register and login
        register_data = {
            "email": unique_email,
            "password": "testpassword123",
            "full_name": "Test User"
        }
        
        register_response = requests.post(f"{API_BASE}/auth/register", json=register_data)
        if register_response.status_code != 201:
            return None
            
        login_data = {
            "email": unique_email,
            "password": "testpassword123"
        }
        
        login_response = requests.post(f"{API_BASE}/auth/login", json=login_data)
        if login_response.status_code != 200:
            return None
            
        token = login_response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
        
    except Exception as e:
        print(f"Auth error: {e}")
        return None

def create_linked_invoice():
    """Create an invoice properly linked to inventory"""
    
    print("Creating Invoice Linked to Inventory...")
    
    auth_headers = get_auth_headers()
    if not auth_headers:
        print("❌ Failed to authenticate")
        return None, None, None
        
    try:
        # 1. Create client
        client_data = {"name": "Test Client for Linking", "email": "linking@example.com"}
        client_response = requests.post(f"{API_BASE}/clients/", json=client_data, headers=auth_headers)
        client_id = client_response.json()["id"]
        print(f"✅ Created client: {client_id}")
        
        # 2. Create inventory item
        inventory_data = {
            "name": "Linked Test Item",
            "description": "This item should be linked to the invoice",
            "sku": f"LINK-{uuid4().hex[:8]}",
            "unit_price": 49.99,
            "cost_price": 25.00,
            "track_stock": True,
            "current_stock": 75,
            "minimum_stock": 10,
            "unit_of_measure": "pieces",
            "item_type": "product",
            "is_active": True
        }
        
        inventory_response = requests.post(f"{API_BASE}/inventory/items/", json=inventory_data, headers=auth_headers)
        if inventory_response.status_code not in [200, 201]:
            print(f"❌ Failed to create inventory: {inventory_response.status_code}")
            return None, None, None
            
        inventory_id = inventory_response.json()["id"]
        print(f"✅ Created inventory item: {inventory_id}")
        print(f"   - Name: {inventory_data['name']}")
        print(f"   - SKU: {inventory_data['sku']}")
        print(f"   - Stock: {inventory_data['current_stock']}")
        
        # 3. Create invoice with proper inventory linking
        invoice_data = {
            "client_id": client_id,
            "amount": 99.98,  # 2 * 49.99
            "currency": "USD",
            "status": "draft",
            "notes": "Test invoice with inventory linking",
            "items": [{
                "inventory_item_id": inventory_id,  # This is the key field!
                "description": inventory_data['name'],
                "quantity": 2,
                "price": inventory_data['unit_price'],
                "unit_of_measure": inventory_data['unit_of_measure']
            }]
        }
        
        invoice_response = requests.post(f"{API_BASE}/invoices/", json=invoice_data, headers=auth_headers)
        if invoice_response.status_code != 201:
            print(f"❌ Failed to create invoice: {invoice_response.status_code}")
            print(f"Response: {invoice_response.text}")
            return client_id, inventory_id, None
            
        invoice_id = invoice_response.json()["id"]
        print(f"✅ Created linked invoice: {invoice_id}")
        
        # 4. Verify the linking worked
        get_response = requests.get(f"{API_BASE}/invoices/{invoice_id}", headers=auth_headers)
        if get_response.status_code == 200:
            invoice_data = get_response.json()
            items = invoice_data.get('items', [])
            
            if items and items[0].get('inventory_item_id'):
                print(f"✅ Invoice item is linked to inventory ID: {items[0]['inventory_item_id']}")
                
                if items[0].get('inventory_item'):
                    inv_item = items[0]['inventory_item']
                    print(f"✅ Inventory details included in response:")
                    print(f"   - Name: {inv_item.get('name')}")
                    print(f"   - SKU: {inv_item.get('sku')}")
                    print(f"   - Current Stock: {inv_item.get('current_stock')}")
                else:
                    print(f"❌ No inventory_item details in response")
            else:
                print(f"❌ Invoice item not linked to inventory")
        
        return client_id, inventory_id, invoice_id
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None, None

def main():
    print("🔗 Testing Invoice-Inventory Linking")
    print("=" * 50)
    
    client_id, inventory_id, invoice_id = create_linked_invoice()
    
    if invoice_id:
        print(f"\n🎉 SUCCESS! Created linked invoice.")
        print(f"\n📋 Next Steps:")
        print(f"1. Go to your web app")
        print(f"2. Navigate to Invoices")
        print(f"3. Find invoice #{invoice_id}")
        print(f"4. Click 'Edit' on that invoice")
        print(f"5. Look for inventory information below the items")
        print(f"\n🔍 You should see:")
        print(f"- Package icon (📦) next to the item")
        print(f"- 'Inventory Information' section with:")
        print(f"  * Item name: Linked Test Item")
        print(f"  * SKU: LINK-xxxxxxxx")
        print(f"  * Current Stock: 75 pieces")
        print(f"  * Unit Price: $49.99")
        
        # Don't cleanup automatically so user can test
        print(f"\n⚠️  Test data created (not cleaned up):")
        print(f"- Client ID: {client_id}")
        print(f"- Inventory ID: {inventory_id}")
        print(f"- Invoice ID: {invoice_id}")
        
    else:
        print(f"\n❌ Failed to create linked invoice")

if __name__ == "__main__":
    main()