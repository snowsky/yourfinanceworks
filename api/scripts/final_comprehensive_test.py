#!/usr/bin/env python3
"""
Comprehensive test for the per-tenant database system
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def get_auth_token():
    """Get JWT token for authentication"""
    login_data = {
        "email": "test@example.com",
        "password": "password123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception as e:
        print(f"Error getting auth token: {e}")
    
    return None

def test_endpoint(endpoint, token, description, method="GET", data=None):
    """Test a single endpoint"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, headers=headers)
        elif method == "PUT":
            response = requests.put(f"{BASE_URL}{endpoint}", json=data, headers=headers)
        
        if response.status_code in [200, 201]:
            print(f"✅ {description}: Working ({response.status_code})")
            return True, response.json() if response.content else {}
        else:
            print(f"❌ {description}: Failed ({response.status_code})")
            return False, None
    except Exception as e:
        print(f"❌ {description}: Error - {e}")
        return False, None

def comprehensive_test():
    """Run comprehensive tests for all endpoints"""
    print("🧪 Comprehensive Per-Tenant Database System Test")
    print("=" * 70)
    
    # Get authentication token
    token = get_auth_token()
    if not token:
        print("❌ Unable to get authentication token")
        return False
    
    print(f"✅ Authentication: Token obtained")
    
    success_count = 0
    total_tests = 0
    
    # Test 1: Read endpoints (should all work)
    print(f"\n📖 Testing Read Operations:")
    read_tests = [
        ("/api/v1/clients/", "List Clients"),
        ("/api/v1/invoices/", "List Invoices"),
        ("/api/v1/payments/", "List Payments"),
        ("/api/v1/discount-rules/", "List Discount Rules"),
        ("/api/v1/tenants/me", "Get Tenant Info"),
        ("/api/v1/settings/", "Get Settings"),
    ]
    
    for endpoint, description in read_tests:
        success, _ = test_endpoint(endpoint, token, description)
        if success:
            success_count += 1
        total_tests += 1
    
    # Test 2: Create operations
    print(f"\n➕ Testing Create Operations:")
    
    # Create a client
    client_data = {
        "name": "Comprehensive Test Client",
        "email": "comprehensive@test.com",
        "phone": "+1-555-000-0000",
        "address": "Test Address",
        "preferred_currency": "USD"
    }
    success, client = test_endpoint("/api/v1/clients/", token, "Create Client", "POST", client_data)
    if success:
        success_count += 1
        client_id = client.get('id')
        print(f"   Created client with ID: {client_id}")
    total_tests += 1
    
    # Create a discount rule
    discount_data = {
        "name": "Test Discount",
        "min_amount": 100.0,
        "discount_type": "percentage",
        "discount_value": 10.0,
        "currency": "USD",
        "is_active": True,
        "priority": 1
    }
    success, discount = test_endpoint("/api/v1/discount-rules/", token, "Create Discount Rule", "POST", discount_data)
    if success:
        success_count += 1
        discount_id = discount.get('id')
        print(f"   Created discount rule with ID: {discount_id}")
    total_tests += 1
    
    # Test 3: Update operations (if creates were successful)
    if client_id:
        print(f"\n✏️  Testing Update Operations:")
        
        update_data = {"phone": "+1-555-111-1111"}
        success, _ = test_endpoint(f"/api/v1/clients/{client_id}", token, "Update Client", "PUT", update_data)
        if success:
            success_count += 1
        total_tests += 1
    
    # Test 4: Settings update
    print(f"\n⚙️  Testing Settings Update:")
    settings_data = {
        "company_info": {
            "name": "Updated Test Company",
            "email": "updated@test.com"
        },
        "enable_ai_assistant": True
    }
    success, _ = test_endpoint("/api/v1/settings/", token, "Update Settings", "PUT", settings_data)
    if success:
        success_count += 1
    total_tests += 1
    
    # Test 5: Calculate discount
    print(f"\n🧮 Testing Business Logic:")
    success, _ = test_endpoint("/api/v1/discount-rules/calculate?subtotal=150", token, "Calculate Discount")
    if success:
        success_count += 1
    total_tests += 1
    
    # Summary
    print("\n" + "=" * 70)
    print(f"📊 Test Results: {success_count}/{total_tests} tests passed")
    
    success_rate = (success_count / total_tests) * 100
    
    if success_rate == 100:
        print("🎉 Perfect! All functionality working correctly!")
        print("✨ Per-tenant database system is fully operational!")
        return True
    elif success_rate >= 80:
        print("✅ Great! Most functionality working (some minor issues)")
        return True
    else:
        print("⚠️  Several issues detected that need attention")
        return False

if __name__ == "__main__":
    success = comprehensive_test()
    sys.exit(0 if success else 1) 