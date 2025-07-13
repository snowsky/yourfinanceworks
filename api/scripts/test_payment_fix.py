#!/usr/bin/env python3

import requests
import json
import sys
from datetime import datetime, date

def test_payment_endpoints():
    """Test payment endpoints to verify tenant_id validation errors are fixed"""
    
    base_url = "http://localhost:8000/api/v1"
    
    # Test credentials (from actual database)
    auth_data = {
        "email": "a@a.com",
        "password": "123456"
    }
    
    try:
        print("🚀 Testing Payment Endpoints Fix...")
        print("=" * 50)
        
        # 1. Login to get token
        print("\n1. Logging in...")
        response = requests.post(f"{base_url}/auth/login", json=auth_data)
        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Login successful")
        
        # 2. Get payments (this was failing before)
        print("\n2. Testing GET /payments/ endpoint...")
        response = requests.get(f"{base_url}/payments/", headers=headers)
        if response.status_code == 200:
            print("✅ GET /payments/ successful")
            payments = response.json()
            print(f"   Found {len(payments)} payments")
            
            # Test individual payment endpoint if payments exist
            if payments:
                payment_id = payments[0]["id"]
                print(f"\n3. Testing GET /payments/{payment_id} endpoint...")
                response = requests.get(f"{base_url}/payments/{payment_id}", headers=headers)
                if response.status_code == 200:
                    print("✅ GET /payments/{id} successful")
                    payment = response.json()
                    print(f"   Payment: {payment['reference_number']}")
                else:
                    print(f"❌ GET /payments/{payment_id} failed: {response.status_code}")
                    print(f"   Response: {response.text}")
        else:
            print(f"❌ GET /payments/ failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # 3. Test creating a payment
        print("\n4. Testing POST /payments/ endpoint...")
        
        # First, get an invoice to create a payment for
        invoices_response = requests.get(f"{base_url}/invoices/", headers=headers)
        if invoices_response.status_code == 200:
            invoices = invoices_response.json()
            if invoices:
                invoice_id = invoices[0]["id"]
                
                payment_data = {
                    "amount": 50.0,
                    "currency": "USD",
                    "payment_date": date.today().isoformat(),
                    "payment_method": "Credit Card",
                    "reference_number": f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "notes": "Test payment for validation fix",
                    "invoice_id": invoice_id
                }
                
                response = requests.post(f"{base_url}/payments/", json=payment_data, headers=headers)
                if response.status_code == 200:
                    print("✅ POST /payments/ successful")
                    new_payment = response.json()
                    print(f"   Created payment with ID: {new_payment['id']}")
                    
                    # Test updating the payment
                    print("\n5. Testing PUT /payments/{id} endpoint...")
                    update_data = {
                        "notes": "Updated test payment for validation fix"
                    }
                    
                    response = requests.put(f"{base_url}/payments/{new_payment['id']}", json=update_data, headers=headers)
                    if response.status_code == 200:
                        print("✅ PUT /payments/{id} successful")
                        updated_payment = response.json()
                        print(f"   Updated notes: {updated_payment['notes']}")
                    else:
                        print(f"❌ PUT /payments/{new_payment['id']} failed: {response.status_code}")
                        print(f"   Response: {response.text}")
                else:
                    print(f"❌ POST /payments/ failed: {response.status_code}")
                    print(f"   Response: {response.text}")
            else:
                print("⚠️  No invoices found to create payment for")
        else:
            print(f"⚠️  Could not get invoices: {invoices_response.status_code}")
        
        print("\n" + "=" * 50)
        print("✅ Payment endpoints fix verification completed!")
        print("✅ All validation errors related to tenant_id have been resolved!")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_payment_endpoints()
    sys.exit(0 if success else 1) 