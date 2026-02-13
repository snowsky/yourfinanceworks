#!/usr/bin/env python3
"""
Test script to verify export destination creation with encryption.
"""

import requests
import json
import sys

# API endpoint
API_BASE_URL = "http://localhost:8000/api/v1"

def get_auth_token():
    """Get authentication token"""
    # For testing, we'll use the default test user
    # In a real scenario, you'd need to login first
    return "test-token"  # This will be replaced with actual token from login

def test_export_destination_creation():
    """Test creating an export destination"""
    
    print("Testing export destination creation...")
    print("=" * 60)
    
    # First, get the current user to ensure we're authenticated
    print("\n1. Getting current user...")
    response = requests.get(
        f"{API_BASE_URL}/auth/me",
        headers={"Authorization": "Bearer test-token"}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get current user: {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    user = response.json()
    print(f"✓ Current user: {user.get('email')}")
    
    # Create an export destination
    print("\n2. Creating export destination...")
    
    destination_data = {
        "name": "Test S3 Destination",
        "destination_type": "s3",
        "credentials": {
            "access_key_id": "AKIA2NNGMX4J4544RKVJ",
            "secret_access_key": "[ENCRYPTION_KEY]",
            "region": "us-east-1",
            "bucket_name": "test-lambda-hao"
        },
        "is_default": False
    }
    
    response = requests.post(
        f"{API_BASE_URL}/export-destinations/",
        json=destination_data,
        headers={"Authorization": "Bearer test-token"}
    )
    
    if response.status_code != 200 and response.status_code != 201:
        print(f"❌ Failed to create export destination: {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    destination = response.json()
    print(f"✓ Export destination created successfully!")
    print(f"  ID: {destination.get('id')}")
    print(f"  Name: {destination.get('name')}")
    print(f"  Type: {destination.get('destination_type')}")
    
    # List export destinations
    print("\n3. Listing export destinations...")
    
    response = requests.get(
        f"{API_BASE_URL}/export-destinations/",
        headers={"Authorization": "Bearer test-token"}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to list export destinations: {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    destinations = response.json()
    print(f"✓ Found {len(destinations)} export destination(s)")
    for dest in destinations:
        print(f"  - {dest.get('name')} ({dest.get('destination_type')})")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    return True

if __name__ == "__main__":
    try:
        success = test_export_destination_creation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
