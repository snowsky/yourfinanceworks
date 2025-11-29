#!/usr/bin/env python3
"""
Debug Batch API Key Issues

This script helps diagnose why batch processing API calls are failing with TENANT_CONTEXT_REQUIRED.
"""

import sys
import os
import hashlib
import secrets

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.api_models import APIClient


def get_db_session():
    """Get database session for master database."""
    db_host = os.getenv('POSTGRES_HOST', 'invoice_app_db')
    db_port = os.getenv('POSTGRES_PORT', '5432')
    db_name = os.getenv('POSTGRES_DB', 'invoice_db')
    db_user = os.getenv('POSTGRES_USER', 'invoice_user')
    db_password = os.getenv('POSTGRES_PASSWORD', 'invoice_password')
    
    db_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_api_key(api_key: str):
    """Test if an API key exists and is properly configured."""
    print(f"\n🔍 Testing API key: {api_key[:7]}...")
    
    # Hash the API key
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    print(f"   Hash: {api_key_hash[:16]}...")
    
    db = get_db_session()
    
    try:
        # Query for the API client
        api_client = db.query(APIClient).filter(
            APIClient.api_key_hash == api_key_hash
        ).first()
        
        if not api_client:
            print(f"\n❌ API key NOT found in database!")
            print(f"\n💡 Possible issues:")
            print(f"   1. API key was not created correctly")
            print(f"   2. API key hash doesn't match (typo in key?)")
            print(f"   3. API key was deleted")
            
            # List all API clients
            print(f"\n📋 Existing API clients in database:")
            all_clients = db.query(APIClient).all()
            if all_clients:
                for client in all_clients:
                    print(f"   - {client.client_id}: {client.client_name} (tenant {client.tenant_id}, user {client.user_id})")
            else:
                print(f"   (none found)")
            return False
        
        print(f"\n✅ API key found!")
        print(f"   Client ID: {api_client.client_id}")
        print(f"   Client Name: {api_client.client_name}")
        print(f"   User ID: {api_client.user_id}")
        print(f"   Tenant ID: {api_client.tenant_id}")
        print(f"   Status: {api_client.status}")
        print(f"   Is Active: {api_client.is_active}")
        print(f"   Rate Limits: {api_client.rate_limit_per_minute}/min, {api_client.rate_limit_per_hour}/hour")
        
        # Check if status is correct
        if api_client.status != "active":
            print(f"\n⚠️  WARNING: API client status is '{api_client.status}', not 'active'")
            return False
        
        if not api_client.is_active:
            print(f"\n⚠️  WARNING: API client is_active is False")
            return False
        
        # Check if tenant exists
        print(f"\n🔍 Checking tenant {api_client.tenant_id}...")
        from core.models.models import Tenant
        tenant = db.query(Tenant).filter(Tenant.id == api_client.tenant_id).first()
        
        if not tenant:
            print(f"   ❌ Tenant {api_client.tenant_id} NOT found!")
            return False
        
        print(f"   ✅ Tenant found: {tenant.name}")
        
        # Check if user exists
        print(f"\n🔍 Checking user {api_client.user_id}...")
        from core.models.models import MasterUser
        user = db.query(MasterUser).filter(MasterUser.id == api_client.user_id).first()
        
        if not user:
            print(f"   ❌ User {api_client.user_id} NOT found!")
            return False
        
        print(f"   ✅ User found: {user.email}")
        
        print(f"\n✅ API key is properly configured!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def list_all_api_clients():
    """List all API clients in the database."""
    print(f"\n📋 All API clients in database:")
    
    db = get_db_session()
    
    try:
        clients = db.query(APIClient).all()
        
        if not clients:
            print(f"   (none found)")
            return
        
        for client in clients:
            status_icon = "✅" if (client.status == "active" and client.is_active) else "❌"
            print(f"\n   {status_icon} {client.client_id}")
            print(f"      Name: {client.client_name}")
            print(f"      User ID: {client.user_id}")
            print(f"      Tenant ID: {client.tenant_id}")
            print(f"      Status: {client.status}")
            print(f"      Is Active: {client.is_active}")
            print(f"      API Key Prefix: {client.api_key_prefix}")
            
    except Exception as e:
        print(f"   Error: {e}")
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Debug batch API key issues'
    )
    
    parser.add_argument(
        '--api-key',
        help='API key to test'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all API clients'
    )
    
    args = parser.parse_args()
    
    if args.api_key:
        success = test_api_key(args.api_key)
        sys.exit(0 if success else 1)
    elif args.list:
        list_all_api_clients()
    else:
        # Try to get API key from environment
        api_key = os.getenv('API_KEY')
        if api_key:
            print(f"Testing API key from API_KEY environment variable...")
            success = test_api_key(api_key)
            sys.exit(0 if success else 1)
        else:
            print("Usage:")
            print("  python debug_batch_api_key.py --api-key <your-api-key>")
            print("  python debug_batch_api_key.py --list")
            print("  API_KEY=<your-api-key> python debug_batch_api_key.py")
            sys.exit(1)


if __name__ == '__main__':
    main()
