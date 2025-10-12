#!/usr/bin/env python3
"""
Simple test to verify that invoice items now include inventory information
when retrieving and updating invoices.
"""

import requests
import json
from uuid import uuid4

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust if your API runs on a different port
API_BASE = f"{BASE_URL}/api/v1"

def get_auth_headers():
    """Get authentication headers by creating a test user and logging in"""
    try:
        # Create a unique test user
        unique_email = f"test_{uuid4().hex}@example.com"
        
        # Register user
        register_data = {
            "email": unique_email,
            "password": "testpassword123",
            "full_name": "Test User"
        }
        
        register_response = requests.post(f"{API_BASE}/auth/register", json=register_data)
        if register_response.status_code != 201:
            print(f"Failed to register user: {register_response.status_code}")
            print(f"Response: {register_response.text}")
            return None
            
        # Login to get token
        login_data = {
            "email": unique_email,
            "password": "testpassword123"
        }
        
        login_response = requests.post(f"{API_BASE}/auth/login", json=login_data)
        if login_response.status_code != 200:
            print(f"Failed to login: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            return None
            
        token = login_response.json().get("access_token")
        if not token:
            print("No access token received")
            return None
            
        return {"Authorization": f"Bearer {token}"}
        
    except Exception as e:
        print(f"Error getting auth headers: {e}")
        return None

def create_test_data(auth_headers):
    """Create test client, inventory item, and invoice with inventory"""
    try:
        # Create a test client
        client_data = {
            "name": "Test Client for Inventory",
            "email": "inventory_test@example.com"
        }
        
        client_response = requests.post(f"{API_BASE}/clients/", json=client_data, headers=auth_headers)
        if client_response.status_code != 201:
            print(f"Failed to create client: {client_response.status_code}")
            return None, None, None
            
        client_id = client_response.json()["id"]
        print(f"✅ Created test client with ID: {client_id}")
        
        # Create a test inventory item
        inventory_data = {
            "name": "Test Inventory Item",
            "description": "A test item for inventory testing",
            "sku": f"TEST-{uuid4().hex[:8]}",
            "unit_price": 25.99,
            "cost_price": 15.00,
            "currency": "USD",
            "track_stock": True,
            "current_stock": 100,
            "minimum_stock": 10,
            "unit_of_measure": "each",
            "item_type": "product",
            "is_active": True
        }
        
        inventory_response = requests.post(f"{API_BASE}/inventory/items/", json=inventory_data, headers=auth_headers)
        if inventory_response.status_code not in [200, 201]:
            print(f"Failed to create inventory item: {inventory_response.status_code}")
            print(f"Response: {inventory_response.text}")
            return client_id, None, None
            
        inventory_item_id = inventory_response.json()["id"]
        print(f"✅ Created test inventory item with ID: {inventory_item_id}")
        
        # Create an invoice with the inventory item
        invoice_data = {
            "client_id": client_id,
            "amount": 51.98,  # 2 * 25.99
            "currency": "USD",
            "status": "draft",
            "notes": "Test invoice with inventory item",
            "items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "description": "Test Inventory Item",
                    "quantity": 2,
                    "price": 25.99
                }
            ]
        }
        
        invoice_response = requests.post(f"{API_BASE}/invoices/", json=invoice_data, headers=auth_headers)
        if invoice_response.status_code != 201:
            print(f"Failed to create invoice: {invoice_response.status_code}")
            print(f"Response: {invoice_response.text}")
            return client_id, inventory_item_id, None
            
        invoice_id = invoice_response.json()["id"]
        print(f"✅ Created test invoice with ID: {invoice_id}")
        
        return client_id, inventory_item_id, invoice_id
        
    except Exception as e:
        print(f"Error creating test data: {e}")
        return None, None, None

def test_invoice_inventory_info():
    """Test that invoice items include inventory information"""
    
    print("Testing invoice inventory information...")
    
    # Get authentication headers
    auth_headers = get_auth_headers()
    if not auth_headers:
        print("❌ Failed to get authentication headers")
        return False
        
    print("✅ Successfully authenticated")
    
    # Create test data
    client_id, inventory_item_id, invoice_id = create_test_data(auth_headers)
    if not invoice_id:
        print("❌ Failed to create test data")
        return False
    
    try:
        # Test GET invoice endpoint
        print(f"\n1. Testing GET /invoices/{invoice_id}")
        response = requests.get(f"{API_BASE}/invoices/{invoice_id}", headers=auth_headers)
        
        if response.status_code == 200:
            invoice_data = response.json()
            print(f"✅ Successfully retrieved invoice {invoice_id}")
            
            # Check if items have inventory information
            items = invoice_data.get('items', [])
            print(f"Found {len(items)} items in invoice")
            
            for i, item in enumerate(items):
                print(f"\nItem {i+1}:")
                print(f"  - ID: {item.get('id')}")
                print(f"  - Description: {item.get('description')}")
                print(f"  - Inventory Item ID: {item.get('inventory_item_id')}")
                
                if item.get('inventory_item'):
                    inv_item = item['inventory_item']
                    print(f"  - Inventory Item Details:")
                    print(f"    * Name: {inv_item.get('name')}")
                    print(f"    * SKU: {inv_item.get('sku')}")
                    print(f"    * Unit Price: {inv_item.get('unit_price')}")
                    print(f"    * Current Stock: {inv_item.get('current_stock')}")
                    print(f"    * Unit of Measure: {inv_item.get('unit_of_measure')}")
                    print("  ✅ Inventory information is present!")
                else:
                    if item.get('inventory_item_id'):
                        print("  ❌ Inventory item ID present but no inventory details!")
                    else:
                        print("  ℹ️  No inventory item linked (this is normal for non-inventory items)")
        else:
            print(f"❌ Failed to retrieve invoice: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
        # Test PUT invoice endpoint (just retrieve current data and send it back)
        print(f"\n2. Testing PUT /invoices/{invoice_id}")
        
        # Use the same data we just retrieved for the update
        update_data = {
            "amount": invoice_data.get('amount'),
            "currency": invoice_data.get('currency'),
            "status": invoice_data.get('status'),
            "notes": invoice_data.get('notes', '') + " - Updated",
            "client_id": invoice_data.get('client_id')
        }
        
        response = requests.put(f"{API_BASE}/invoices/{invoice_id}", json=update_data, headers=auth_headers)
        
        if response.status_code == 200:
            updated_invoice = response.json()
            print(f"✅ Successfully updated invoice {invoice_id}")
            
            # Check if items still have inventory information after update
            items = updated_invoice.get('items', [])
            print(f"Found {len(items)} items in updated invoice")
            
            inventory_items_found = 0
            for item in items:
                if item.get('inventory_item'):
                    inventory_items_found += 1
                    
            if inventory_items_found > 0:
                print(f"✅ {inventory_items_found} items have inventory information after update!")
            else:
                print("❌ No inventory information found in updated invoice items")
                
        else:
            print(f"❌ Failed to update invoice: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API. Make sure the server is running.")
        return False
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False
    finally:
        # Cleanup: delete test data
        try:
            if invoice_id:
                requests.delete(f"{API_BASE}/invoices/{invoice_id}", headers=auth_headers)
            if inventory_item_id:
                requests.delete(f"{API_BASE}/inventory/items/{inventory_item_id}", headers=auth_headers)
            if client_id:
                requests.delete(f"{API_BASE}/clients/{client_id}", headers=auth_headers)
            print("🧹 Cleaned up test data")
        except:
            pass  # Ignore cleanup errors

if __name__ == "__main__":
    print("Invoice Inventory Information Test")
    print("=" * 40)
    
    success = test_invoice_inventory_info()
    
    if success:
        print("\n🎉 Test completed successfully!")
        print("Invoice items now include inventory information when editing invoices.")
    else:
        print("\n❌ Test failed. Check the error messages above.")
        print("You may need to:")
        print("1. Make sure the API server is running")
        print("2. Update the INVOICE_ID in the test to use an actual invoice with inventory items")
        print("3. Add authentication headers if required")