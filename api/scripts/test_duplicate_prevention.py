#!/usr/bin/env python3

import requests
import json

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

def test_duplicate_prevention():
    """Test that duplicate client creation is prevented"""
    print("🧪 Testing Duplicate Prevention...")
    
    # Login
    token = login_user("test@example.com", "password123")
    if not token:
        print("❌ Failed to login")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to create a client with the same name and email as an existing one
    duplicate_client_data = {
        "name": "Test Client Company",
        "email": "client@example.com",
        "phone": "123-456-7890",
        "address": "123 Test St"
    }
    
    print(f"\n🔍 Attempting to create duplicate client...")
    print(f"   Name: {duplicate_client_data['name']}")
    print(f"   Email: {duplicate_client_data['email']}")
    
    response = requests.post(f"{API_BASE}/clients", json=duplicate_client_data, headers=headers)
    
    if response.status_code == 400:
        print("✅ Duplicate prevention working correctly!")
        print(f"   Error message: {response.json()['detail']}")
    else:
        print(f"❌ Duplicate prevention failed - Status: {response.status_code}")
        print(f"   Response: {response.text}")
    
    # Try to create a client with different details (should succeed)
    new_client_data = {
        "name": "New Unique Client",
        "email": "unique@example.com",
        "phone": "987-654-3210",
        "address": "456 Unique Ave"
    }
    
    print(f"\n🔍 Attempting to create new unique client...")
    print(f"   Name: {new_client_data['name']}")
    print(f"   Email: {new_client_data['email']}")
    
    response = requests.post(f"{API_BASE}/clients", json=new_client_data, headers=headers)
    
    if response.status_code == 200:
        print("✅ New unique client creation successful!")
        client = response.json()
        print(f"   Created client ID: {client['id']}")
        
        # Clean up - delete the created client
        delete_response = requests.delete(f"{API_BASE}/clients/{client['id']}", headers=headers)
        if delete_response.status_code == 204:
            print("✅ Cleanup successful - test client deleted")
        else:
            print(f"⚠️  Cleanup failed - Status: {delete_response.status_code}")
    else:
        print(f"❌ New client creation failed - Status: {response.status_code}")
        print(f"   Response: {response.text}")

if __name__ == "__main__":
    test_duplicate_prevention() 