#!/usr/bin/env python3
"""
Comprehensive script to fix encryption corruption issues.

This script will:
1. Identify corrupted encrypted data in the database
2. Clean up corrupted entries by setting them to NULL or safe defaults
3. Ensure proper encryption keys exist for all tenants
4. Test encryption functionality after cleanup
"""

import sys
import os
import json
import base64
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

# Add the API directory to the Python path
sys.path.insert(0, '/app')

def setup_environment():
    """Set up the environment for the script."""
    # Set environment variables to prevent hanging during database operations
    os.environ['DB_INIT_PHASE'] = 'false'

    # Import required modules
    try:
        from core.services.encryption_service import get_encryption_service
        from core.services.key_management_service import get_key_management_service
        from core.models.database import SessionLocal, set_tenant_context
        from core.services.tenant_database_manager import tenant_db_manager
        from core.models.models_per_tenant import Expense
        from core.models.models import TenantKey
        
        return {
            'encryption_service': get_encryption_service(),
            'key_management': get_key_management_service(),
            'SessionLocal': SessionLocal,
            'set_tenant_context': set_tenant_context,
            'tenant_db_manager': tenant_db_manager,
            'Expense': Expense,
            'TenantKey': TenantKey
        }
    except Exception as e:
        print(f"❌ Failed to import required modules: {str(e)}")
        sys.exit(1)

def looks_like_encrypted_data(data: str) -> bool:
    """Check if data looks like it might be encrypted (base64-like)."""
    if not data or len(data) < 20:
        return False
    
    try:
        # Check for base64-like characteristics
        import re
        base64_pattern = re.compile(r'^[A-Za-z0-9+/=]+$')
        
        # Must be mostly base64 characters and reasonable length
        return (
            base64_pattern.match(data) and 
            len(data) > 50 and
            len(data) % 4 == 0  # Base64 is always multiple of 4
        )
    except:
        return False

def test_decryption(encryption_service, data: str, tenant_id: int) -> Tuple[bool, str]:
    """Test if data can be decrypted successfully."""
    try:
        decrypted = encryption_service.decrypt_data(data, tenant_id)
        return True, decrypted
    except Exception as e:
        return False, str(e)

def test_json_decryption(encryption_service, data: str, tenant_id: int) -> Tuple[bool, Any]:
    """Test if JSON data can be decrypted successfully."""
    try:
        decrypted = encryption_service.decrypt_json(data, tenant_id)
        return True, decrypted
    except Exception as e:
        return False, str(e)

def ensure_tenant_keys(modules: Dict) -> bool:
    """Ensure all tenants have valid encryption keys."""
    print("🔑 Ensuring all tenants have valid encryption keys...")
    
    try:
        tenant_ids = modules['tenant_db_manager'].get_existing_tenant_ids()
        key_management = modules['key_management']
        
        for tenant_id in tenant_ids:
            try:
                # Try to retrieve the key
                key_material = key_management.retrieve_tenant_key(tenant_id)
                print(f"✅ Tenant {tenant_id} has valid encryption key")
            except Exception as e:
                print(f"🔑 Generating new key for tenant {tenant_id} (error: {str(e)})")
                try:
                    key_id = key_management.generate_tenant_key(tenant_id)
                    print(f"✅ Generated new key for tenant {tenant_id}: {key_id}")
                except Exception as gen_error:
                    print(f"❌ Failed to generate key for tenant {tenant_id}: {str(gen_error)}")
                    return False
        
        return True
    except Exception as e:
        print(f"❌ Failed to ensure tenant keys: {str(e)}")
        return False

def clean_corrupted_expense_data(modules: Dict) -> bool:
    """Clean corrupted encrypted data in expense records."""
    print("🧹 Cleaning corrupted encrypted data in expenses...")
    
    try:
        tenant_ids = modules['tenant_db_manager'].get_existing_tenant_ids()
        encryption_service = modules['encryption_service']
        
        total_cleaned = 0
        
        for tenant_id in tenant_ids:
            print(f"\n🔍 Processing tenant {tenant_id}...")
            
            # Set tenant context
            modules['set_tenant_context'](tenant_id)
            
            # Get tenant session
            SessionLocalTenant = modules['tenant_db_manager'].get_tenant_session(tenant_id)
            db = SessionLocalTenant()
            
            try:
                expenses = db.query(modules['Expense']).all()
                print(f"📄 Found {len(expenses)} expenses for tenant {tenant_id}")
                
                tenant_cleaned = 0
                
                for expense in expenses:
                    expense_updated = False
                    
                    # Check string fields that might be encrypted
                    string_fields = [
                        'notes', 'vendor', 'category', 'reference_number', 'payment_method'
                    ]
                    
                    for field_name in string_fields:
                        field_value = getattr(expense, field_name, None)
                        
                        if field_value and looks_like_encrypted_data(str(field_value)):
                            # This looks like encrypted data, test if it can be decrypted
                            can_decrypt, result = test_decryption(encryption_service, str(field_value), tenant_id)
                            
                            if not can_decrypt:
                                print(f"🧹 Cleaning corrupted {field_name} in expense {expense.id}")
                                setattr(expense, field_name, None)
                                expense_updated = True
                                tenant_cleaned += 1
                    
                    # Check analysis_result (JSON field)
                    if hasattr(expense, 'analysis_result') and expense.analysis_result:
                        if isinstance(expense.analysis_result, str) and looks_like_encrypted_data(expense.analysis_result):
                            # This looks like encrypted JSON data
                            can_decrypt, result = test_json_decryption(encryption_service, expense.analysis_result, tenant_id)
                            
                            if not can_decrypt:
                                print(f"🧹 Cleaning corrupted analysis_result in expense {expense.id}")
                                expense.analysis_result = None
                                expense_updated = True
                                tenant_cleaned += 1
                    
                    if expense_updated:
                        db.add(expense)
                
                # Commit changes for this tenant
                if tenant_cleaned > 0:
                    db.commit()
                    print(f"✅ Cleaned {tenant_cleaned} corrupted fields for tenant {tenant_id}")
                    total_cleaned += tenant_cleaned
                else:
                    print(f"✅ No corrupted data found for tenant {tenant_id}")
                
            finally:
                db.close()
        
        print(f"\n🎉 Total corrupted fields cleaned: {total_cleaned}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to clean corrupted data: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_encryption_functionality(modules: Dict) -> bool:
    """Test that encryption is working properly after cleanup."""
    print("🧪 Testing encryption functionality...")
    
    try:
        encryption_service = modules['encryption_service']
        tenant_ids = modules['tenant_db_manager'].get_existing_tenant_ids()
        
        for tenant_id in tenant_ids:
            print(f"🧪 Testing encryption for tenant {tenant_id}...")
            
            # Test string encryption/decryption
            test_string = f"Test encryption for tenant {tenant_id} at {datetime.now().isoformat()}"
            
            try:
                encrypted = encryption_service.encrypt_data(test_string, tenant_id)
                decrypted = encryption_service.decrypt_data(encrypted, tenant_id)
                
                if decrypted != test_string:
                    print(f"❌ String encryption test failed for tenant {tenant_id}: data mismatch")
                    return False
                
                print(f"✅ String encryption test passed for tenant {tenant_id}")
            except Exception as e:
                print(f"❌ String encryption test failed for tenant {tenant_id}: {str(e)}")
                return False
            
            # Test JSON encryption/decryption
            test_json = {
                "tenant_id": tenant_id,
                "test_data": "encryption_test",
                "timestamp": datetime.now().isoformat(),
                "amount": 123.45,
                "items": ["item1", "item2", "item3"]
            }
            
            try:
                encrypted_json = encryption_service.encrypt_json(test_json, tenant_id)
                decrypted_json = encryption_service.decrypt_json(encrypted_json, tenant_id)
                
                if decrypted_json != test_json:
                    print(f"❌ JSON encryption test failed for tenant {tenant_id}: data mismatch")
                    return False
                
                print(f"✅ JSON encryption test passed for tenant {tenant_id}")
            except Exception as e:
                print(f"❌ JSON encryption test failed for tenant {tenant_id}: {str(e)}")
                return False
        
        print("🎉 All encryption tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Encryption testing failed: {str(e)}")
        return False

def clear_encryption_caches(modules: Dict) -> bool:
    """Clear all encryption caches to ensure fresh state."""
    print("🗄️ Clearing encryption caches...")
    
    try:
        encryption_service = modules['encryption_service']
        key_management = modules['key_management']
        
        # Clear encryption service cache
        encryption_service.clear_cache()
        
        # Clear key management cache
        if hasattr(key_management, '_key_cache'):
            key_management._key_cache.clear()
        if hasattr(key_management, '_cache_timestamps'):
            key_management._cache_timestamps.clear()
        
        print("✅ Encryption caches cleared")
        return True
        
    except Exception as e:
        print(f"❌ Failed to clear caches: {str(e)}")
        return False

def main():
    """Main function to run the encryption corruption fix."""
    print("🚀 Starting Encryption Corruption Fix")
    print("=" * 60)
    
    # Setup environment
    modules = setup_environment()
    
    # Step 1: Clear caches
    if not clear_encryption_caches(modules):
        print("❌ Failed to clear caches")
        sys.exit(1)
    
    # Step 2: Ensure tenant keys exist
    if not ensure_tenant_keys(modules):
        print("❌ Failed to ensure tenant keys")
        sys.exit(1)
    
    # Step 3: Clean corrupted data
    if not clean_corrupted_expense_data(modules):
        print("❌ Failed to clean corrupted data")
        sys.exit(1)
    
    # Step 4: Test encryption functionality
    if not test_encryption_functionality(modules):
        print("❌ Encryption functionality test failed")
        sys.exit(1)
    
    print("\n🎉 Encryption corruption fix completed successfully!")
    print("✅ All corrupted data has been cleaned")
    print("✅ Encryption keys are working properly")
    print("✅ System should now function normally")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)