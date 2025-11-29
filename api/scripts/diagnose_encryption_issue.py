#!/usr/bin/env python3
"""
Diagnostic script to identify encryption issues for a specific tenant.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db, set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from core.services.encryption_service import EncryptionService
from sqlalchemy import inspect, text
import traceback


def diagnose_tenant_encryption(tenant_id: int):
    """Diagnose encryption issues for a specific tenant."""
    
    print(f"\n{'='*60}")
    print(f"🔍 Diagnosing Encryption for Tenant {tenant_id}")
    print(f"{'='*60}\n")
    
    # Step 1: Check master database encryption keys
    print("📋 Step 1: Checking Master Database Encryption Keys")
    print("-" * 60)
    
    master_db = next(get_master_db())
    try:
        result = master_db.execute(
            text("SELECT id, tenant_id, key_version, is_active, created_at FROM encryption_keys WHERE tenant_id = :tid ORDER BY created_at DESC"),
            {"tid": tenant_id}
        ).fetchall()
        
        if result:
            print(f"✅ Found {len(result)} encryption key(s) in master database:")
            for row in result:
                print(f"   - ID: {row[0]}, Version: {row[2]}, Active: {row[3]}, Created: {row[4]}")
        else:
            print(f"❌ No encryption keys found for tenant {tenant_id} in master database")
            return
    except Exception as e:
        print(f"❌ Error querying master database: {e}")
        traceback.print_exc()
        return
    finally:
        master_db.close()
    
    # Step 2: Test encryption service
    print(f"\n📋 Step 2: Testing Encryption Service")
    print("-" * 60)
    
    set_tenant_context(tenant_id)
    encryption_service = EncryptionService()
    
    try:
        # Try to get the key
        print(f"🔑 Attempting to retrieve encryption key for tenant {tenant_id}...")
        key = encryption_service._get_tenant_key(tenant_id)
        if key:
            print(f"✅ Successfully retrieved encryption key")
            print(f"   Key version: {key.key_version}")
            print(f"   Is active: {key.is_active}")
        else:
            print(f"❌ Failed to retrieve encryption key (returned None)")
    except Exception as e:
        print(f"❌ Error retrieving encryption key: {e}")
        traceback.print_exc()
    
    # Step 3: Test encryption/decryption
    print(f"\n📋 Step 3: Testing Encryption/Decryption")
    print("-" * 60)
    
    test_data = "test_encryption_data_12345"
    try:
        print(f"🔐 Encrypting test data: '{test_data}'")
        encrypted = encryption_service.encrypt(test_data, tenant_id)
        print(f"✅ Encryption successful: {encrypted[:50]}...")
        
        print(f"🔓 Decrypting test data...")
        decrypted = encryption_service.decrypt(encrypted, tenant_id)
        print(f"✅ Decryption successful: '{decrypted}'")
        
        if decrypted == test_data:
            print(f"✅ Encryption/Decryption working correctly!")
        else:
            print(f"❌ Decrypted data doesn't match original")
    except Exception as e:
        print(f"❌ Encryption/Decryption test failed: {e}")
        traceback.print_exc()
    
    # Step 4: Check tenant database for encrypted columns
    print(f"\n📋 Step 4: Checking Tenant Database for Encrypted Data")
    print("-" * 60)
    
    try:
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()
        
        # Check Settings table (has encrypted columns)
        print(f"\n🔍 Checking 'settings' table...")
        settings_result = tenant_db.execute(
            text("SELECT id, key, value FROM settings WHERE value IS NOT NULL LIMIT 5")
        ).fetchall()
        
        if settings_result:
            print(f"   Found {len(settings_result)} settings records")
            for row in settings_result:
                print(f"   - ID: {row[0]}, Key: {row[1]}, Value length: {len(str(row[2])) if row[2] else 0}")
        else:
            print(f"   No settings records found")
        
        # Check AIConfig table (has encrypted columns)
        print(f"\n🔍 Checking 'ai_configs' table...")
        ai_config_result = tenant_db.execute(
            text("SELECT id, provider_name, api_key FROM ai_configs WHERE api_key IS NOT NULL LIMIT 5")
        ).fetchall()
        
        if ai_config_result:
            print(f"   Found {len(ai_config_result)} AI config records with API keys")
            for row in ai_config_result:
                api_key_preview = str(row[2])[:50] if row[2] else "None"
                print(f"   - ID: {row[0]}, Provider: {row[1]}, API Key: {api_key_preview}...")
                
                # Try to decrypt
                if row[2]:
                    try:
                        decrypted = encryption_service.decrypt(row[2], tenant_id)
                        print(f"     ✅ Successfully decrypted API key")
                    except Exception as e:
                        print(f"     ❌ Failed to decrypt API key: {e}")
        else:
            print(f"   No AI config records with API keys found")
        
        tenant_db.close()
        
    except Exception as e:
        print(f"❌ Error checking tenant database: {e}")
        traceback.print_exc()
    
    # Step 5: Summary
    print(f"\n{'='*60}")
    print(f"📊 Diagnosis Summary")
    print(f"{'='*60}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Check the output above to identify the issue.")
    print(f"\nCommon issues:")
    print(f"  1. Encryption key exists but can't be retrieved (cache issue)")
    print(f"  2. Data encrypted with old key (key rotation issue)")
    print(f"  3. Corrupted encrypted data in database")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnose encryption issues for a tenant")
    parser.add_argument("--tenant-id", type=int, required=True, help="Tenant ID to diagnose")
    
    args = parser.parse_args()
    
    diagnose_tenant_encryption(args.tenant_id)
