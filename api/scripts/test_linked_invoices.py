#!/usr/bin/env python3

import requests
import json

# Configuration
API_BASE_URL = "http://localhost:8000"

def get_auth_headers():
    """Get authentication headers"""
    # You'll need to replace this with actual token
    token = "your_token_here"  # Replace with actual token
    return {"Authorization": f"Bearer {token}"}

def test_linked_invoices():
    """Test the linked invoices endpoint"""
    try:
        headers = get_auth_headers()
        
        # Test with inventory item ID 2 (the one we know is linked)
        inventory_item_id = 2
        
        print(f"🔍 Testing linked invoices for inventory item {inventory_item_id}")
        
        # Get linked invoices
        response = requests.get(f"{API_BASE_URL}/inventory/items/{inventory_item_id}/linked-invoices", headers=headers)
        
        if response.status_code == 200:
            linked_invoices = response.json()
            print(f"✅ API call successful")
            print(f"📋 Found {len(linked_invoices)} linked invoices:")
            
            for invoice in linked_invoices:
                print(f"   - Invoice #{invoice.get('number')} (ID: {invoice.get('id')})")
                print(f"     Status: {invoice.get('status')}")
                print(f"     Amount: {invoice.get('amount')} {invoice.get('currency')}")
                print(f"     Items: {len(invoice.get('invoice_items', []))}")
                print(f"     Stock movements: {len(invoice.get('stock_movements', []))}")
                print()
                
            if len(linked_invoices) == 0:
                print("❌ No linked invoices found - this suggests:")
                print("   1. No stock movements exist for this item")
                print("   2. Stock movements don't have reference_type='invoice'")
                print("   3. The invoice items don't have inventory_item_id set")
                
        else:
            print(f"❌ API call failed: {response.status_code}")
            print(f"Response: {response.text}")
            
        # Also check stock movements directly
        print(f"\n🔍 Checking stock movements for inventory item {inventory_item_id}")
        response = requests.get(f"{API_BASE_URL}/inventory/items/{inventory_item_id}/stock-movements", headers=headers)
        
        if response.status_code == 200:
            movements = response.json()
            print(f"📋 Found {len(movements)} stock movements:")
            
            for movement in movements:
                print(f"   - Movement ID: {movement.get('id')}")
                print(f"     Type: {movement.get('movement_type')}")
                print(f"     Quantity: {movement.get('quantity')}")
                print(f"     Reference type: {movement.get('reference_type')}")
                print(f"     Reference ID: {movement.get('reference_id')}")
                print()
        else:
            print(f"❌ Stock movements API call failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_linked_invoices()