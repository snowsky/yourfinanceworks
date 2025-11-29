#!/usr/bin/env python3
"""
Create Export Destination via API

This script creates an export destination using the API instead of direct database access.
"""

import sys
import requests
import json


def create_export_destination(api_url: str = "http://localhost:8000", jwt_token: str = None):
    """Create an export destination via API."""
    
    if not jwt_token:
        print("❌ Error: JWT token required")
        print("\nTo get a JWT token:")
        print("1. Login to http://localhost:8080")
        print("2. Open browser DevTools (F12)")
        print("3. Go to Application → Cookies")
        print("4. Find the 'access_token' cookie and copy its value")
        print("\nUsage:")
        print("  python create_export_destination_via_api.py --token <your-jwt-token>")
        sys.exit(1)
    
    print(f"\n📝 Creating export destination...")
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": "Default Export",
        "description": "Default export destination for batch processing",
        "destination_type": "local",
        "config": {
            "path": "/exports",
            "format": "csv"
        },
        "is_default": True
    }
    
    try:
        response = requests.post(
            f"{api_url}/api/v1/export-destinations",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 201:
            data = response.json()
            print(f"✅ Export destination created successfully!")
            print(f"   ID: {data.get('id')}")
            print(f"   Name: {data.get('name')}")
            print(f"   Type: {data.get('destination_type')}")
            print(f"   Is Default: {data.get('is_default')}")
            return True
        else:
            print(f"❌ Failed to create export destination")
            try:
                error = response.json()
                print(f"   Error: {json.dumps(error, indent=2)}")
            except:
                print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        print(f"   Make sure the API is running at {api_url}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Create export destination via API'
    )
    
    parser.add_argument(
        '--token',
        required=True,
        help='JWT token for authentication'
    )
    parser.add_argument(
        '--api-url',
        default='http://localhost:8000',
        help='API URL (default: http://localhost:8000)'
    )
    
    args = parser.parse_args()
    
    success = create_export_destination(args.api_url, args.token)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
