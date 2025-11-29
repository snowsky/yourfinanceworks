"""
Key Management Service for tenant database encryption.

This service handles secure generation, storage, and management of encryption keys
with master key encryption and audit logging capabilities.
"""

from __future__ import annotations

import logging
import secrets
import base64
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import time
from threading import Lock
# Removed threading.Lock to avoid deadlock issues

from encryption_config import EncryptionConfig
from core.exceptions.encryption_exceptions import (
    KeyNotFoundError,
    KeyRotationError,
    EncryptionError
)
# from commercial.integrations.key_vault_factory import KeyVaultFactory  # Moved to conditional import
from core.models.models import TenantKey
from core.models.database import SessionLocal as get_db_session

logger = logging.getLogger(__name__)

# Global key management service instance
_key_management_service: Optional['KeyManagementService'] = None


def get_key_management_service() -> 'KeyManagementService':
    """
    Get global key management service instance.

    Returns:
        KeyManagementService instance
    """
    global _key_management_service
    if _key_management_service is None:
        _key_management_service = KeyManagementService()
    return _key_management_service


class KeyManagementService:
    """
    Service for managing encryption keys with master key encryption.
    
    Features:
    - Secure key generation using cryptographically secure random
    - Master key encryption for tenant keys
    - Key storage and retrieval
    - Key rotation capabilities
    - Comprehensive audit logging
    """
    
    def __init__(self):
        self.config = EncryptionConfig()
        self._master_key: Optional[bytes] = None
        self._key_cache: Dict[int, str] = {}  # Cache for decrypted key material
        self._cache_timestamps: Dict[int, float] = {}

        # Initialize key vault provider if not using local storage
        self._key_vault_provider = None
        if self.config.KEY_VAULT_PROVIDER != "local":
            try:
                from commercial.integrations.key_vault_factory import KeyVaultFactory
                self._key_vault_provider = KeyVaultFactory.create_provider(self.config)
                logger.info(f"Initialized key vault provider: {self.config.KEY_VAULT_PROVIDER}")
            except ImportError:
                logger.warning("Commercial KeyVaultFactory not found, falling back to local storage")
                self._key_vault_provider = None
            except Exception as e:
                logger.error(f"Failed to initialize key vault provider: {str(e)}")
                # Fall back to local storage
                logger.warning("Falling back to local key storage")

        # Initialize master key (only for local storage)
        if self.config.KEY_VAULT_PROVIDER == "local":
            try:
                self._initialize_master_key()
            except Exception as e:
                logger.error(f"Failed to initialize master key during startup: {str(e)}")
                # Don't fail the entire service, just log the error
                # The key will be initialized on first use
                self._master_key = None

        logger.info("KeyManagementService initialized")
    
    def export_master_key_for_env(self) -> str:
        """
        Export the current master key as a base64 string for environment variable use.
        
        Returns:
            Base64 encoded master key string
        """
        if self._master_key is None:
            raise EncryptionError("Master key not initialized")
        
        return base64.b64encode(self._master_key).decode('utf-8')

    def _initialize_master_key(self):
        """Initialize or load the master key."""
        try:
            # Check for environment variable first (most secure)
            env_master_key = os.getenv("MASTER_KEY")
            if env_master_key:
                logger.info("Loading master key from environment variable")
                try:
                    # Decode base64 encoded key from environment
                    self._master_key = base64.b64decode(env_master_key.encode('utf-8'))
                    logger.info("Successfully loaded master key from environment variable")
                    return
                except Exception as e:
                    logger.error(f"Failed to decode master key from environment variable: {str(e)}")
                    # Fall through to file-based loading
            
            # Fall back to file-based storage
            master_key_path = self.config.MASTER_KEY_PATH
            logger.info(f"Initializing master key at: {master_key_path}")
            
            if os.path.exists(master_key_path):
                # Load existing master key
                logger.info("Loading existing master key")
                with open(master_key_path, 'rb') as f:
                    encoded_key = f.read()
                    self._master_key = base64.b64decode(encoded_key)
                logger.info("Loaded existing master key successfully")
            else:
                # Generate new master key
                logger.info("Generating new master key")
                self._master_key = secrets.token_bytes(32)  # 256-bit key
                
                # Save master key (in production, use secure storage)
                key_dir = os.path.dirname(master_key_path)
                logger.info(f"Creating key directory: {key_dir}")
                
                try:
                    os.makedirs(key_dir, exist_ok=True)
                    logger.info(f"Key directory created successfully: {key_dir}")
                except Exception as dir_error:
                    logger.error(f"Failed to create key directory {key_dir}: {str(dir_error)}")
                    raise
                
                logger.info(f"Writing master key to: {master_key_path}")
                with open(master_key_path, 'wb') as f:
                    f.write(base64.b64encode(self._master_key))

                # Set restrictive permissions
                try:
                    os.chmod(master_key_path, 0o600)
                    logger.info("Set restrictive permissions on master key file")
                except Exception as perm_error:
                    logger.warning(f"Failed to set permissions on master key file: {str(perm_error)}")

                logger.info("Generated new master key successfully")

        except Exception as e:
            logger.error(f"Failed to initialize master key: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise EncryptionError(f"Master key initialization failed: {str(e)}")

    def generate_tenant_key(self, tenant_id: int) -> str:
        """
        Generate a new encryption key for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Generated key identifier/reference

        Raises:
            EncryptionError: If key generation fails
        """
        try:
            if self._key_vault_provider:
                # Use external key vault provider
                key_data = self._key_vault_provider.generate_data_key(tenant_id)

                # Store metadata locally for quick access
                self._key_metadata[tenant_id] = {
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'version': 1,
                    'algorithm': 'AES-256-GCM',
                    'key_id': key_data['key_id'],
                    'encrypted_key': key_data['encrypted_key'],
                    'provider': self.config.KEY_VAULT_PROVIDER
                }

                # Audit log
                self._key_vault_provider.audit_key_access(tenant_id, "KEY_GENERATED", key_data['key_id'], True)
                
                logger.info(f"Generated new key for tenant {tenant_id} using {self.config.KEY_VAULT_PROVIDER}")
                return key_data['key_id']
            else:
                # Use local key generation
                return self._generate_local_tenant_key(tenant_id)
            
        except Exception as e:
            logger.error(f"Key generation failed for tenant {tenant_id}: {str(e)}")
            if self._key_vault_provider:
                self._key_vault_provider.audit_key_access(tenant_id, "KEY_GENERATED", "", False)
            raise EncryptionError(f"Failed to generate tenant key: {str(e)}")
    
    def _generate_local_tenant_key(self, tenant_id: int) -> str:
        """Generate a tenant key using database-backed storage."""
        logger.info(f"Starting database-backed key generation for tenant {tenant_id}")

        try:
            # Generate cryptographically secure random key
            logger.info(f"Generating random key material for tenant {tenant_id}")
            tenant_key = secrets.token_bytes(32)  # 256-bit key
            logger.info(f"Generated random key material for tenant {tenant_id}")

            # Encrypt tenant key with master key
            logger.info(f"Encrypting tenant key with master key for tenant {tenant_id}")
            encrypted_key = self._encrypt_with_master_key(tenant_key)
            logger.info(f"Encrypted tenant key for tenant {tenant_id}")

            # Store encrypted key in database
            logger.info(f"Storing encrypted key in database for tenant {tenant_id}")
            db = get_db_session()
            try:
                # Check if key already exists
                existing_key = db.query(TenantKey).filter(TenantKey.tenant_id == tenant_id).first()
                if existing_key:
                    logger.warning(f"Tenant key already exists for tenant {tenant_id}, updating...")
                    existing_key.encrypted_key_material = encrypted_key
                    existing_key.version += 1
                    existing_key.updated_at = datetime.now(timezone.utc)
                else:
                    # Create new key record
                    tenant_key_record = TenantKey(
                        tenant_id=tenant_id,
                        key_id=f"tenant_{tenant_id}_v1",
                        encrypted_key_material=encrypted_key,
                        algorithm='AES-256-GCM',
                        version=1,
                        is_active=True
                    )
                    db.add(tenant_key_record)

                db.commit()
                logger.info(f"Successfully stored key in database for tenant {tenant_id}")

            except Exception as db_error:
                db.rollback()
                logger.error(f"Failed to store key in database for tenant {tenant_id}: {str(db_error)}")
                raise
            finally:
                db.close()

            # Cache the decrypted key material for performance
            import base64
            self._key_cache[tenant_id] = base64.b64encode(tenant_key).decode('ascii')
            self._cache_timestamps[tenant_id] = time.time()

            # Audit log
            logger.info(f"Creating audit log for tenant {tenant_id}")
            self.audit_key_access(tenant_id, "KEY_GENERATED", {
                'key_id': f"tenant_{tenant_id}_v1",
                'algorithm': 'AES-256-GCM'
            })

            logger.info(f"Generated new database-backed key for tenant {tenant_id} successfully")
            return f"tenant_{tenant_id}_v1"

        except Exception as e:
            logger.error(f"Failed to generate database-backed key for tenant {tenant_id}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def store_tenant_key(self, tenant_id: int, key: str) -> bool:
        """
        Store an encryption key for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            key: Key material to store
            
        Returns:
            True if storage successful
            
        Raises:
            EncryptionError: If key storage fails
        """
        try:
            # Convert key string to bytes
            key_bytes = key.encode('utf-8') if isinstance(key, str) else key
            
            # Encrypt with master key
            encrypted_key = self._encrypt_with_master_key(key_bytes)
            
            # Store encrypted key
            with self._storage_lock:
                self._key_storage[tenant_id] = encrypted_key
                self._key_metadata[tenant_id] = {
                    'stored_at': datetime.now(timezone.utc).isoformat(),
                    'version': self._key_metadata.get(tenant_id, {}).get('version', 0) + 1,
                    'algorithm': 'AES-256-GCM',
                    'key_id': f"tenant_{tenant_id}_v{self._key_metadata.get(tenant_id, {}).get('version', 0) + 1}"
                }
            
            # Audit log
            self.audit_key_access(tenant_id, "KEY_STORED", {
                'key_id': self._key_metadata[tenant_id]['key_id']
            })
            
            logger.info(f"Stored key for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Key storage failed for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Failed to store tenant key: {str(e)}")
    
    def retrieve_tenant_key(self, tenant_id: int) -> str:
        """
        Retrieve encryption key for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Decrypted key material
            
        Raises:
            KeyNotFoundError: If tenant key not found
        """
        try:
            if self._key_vault_provider:
                # Use external key vault provider
                with self._storage_lock:
                    if tenant_id not in self._key_metadata:
                        # Auto-generate key if not exists
                        logger.info(f"Auto-generating key for tenant {tenant_id}")
                        self.generate_tenant_key(tenant_id)
                    
                    metadata = self._key_metadata[tenant_id]
                    encrypted_key = metadata['encrypted_key']
                
                # Decrypt using key vault provider
                decrypted_key = self._key_vault_provider.decrypt_data_key(encrypted_key, tenant_id)
                
                # Audit log
                self._key_vault_provider.audit_key_access(tenant_id, "KEY_RETRIEVED", metadata['key_id'], True)
                
                return decrypted_key
            else:
                # Use local key retrieval
                return self._retrieve_local_tenant_key(tenant_id)
            
        except Exception as e:
            logger.error(f"Key retrieval failed for tenant {tenant_id}: {str(e)}")
            if self._key_vault_provider:
                self._key_vault_provider.audit_key_access(tenant_id, "KEY_RETRIEVED", "", False)
            raise KeyNotFoundError(f"Tenant key not found for tenant {tenant_id}")
    
    def _retrieve_local_tenant_key(self, tenant_id: int) -> str:
        """Retrieve a tenant key using database-backed storage."""
        # Check cache first
        current_time = time.time()
        if (tenant_id in self._key_cache and
            tenant_id in self._cache_timestamps and
            current_time - self._cache_timestamps[tenant_id] < self.config.KEY_CACHE_TTL_SECONDS):
            logger.debug(f"Returning cached key for tenant {tenant_id}")
            return self._key_cache[tenant_id]

        # Check database for key
        db = get_db_session()
        try:
            tenant_key_record = db.query(TenantKey).filter(
                TenantKey.tenant_id == tenant_id,
                TenantKey.is_active == True
            ).first()

            if not tenant_key_record:
                # Check if we're in database initialization phase
                import os
                import threading
                current_thread = threading.current_thread()

                # Only block during actual database initialization, not during runtime operations
                is_db_init = os.environ.get('DB_INIT_PHASE', 'false').lower() == 'true'

                if is_db_init and hasattr(current_thread, 'name') and 'MainThread' in current_thread.name:
                    logger.warning(f"Skipping key auto-generation for tenant {tenant_id} during database initialization")
                    raise KeyNotFoundError(f"Tenant key not found for tenant {tenant_id} and auto-generation disabled during startup")

                # Auto-generate key if not exists (during runtime or non-init operations)
                logger.info(f"Auto-generating database-backed key for tenant {tenant_id}")
                self.generate_tenant_key(tenant_id)

                # Re-query after generation
                tenant_key_record = db.query(TenantKey).filter(
                    TenantKey.tenant_id == tenant_id,
                    TenantKey.is_active == True
                ).first()

                if not tenant_key_record:
                    raise KeyNotFoundError(f"Tenant key not found for tenant {tenant_id} after generation attempt")

            # Decrypt with master key
            decrypted_key = self._decrypt_with_master_key(tenant_key_record.encrypted_key_material)

            # Cache the result
            import base64
            cached_key = base64.b64encode(decrypted_key).decode('ascii')
            self._key_cache[tenant_id] = cached_key
            self._cache_timestamps[tenant_id] = current_time

            # Audit log
            self.audit_key_access(tenant_id, "KEY_RETRIEVED", {
                'key_id': tenant_key_record.key_id
            })

            logger.debug(f"Retrieved and cached key for tenant {tenant_id}")
            return cached_key

        finally:
            db.close()
    
    def rotate_key(self, tenant_id: int) -> bool:
        """
        Rotate encryption key for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if rotation successful

        Raises:
            KeyRotationError: If key rotation fails
        """
        try:
            # Store old key for rollback
            db = get_db_session()
            try:
                old_key_record = db.query(TenantKey).filter(
                    TenantKey.tenant_id == tenant_id,
                    TenantKey.is_active == True
                ).first()

                # Generate new key
                new_key_id = self.generate_tenant_key(tenant_id)

                # Deactivate old key
                if old_key_record:
                    old_key_record.is_active = False
                    old_key_record.updated_at = datetime.now(timezone.utc)
                    db.commit()

                # Audit log
                self.audit_key_access(tenant_id, "KEY_ROTATED", {
                    'old_key_id': old_key_record.key_id if old_key_record else 'unknown',
                    'new_key_id': new_key_id
                })

                logger.info(f"Successfully rotated key for tenant {tenant_id}")
                return True

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Key rotation failed for tenant {tenant_id}: {str(e)}")

            # Attempt rollback - reactivate old key
            try:
                db = get_db_session()
                old_key_record = db.query(TenantKey).filter(
                    TenantKey.tenant_id == tenant_id,
                    TenantKey.is_active == False
                ).order_by(TenantKey.version.desc()).first()

                if old_key_record:
                    old_key_record.is_active = True
                    old_key_record.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info(f"Rolled back key rotation for tenant {tenant_id}")
            except Exception as rollback_error:
                logger.error(f"Rollback failed for tenant {tenant_id}: {str(rollback_error)}")
            finally:
                db.close()

            raise KeyRotationError(f"Failed to rotate key for tenant {tenant_id}: {str(e)}")
    
    def backup_keys(self) -> bool:
        """
        Create backup of all tenant keys.
        
        Returns:
            True if backup successful
            
        Raises:
            EncryptionError: If backup fails
        """
        try:
            backup_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'keys': {},
                'metadata': {}
            }
            
            with self._storage_lock:
                # Copy all keys and metadata
                backup_data['keys'] = self._key_storage.copy()
                backup_data['metadata'] = self._key_metadata.copy()
            
            # Save backup (in production, use secure backup storage)
            backup_path = os.path.join(self.config.KEY_BACKUP_PATH, 
                                     f"key_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(backup_path, 0o600)
            
            # Audit log
            self.audit_key_access(None, "KEYS_BACKED_UP", {
                'backup_path': backup_path,
                'key_count': len(backup_data['keys'])
            })
            
            logger.info(f"Successfully backed up {len(backup_data['keys'])} keys")
            return True
            
        except Exception as e:
            logger.error(f"Key backup failed: {str(e)}")
            raise EncryptionError(f"Failed to backup keys: {str(e)}")
    
    def audit_key_access(self, tenant_id: Optional[int], operation: str, details: Optional[Dict[str, Any]] = None):
        """
        Log key access operations for audit purposes.
        
        Args:
            tenant_id: Tenant identifier (None for system operations)
            operation: Type of operation performed
            details: Additional operation details
        """
        try:
            audit_entry = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'tenant_id': tenant_id,
                'operation': operation,
                'details': details or {},
                'service': 'KeyManagementService'
            }
            
            # In production, this would write to a secure audit log system
            logger.info(f"AUDIT: {json.dumps(audit_entry)}")
            
        except Exception as e:
            logger.error(f"Audit logging failed: {str(e)}")
            # Don't raise exception for audit failures
    
    def _encrypt_with_master_key(self, data: bytes) -> str:
        """
        Encrypt data with the master key.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Base64 encoded encrypted data
        """
        if not self._master_key:
            logger.info("Master key not initialized, initializing now...")
            self._initialize_master_key()
            if not self._master_key:
                raise EncryptionError("Master key initialization failed")
        
        # Create cipher
        cipher = AESGCM(self._master_key)
        
        # Generate nonce
        nonce = os.urandom(12)
        
        # Encrypt
        encrypted_data = cipher.encrypt(nonce, data, None)
        
        # Combine nonce and encrypted data
        combined = nonce + encrypted_data
        
        return base64.b64encode(combined).decode('ascii')
    
    def _decrypt_with_master_key(self, encrypted_data: str) -> bytes:
        """
        Decrypt data with the master key.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted data
        """
        if not self._master_key:
            logger.info("Master key not initialized, initializing now...")
            self._initialize_master_key()
            if not self._master_key:
                raise EncryptionError("Master key initialization failed")
        
        # Create cipher
        cipher = AESGCM(self._master_key)
        
        # Decode data
        combined = base64.b64decode(encrypted_data.encode('ascii'))
        
        # Extract nonce and ciphertext
        nonce = combined[:12]
        ciphertext = combined[12:]
        
        # Decrypt
        return cipher.decrypt(nonce, ciphertext, None)
    
    def get_key_metadata(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a tenant's key.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Key metadata or None if not found
        """
        with self._storage_lock:
            return self._key_metadata.get(tenant_id)
    
    def list_tenant_keys(self) -> Dict[int, Dict[str, Any]]:
        """
        List all tenant keys with metadata.

        Returns:
            Dictionary mapping tenant IDs to key metadata
        """
        db = get_db_session()
        try:
            keys = {}
            tenant_key_records = db.query(TenantKey).filter(TenantKey.is_active == True).all()
            for record in tenant_key_records:
                keys[record.tenant_id] = {
                    'key_id': record.key_id,
                    'algorithm': record.algorithm,
                    'version': record.version,
                    'created_at': record.created_at.isoformat() if record.created_at else None,
                    'updated_at': record.updated_at.isoformat() if record.updated_at else None
                }
            return keys
        finally:
            db.close()
    
    def delete_tenant_key(self, tenant_id: int) -> bool:
        """
        Delete a tenant's encryption key.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if deletion successful
        """
        try:
            db = get_db_session()
            try:
                # Soft delete by marking as inactive
                tenant_key_records = db.query(TenantKey).filter(TenantKey.tenant_id == tenant_id).all()
                for record in tenant_key_records:
                    record.is_active = False
                    record.updated_at = datetime.now(timezone.utc)

                # Clear cache
                self._key_cache.pop(tenant_id, None)
                self._cache_timestamps.pop(tenant_id, None)

                db.commit()

                # Audit log
                self.audit_key_access(tenant_id, "KEY_DELETED", {})

                logger.info(f"Deleted key for tenant {tenant_id}")
                return True

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Key deletion failed for tenant {tenant_id}: {str(e)}")
            return False

    def rotate_tenant_key_external(self, tenant_id: int) -> bool:
        """
        Rotate encryption key for a tenant using external key vault provider.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if rotation successful
            
        Raises:
            KeyRotationError: If rotation fails
        """
        if not self._key_vault_provider:
            raise KeyRotationError("External key vault provider not configured")
        
        try:
            # Rotate key using external provider
            rotation_result = self._key_vault_provider.rotate_tenant_key(tenant_id)
            
            # Update local metadata
            with self._storage_lock:
                if tenant_id in self._key_metadata:
                    old_version = self._key_metadata[tenant_id].get('version', 1)
                    self._key_metadata[tenant_id].update({
                        'version': old_version + 1,
                        'rotated_at': datetime.now(timezone.utc).isoformat(),
                        'key_id': rotation_result['key_id'],
                        'encrypted_key': rotation_result['encrypted_key']
                    })
                else:
                    self._key_metadata[tenant_id] = {
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'version': 1,
                        'algorithm': 'AES-256-GCM',
                        'key_id': rotation_result['key_id'],
                        'encrypted_key': rotation_result['encrypted_key'],
                        'provider': self.config.KEY_VAULT_PROVIDER
                    }
            
            # Audit log
            self._key_vault_provider.audit_key_access(tenant_id, "KEY_ROTATED", rotation_result['key_id'], True)
            
            logger.info(f"Successfully rotated key for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Key rotation failed for tenant {tenant_id}: {str(e)}")
            if self._key_vault_provider:
                self._key_vault_provider.audit_key_access(tenant_id, "KEY_ROTATED", "", False)
            raise KeyRotationError(f"Failed to rotate key for tenant {tenant_id}: {str(e)}")
    
    def get_key_vault_health(self) -> Dict[str, Any]:
        """
        Get health status of the key vault provider.
        
        Returns:
            Dictionary containing health information
        """
        if self._key_vault_provider:
            return self._key_vault_provider.health_check()
        else:
            return {
                'provider': 'local',
                'status': 'healthy',
                'master_key_available': self._master_key is not None,
                'keys_stored': len(self._key_storage)
            }
    
    def list_tenant_keys_external(self) -> Dict[int, Dict[str, Any]]:
        """
        List all tenant keys from external key vault provider.
        
        Returns:
            Dictionary mapping tenant IDs to key information
        """
        if self._key_vault_provider and hasattr(self._key_vault_provider, 'list_tenant_keys'):
            try:
                return self._key_vault_provider.list_tenant_keys()
            except Exception as e:
                logger.error(f"Failed to list tenant keys from external provider: {str(e)}")
                return {}
        else:
            # Return local key information
            with self._storage_lock:
                return {
                    tenant_id: {
                        'metadata': metadata,
                        'has_key': tenant_id in self._key_storage
                    }
                    for tenant_id, metadata in self._key_metadata.items()
                }
    
    def validate_key_vault_config(self) -> Dict[str, Any]:
        """
        Validate the key vault configuration.
        
        Returns:
            Dictionary containing validation results
        """
        return KeyVaultFactory.validate_provider_config(self.config)
    
    def test_key_vault_connection(self) -> Dict[str, Any]:
        """
        Test the connection to the key vault provider.
        
        Returns:
            Dictionary containing connection test results
        """
        return KeyVaultFactory.test_provider_connection(self.config)