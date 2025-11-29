#!/usr/bin/env python3
"""
Test Batch API Key by making actual API calls

This script tests if your API key works by making a real request to the batch processing endpoint.
"""

import sys
import requests
import json


def test_batch_api_key(api_key: str, api_url: str = "http://localhost:8000"):
    """Test if an API key works by making a request to the batch processing endpoint."""
    
    print(f"\n🔍 Testing API key: {api_key[:7]}...")
    print(f"   API URL: {api_url}")
    
    # Test 1: Try to list jobs (should work if API key is valid)
    print(f"\n📋 Test 1: Listing jobs...")
    
    headers = {
        "X-API-Key": api_key
    }
    
    try:
        response = requests.get(
            f"{api_url}/api/v1/external-transactions/batch-processing/jobs",
            headers=headers,
            timeout=5
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ API key is valid!")
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
            return True
        elif response.status_code == 401:
            print(f"   ❌ Unauthorized (401)")
            try:
                error = response.json()
                print(f"   Error: {error.get('detail', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return False
        else:
            print(f"   ❌ Unexpected status code")
            try:
                error = response.json()
                print(f"   Error: {json.dumps(error, indent=2)}")
            except:
                print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Connection error: {e}")
        print(f"   Make sure the API is running at {api_url}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Main entry point."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(
        description='Test batch API key'
    )
    
    parser.add_argument(
        '--api-key',
        help='API key to test'
    )
    parser.add_argument(
        '--api-url',
        default='http://localhost:8000',
        help='API URL (default: http://localhost:8000)'
    )
    
    args = parser.parse_args()
    
    # Get API key from argument or environment
    api_key = args.api_key or os.getenv('API_KEY')
    
    if not api_key:
        print("Usage:")
        print("  python test_batch_api_key.py --api-key <your-api-key>")
        print("  API_KEY=<your-api-key> python test_batch_api_key.py")
        sys.exit(1)
    
    success = test_batch_api_key(api_key, args.api_url)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
