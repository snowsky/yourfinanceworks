#!/usr/bin/env python3
"""
Test script for email availability endpoint
"""

import requests
import json
import sys
import os

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000/api/v1"

def test_email_availability():
    """Test the email availability endpoint"""
    
    test_cases = [
        {
            "email": "new.user@example.com",
            "expected_available": True,
            "description": "New email should be available"
        },
        {
            "email": "invalid-email",
            "expected_error": True,
            "description": "Invalid email format should return error"
        },
        {
            "email": "",
            "expected_error": True,
            "description": "Empty email should return error"
        },
        {
            "email": "ab",
            "expected_error": True,
            "description": "Too short email should return error"
        }
    ]
    
    print("Testing email availability endpoint...")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"Email: '{test_case['email']}'")
        
        try:
            response = requests.get(
                f"{BASE_URL}/auth/check-email-availability",
                params={"email": test_case['email']}
            )
            
            if test_case.get('expected_error'):
                if response.status_code != 200:
                    print(f"✅ Expected error received: {response.status_code}")
                    if response.status_code == 400:
                        error_data = response.json()
                        print(f"   Error detail: {error_data.get('detail', 'N/A')}")
                else:
                    print(f"❌ Expected error but got 200: {response.json()}")
            else:
                if response.status_code == 200:
                    data = response.json()
                    available = data.get('available')
                    email = data.get('email')
                    
                    print(f"✅ Response: available={available}, email='{email}'")
                    
                    if available == test_case['expected_available']:
                        print("✅ Availability matches expected result")
                    else:
                        print(f"❌ Expected available={test_case['expected_available']}, got {available}")
                else:
                    print(f"❌ Expected 200 but got {response.status_code}: {response.text}")
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    print("\n" + "=" * 50)
    print("Email availability testing completed!")

if __name__ == "__main__":
    test_email_availability() 