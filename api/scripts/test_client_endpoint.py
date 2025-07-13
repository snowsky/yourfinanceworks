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

def test_client_endpoint():
    """Test the client endpoint to see what's being returned"""
    print("🧪 Testing Client Endpoint...")
    
    # Login
    token = login_user("test@example.com", "password123")
    if not token:
        print("❌ Failed to login")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get clients
    print("\n📋 Getting clients...")
    response = requests.get(f"{API_BASE}/clients", headers=headers)
    
    if response.status_code == 200:
        clients = response.json()
        print(f"✅ Got {len(clients)} clients")
        
        # Check for duplicates
        seen_ids = set()
        seen_names = set()
        
        for i, client in enumerate(clients):
            print(f"\n📋 Client {i+1}:")
            print(f"  ID: {client['id']}")
            print(f"  Name: {client['name']}")
            print(f"  Email: {client['email']}")
            print(f"  Balance: {client.get('balance', 'N/A')}")
            print(f"  Outstanding Balance: {client.get('outstanding_balance', 'N/A')}")
            
            # Check for ID duplicates
            if client['id'] in seen_ids:
                print(f"  ❌ DUPLICATE ID: {client['id']}")
            else:
                seen_ids.add(client['id'])
            
            # Check for name duplicates
            if client['name'] in seen_names:
                print(f"  ❌ DUPLICATE NAME: {client['name']}")
            else:
                seen_names.add(client['name'])
        
        print(f"\n📊 Summary:")
        print(f"  Total clients: {len(clients)}")
        print(f"  Unique IDs: {len(seen_ids)}")
        print(f"  Unique names: {len(seen_names)}")
        
        if len(clients) > len(seen_ids):
            print(f"  ❌ Found {len(clients) - len(seen_ids)} duplicate IDs")
        if len(clients) > len(seen_names):
            print(f"  ❌ Found {len(clients) - len(seen_names)} duplicate names")
        
    else:
        print(f"❌ Failed to get clients: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_client_endpoint() 