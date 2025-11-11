#!/usr/bin/env python3
"""
Test script to demonstrate API key functionality.
This script shows how to:
1. Create a user and login
2. Create an API key
3. Use the API key to make requests
"""

import requests
import json
import sys
import os

# API base URL
BASE_URL = "http://localhost:8000/api/v1"

def test_api_key_functionality():
    """Test the complete API key workflow."""
    
    print("🔑 Testing API Key Functionality")
    print("=" * 50)
    
    # Step 1: Register a test user
    print("\n1. Registering test user...")
    register_data = {
        "email": "apitest@example.com",
        "password": "testpassword123",
        "first_name": "API",
        "last_name": "Tester",
        "organization_name": "API Test Organization"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        if response.status_code == 201:
            print("✅ User registered successfully")
            auth_data = response.json()
            jwt_token = auth_data["access_token"]
        elif response.status_code == 400 and "already registered" in response.text:
            print("ℹ️  User already exists, logging in...")
            # Login instead
            login_data = {
                "email": "apitest@example.com",
                "password": "testpassword123"
            }
            response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
            if response.status_code == 200:
                auth_data = response.json()
                jwt_token = auth_data["access_token"]
                print("✅ User logged in successfully")
            else:
                print(f"❌ Login failed: {response.text}")
                return
        else:
            print(f"❌ Registration failed: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error during registration: {e}")
        return
    
    # Step 2: Create an API key
    print("\n2. Creating API key...")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    api_key_data = {
        "client_name": "Test API Client",
        "client_description": "Test client for API key functionality",
        "allowed_document_types": ["invoice", "expense"],
        "rate_limit_per_minute": 60,
        "rate_limit_per_hour": 1000,
        "rate_limit_per_day": 10000,
        "is_sandbox": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/external-auth/api-keys", json=api_key_data, headers=headers)
        if response.status_code == 200:
            api_key_response = response.json()
            api_key = api_key_response["api_key"]
            client_id = api_key_response["client_id"]
            print("✅ API key created successfully")
            print(f"   Client ID: {client_id}")
            print(f"   API Key: {api_key[:20]}...")
        else:
            print(f"❌ API key creation failed: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error creating API key: {e}")
        return
    
    # Step 3: Test API key authentication
    print("\n3. Testing API key authentication...")
    api_headers = {"X-API-Key": api_key}
    
    # Test creating an external transaction
    transaction_data = {
        "transaction_type": "expense",
        "amount": 100.50,
        "currency": "USD",
        "date": "2024-01-15T10:00:00Z",
        "description": "Test expense transaction",
        "source_system": "Test System",
        "category": "Office Supplies",
        "business_purpose": "Testing API key functionality"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/external-transactions/transactions", 
                               json=transaction_data, headers=api_headers)
        if response.status_code == 200:
            transaction_response = response.json()
            transaction_id = transaction_response["external_transaction_id"]
            print("✅ External transaction created successfully")
            print(f"   Transaction ID: {transaction_id}")
            print(f"   Amount: ${transaction_response['amount']} {transaction_response['currency']}")
            print(f"   Status: {transaction_response['status']}")
        else:
            print(f"❌ Transaction creation failed: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error creating transaction: {e}")
        return
    
    # Step 4: List transactions
    print("\n4. Listing external transactions...")
    try:
        response = requests.get(f"{BASE_URL}/external-transactions/transactions", headers=api_headers)
        if response.status_code == 200:
            transactions_response = response.json()
            transactions = transactions_response["transactions"]
            print(f"✅ Retrieved {len(transactions)} transactions")
            print(f"   Total: {transactions_response['total']}")
            print(f"   Page: {transactions_response['page']}")
        else:
            print(f"❌ Failed to list transactions: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error listing transactions: {e}")
        return
    
    # Step 5: List API keys
    print("\n5. Listing API keys...")
    try:
        response = requests.get(f"{BASE_URL}/external-auth/api-keys", headers=headers)
        if response.status_code == 200:
            api_keys = response.json()
            print(f"✅ Retrieved {len(api_keys)} API keys")
            for key in api_keys:
                print(f"   - {key['client_name']} ({key['api_key_prefix']})")
                print(f"     Status: {'Active' if key['is_active'] else 'Inactive'}")
                print(f"     Requests: {key['total_requests']}")
                print(f"     Transactions: {key['total_transactions_submitted']}")
        else:
            print(f"❌ Failed to list API keys: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error listing API keys: {e}")
        return
    
    # Step 6: Test permissions endpoint
    print("\n6. Testing permissions endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/external-auth/permissions", headers=headers)
        if response.status_code == 200:
            permissions = response.json()
            print("✅ Retrieved available permissions:")
            for perm in permissions["permissions"]:
                print(f"   - {perm['name']}: {perm['description']}")
        else:
            print(f"❌ Failed to get permissions: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error getting permissions: {e}")
        return
    
    print("\n🎉 All API key functionality tests passed!")
    print("\nAPI Key Details:")
    print(f"  Client ID: {client_id}")
    print(f"  API Key: {api_key}")
    print(f"  Usage: Include 'X-API-Key: {api_key}' header in requests")
    print("\nExample curl command:")
    print(f"curl -H 'X-API-Key: {api_key}' \\")
    print(f"     -H 'Content-Type: application/json' \\")
    print(f"     -d '{json.dumps(transaction_data, indent=2)}' \\")
    print(f"     {BASE_URL}/external-transactions/transactions")

if __name__ == "__main__":
    test_api_key_functionality()
