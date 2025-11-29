#!/usr/bin/env python3
"""
Encryption initialization script for production deployment.
This script sets up the encryption system during application startup.
"""

import os
import sys
import logging
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from encryption_config import EncryptionConfig
from core.services.key_management_service import KeyManagementService
from core.services.encryption_service import EncryptionService
from commercial.integrations.key_vault_factory import KeyVaultFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ensure_key_directory(config):
    """Ensure the encryption key directory exists."""
    key_dir = Path(config.MASTER_KEY_PATH).parent
    key_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    logger.info(f"Ensured key directory exists: {key_dir}")


def initialize_master_key():
    """Initialize the master key if it doesn't exist."""
    try:
        # For local provider, KeyManagementService handles master key initialization
        key_management = KeyManagementService()
        logger.info("Key management service initialized successfully")
        
        # Test key generation for tenant 1 to ensure everything works
        try:
            # Check if tenant 1 already has a key
            existing_key = key_management.get_tenant_key(1)
            if existing_key:
                logger.info("Tenant 1 already has an encryption key")
            else:
                logger.info("Generating key for tenant 1...")
                key_id = key_management.generate_tenant_key(1)
                logger.info(f"Generated key for tenant 1: {key_id}")
        except Exception as key_error:
            logger.warning(f"Could not test key generation: {key_error}")
            # This is not critical for initialization
        
    except Exception as e:
        logger.error(f"Failed to initialize master key: {e}")
        raise


def initialize_encryption_service():
    """Initialize and verify the encryption service."""
    try:
        encryption_service = EncryptionService()
        
        # Test encryption/decryption with a sample
        test_data = "test-encryption-data"
        test_tenant_id = 1
        
        encrypted = encryption_service.encrypt_data(test_data, test_tenant_id)
        decrypted = encryption_service.decrypt_data(encrypted, test_tenant_id)
        
        if decrypted != test_data:
            raise ValueError("Encryption service test failed")
            
        logger.info("Encryption service initialized and verified successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize encryption service: {e}")
        raise


def verify_configuration():
    """Verify encryption configuration is valid."""
    try:
        config = EncryptionConfig.from_env()
        
        # Check required configuration
        if not config.ENCRYPTION_ENABLED:
            logger.warning("Encryption is disabled")
            return config
            
        if not config.KEY_VAULT_PROVIDER:
            raise ValueError("KEY_VAULT_PROVIDER must be specified")
            
        if not config.MASTER_KEY_ID:
            raise ValueError("MASTER_KEY_ID must be specified")
            
        # Validate key vault provider specific configuration
        if config.KEY_VAULT_PROVIDER == "aws_kms":
            if not config.AWS_KMS_MASTER_KEY_ID:
                raise ValueError("AWS_KMS_MASTER_KEY_ID required for AWS KMS provider")
                
        elif config.KEY_VAULT_PROVIDER == "azure_keyvault":
            if not config.AZURE_KEYVAULT_URL:
                raise ValueError("AZURE_KEYVAULT_URL required for Azure Key Vault provider")
                    
        elif config.KEY_VAULT_PROVIDER == "hashicorp_vault":
            if not config.HASHICORP_VAULT_URL:
                raise ValueError("HASHICORP_VAULT_URL required for HashiCorp Vault provider")
            if not config.HASHICORP_VAULT_TOKEN:
                raise ValueError("HASHICORP_VAULT_TOKEN required for HashiCorp Vault provider")
        
        logger.info(f"Configuration verified for provider: {config.KEY_VAULT_PROVIDER}")
        return config
        
    except Exception as e:
        logger.error(f"Configuration verification failed: {e}")
        raise


def main():
    """Main initialization function."""
    try:
        logger.info("Starting encryption system initialization...")
        
        # Verify configuration
        config = verify_configuration()
        
        # Skip initialization if encryption is disabled
        if not config.ENCRYPTION_ENABLED:
            logger.info("Encryption is disabled, skipping initialization")
            return
        
        # Ensure key directory exists
        ensure_key_directory(config)
        
        # Initialize master key
        initialize_master_key()
        
        # Initialize encryption service
        initialize_encryption_service()
        
        logger.info("Encryption system initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Encryption initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()