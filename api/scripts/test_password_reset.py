#!/usr/bin/env python3
"""
Test script for password reset functionality
"""

import requests
import json
import sys
import os

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000/api/v1"

def test_password_reset_flow():
    """Test the complete password reset flow"""
    
    print("Testing password reset functionality...")
    print("=" * 60)
    
    # Test 1: Request password reset for existing user
    print("\n1. Testing password reset request for existing user...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/request-password-reset",
            json={"email": "test@example.com"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Password reset request successful")
            print(f"   Message: {data.get('message')}")
            print(f"   Success: {data.get('success')}")
        else:
            print(f"❌ Password reset request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during password reset request: {e}")
    
    # Test 2: Request password reset for non-existing user
    print("\n2. Testing password reset request for non-existing user...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/request-password-reset",
            json={"email": "nonexistent@example.com"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Password reset request handled correctly (prevents email enumeration)")
            print(f"   Message: {data.get('message')}")
            print(f"   Success: {data.get('success')}")
        else:
            print(f"❌ Password reset request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during password reset request: {e}")
    
    # Test 3: Test invalid email format
    print("\n3. Testing password reset request with invalid email...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/request-password-reset",
            json={"email": "invalid-email"}
        )
        
        if response.status_code == 422:
            print(f"✅ Invalid email format properly rejected")
        else:
            print(f"❌ Expected 422 for invalid email, got {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during invalid email test: {e}")
    
    # Test 4: Test reset with invalid token
    print("\n4. Testing password reset with invalid token...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/reset-password",
            json={
                "token": "invalid-token-12345",
                "new_password": "newpassword123"
            }
        )
        
        if response.status_code == 400:
            data = response.json()
            print(f"✅ Invalid token properly rejected")
            print(f"   Error: {data.get('detail')}")
        else:
            print(f"❌ Expected 400 for invalid token, got {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during invalid token test: {e}")
    
    # Test 5: Test reset with short password
    print("\n5. Testing password reset with short password...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/reset-password",
            json={
                "token": "some-valid-token",
                "new_password": "123"
            }
        )
        
        if response.status_code == 400:
            data = response.json()
            print(f"✅ Short password properly rejected")
            print(f"   Error: {data.get('detail')}")
        else:
            print(f"❌ Expected 400 for short password, got {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during short password test: {e}")
    
    print("\n" + "=" * 60)
    print("Password reset testing completed!")
    print("\nNOTE: Check the API logs for actual password reset tokens to test the full flow.")

if __name__ == "__main__":
    test_password_reset_flow() 