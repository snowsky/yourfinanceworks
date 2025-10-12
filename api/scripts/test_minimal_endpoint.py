#!/usr/bin/env python3
"""
Test the minimal inventory attachments endpoint
"""
import requests
import json

def test_minimal_endpoint():
    """Test the minimal inventory attachments endpoint"""
    
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/v1/inventory/1/attachments/"
    
    print(f"Testing minimal endpoint: {endpoint}")
    
    try:
        # Test GET request
        response = requests.get(endpoint, timeout=5)
        print(f"GET Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ GET endpoint is working")
            print(f"Response: {response.json()}")
        elif response.status_code == 401:
            print("✓ Endpoint accessible (requires authentication)")
        else:
            print(f"Response: {response.text}")
            
        return True
        
    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - API server may not be running")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    test_minimal_endpoint()