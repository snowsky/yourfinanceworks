#!/usr/bin/env python3
"""
Compare the actual encryption keys being used by both containers.
"""

import os
import sys
import logging
import base64

# Add the API directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Compare actual encryption keys."""
    logger.info("Comparing actual encryption keys...")
    
    try:
        from core.models.database import set_tenant_context
        from core.services.key_management_service import get_key_management_service
        from core.services.encryption_service import get_encryption_service
        
        # Set tenant context
        set_tenant_context(1)
        
        # Get key management service
        key_service = get_key_management_service()
        
        # Get the actual tenant key being used
        tenant_key_b64 = key_service.retrieve_tenant_key(1)
        logger.info(f"Tenant key (base64): {tenant_key_b64}")
        
        # Decode to get the actual key bytes
        tenant_key_bytes = base64.b64decode(tenant_key_b64)
        logger.info(f"Tenant key (hex): {tenant_key_bytes.hex()}")
        logger.info(f"Tenant key length: {len(tenant_key_bytes)} bytes")
        
        # Get encryption service and test encryption
        encryption_service = get_encryption_service()
        
        # Test encrypt/decrypt cycle
        test_data = "GoodLife Fitness"
        encrypted = encryption_service.encrypt_data(test_data, 1)
        logger.info(f"Test encryption result: {encrypted}")
        
        decrypted = encryption_service.decrypt_data(encrypted, 1)
        logger.info(f"Test decryption result: {decrypted}")
        
        # Test the problematic encrypted data
        problematic_data = "2P8b4rMdeTVEZXqqzD+EQzUBzW/dgHQpJNEwjfhy7Yk+4TDLGiYybkaTB5I="
        try:
            decrypted_problematic = encryption_service.decrypt_data(problematic_data, 1)
            logger.info(f"✅ Problematic data decrypted: {decrypted_problematic}")
        except Exception as e:
            logger.error(f"❌ Problematic data failed: {e}")
        
    except Exception as e:
        logger.error(f"Error comparing keys: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)