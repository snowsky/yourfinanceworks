#!/usr/bin/env python3
"""
Test to verify that the API is returning inventory information in invoice responses
"""

import requests
import json
from uuid import uuid4

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def get_auth_headers():
    """Get authentication headers"""
    try:
        unique_email = f"test_{uuid4().hex}@example.com"
        
        # Register user
        register_data = {
            "email": unique_email,
            "password": "testpassword123",
            "full_name": "Test User"
        }
        
        register_response = requests.post(f"{API_BASE}/auth/register", json=register_data)
        if register_response.status_code != 201:
            print(f"Failed to register: {register_response.status_code}")
            return None
            
        # Login
        login_data = {
            "email": unique_email,
            "password": "testpassword123"
        }
        
        login_response = requests.post(f"{API_BASE}/auth/login", json=login_data)
        if login_response.status_code != 200:
            print(f"Failed to login: {login_response.status_code}")
            return None
            
        token = login_response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
        
    except Exception as e:
        print(f"Error getting auth: {e}")
        return None

def test_api_response():
    """Test the API response format"""
    
    print("Testing API Response Format...")
    
    auth_headers = get_auth_headers()
    if not auth_headers:
        print("❌ Failed to authenticate")
        return
        
    try:
        # Create test data
        client_data = {"name": "Test Client", "email": "test@example.com"}
        client_response = requests.post(f"{API_BASE}/clients/", json=client_data, headers=auth_headers)
        client_id = client_response.json()["id"]
        
        inventory_data = {
            "name": "Test Item",
            "sku": "TEST-001",
            "unit_price": 25.99,
            "track_stock": True,
            "current_stock": 50,
            "unit_of_measure": "each"
        }
        inventory_response = requests.post(f"{API_BASE}/inventory/items/", json=inventory_data, headers=auth_headers)
        inventory_id = inventory_response.json()["id"]
        
        # Create invoice with inventory item
        invoice_data = {
            "client_id": client_id,
            "amount": 25.99,
            "currency": "USD",
            "status": "draft",
            "items": [{
                "inventory_item_id": inventory_id,
                "description": "Test Item",
                "quantity": 1,
                "price": 25.99
            }]
        }
        
        invoice_response = requests.post(f"{API_BASE}/invoices/", json=invoice_data, headers=auth_headers)
        if invoice_response.status_code != 201:
            print(f"❌ Failed to create invoice: {invoice_response.status_code}")
            print(f"Response: {invoice_response.text}")
            return
            
        invoice_id = invoice_response.json()["id"]
        print(f"✅ Created invoice with ID: {invoice_id}")
        
        # Test GET invoice
        get_response = requests.get(f"{API_BASE}/invoices/{invoice_id}", headers=auth_headers)
        if get_response.status_code != 200:
            print(f"❌ Failed to get invoice: {get_response.status_code}")
            return
            
        invoice_data = get_response.json()
        print(f"✅ Retrieved invoice successfully")
        
        # Check invoice structure
        print(f"\n📋 Invoice Structure:")
        print(f"- ID: {invoice_data.get('id')}")
        print(f"- Number: {invoice_data.get('number')}")
        print(f"- Items count: {len(invoice_data.get('items', []))}")
        
        # Check items structure
        items = invoice_data.get('items', [])
        if items:
            first_item = items[0]
            print(f"\n📋 First Item Structure:")
            print(f"- ID: {first_item.get('id')}")
            print(f"- Description: {first_item.get('description')}")
            print(f"- Inventory Item ID: {first_item.get('inventory_item_id')}")
            print(f"- Has inventory_item field: {'inventory_item' in first_item}")
            
            if 'inventory_item' in first_item:
                inventory_item = first_item['inventory_item']
                if inventory_item:
                    print(f"✅ Inventory item data found:")
                    print(f"  - Name: {inventory_item.get('name')}")
                    print(f"  - SKU: {inventory_item.get('sku')}")
                    print(f"  - Unit Price: {inventory_item.get('unit_price')}")
                    print(f"  - Current Stock: {inventory_item.get('current_stock')}")
                    print(f"  - Track Stock: {inventory_item.get('track_stock')}")
                else:
                    print(f"❌ inventory_item field is null")
            else:
                print(f"❌ No inventory_item field in response")
                
        # Test PUT invoice
        update_data = {
            "notes": "Updated via API test"
        }
        
        put_response = requests.put(f"{API_BASE}/invoices/{invoice_id}", json=update_data, headers=auth_headers)
        if put_response.status_code != 200:
            print(f"❌ Failed to update invoice: {put_response.status_code}")
            print(f"Response: {put_response.text}")
        else:
            updated_invoice = put_response.json()
            print(f"✅ Updated invoice successfully")
            
            # Check updated items structure
            updated_items = updated_invoice.get('items', [])
            if updated_items:
                first_updated_item = updated_items[0]
                print(f"\n📋 Updated Item Structure:")
                print(f"- Has inventory_item field: {'inventory_item' in first_updated_item}")
                
                if 'inventory_item' in first_updated_item and first_updated_item['inventory_item']:
                    print(f"✅ Inventory item data preserved after update")
                else:
                    print(f"❌ Inventory item data lost after update")
        
        # Cleanup
        requests.delete(f"{API_BASE}/invoices/{invoice_id}", headers=auth_headers)
        requests.delete(f"{API_BASE}/inventory/items/{inventory_id}", headers=auth_headers)
        requests.delete(f"{API_BASE}/clients/{client_id}", headers=auth_headers)
        
        print(f"\n🧹 Cleaned up test data")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    test_api_response()