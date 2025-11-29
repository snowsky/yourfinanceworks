#!/usr/bin/env python3
"""
Create API Key for Batch Processing

This script creates an API client with an API key for batch processing.
The key is properly hashed and stored in the database.

Usage:
    python api/scripts/create_batch_api_key.py --user-id 1 --tenant-id 1 --name "Batch Processing Client"
"""

import sys
import os
import secrets
import hashlib
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.api_models import APIClient


def get_db_session():
    """Get database session for master database."""
    # Use the same database configuration as the main app
    db_host = os.getenv('POSTGRES_HOST', 'invoice_app_db')
    db_port = os.getenv('POSTGRES_PORT', '5432')
    db_name = os.getenv('POSTGRES_DB', 'invoice_db')
    db_user = os.getenv('POSTGRES_USER', 'invoice_user')
    db_password = os.getenv('POSTGRES_PASSWORD', 'invoice_password')
    
    db_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    
    print(f"Connecting to database at {db_host}:{db_port}/{db_name}...")
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"ak_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_api_key_prefix(api_key: str) -> str:
    """Get the first 7 characters of API key for identification."""
    return api_key[:7] + "..."


def create_api_client(
    user_id: int,
    tenant_id: int,
    name: str = "Batch Processing Client",
    description: str = "API client for batch file processing"
) -> tuple[APIClient, str]:
    """
    Create an API client with proper configuration for batch processing.
    
    Args:
        user_id: User ID who owns this API client
        tenant_id: Tenant ID
        name: Client name
        description: Client description
        
    Returns:
        Tuple of (APIClient instance, plain text API key)
    """
    # Generate API key
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)
    api_key_prefix = get_api_key_prefix(api_key)
    
    # Generate client ID
    client_id = f"client_{secrets.token_urlsafe(16)}"
    
    # Create API client
    db = get_db_session()
    
    try:
        api_client = APIClient(
            client_id=client_id,
            client_name=name,
            client_description=description,
            user_id=user_id,
            tenant_id=tenant_id,
            api_key_hash=api_key_hash,
            api_key_prefix=api_key_prefix,
            allowed_document_types=["invoice", "expense", "statement"],
            rate_limit_per_minute=60,
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000,
            custom_quotas={
                "max_concurrent_jobs": 10,
                "max_files_per_job": 50
            },
            status="active",
            is_active=True,
            is_sandbox=False,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(api_client)
        db.commit()
        db.refresh(api_client)
        
        print(f"✅ API Client created successfully!")
        print(f"   Client ID: {api_client.client_id}")
        print(f"   Client Name: {api_client.client_name}")
        print(f"   User ID: {api_client.user_id}")
        print(f"   Tenant ID: {api_client.tenant_id}")
        print(f"   Status: {api_client.status}")
        print(f"   Rate Limits: {api_client.rate_limit_per_minute}/min, {api_client.rate_limit_per_hour}/hour")
        print(f"\n🔑 API Key (save this - it won't be shown again):")
        print(f"   {api_key}")
        print(f"\n💡 Usage:")
        print(f"   export API_KEY='{api_key}'")
        print(f"   python api/scripts/batch_upload_files.py --files *.pdf")
        
        return api_client, api_key
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating API client: {e}")
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Create an API key for batch processing',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--user-id',
        type=int,
        required=True,
        help='User ID who will own this API client'
    )
    parser.add_argument(
        '--tenant-id',
        type=int,
        required=True,
        help='Tenant ID'
    )
    parser.add_argument(
        '--name',
        default='Batch Processing Client',
        help='Client name (default: Batch Processing Client)'
    )
    parser.add_argument(
        '--description',
        default='API client for batch file processing',
        help='Client description'
    )
    
    args = parser.parse_args()
    
    print(f"Creating API client for user {args.user_id}, tenant {args.tenant_id}...")
    print()
    
    try:
        create_api_client(
            user_id=args.user_id,
            tenant_id=args.tenant_id,
            name=args.name,
            description=args.description
        )
    except Exception as e:
        print(f"\n❌ Failed to create API client: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
