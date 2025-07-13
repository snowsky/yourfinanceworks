#!/usr/bin/env python3

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def login_user(email, password):
    """Login and get authentication token"""
    response = requests.post(f"{API_BASE}/auth/login", json={
        "email": email,
        "password": password
    })
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        return None

def create_test_invoice(headers):
    """Create a test invoice for testing"""
    # First, get a client to attach the invoice to
    clients_response = requests.get(f"{API_BASE}/clients", headers=headers)
    if clients_response.status_code != 200:
        print("❌ Failed to get clients")
        return None
    
    clients = clients_response.json()
    if not clients:
        print("❌ No clients available")
        return None
    
    client_id = clients[0]["id"]
    
    # Create test invoice
    invoice_data = {
        "amount": 500.00,
        "currency": "USD",
        "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
        "status": "draft",
        "notes": "Test invoice for recycle bin testing",
        "client_id": client_id,
        "is_recurring": False,
        "discount_type": "percentage",
        "discount_value": 0.0,
        "subtotal": 500.00,
        "items": [
            {
                "description": "Test service",
                "quantity": 1.0,
                "price": 500.00
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/invoices", json=invoice_data, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Failed to create test invoice: {response.status_code}")
        print(response.text)
        return None

def test_recycle_bin():
    """Test the complete recycle bin functionality"""
    print("🧪 Testing Recycle Bin Functionality...")
    
    # Login
    token = login_user("test@example.com", "password123")
    if not token:
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n📋 Step 1: Creating test invoice...")
    test_invoice = create_test_invoice(headers)
    if not test_invoice:
        return
    
    invoice_id = test_invoice["id"]
    print(f"✅ Created test invoice with ID: {invoice_id}")
    
    print("\n📋 Step 2: Verifying invoice appears in regular list...")
    invoices_response = requests.get(f"{API_BASE}/invoices", headers=headers)
    if invoices_response.status_code == 200:
        invoices = invoices_response.json()
        invoice_found = any(inv["id"] == invoice_id for inv in invoices)
        if invoice_found:
            print("✅ Invoice appears in regular invoice list")
        else:
            print("❌ Invoice not found in regular list")
            return
    else:
        print(f"❌ Failed to get invoices: {invoices_response.status_code}")
        return
    
    print("\n📋 Step 3: Moving invoice to recycle bin...")
    delete_response = requests.delete(f"{API_BASE}/invoices/{invoice_id}", headers=headers)
    if delete_response.status_code == 200:
        result = delete_response.json()
        print(f"✅ Invoice moved to recycle bin: {result['message']}")
        print(f"   Action: {result['action']}")
    else:
        print(f"❌ Failed to delete invoice: {delete_response.status_code}")
        print(delete_response.text)
        return
    
    print("\n📋 Step 4: Verifying invoice no longer appears in regular list...")
    invoices_response = requests.get(f"{API_BASE}/invoices", headers=headers)
    if invoices_response.status_code == 200:
        invoices = invoices_response.json()
        invoice_found = any(inv["id"] == invoice_id for inv in invoices)
        if not invoice_found:
            print("✅ Invoice no longer appears in regular invoice list")
        else:
            print("❌ Invoice still appears in regular list (should be hidden)")
    else:
        print(f"❌ Failed to get invoices: {invoices_response.status_code}")
    
    print("\n📋 Step 5: Checking recycle bin...")
    recycle_response = requests.get(f"{API_BASE}/invoices/recycle-bin", headers=headers)
    if recycle_response.status_code == 200:
        deleted_invoices = recycle_response.json()
        deleted_invoice = next((inv for inv in deleted_invoices if inv["id"] == invoice_id), None)
        if deleted_invoice:
            print("✅ Invoice appears in recycle bin")
            print(f"   Deleted at: {deleted_invoice['deleted_at']}")
            print(f"   Deleted by: {deleted_invoice['deleted_by_username']}")
        else:
            print("❌ Invoice not found in recycle bin")
            return
    else:
        print(f"❌ Failed to get recycle bin: {recycle_response.status_code}")
        print(recycle_response.text)
        return
    
    print("\n📋 Step 6: Restoring invoice from recycle bin...")
    restore_response = requests.post(
        f"{API_BASE}/invoices/{invoice_id}/restore",
        json={"new_status": "draft"},
        headers=headers
    )
    if restore_response.status_code == 200:
        result = restore_response.json()
        print(f"✅ Invoice restored: {result['message']}")
        print(f"   Action: {result['action']}")
    else:
        print(f"❌ Failed to restore invoice: {restore_response.status_code}")
        print(restore_response.text)
        return
    
    print("\n📋 Step 7: Verifying invoice reappears in regular list...")
    invoices_response = requests.get(f"{API_BASE}/invoices", headers=headers)
    if invoices_response.status_code == 200:
        invoices = invoices_response.json()
        invoice_found = any(inv["id"] == invoice_id for inv in invoices)
        if invoice_found:
            print("✅ Invoice reappears in regular invoice list")
        else:
            print("❌ Invoice not found in regular list after restore")
    else:
        print(f"❌ Failed to get invoices: {invoices_response.status_code}")
    
    print("\n📋 Step 8: Moving to recycle bin again for permanent deletion test...")
    delete_response = requests.delete(f"{API_BASE}/invoices/{invoice_id}", headers=headers)
    if delete_response.status_code == 200:
        print("✅ Invoice moved to recycle bin again")
    else:
        print(f"❌ Failed to delete invoice again: {delete_response.status_code}")
        return
    
    print("\n📋 Step 9: Testing permanent deletion...")
    permanent_delete_response = requests.delete(
        f"{API_BASE}/invoices/{invoice_id}/permanent",
        headers=headers
    )
    if permanent_delete_response.status_code == 200:
        result = permanent_delete_response.json()
        print(f"✅ Invoice permanently deleted: {result['message']}")
        print(f"   Action: {result['action']}")
    else:
        print(f"❌ Failed to permanently delete invoice: {permanent_delete_response.status_code}")
        print(permanent_delete_response.text)
        # If it fails, it might be due to permissions (only admins can permanently delete)
        if permanent_delete_response.status_code == 403:
            print("   Note: This is expected if the user is not an admin")
    
    print("\n📋 Step 10: Verifying invoice is gone from recycle bin...")
    recycle_response = requests.get(f"{API_BASE}/invoices/recycle-bin", headers=headers)
    if recycle_response.status_code == 200:
        deleted_invoices = recycle_response.json()
        deleted_invoice = next((inv for inv in deleted_invoices if inv["id"] == invoice_id), None)
        if not deleted_invoice:
            print("✅ Invoice no longer appears in recycle bin")
        else:
            print("❌ Invoice still appears in recycle bin (should be permanently deleted)")
    else:
        print(f"❌ Failed to get recycle bin: {recycle_response.status_code}")
    
    print("\n🎉 Recycle bin functionality test completed!")

def test_try_to_access_deleted_invoice():
    """Test that deleted invoices can't be accessed through regular endpoints"""
    print("\n🔒 Testing access protection for deleted invoices...")
    
    token = login_user("test@example.com", "password123")
    if not token:
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create and delete an invoice
    test_invoice = create_test_invoice(headers)
    if not test_invoice:
        return
    
    invoice_id = test_invoice["id"]
    
    # Delete it
    requests.delete(f"{API_BASE}/invoices/{invoice_id}", headers=headers)
    
    # Try to access it through regular endpoints
    print(f"   Trying to access deleted invoice {invoice_id}...")
    
    get_response = requests.get(f"{API_BASE}/invoices/{invoice_id}", headers=headers)
    if get_response.status_code == 404:
        print("✅ Cannot access deleted invoice via GET")
    else:
        print(f"❌ Deleted invoice accessible via GET: {get_response.status_code}")
    
    update_response = requests.put(
        f"{API_BASE}/invoices/{invoice_id}",
        json={"amount": 1000.00},
        headers=headers
    )
    if update_response.status_code == 404:
        print("✅ Cannot update deleted invoice via PUT")
    else:
        print(f"❌ Deleted invoice updatable via PUT: {update_response.status_code}")

if __name__ == "__main__":
    test_recycle_bin()
    test_try_to_access_deleted_invoice() 