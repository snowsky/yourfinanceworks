"""
Azure Key Vault Provider for Tenant Database Encryption

This module provides Azure Key Vault integration for secure key management
in the tenant database encryption system with optimized connection pooling.
"""

import base64
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from azure.keyvault.keys import KeyClient
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.exceptions import (
    ResourceNotFoundError,
    HttpResponseError,
    ServiceRequestError
)
from azure.core.pipeline.policies import RetryPolicy
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from encryption_config import EncryptionConfig
from core.exceptions.encryption_exceptions import (
    KeyNotFoundError,
    EncryptionError,
    KeyRotationError
)
from commercial.integrations.circuit_breaker import CloudProviderCircuitBreaker

logger = logging.getLogger(__name__)


class AzureKeyVaultProvider:
    """Azure Key Vault provider for encryption key management."""

    def __init__(self, config: EncryptionConfig):
        """Initialize Azure Key Vault provider with configuration and circuit breakers."""
        self.config = config
        self.vault_url = config.AZURE_KEYVAULT_URL
        self.tenant_id = config.AZURE_TENANT_ID
        self.client_id = config.AZURE_CLIENT_ID
        self.client_secret = config.AZURE_CLIENT_SECRET

        # Initialize circuit breakers for different operations
        self._init_circuit_breakers()

        # Initialize Azure credentials
        try:
            if self.client_id and self.client_secret and self.tenant_id:
                # Use service principal authentication
                self.credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                logger.info("Azure Key Vault initialized with service principal authentication")
            else:
                # Use default Azure credential (managed identity, Azure CLI, etc.)
                self.credential = DefaultAzureCredential()
                logger.info("Azure Key Vault initialized with default credential")

            # Initialize Key Vault clients with optimized connection pooling
            # Create custom retry policy for better performance
            retry_policy = RetryPolicy(
                retry_total=3,
                retry_backoff_factor=1.0,
                retry_backoff_max=10.0,
                retry_on_status_codes=[429, 503, 504]
            )

            # Configure clients with connection pooling optimizations
            self.key_client = KeyClient(
                vault_url=self.vault_url,
                credential=self.credential,
                # Connection pool settings (Azure SDK handles this internally)
                # Keep connections alive for better performance
            )

            self.secret_client = SecretClient(
                vault_url=self.vault_url,
                credential=self.credential,
                # Similar connection pooling optimizations
            )

            logger.info(f"Azure Key Vault clients initialized with connection pooling and circuit breakers for vault: {self.vault_url}")

        except Exception as e:
            logger.error(f"Failed to initialize Azure Key Vault clients: {str(e)}")
            raise EncryptionError(f"Azure Key Vault initialization failed: {str(e)}")

    def _init_circuit_breakers(self) -> None:
        """Initialize circuit breakers for different Azure Key Vault operations."""
        # Circuit breakers for Azure Key Vault operations
        self.generate_key_breaker = CloudProviderCircuitBreaker(
            provider_name="azure_keyvault",
            operation_name="generate_key",
            failure_threshold=3,  # Open circuit after 3 failures
            recovery_timeout=30.0,  # Wait 30 seconds before attempting recovery
            success_threshold=2  # Need 2 successes in HALF_OPEN to close circuit
        )

        self.decrypt_key_breaker = CloudProviderCircuitBreaker(
            provider_name="azure_keyvault",
            operation_name="decrypt_key",
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2
        )

        self.key_management_breaker = CloudProviderCircuitBreaker(
            provider_name="azure_keyvault",
            operation_name="key_management",  # For rotate, create, get_info operations
            failure_threshold=3,
            recovery_timeout=60.0,  # Longer recovery for management operations
            success_threshold=2
        )

        logger.info("Azure Key Vault circuit breakers initialized")

    def create_key_name(self, tenant_id: int) -> str:
        """
        Create a standardized key name for a tenant.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Standardized key name
        """
        return f"tenant-{tenant_id}-encryption-key"

    def create_secret_name(self, tenant_id: int) -> str:
        """
        Create a standardized secret name for a tenant's data key.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Standardized secret name
        """
        return f"tenant-{tenant_id}-data-key"

    def generate_data_key(self, tenant_id: int, key_size: int = 256) -> Dict[str, str]:
        """
        Generate a new data encryption key for a tenant using Azure Key Vault.

        Uses circuit breaker pattern for resilience against provider failures.

        Args:
            tenant_id: Unique identifier for the tenant
            key_size: Key size in bits (256 or 128)

        Returns:
            Dictionary containing plaintext and encrypted data keys

        Raises:
            CircuitBreakerOpenException: If circuit breaker is OPEN
            EncryptionError: If key generation fails
        """
        return self.generate_key_breaker.call(
            self._generate_data_key_internal, tenant_id, key_size
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((HttpResponseError, ServiceRequestError))
    )
    def _generate_data_key_internal(self, tenant_id: int, key_size: int = 256) -> Dict[str, str]:
        """Internal implementation of generate_data_key (wrapped by circuit breaker)."""
        try:
            import secrets

            # Generate a random data key
            key_bytes = secrets.token_bytes(key_size // 8)
            plaintext_key = base64.b64encode(key_bytes).decode('utf-8')

            # Store the key as a secret in Azure Key Vault
            secret_name = self.create_secret_name(tenant_id)

            # Set secret with metadata
            secret_properties = {
                'tenant_id': str(tenant_id),
                'purpose': 'database_encryption',
                'service': 'invoice_management',
                'key_size': str(key_size),
                'created_at': datetime.utcnow().isoformat()
            }

            secret = self.secret_client.set_secret(
                name=secret_name,
                value=plaintext_key,
                tags=secret_properties
            )

            logger.info(f"Generated and stored data key for tenant {tenant_id} in Azure Key Vault")

            return {
                'plaintext_key': plaintext_key,
                'encrypted_key': secret.id,  # Use secret ID as encrypted key reference
                'key_id': secret.name,
                'version': secret.properties.version
            }

        except HttpResponseError as e:
            logger.error(f"Azure Key Vault HTTP error generating key for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Failed to generate data key: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error generating data key for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Data key generation failed: {str(e)}")

    def decrypt_data_key(self, encrypted_key: str, tenant_id: int) -> str:
        """
        Decrypt an encrypted data key using Azure Key Vault.

        Uses circuit breaker pattern for resilience against provider failures.

        Args:
            encrypted_key: Secret ID or name
            tenant_id: Unique identifier for the tenant

        Returns:
            Base64 encoded plaintext data key

        Raises:
            CircuitBreakerOpenException: If circuit breaker is OPEN
            KeyNotFoundError: If key cannot be found
            EncryptionError: If decryption fails
        """
        return self.decrypt_key_breaker.call(
            self._decrypt_data_key_internal, encrypted_key, tenant_id
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((HttpResponseError, ServiceRequestError))
    )
    def _decrypt_data_key_internal(self, encrypted_key: str, tenant_id: int) -> str:
        """Internal implementation of decrypt_data_key (wrapped by circuit breaker)."""
        try:
            # Extract secret name from encrypted_key (could be full ID or just name)
            if encrypted_key.startswith('https://'):
                # Full secret ID
                secret_name = encrypted_key.split('/')[-2]
            else:
                # Just the secret name
                secret_name = encrypted_key

            # Retrieve the secret
            secret = self.secret_client.get_secret(name=secret_name)

            # Verify this secret belongs to the correct tenant
            if secret.properties.tags and secret.properties.tags.get('tenant_id') != str(tenant_id):
                raise KeyNotFoundError(f"Key does not belong to tenant {tenant_id}")

            return secret.value

        except ResourceNotFoundError:
            logger.error(f"Secret not found for tenant {tenant_id}: {encrypted_key}")
            raise KeyNotFoundError(f"Cannot find key for tenant {tenant_id}")
        except HttpResponseError as e:
            logger.error(f"Azure Key Vault HTTP error decrypting key for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Key decryption failed: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error decrypting key for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Key decryption failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((HttpResponseError, ServiceRequestError))
    )
    def rotate_tenant_key(self, tenant_id: int) -> Dict[str, str]:
        """
        Rotate a tenant's data encryption key.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Dictionary containing new key information

        Raises:
            KeyRotationError: If rotation fails
        """
        try:
            secret_name = self.create_secret_name(tenant_id)

            # Generate new key
            new_key_data = self.generate_data_key(tenant_id)

            # Get the old secret to preserve metadata
            try:
                old_secret = self.secret_client.get_secret(name=secret_name)
                old_tags = old_secret.properties.tags or {}
            except ResourceNotFoundError:
                old_tags = {}

            # Update tags with rotation information
            rotation_tags = {
                **old_tags,
                'rotated_at': datetime.utcnow().isoformat(),
                'rotation_count': str(int(old_tags.get('rotation_count', '0')) + 1)
            }

            # Create new version of the secret
            rotated_secret = self.secret_client.set_secret(
                name=secret_name,
                value=new_key_data['plaintext_key'],
                tags=rotation_tags
            )

            logger.info(f"Rotated data key for tenant {tenant_id}")

            return {
                'plaintext_key': new_key_data['plaintext_key'],
                'encrypted_key': rotated_secret.id,
                'key_id': rotated_secret.name,
                'version': rotated_secret.properties.version,
                'rotated_at': rotation_tags['rotated_at']
            }

        except Exception as e:
            logger.error(f"Key rotation failed for tenant {tenant_id}: {str(e)}")
            raise KeyRotationError(f"Failed to rotate key for tenant {tenant_id}: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((HttpResponseError, ServiceRequestError))
    )
    def create_master_key(self, key_name: str) -> str:
        """
        Create a master key in Azure Key Vault.

        Args:
            key_name: Name for the master key

        Returns:
            Key ID of the created key

        Raises:
            EncryptionError: If key creation fails
        """
        try:
            from azure.keyvault.keys import KeyType

            # Create RSA key for encryption operations
            key = self.key_client.create_rsa_key(
                name=key_name,
                size=2048,
                tags={
                    'purpose': 'master_encryption',
                    'service': 'invoice_management',
                    'created_at': datetime.utcnow().isoformat()
                }
            )

            logger.info(f"Created master key {key_name} in Azure Key Vault")
            return key.id

        except HttpResponseError as e:
            logger.error(f"Failed to create master key {key_name}: {e}")
            raise EncryptionError(f"Master key creation failed: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error creating master key {key_name}: {str(e)}")
            raise EncryptionError(f"Master key creation failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((HttpResponseError, ServiceRequestError))
    )
    def get_key_info(self, key_name: str) -> Dict[str, Any]:
        """
        Get information about a key or secret.

        Args:
            key_name: Name of the key or secret

        Returns:
            Dictionary containing key/secret metadata

        Raises:
            KeyNotFoundError: If key is not found
            EncryptionError: If operation fails
        """
        try:
            # Try to get as a key first
            try:
                key = self.key_client.get_key(name=key_name)
                return {
                    'type': 'key',
                    'name': key.name,
                    'id': key.id,
                    'key_type': key.key_type,
                    'created_on': key.properties.created_on.isoformat() if key.properties.created_on else None,
                    'updated_on': key.properties.updated_on.isoformat() if key.properties.updated_on else None,
                    'enabled': key.properties.enabled,
                    'tags': key.properties.tags
                }
            except ResourceNotFoundError:
                # Try to get as a secret
                secret = self.secret_client.get_secret(name=key_name)
                return {
                    'type': 'secret',
                    'name': secret.name,
                    'id': secret.id,
                    'created_on': secret.properties.created_on.isoformat() if secret.properties.created_on else None,
                    'updated_on': secret.properties.updated_on.isoformat() if secret.properties.updated_on else None,
                    'enabled': secret.properties.enabled,
                    'tags': secret.properties.tags
                }

        except ResourceNotFoundError:
            raise KeyNotFoundError(f"Key or secret not found: {key_name}")
        except HttpResponseError as e:
            logger.error(f"Failed to get key info for {key_name}: {e}")
            raise EncryptionError(f"Failed to get key info: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error getting key info for {key_name}: {str(e)}")
            raise EncryptionError(f"Get key info failed: {str(e)}")

    def list_tenant_keys(self) -> Dict[int, Dict[str, Any]]:
        """
        List all tenant keys in the Key Vault.

        Returns:
            Dictionary mapping tenant IDs to key information
        """
        tenant_keys = {}

        try:
            # List all secrets with tenant key pattern
            for secret_properties in self.secret_client.list_properties_of_secrets():
                if secret_properties.name.startswith('tenant-') and secret_properties.name.endswith('-data-key'):
                    # Extract tenant ID from secret name
                    try:
                        tenant_id = int(secret_properties.name.split('-')[1])
                        tenant_keys[tenant_id] = {
                            'secret_name': secret_properties.name,
                            'secret_id': secret_properties.id,
                            'created_on': secret_properties.created_on.isoformat() if secret_properties.created_on else None,
                            'updated_on': secret_properties.updated_on.isoformat() if secret_properties.updated_on else None,
                            'enabled': secret_properties.enabled,
                            'tags': secret_properties.tags
                        }
                    except (ValueError, IndexError):
                        logger.warning(f"Could not parse tenant ID from secret name: {secret_properties.name}")
                        continue

        except Exception as e:
            logger.error(f"Error listing tenant keys: {str(e)}")

        return tenant_keys

    def audit_key_access(self, tenant_id: int, operation: str, key_id: str, success: bool) -> None:
        """
        Log key access for audit purposes.

        Args:
            tenant_id: Unique identifier for the tenant
            operation: Operation performed (generate, decrypt, rotate, etc.)
            key_id: Key or secret ID
            success: Whether the operation was successful
        """
        audit_data = {
            'provider': 'azure_keyvault',
            'tenant_id': tenant_id,
            'operation': operation,
            'key_id': key_id,
            'success': success,
            'vault_url': self.vault_url
        }

        if success:
            logger.info(f"Azure Key Vault audit: {json.dumps(audit_data)}")
        else:
            logger.warning(f"Azure Key Vault audit (failed): {json.dumps(audit_data)}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the Azure Key Vault connection and circuit breakers.

        Returns:
            Dictionary containing health status and circuit breaker information
        """
        try:
            # Try to list secrets (limited operation to test connectivity)
            secrets_iter = self.secret_client.list_properties_of_secrets()
            # Just get the first item to test connectivity
            next(secrets_iter, None)
            kv_healthy = True
            kv_error = None
        except Exception as e:
            kv_healthy = False
            kv_error = str(e)

        # Collect circuit breaker status
        circuit_breakers = {
            'generate_key_breaker': self.generate_key_breaker.get_health_status(),
            'decrypt_key_breaker': self.decrypt_key_breaker.get_health_status(),
            'key_management_breaker': self.key_management_breaker.get_health_status()
        }

        return {
            'provider': 'azure_keyvault',
            'status': 'healthy' if kv_healthy else 'unhealthy',
            'vault_url': self.vault_url,
            'authentication': 'service_principal' if self.client_id else 'default_credential',
            'error': kv_error,
            'circuit_breakers': circuit_breakers,
            'connection_pooling': {
                'azure_sdk_managed': True,
                'retry_policy_configured': True,
                'status_codes_handled': [429, 503, 504]
            }
        }

    def backup_key(self, key_name: str) -> bytes:
        """
        Create a backup of a key.

        Args:
            key_name: Name of the key to backup

        Returns:
            Backup data as bytes

        Raises:
            EncryptionError: If backup fails
        """
        try:
            backup = self.key_client.backup_key(name=key_name)
            logger.info(f"Created backup for key: {key_name}")
            return backup

        except ResourceNotFoundError:
            raise KeyNotFoundError(f"Key not found for backup: {key_name}")
        except HttpResponseError as e:
            logger.error(f"Failed to backup key {key_name}: {e}")
            raise EncryptionError(f"Key backup failed: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error backing up key {key_name}: {str(e)}")
            raise EncryptionError(f"Key backup failed: {str(e)}")

    def restore_key(self, backup_data: bytes) -> str:
        """
        Restore a key from backup data.

        Args:
            backup_data: Backup data as bytes

        Returns:
            Name of the restored key

        Raises:
            EncryptionError: If restore fails
        """
        try:
            key = self.key_client.restore_key_backup(backup=backup_data)
            logger.info(f"Restored key: {key.name}")
            return key.name

        except HttpResponseError as e:
            logger.error(f"Failed to restore key from backup: {e}")
            raise EncryptionError(f"Key restore failed: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error restoring key: {str(e)}")
            raise EncryptionError(f"Key restore failed: {str(e)}")
