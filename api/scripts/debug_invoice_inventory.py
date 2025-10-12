#!/usr/bin/env python3

import requests
import json
import sys

# Configuration
API_BASE_URL = "http://localhost:8000"

def get_auth_headers():
    """Get authentication headers"""
    # You'll need to replace this with actual token
    token = "your_token_here"  # Replace with actual token
    return {"Authorization": f"Bearer {token}"}

def check_invoice_inventory_data(invoice_id):
    """Check if invoice has inventory data"""
    try:
        headers = get_auth_headers()
        
        # Get invoice details
        response = requests.get(f"{API_BASE_URL}/invoices/{invoice_id}", headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to get invoice: {response.status_code}")
            return
            
        invoice = response.json()
        print(f"📋 Invoice {invoice_id} Details:")
        print(f"   Number: {invoice.get('number')}")
        print(f"   Items count: {len(invoice.get('items', []))}")
        
        # Check each item for inventory data
        for i, item in enumerate(invoice.get('items', [])):
            print(f"\n🔍 Item {i+1}:")
            print(f"   Description: {item.get('description')}")
            print(f"   Inventory Item ID: {item.get('inventory_item_id')}")
            print(f"   Has inventory_item field: {'inventory_item' in item}")
            
            if 'inventory_item' in item and item['inventory_item']:
                inv_item = item['inventory_item']
                print(f"   Inventory Item Name: {inv_item.get('name')}")
                print(f"   Inventory Item SKU: {inv_item.get('sku')}")
                print(f"   Current Stock: {inv_item.get('current_stock')}")
            elif item.get('inventory_item_id'):
                print(f"   ⚠️  Has inventory_item_id but no inventory_item data!")
                
                # Try to fetch inventory item directly
                inv_response = requests.get(f"{API_BASE_URL}/inventory/{item['inventory_item_id']}", headers=headers)
                if inv_response.status_code == 200:
                    inv_item = inv_response.json()
                    print(f"   ✅ Direct fetch successful:")
                    print(f"      Name: {inv_item.get('name')}")
                    print(f"      SKU: {inv_item.get('sku')}")
                    print(f"      Current Stock: {inv_item.get('current_stock')}")
                else:
                    print(f"   ❌ Direct fetch failed: {inv_response.status_code}")
            else:
                print(f"   ℹ️  No inventory item linked")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_invoice_inventory.py <invoice_id>")
        sys.exit(1)
        
    invoice_id = sys.argv[1]
    check_invoice_inventory_data(invoice_id)