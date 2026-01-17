#!/usr/bin/env python3
"""
Create API Key for Batch Processing via Docker
"""

import sys
import os
import secrets
import hashlib
from datetime import datetime, timezone

# Set environment variables for Docker database
os.environ['DATABASE_URL'] = 'postgresql://postgres:password@localhost:5432/invoice_master'
os.environ['POSTGRES_HOST'] = 'localhost'
os.environ['POSTGRES_PORT'] = '5432'
os.environ['POSTGRES_DB'] = 'invoice_master'
os.environ['POSTGRES_USER'] = 'postgres'
os.environ['POSTGRES_PASSWORD'] = 'password'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("❌ Error: psycopg2 not installed")
    print("   Run: pip install psycopg2-binary")
    sys.exit(1)


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"ak_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_api_key_prefix(api_key: str) -> str:
    """Get the first 7 characters of API key for identification."""
    return api_key[:7] + "..."


def create_api_client(user_id: int = 1, tenant_id: int = 1):
    """Create an API client for batch processing."""
    
    # Generate API key
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)
    api_key_prefix = get_api_key_prefix(api_key)
    
    # Generate client ID
    client_id = f"client_{secrets.token_urlsafe(16)}"
    
    print(f"🔗 Connecting to PostgreSQL...")
    
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            database="invoice_master",
            user="postgres",
            password="password",
            connect_timeout=5
        )
        
        cursor = conn.cursor()
        
        # Insert API client
        insert_sql = """
        INSERT INTO api_clients (
            client_id, client_name, client_description, user_id, tenant_id,
            api_key_hash, api_key_prefix, allowed_document_types,
            rate_limit_per_minute, rate_limit_per_hour, rate_limit_per_day,
            custom_quotas, status, is_active, is_sandbox, created_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        """
        
        cursor.execute(insert_sql, (
            client_id,
            "Batch Processing Client",
            "API client for batch file processing",
            user_id,
            tenant_id,
            api_key_hash,
            api_key_prefix,
            '["invoice", "expense", "statement"]',  # JSON array as string
            60,  # rate_limit_per_minute
            1000,  # rate_limit_per_hour
            10000,  # rate_limit_per_day
            '{"max_concurrent_jobs": 10, "max_files_per_job": 50}',  # custom_quotas as JSON
            "active",
            True,
            False,
            datetime.now(timezone.utc)
        ))
        
        conn.commit()
        
        print(f"✅ API Client created successfully!")
        print(f"   Client ID: {client_id}")
        print(f"   User ID: {user_id}")
        print(f"   Tenant ID: {tenant_id}")
        print(f"\n🔑 API Key (save this - it won't be shown again):")
        print(f"   {api_key}")
        print(f"\n💡 Usage:")
        print(f"   export API_KEY='{api_key}'")
        print(f"   python api/scripts/batch_upload_files.py --files *.pdf")
        
        cursor.close()
        conn.close()
        
        return api_key
        
    except psycopg2.OperationalError as e:
        print(f"❌ Connection error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    api_key = create_api_client()
    sys.exit(0 if api_key else 1)
