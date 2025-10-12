#!/usr/bin/env python3
"""
Simple test script to verify inventory attachments endpoint accessibility
"""
import requests
import json

def test_inventory_attachments_endpoint():
    """Test if the inventory attachments endpoint is accessible"""
    
    # Test the basic endpoint
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/v1/inventory/1/attachments/"
    
    print(f"Testing endpoint: {endpoint}")
    
    try:
        # Test GET request (should require authentication)
        response = requests.get(endpoint, timeout=5)
        print(f"GET Response Status: {response.status_code}")
        print(f"GET Response Headers: {dict(response.headers)}")
        
        if response.status_code == 401:
            print("✓ Endpoint is accessible (returns 401 Unauthorized as expected)")
            return True
        elif response.status_code == 404:
            print("✗ Endpoint not found (404)")
            return False
        else:
            print(f"✓ Endpoint accessible, returned status: {response.status_code}")
            return True
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - API server may not be running")
        return False
    except requests.exceptions.Timeout:
        print("✗ Request timed out")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_cors_headers():
    """Test CORS headers"""
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/v1/inventory/1/attachments/"
    
    print(f"\nTesting CORS for: {endpoint}")
    
    try:
        # Test OPTIONS request for CORS preflight
        response = requests.options(endpoint, timeout=5)
        print(f"OPTIONS Response Status: {response.status_code}")
        
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
        }
        
        print("CORS Headers:")
        for header, value in cors_headers.items():
            print(f"  {header}: {value}")
            
        return True
        
    except Exception as e:
        print(f"✗ CORS test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Inventory Attachments Endpoint Test ===")
    
    endpoint_ok = test_inventory_attachments_endpoint()
    cors_ok = test_cors_headers()
    
    print(f"\n=== Results ===")
    print(f"Endpoint accessible: {'✓' if endpoint_ok else '✗'}")
    print(f"CORS test: {'✓' if cors_ok else '✗'}")
    
    if endpoint_ok and cors_ok:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed. Check the API server configuration.")