#!/usr/bin/env python3
"""
Create test inventory and invoice data using existing user credentials
"""

import requests
import json
from uuid import uuid4

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def get_auth_token():
    """Get authentication token using existing user credentials"""
    print("Please provide your login credentials:")
    email = input("Email: ")
    password = input("Password: ")
    
    try:
        login_data = {
            "email": email,
            "password": password
        }
        
        login_response = requests.post(f"{API_BASE}/auth/login", json=login_data)
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            return None
            
        token = login_response.json().get("access_token")
        if token:
            print("✅ Successfully logged in!")
            return {"Authorization": f"Bearer {token}"}
        else:
            print("❌ No access token received")
            return None
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def create_test_data_in_your_account():
    """Create test data in your existing account"""
    
    print("🔗 Creating Test Data in Your Account")
    print("=" * 50)
    
    # Get your credentials
    auth_headers = get_auth_token()
    if not auth_headers:
        return
    
    try:
        # Check if you already have clients
        clients_response = requests.get(f"{API_BASE}/clients/", headers=auth_headers)
        existing_clients = clients_response.json() if clients_response.status_code == 200 else []
        
        if existing_clients:
            print(f"✅ Found {len(existing_clients)} existing clients")
            client_id = existing_clients[0]["id"]
            client_name = existing_clients[0]["name"]
            print(f"   Using client: {client_name} (ID: {client_id})")
        else:
            # Create a test client
            client_data = {
                "name": "Test Client for Inventory Linking",
                "email": "inventory_test@example.com"
            }
            
            client_response = requests.post(f"{API_BASE}/clients/", json=client_data, headers=auth_headers)
            if client_response.status_code != 201:
                print(f"❌ Failed to create client: {client_response.status_code}")
                return
                
            client_id = client_response.json()["id"]
            client_name = client_data["name"]
            print(f"✅ Created new client: {client_name} (ID: {client_id})")
        
        # Create inventory item
        inventory_data = {
            "name": "Test Inventory Item for Linking",
            "description": "This item will be linked to an invoice to test the feature",
            "sku": f"TEST-LINK-{uuid4().hex[:8].upper()}",
            "unit_price": 75.50,
            "cost_price": 45.00,
            "track_stock": True,
            "current_stock": 25,
            "minimum_stock": 5,
            "unit_of_measure": "units",
            "item_type": "product",
            "is_active": True
        }
        
        inventory_response = requests.post(f"{API_BASE}/inventory/items/", json=inventory_data, headers=auth_headers)
        if inventory_response.status_code not in [200, 201]:
            print(f"❌ Failed to create inventory item: {inventory_response.status_code}")
            print(f"Response: {inventory_response.text}")
            return
            
        inventory_id = inventory_response.json()["id"]
        print(f"✅ Created inventory item: {inventory_data['name']}")
        print(f"   - ID: {inventory_id}")
        print(f"   - SKU: {inventory_data['sku']}")
        print(f"   - Price: ${inventory_data['unit_price']}")
        print(f"   - Stock: {inventory_data['current_stock']} {inventory_data['unit_of_measure']}")
        
        # Create invoice linked to inventory
        invoice_data = {
            "client_id": client_id,
            "amount": 151.00,  # 2 * 75.50
            "currency": "USD",
            "status": "draft",
            "notes": "Test invoice created to demonstrate inventory linking feature",
            "items": [{
                "inventory_item_id": inventory_id,  # This creates the link!
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
            return
            
        invoice_id = invoice_response.json()["id"]
        invoice_number = invoice_response.json()["number"]
        print(f"✅ Created linked invoice: {invoice_number}")
        print(f"   - ID: {invoice_id}")
        print(f"   - Amount: $151.00 (2 × $75.50)")
        
        # Verify the linking
        get_response = requests.get(f"{API_BASE}/invoices/{invoice_id}", headers=auth_headers)
        if get_response.status_code == 200:
            invoice_data = get_response.json()
            items = invoice_data.get('items', [])
            
            if items and items[0].get('inventory_item_id'):
                print(f"✅ Verification: Invoice item linked to inventory ID {items[0]['inventory_item_id']}")
                
                if items[0].get('inventory_item'):
                    print(f"✅ Verification: Inventory details included in API response")
                else:
                    print(f"❌ Verification: No inventory details in API response")
            else:
                print(f"❌ Verification: Invoice item not properly linked")
        
        print(f"\n🎯 NOW TEST THE FEATURE:")
        print(f"1. Go to your web app")
        print(f"2. Navigate to Invoices")
        print(f"3. Find invoice: {invoice_number}")
        print(f"4. Click 'Edit' on that invoice")
        print(f"5. Look for:")
        print(f"   - Package icon (📦) next to the item")
        print(f"   - Stock info like '25 avail' in quantity field")
        print(f"   - 'Inventory Information' section below items")
        print(f"   - Item details: {inventory_data['name']}")
        print(f"   - SKU: {inventory_data['sku']}")
        print(f"   - Current Stock: 25 units")
        
        print(f"\n📋 Test Data Created:")
        print(f"- Client: {client_name} (ID: {client_id})")
        print(f"- Inventory: {inventory_data['name']} (ID: {inventory_id})")
        print(f"- Invoice: {invoice_number} (ID: {invoice_id})")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    create_test_data_in_your_account()