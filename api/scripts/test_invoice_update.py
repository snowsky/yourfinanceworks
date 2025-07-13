#!/usr/bin/env python3

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def login_user(email, password):
    """Login and get authentication token"""
    login_response = requests.post(f"{API_BASE}/auth/login", json={
        "email": email,
        "password": password
    })
    
    if login_response.status_code == 200:
        return login_response.json()["access_token"]
    else:
        print(f"Login failed: {login_response.status_code}")
        print(login_response.text)
        return None

def test_invoice_update():
    """Test invoice update functionality"""
    print("🧪 Testing Invoice Update Endpoint...")
    
    # Login
    token = login_user("test@example.com", "password123")
    if not token:
        print("❌ Failed to login")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get existing invoices
    print("\n📋 Getting existing invoices...")
    invoices_response = requests.get(f"{API_BASE}/invoices", headers=headers)
    
    if invoices_response.status_code != 200:
        print(f"❌ Failed to get invoices: {invoices_response.status_code}")
        print(invoices_response.text)
        return
    
    invoices = invoices_response.json()
    if not invoices:
        print("❌ No invoices found to update")
        return
    
    # Test updating the first invoice
    invoice_id = invoices[0]["id"]
    print(f"\n📝 Testing update for invoice ID: {invoice_id}")
    
    # Update invoice data
    update_data = {
        "amount": 1500.00,
        "notes": "Updated notes from test",
        "status": "paid"
    }
    
    update_response = requests.put(
        f"{API_BASE}/invoices/{invoice_id}", 
        json=update_data, 
        headers=headers
    )
    
    if update_response.status_code == 200:
        print("✅ Invoice update successful!")
        updated_invoice = update_response.json()
        print(f"   Updated amount: {updated_invoice['amount']}")
        print(f"   Updated notes: {updated_invoice['notes']}")
        print(f"   Updated status: {updated_invoice['status']}")
    else:
        print(f"❌ Invoice update failed: {update_response.status_code}")
        print(update_response.text)
    
    # Test getting the updated invoice
    print(f"\n🔍 Verifying update by getting invoice {invoice_id}...")
    get_response = requests.get(f"{API_BASE}/invoices/{invoice_id}", headers=headers)
    
    if get_response.status_code == 200:
        invoice = get_response.json()
        print("✅ Invoice retrieval successful!")
        print(f"   Amount: {invoice['amount']}")
        print(f"   Notes: {invoice['notes']}")
        print(f"   Status: {invoice['status']}")
    else:
        print(f"❌ Invoice retrieval failed: {get_response.status_code}")
        print(get_response.text)

if __name__ == "__main__":
    test_invoice_update() 