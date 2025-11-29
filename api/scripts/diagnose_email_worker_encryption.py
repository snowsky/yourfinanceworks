#!/usr/bin/env python3
"""
Diagnostic script for email worker encryption issues.

This script helps diagnose why the email worker is failing to decrypt data
by checking:
1. Master key availability
2. Tenant key availability
3. Sample data decryption
4. Key consistency
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from core.models.database import get_master_db, set_tenant_context
from core.models.models import Tenant, TenantKey
from core.models.models_per_tenant import User
from core.services.tenant_database_manager import tenant_db_manager
from core.services.key_management_service import get_key_management_service
from core.services.encryption_service import get_encryption_service
from encryption_config import EncryptionConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def diagnose_encryption_for_tenant(tenant_id: int):
    """Diagnose encryption issues for a specific tenant."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Diagnosing encryption for tenant {tenant_id}")
    logger.info(f"{'='*60}\n")
    
    # 1. Check encryption configuration
    logger.info("1. Checking encryption configuration...")
    config = EncryptionConfig()
    logger.info(f"   - Encryption enabled: {config.ENCRYPTION_ENABLED}")
    logger.info(f"   - Algorithm: {config.ENCRYPTION_ALGORITHM}")
    logger.info(f"   - Key vault provider: {config.KEY_VAULT_PROVIDER}")
    logger.info(f"   - Master key path: {config.MASTER_KEY_PATH}")
    
    # 2. Check master key
    logger.info("\n2. Checking master key...")
    key_mgmt = get_key_management_service()
    try:
        if key_mgmt._master_key:
            logger.info(f"   ✓ Master key loaded (length: {len(key_mgmt._master_key)} bytes)")
        else:
            logger.error("   ✗ Master key not loaded!")
            return False
    except Exception as e:
        logger.error(f"   ✗ Error checking master key: {e}")
        return False
    
    # 3. Check tenant key in database
    logger.info("\n3. Checking tenant key in database...")
    master_db = next(get_master_db())
    try:
        tenant_key_record = master_db.query(TenantKey).filter(
            TenantKey.tenant_id == tenant_id,
            TenantKey.is_active == True
        ).first()
        
        if tenant_key_record:
            logger.info(f"   ✓ Tenant key found:")
            logger.info(f"     - Key ID: {tenant_key_record.key_id}")
            logger.info(f"     - Algorithm: {tenant_key_record.algorithm}")
            logger.info(f"     - Version: {tenant_key_record.version}")
            logger.info(f"     - Created: {tenant_key_record.created_at}")
            logger.info(f"     - Updated: {tenant_key_record.updated_at}")
        else:
            logger.error(f"   ✗ No active tenant key found for tenant {tenant_id}")
            return False
    finally:
        master_db.close()
    
    # 4. Try to retrieve and decrypt tenant key
    logger.info("\n4. Testing tenant key retrieval and decryption...")
    try:
        tenant_key_material = key_mgmt.retrieve_tenant_key(tenant_id)
        logger.info(f"   ✓ Successfully retrieved and decrypted tenant key")
        logger.info(f"     - Key material length: {len(tenant_key_material)} characters")
    except Exception as e:
        logger.error(f"   ✗ Failed to retrieve tenant key: {e}")
        return False
    
    # 5. Test encryption/decryption round-trip
    logger.info("\n5. Testing encryption/decryption round-trip...")
    try:
        encryption_service = get_encryption_service()
        test_data = "test_data_12345"
        
        # Encrypt
        encrypted = encryption_service.encrypt_data(test_data, tenant_id)
        logger.info(f"   ✓ Encryption successful")
        logger.info(f"     - Encrypted length: {len(encrypted)} characters")
        
        # Decrypt
        decrypted = encryption_service.decrypt_data(encrypted, tenant_id)
        logger.info(f"   ✓ Decryption successful")
        
        # Verify
        if decrypted == test_data:
            logger.info(f"   ✓ Round-trip verification successful")
        else:
            logger.error(f"   ✗ Round-trip verification failed!")
            logger.error(f"     - Original: {test_data}")
            logger.error(f"     - Decrypted: {decrypted}")
            return False
    except Exception as e:
        logger.error(f"   ✗ Encryption/decryption test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    # 6. Check tenant database and sample encrypted data
    logger.info("\n6. Checking tenant database and sample data...")
    set_tenant_context(tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(tenant_id)
    
    if not SessionLocal:
        logger.error(f"   ✗ Could not get tenant database session")
        return False
    
    tenant_db = SessionLocal()
    try:
        # Count users
        user_count = tenant_db.query(User).count()
        logger.info(f"   - Total users in tenant database: {user_count}")
        
        if user_count > 0:
            # Try to query first user (this will trigger decryption)
            logger.info("\n7. Testing actual data decryption...")
            try:
                first_user = tenant_db.query(User).first()
                logger.info(f"   ✓ Successfully queried user:")
                logger.info(f"     - User ID: {first_user.id}")
                logger.info(f"     - Email: {first_user.email[:20]}..." if first_user.email else "     - Email: None")
                logger.info(f"     - First name: {first_user.first_name}" if first_user.first_name else "     - First name: None")
                logger.info(f"     - Last name: {first_user.last_name}" if first_user.last_name else "     - Last name: None")
            except Exception as e:
                logger.error(f"   ✗ Failed to decrypt user data: {e}")
                logger.error(f"   This indicates the data was encrypted with a different key!")
                import traceback
                logger.error(traceback.format_exc())
                return False
        else:
            logger.info("   - No users found in database (nothing to decrypt)")
    finally:
        tenant_db.close()
    
    logger.info(f"\n{'='*60}")
    logger.info("✓ All encryption checks passed!")
    logger.info(f"{'='*60}\n")
    return True


def main():
    """Main diagnostic function."""
    logger.info("Email Worker Encryption Diagnostic Tool")
    logger.info("=" * 60)
    
    # Get all active tenants
    master_db = next(get_master_db())
    try:
        tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        logger.info(f"Found {len(tenants)} active tenant(s)\n")
        
        all_passed = True
        for tenant in tenants:
            passed = diagnose_encryption_for_tenant(tenant.id)
            if not passed:
                all_passed = False
                logger.error(f"\n⚠️  Tenant {tenant.id} has encryption issues!")
        
        if all_passed:
            logger.info("\n✓ All tenants passed encryption diagnostics")
            return 0
        else:
            logger.error("\n✗ Some tenants have encryption issues")
            logger.error("\nPossible solutions:")
            logger.error("1. If master key was changed, restore the original master key")
            logger.error("2. Run the re-encryption script to re-encrypt all data with current key")
            logger.error("3. Clear and re-initialize the tenant database")
            return 1
    finally:
        master_db.close()


if __name__ == "__main__":
    sys.exit(main())
