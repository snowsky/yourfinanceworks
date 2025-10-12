#!/usr/bin/env python3
"""
Check what's in invoice ID 2 and verify if it has inventory items
"""

import requests
import json

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def check_invoice_2():
    """Check invoice ID 2"""
    
    print("🔍 Checking Invoice ID 2")
    print("=" * 30)
    
    # Use your credentials
    email = "a@a.com"
    password = "123456"
    
    try:
        # Login
        login_data = {"email": email, "password": password}
        login_response = requests.post(f"{API_BASE}/auth/login", json=login_data)
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            return
            
        token = login_response.json().get("access_token")
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # Get invoice 2
        invoice_response = requests.get(f"{API_BASE}/invoices/2", headers=auth_headers)
        
        if invoice_response.status_code != 200:
            print(f"❌ Failed to get invoice 2: {invoice_response.status_code}")
            print(f"Response: {invoice_response.text}")
            return
            
        invoice_data = invoice_response.json()
        
        print(f"✅ Invoice 2 Details:")
        print(f"- Number: {invoice_data.get('number')}")
        print(f"- Client: {invoice_data.get('client_name')}")
        print(f"- Amount: ${invoice_data.get('amount')}")
        print(f"- Status: {invoice_data.get('status')}")
        print(f"- Items count: {len(invoice_data.get('items', []))}")
        
        # Check items
        items = invoice_data.get('items', [])
        for i, item in enumerate(items):
            print(f"\n📋 Item {i+1}:")
            print(f"- ID: {item.get('id')}")
            print(f"- Description: {item.get('description')}")
            print(f"- Quantity: {item.get('quantity')}")
            print(f"- Price: ${item.get('price')}")
            print(f"- Inventory Item ID: {item.get('inventory_item_id')}")
            print(f"- Has inventory_item field: {'inventory_item' in item}")
            
            if item.get('inventory_item'):
                inv_item = item['inventory_item']
                print(f"✅ Inventory Details:")
                print(f"  - Name: {inv_item.get('name')}")
                print(f"  - SKU: {inv_item.get('sku')}")
                print(f"  - Current Stock: {inv_item.get('current_stock')}")
                print(f"  - Unit Price: ${inv_item.get('unit_price')}")
            elif item.get('inventory_item_id'):
                print(f"❌ Has inventory_item_id but no inventory_item data")
            else:
                print(f"ℹ️  No inventory linking (manual item)")
        
        # Also check invoice 3 for comparison
        print(f"\n" + "="*50)
        print(f"🔍 Checking Invoice ID 3 for comparison")
        
        invoice3_response = requests.get(f"{API_BASE}/invoices/3", headers=auth_headers)
        if invoice3_response.status_code == 200:
            invoice3_data = invoice3_response.json()
            print(f"✅ Invoice 3 Details:")
            print(f"- Number: {invoice3_data.get('number')}")
            print(f"- Items count: {len(invoice3_data.get('items', []))}")
            
            items3 = invoice3_data.get('items', [])
            for i, item in enumerate(items3):
                print(f"\n📋 Invoice 3 - Item {i+1}:")
                print(f"- Description: {item.get('description')}")
                print(f"- Inventory Item ID: {item.get('inventory_item_id')}")
                print(f"- Has inventory_item field: {'inventory_item' in item}")
                
                if item.get('inventory_item'):
                    print(f"✅ Has inventory data")
                else:
                    print(f"❌ Missing inventory data")
        else:
            print(f"❌ Invoice 3 not found: {invoice3_response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_invoice_2()