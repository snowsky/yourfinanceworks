"""
Encryption Service for tenant database encryption.

This service provides AES-256-GCM encryption/decryption capabilities
with tenant-specific key management and PostgreSQL optimizations.
"""

import json
import logging
from typing import Dict, Optional, Any, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64
from functools import lru_cache
import time
from threading import Lock

from encryption_config import EncryptionConfig
from core.services.key_management_service import KeyManagementService
from core.exceptions.encryption_exceptions import (
    EncryptionError,
    DecryptionError,
    KeyNotFoundError,
    InvalidEncodingError,
    DataTooShortError,
    EncryptionIntegrityError,
    TenantIdMissingError
)

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting and decrypting tenant data using AES-256-GCM.

    Features:
    - Tenant-specific encryption keys
    - JSON data encryption for PostgreSQL JSONB fields
    - Key caching for performance optimization
    - Thread-safe operations
    """

    def __init__(self, key_management_service: Optional[KeyManagementService] = None):
        self.config = EncryptionConfig()
        self.key_management = key_management_service or KeyManagementService()
        self._key_cache: Dict[str, bytes] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_lock = Lock()

        # Initialize AESGCM cipher
        self.cipher_class = AESGCM

        logger.info("EncryptionService initialized with AES-256-GCM")

    def encrypt_data(self, data: str, tenant_id: int) -> str:
        """
        Encrypt string data for a specific tenant.

        Args:
            data: Plain text data to encrypt
            tenant_id: Tenant identifier for key selection

        Returns:
            Base64 encoded encrypted data with nonce

        Raises:
            EncryptionError: If encryption fails
            KeyNotFoundError: If tenant key not found
        """
        if not data:
            return ""

        try:
            # Get tenant-specific encryption key
            key = self.get_tenant_key(tenant_id)

            # Create cipher instance
            cipher = self.cipher_class(key)

            # Generate random nonce (12 bytes for GCM)
            nonce = os.urandom(12)

            # Encrypt data
            encrypted_data = cipher.encrypt(nonce, data.encode('utf-8'), None)

            # Combine nonce and encrypted data
            combined = nonce + encrypted_data

            # Return base64 encoded result
            return base64.b64encode(combined).decode('ascii')

        except Exception as e:
            logger.error(f"Encryption failed for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Failed to encrypt data: {str(e)}")

    def decrypt_data(self, encrypted_data: str, tenant_id: int) -> str:
        """
        Decrypt string data for a specific tenant.

        Args:
            encrypted_data: Base64 encoded encrypted data
            tenant_id: Tenant identifier for key selection

        Returns:
            Decrypted plain text data

        Raises:
            DecryptionError: If decryption fails
            KeyNotFoundError: If tenant key not found
        """
        if not encrypted_data:
            return ""

        if tenant_id is None:
            raise TenantIdMissingError(
                "Tenant ID cannot be None for decryption",
                operation="decryption",
                context="Data decryption requires tenant isolation"
            )

        try:
            # Get primary iteration count
            primary_iters = self.config.KEY_DERIVATION_ITERATIONS

            # List of iteration counts to try (primary first, then fallbacks)
            fallback_iters = getattr(self.config, 'KEY_DERIVATION_ITERATIONS_FALLBACK', [])
            all_iters = [primary_iters]
            for it in fallback_iters:
                if it != primary_iters and it not in all_iters:
                    all_iters.append(it)

            last_error = None

            for iters in all_iters:
                try:
                    # Get tenant-specific encryption key for these iterations
                    key = self.get_tenant_key(tenant_id, iterations=iters)

                    # Create cipher instance
                    cipher = self.cipher_class(key)

                    # Decode base64 data with proper error handling
                    try:
                        # Fix base64 padding if needed
                        data_to_decode = encrypted_data
                        if isinstance(encrypted_data, str):
                            # Add missing padding if needed
                            missing_padding = len(encrypted_data) % 4
                            if missing_padding:
                                data_to_decode = encrypted_data + '=' * (4 - missing_padding)
                            combined = base64.b64decode(data_to_decode.encode('ascii'))
                        else:
                            combined = base64.b64decode(encrypted_data)
                    except Exception as base64_error:
                        logger.error(f"Invalid base64 data for tenant {tenant_id}: {str(base64_error)}")
                        raise InvalidEncodingError(
                            "Invalid base64 encoding for encrypted data",
                            tenant_id=tenant_id,
                            encoding_type="base64"
                        )

                    # Validate minimum length (nonce + at least 1 byte of data)
                    if len(combined) < 13:
                        logger.error(f"Encrypted data too short for tenant {tenant_id}: {len(combined)} bytes")
                        raise DataTooShortError(
                            "Encrypted data is too short to be valid",
                            tenant_id=tenant_id,
                            expected_length=">=13 bytes (12-byte nonce + data)",
                            actual_length=len(combined)
                        )

                    # Extract nonce (first 12 bytes) and encrypted data
                    nonce = combined[:12]
                    ciphertext = combined[12:]

                    # Decrypt data
                    decrypted_data = cipher.decrypt(nonce, ciphertext, None)

                    if iters != primary_iters:
                        logger.info(f"Successfully decrypted data for tenant {tenant_id} using fallback iterations: {iters}")

                    return decrypted_data.decode('utf-8')

                except Exception as crypto_error:
                    from cryptography.exceptions import InvalidTag
                    if isinstance(crypto_error, InvalidTag):
                        # Tag failure might mean wrong iteration count, try next one
                        last_error = crypto_error
                        continue
                    else:
                        # Other errors should probably be reported immediately
                        logger.error(f"Cryptography error during decryption for tenant {tenant_id}: {str(crypto_error)}")
                        raise DecryptionError(f"Failed to decrypt data: Cryptographic error", tenant_id=tenant_id)

            # If we're here, all iteration counts failed
            if last_error:
                logger.warning(f"Authentication tag verification failed for tenant {tenant_id} after trying {len(all_iters)} iteration variants")
                raise DecryptionError(f"Failed to decrypt data: Authentication tag verification failed (wrong key or corrupted data)", tenant_id=tenant_id)
            else:
                raise DecryptionError(f"Failed to decrypt data: All decryption attempts failed", tenant_id=tenant_id)

        except (DecryptionError, KeyNotFoundError, InvalidEncodingError, DataTooShortError, TenantIdMissingError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            # Catch any other unexpected errors and convert to DecryptionError
            logger.error(f"Unexpected decryption error for tenant {tenant_id}: {str(e)}")
            raise DecryptionError(f"Failed to decrypt data: {str(e)}", tenant_id=tenant_id)

    def encrypt_json(self, data: Dict[str, Any], tenant_id: int) -> str:
        """
        Encrypt JSON data for PostgreSQL JSONB fields.

        Args:
            data: Dictionary to encrypt
            tenant_id: Tenant identifier for key selection

        Returns:
            Base64 encoded encrypted JSON data

        Raises:
            EncryptionError: If encryption fails
        """
        if not data:
            return ""

        try:
            # Convert dict to JSON string
            json_string = json.dumps(data, separators=(',', ':'), sort_keys=True)

            # Encrypt the JSON string
            return self.encrypt_data(json_string, tenant_id)

        except Exception as e:
            logger.error(f"JSON encryption failed for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Failed to encrypt JSON data: {str(e)}")

    def decrypt_json(self, encrypted_data: str, tenant_id: int) -> Dict[str, Any]:
        """
        Decrypt JSON data from PostgreSQL JSONB fields.

        Args:
            encrypted_data: Base64 encoded encrypted JSON data
            tenant_id: Tenant identifier for key selection

        Returns:
            Decrypted dictionary

        Raises:
            DecryptionError: If decryption fails
        """
        if not encrypted_data:
            return {}

        if tenant_id is None:
            raise DecryptionError("Tenant ID cannot be None for JSON decryption", tenant_id=tenant_id)

        try:
            # Decrypt the JSON string
            json_string = self.decrypt_data(encrypted_data, tenant_id)

            # Parse JSON back to dict
            return json.loads(json_string)

        except Exception as e:
            # Handle the underlying decryption error more specifically
            error_msg = str(e)
            if "Failed to decrypt data:" in error_msg:
                # This is already a DecryptionError from decrypt_data
                if "Authentication tag verification failed" in error_msg:
                    # Log corrupted data at debug level to reduce noise
                    logger.debug(f"JSON decryption failed for tenant {tenant_id}: {error_msg}")
                else:
                    # Log other decryption errors at error level
                    logger.error(f"JSON decryption failed for tenant {tenant_id}: {error_msg}")
                raise DecryptionError(f"Failed to decrypt JSON data: {error_msg.replace('Failed to decrypt data:', '').strip()}", tenant_id=tenant_id)
            else:
                logger.error(f"JSON decryption failed for tenant {tenant_id}: {error_msg}")
                raise DecryptionError(f"Failed to decrypt JSON data: {error_msg}", tenant_id=tenant_id)

    def get_tenant_key(self, tenant_id: int, iterations: Optional[int] = None) -> bytes:
        """
        Get or derive encryption key for a specific tenant with caching.

        Args:
            tenant_id: Tenant identifier
            iterations: Optional override for PBKDF2 iterations

        Returns:
            32-byte encryption key for AES-256

        Raises:
            KeyNotFoundError: If tenant key cannot be retrieved
        """
        iters = iterations or self.config.KEY_DERIVATION_ITERATIONS
        cache_key = f"{tenant_id}:{iters}"

        with self._cache_lock:
            # Check cache first
            current_time = time.time()

            if (cache_key in self._key_cache and
                cache_key in self._cache_timestamps and
                current_time - self._cache_timestamps[cache_key] < self.config.KEY_CACHE_TTL_SECONDS):
                return self._key_cache[cache_key]

            try:
                # Get tenant key from key management service
                tenant_key_material = self.key_management.retrieve_tenant_key(tenant_id)

                # Derive encryption key using PBKDF2
                derived_key = self._derive_key(tenant_key_material, tenant_id, iterations=iters)

                # Cache the derived key
                self._key_cache[cache_key] = derived_key
                self._cache_timestamps[cache_key] = current_time

                # Clean old cache entries
                self._cleanup_cache()

                return derived_key

            except Exception as e:
                logger.error(f"Failed to get tenant key for {tenant_id} with {iters} iterations: {str(e)}")
                raise KeyNotFoundError(f"Tenant key not found for tenant {tenant_id}")

    def _derive_key(self, key_material: str, tenant_id: int, iterations: Optional[int] = None) -> bytes:
        """
        Derive encryption key from key material using PBKDF2.

        Args:
            key_material: Base64 encoded key material
            tenant_id: Tenant ID used as salt component
            iterations: Optional iterations override

        Returns:
            32-byte derived key
        """
        # Decode base64 key material
        import base64
        key_bytes = base64.b64decode(key_material.encode('ascii'))

        # Create salt from tenant ID and config salt
        salt = f"{self.config.KEY_DERIVATION_SALT}:{tenant_id}".encode('utf-8')

        iters = iterations or self.config.KEY_DERIVATION_ITERATIONS

        # Use PBKDF2 for key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=salt,
            iterations=iters,
        )

        return kdf.derive(key_bytes)

    def _cleanup_cache(self):
        """Clean up expired cache entries."""
        current_time = time.time()
        expired_keys = [
            tenant_id for tenant_id, timestamp in self._cache_timestamps.items()
            if current_time - timestamp >= self.config.KEY_CACHE_TTL_SECONDS
        ]

        for tenant_id in expired_keys:
            self._key_cache.pop(tenant_id, None)
            self._cache_timestamps.pop(tenant_id, None)

    def rotate_tenant_key(self, tenant_id: int) -> bool:
        """
        Rotate encryption key for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if rotation successful

        Raises:
            EncryptionError: If key rotation fails
        """
        try:
            # Clear cached key
            with self._cache_lock:
                self._key_cache.pop(tenant_id, None)
                self._cache_timestamps.pop(tenant_id, None)

            # Delegate to key management service
            success = self.key_management.rotate_key(tenant_id)

            if success:
                logger.info(f"Successfully rotated key for tenant {tenant_id}")
            else:
                logger.error(f"Failed to rotate key for tenant {tenant_id}")

            return success

        except Exception as e:
            logger.error(f"Key rotation failed for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Failed to rotate key: {str(e)}")

    def clear_cache(self, tenant_id: Optional[int] = None):
        """
        Clear encryption key cache.

        Args:
            tenant_id: Specific tenant to clear, or None for all
        """
        with self._cache_lock:
            if tenant_id is not None:
                # Find all keys for this tenant (format: "{tenant_id}:{iters}")
                keys_to_remove = [
                    k for k in self._key_cache.keys()
                    if str(k).startswith(f"{tenant_id}:")
                ]
                for key in keys_to_remove:
                    self._key_cache.pop(key, None)
                    self._cache_timestamps.pop(key, None)
                logger.info(f"Cleared cache for tenant {tenant_id}")
            else:
                self._key_cache.clear()
                self._cache_timestamps.clear()
                logger.info("Cleared all encryption key cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with cache statistics
        """
        with self._cache_lock:
            return {
                "cached_keys": len(self._key_cache),
                "cache_size_bytes": sum(len(key) for key in self._key_cache.values()),
                "oldest_entry_age": (
                    time.time() - min(self._cache_timestamps.values())
                    if self._cache_timestamps else 0
                )
            }


# Global encryption service instance
_encryption_service: Optional[EncryptionService] = None


class AsyncEncryptionService(EncryptionService):
    """
    Async version of EncryptionService for improved I/O performance.

    Provides asynchronous encryption/decryption operations using async key vault providers
    for better performance in concurrent environments.
    """

    def __init__(self, key_management_service: Optional['AsyncKeyManagementService'] = None):
        """Initialize async encryption service."""
        super().__init__(key_management_service)
        self._async_key_management: Optional['AsyncKeyManagementService'] = key_management_service

        logger.info("AsyncEncryptionService initialized with AES-256-GCM")

    async def encrypt_data_async(self, data: str, tenant_id: int) -> str:
        """
        Asynchronously encrypt string data for a specific tenant.

        Args:
            data: Plain text data to encrypt
            tenant_id: Tenant identifier for key selection

        Returns:
            Base64 encoded encrypted data with nonce

        Raises:
            EncryptionError: If encryption fails
            KeyNotFoundError: If tenant key not found
        """
        if not data:
            return ""

        try:
            # Get tenant-specific encryption key asynchronously
            key = await self.get_tenant_key_async(tenant_id)

            # Create cipher instance
            cipher = self.cipher_class(key)

            # Generate random nonce (12 bytes for GCM)
            nonce = os.urandom(12)

            # Encrypt data
            encrypted_data = cipher.encrypt(nonce, data.encode('utf-8'), None)

            # Combine nonce and encrypted data
            combined = nonce + encrypted_data

            # Return base64 encoded result
            return base64.b64encode(combined).decode('ascii')

        except Exception as e:
            logger.error(f"Async encryption failed for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Failed to encrypt data: {str(e)}")

    async def decrypt_data_async(self, encrypted_data: str, tenant_id: int) -> str:
        """
        Asynchronously decrypt string data for a specific tenant.

        Args:
            encrypted_data: Base64 encoded encrypted data
            tenant_id: Tenant identifier for key selection

        Returns:
            Decrypted plain text data

        Raises:
            DecryptionError: If decryption fails
            KeyNotFoundError: If tenant key not found
        """
        if not encrypted_data:
            return ""

        if tenant_id is None:
            raise TenantIdMissingError(
                "Tenant ID cannot be None for async decryption",
                operation="async_decryption",
                context="Async data decryption requires tenant isolation"
            )

        try:
            # Get tenant-specific encryption key asynchronously
            key = await self.get_tenant_key_async(tenant_id)

            # Create cipher instance
            cipher = self.cipher_class(key)

            # Decode base64 data with proper error handling
            try:
                # Fix base64 padding if needed
                data_to_decode = encrypted_data
                if isinstance(encrypted_data, str):
                    # Add missing padding if needed
                    missing_padding = len(encrypted_data) % 4
                    if missing_padding:
                        data_to_decode = encrypted_data + '=' * (4 - missing_padding)
                    combined = base64.b64decode(data_to_decode.encode('ascii'))
                else:
                    combined = base64.b64decode(encrypted_data)
            except Exception as base64_error:
                logger.error(f"Invalid base64 data for tenant {tenant_id}: {str(base64_error)}")
                raise InvalidEncodingError(
                    "Invalid base64 encoding for encrypted data",
                    tenant_id=tenant_id,
                    encoding_type="base64"
                )

            # Validate minimum length (nonce + at least 1 byte of data)
            if len(combined) < 13:
                logger.error(f"Encrypted data too short for tenant {tenant_id}: {len(combined)} bytes")
                raise DataTooShortError(
                    "Encrypted data is too short to be valid",
                    tenant_id=tenant_id,
                    expected_length=">=13 bytes (12-byte nonce + data)",
                    actual_length=len(combined)
                )

            # Extract nonce (first 12 bytes) and encrypted data
            nonce = combined[:12]
            ciphertext = combined[12:]

            # Decrypt data
            try:
                decrypted_data = cipher.decrypt(nonce, ciphertext, None)
                return decrypted_data.decode('utf-8')
            except Exception as crypto_error:
                # Handle cryptography-specific errors without returning sensitive data
                from cryptography.exceptions import InvalidTag

                if isinstance(crypto_error, InvalidTag):
                    logger.warning(f"Authentication tag verification failed for tenant {tenant_id} - wrong key or corrupted data")
                    raise DecryptionError(f"Failed to decrypt data: Authentication tag verification failed (wrong key or corrupted data)", tenant_id=tenant_id)
                else:
                    logger.error(f"Cryptography error during async decryption for tenant {tenant_id}: {str(crypto_error)}")
                    raise DecryptionError(f"Failed to decrypt data: Cryptographic error", tenant_id=tenant_id)

        except DecryptionError:
            # Re-raise DecryptionError exceptions as-is
            raise
        except KeyNotFoundError:
            # Re-raise KeyNotFoundError as-is
            raise
        except Exception as e:
            # Catch any other unexpected errors and convert to DecryptionError
            logger.error(f"Unexpected async decryption error for tenant {tenant_id}: {str(e)}")
            raise DecryptionError(f"Failed to decrypt data: {str(e)}", tenant_id=tenant_id)

    async def encrypt_json_async(self, data: Dict[str, Any], tenant_id: int) -> str:
        """
        Asynchronously encrypt JSON data for PostgreSQL JSONB fields.

        Args:
            data: Dictionary to encrypt
            tenant_id: Tenant identifier for key selection

        Returns:
            Base64 encoded encrypted JSON data

        Raises:
            EncryptionError: If encryption fails
        """
        if not data:
            return ""

        try:
            # Convert dict to JSON string
            json_string = json.dumps(data, separators=(',', ':'), sort_keys=True)

            # Encrypt the JSON string asynchronously
            return await self.encrypt_data_async(json_string, tenant_id)

        except Exception as e:
            logger.error(f"Async JSON encryption failed for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Failed to encrypt JSON data: {str(e)}")

    async def decrypt_json_async(self, encrypted_data: str, tenant_id: int) -> Dict[str, Any]:
        """
        Asynchronously decrypt JSON data from PostgreSQL JSONB fields.

        Args:
            encrypted_data: Base64 encoded encrypted JSON data
            tenant_id: Tenant identifier for key selection

        Returns:
            Decrypted dictionary

        Raises:
            DecryptionError: If decryption fails
        """
        if not encrypted_data:
            return {}

        if tenant_id is None:
            raise DecryptionError("Tenant ID cannot be None for JSON decryption", tenant_id=tenant_id)

        try:
            # Decrypt the JSON string asynchronously
            json_string = await self.decrypt_data_async(encrypted_data, tenant_id)

            # Parse JSON back to dict
            return json.loads(json_string)

        except Exception as e:
            # Handle the underlying decryption error more specifically
            error_msg = str(e)
            if "Failed to decrypt data:" in error_msg:
                # This is already a DecryptionError from decrypt_data_async
                if "Authentication tag verification failed" in error_msg:
                    # Log corrupted data at debug level to reduce noise
                    logger.debug(f"Async JSON decryption failed for tenant {tenant_id}: {error_msg}")
                else:
                    # Log other decryption errors at error level
                    logger.error(f"Async JSON decryption failed for tenant {tenant_id}: {error_msg}")
                raise DecryptionError(f"Failed to decrypt JSON data: {error_msg.replace('Failed to decrypt data:', '').strip()}", tenant_id=tenant_id)
            else:
                logger.error(f"Async JSON decryption failed for tenant {tenant_id}: {error_msg}")
                raise DecryptionError(f"Failed to decrypt JSON data: {error_msg}", tenant_id=tenant_id)

    async def get_tenant_key_async(self, tenant_id: int) -> bytes:
        """
        Asynchronously get or derive encryption key for a specific tenant with caching.

        Args:
            tenant_id: Tenant identifier

        Returns:
            32-byte encryption key for AES-256

        Raises:
            KeyNotFoundError: If tenant key cannot be retrieved
        """
        with self._cache_lock:
            # Check cache first
            current_time = time.time()

            if (tenant_id in self._key_cache and
                tenant_id in self._cache_timestamps and
                current_time - self._cache_timestamps[tenant_id] < self.config.KEY_CACHE_TTL_SECONDS):
                return self._key_cache[tenant_id]

            try:
                # Get tenant key from async key management service
                if self._async_key_management:
                    tenant_key_material = await self._async_key_management.retrieve_tenant_key_async(tenant_id)
                else:
                    # Fallback to sync key management if async not available
                    tenant_key_material = self.key_management.retrieve_tenant_key(tenant_id)

                # Derive encryption key using PBKDF2
                derived_key = self._derive_key(tenant_key_material, tenant_id)

                # Cache the derived key
                self._key_cache[tenant_id] = derived_key
                self._cache_timestamps[tenant_id] = current_time

                # Clean old cache entries
                self._cleanup_cache()

                return derived_key

            except Exception as e:
                logger.error(f"Failed to async get tenant key for {tenant_id}: {str(e)}")
                raise KeyNotFoundError(f"Tenant key not found for tenant {tenant_id}")

    async def rotate_tenant_key_async(self, tenant_id: int) -> bool:
        """
        Asynchronously rotate encryption key for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if rotation successful

        Raises:
            EncryptionError: If key rotation fails
        """
        try:
            # Clear cached key
            with self._cache_lock:
                self._key_cache.pop(tenant_id, None)
                self._cache_timestamps.pop(tenant_id, None)

            # Delegate to async key management service
            if self._async_key_management:
                success = await self._async_key_management.rotate_key_async(tenant_id)
            else:
                # Fallback to sync key rotation
                success = self.key_management.rotate_key(tenant_id)

            if success:
                logger.info(f"Asynchronously rotated key for tenant {tenant_id}")
            else:
                logger.error(f"Async key rotation failed for tenant {tenant_id}")

            return success

        except Exception as e:
            logger.error(f"Async key rotation failed for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Failed to rotate key: {str(e)}")


# Global async encryption service instance
_async_encryption_service: Optional[AsyncEncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get global encryption service instance.

    Returns:
        EncryptionService instance

    Raises:
        RuntimeError: If encryption is disabled
    """
    from encryption_config import EncryptionConfig
    config = EncryptionConfig()

    if not config.ENCRYPTION_ENABLED:
        raise RuntimeError("Encryption service is disabled")

    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def get_async_encryption_service() -> AsyncEncryptionService:
    """
    Get global async encryption service instance.

    Returns:
        AsyncEncryptionService instance

    Raises:
        RuntimeError: If encryption is disabled
    """
    from encryption_config import EncryptionConfig
    config = EncryptionConfig()

    if not config.ENCRYPTION_ENABLED:
        raise RuntimeError("Encryption service is disabled")

    global _async_encryption_service
    if _async_encryption_service is None:
        _async_encryption_service = AsyncEncryptionService()
    return _async_encryption_service
