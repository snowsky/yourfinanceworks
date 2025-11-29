"""
HashiCorp Vault Provider for Tenant Database Encryption

This module provides HashiCorp Vault integration for secure key management
in the tenant database encryption system.
"""

import base64
import json
import logging
import secrets
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import hvac
from hvac.exceptions import VaultError, InvalidPath, Forbidden
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from encryption_config import EncryptionConfig
from core.exceptions.encryption_exceptions import (
    KeyNotFoundError,
    EncryptionError,
    KeyRotationError
)

logger = logging.getLogger(__name__)


class HashiCorpVaultProvider:
    """HashiCorp Vault provider for encryption key management."""

    def __init__(self, config: EncryptionConfig):
        """Initialize HashiCorp Vault provider with configuration."""
        self.config = config
        self.vault_url = config.HASHICORP_VAULT_URL
        self.vault_token = config.HASHICORP_VAULT_TOKEN
        self.vault_namespace = config.HASHICORP_VAULT_NAMESPACE
        self.mount_point = config.HASHICORP_VAULT_MOUNT_POINT or 'secret'
        self.transit_mount = config.HASHICORP_VAULT_TRANSIT_MOUNT or 'transit'

        # Initialize Vault client
        try:
            self.client = hvac.Client(
                url=self.vault_url,
                token=self.vault_token,
                namespace=self.vault_namespace
            )

            # Verify authentication
            if not self.client.is_authenticated():
                raise EncryptionError("HashiCorp Vault authentication failed")

            # Enable transit secrets engine if not already enabled
            self._ensure_transit_engine()

            logger.info(f"HashiCorp Vault client initialized for URL: {self.vault_url}")

        except Exception as e:
            logger.error(f"Failed to initialize HashiCorp Vault client: {str(e)}")
            raise EncryptionError(f"HashiCorp Vault initialization failed: {str(e)}")

    def _ensure_transit_engine(self) -> None:
        """Ensure the transit secrets engine is enabled."""
        try:
            # Check if transit engine is already enabled
            engines = self.client.sys.list_mounted_secrets_engines()
            if f"{self.transit_mount}/" not in engines['data']:
                # Enable transit engine
                self.client.sys.enable_secrets_engine(
                    backend_type='transit',
                    path=self.transit_mount
                )
                logger.info(f"Enabled transit secrets engine at {self.transit_mount}")

        except Exception as e:
            logger.warning(f"Could not ensure transit engine: {str(e)}")

    def create_key_path(self, tenant_id: int) -> str:
        """
        Create a standardized key path for a tenant.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Vault path for the tenant's key
        """
        return f"{self.mount_point}/tenant-{tenant_id}/encryption-key"

    def create_transit_key_name(self, tenant_id: int) -> str:
        """
        Create a standardized transit key name for a tenant.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Transit key name for the tenant
        """
        return f"tenant-{tenant_id}-key"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((VaultError,))
    )
    def generate_data_key(self, tenant_id: int, key_size: int = 256) -> Dict[str, str]:
        """
        Generate a new data encryption key for a tenant using HashiCorp Vault.

        Args:
            tenant_id: Unique identifier for the tenant
            key_size: Key size in bits (256 or 128)
 
        Returns:
            Dictionary containing plaintext and encrypted data keys

        Raises:
            EncryptionError: If key generation fails
        """
        try:
            # Generate a random data key
            key_bytes = secrets.token_bytes(key_size // 8)
            plaintext_key = base64.b64encode(key_bytes).decode('utf-8')

            # Create or get transit key for this tenant
            transit_key_name = self.create_transit_key_name(tenant_id)
            self._ensure_transit_key(transit_key_name, tenant_id)

            # Encrypt the data key using transit engine
            encrypt_response = self.client.secrets.transit.encrypt_data(
                name=transit_key_name,
                plaintext=base64.b64encode(key_bytes).decode('utf-8'),
                mount_point=self.transit_mount
            )

            encrypted_key = encrypt_response['data']['ciphertext']

            # Store key metadata in KV store
            key_path = self.create_key_path(tenant_id)
            metadata = {
                'tenant_id': tenant_id,
                'purpose': 'database_encryption',
                'service': 'invoice_management',
                'key_size': key_size,
                'created_at': datetime.utcnow().isoformat(),
                'transit_key': transit_key_name,
                'encrypted_key': encrypted_key
            }

            self.client.secrets.kv.v2.create_or_update_secret(
                path=key_path,
                secret=metadata,
                mount_point=self.mount_point
            )

            logger.info(f"Generated and stored data key for tenant {tenant_id} in HashiCorp Vault")

            return {
                'plaintext_key': plaintext_key,
                'encrypted_key': encrypted_key,
                'key_id': transit_key_name,
                'vault_path': key_path
            }

        except VaultError as e:
            logger.error(f"HashiCorp Vault error generating key for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Failed to generate data key: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error generating data key for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Data key generation failed: {str(e)}")

    def _ensure_transit_key(self, key_name: str, tenant_id: int) -> None:
        """
        Ensure a transit key exists for the tenant.

        Args:
            key_name: Name of the transit key
            tenant_id: Unique identifier for the tenant
        """
        try:
            # Check if key exists
            self.client.secrets.transit.read_key(
                name=key_name,
                mount_point=self.transit_mount
            )
        except (InvalidPath, VaultError):
            # Key doesn't exist, create it
            try:
                self.client.secrets.transit.create_key(
                    name=key_name,
                    key_type='aes256-gcm96',
                    mount_point=self.transit_mount
                )
                logger.info(f"Created transit key {key_name} for tenant {tenant_id}")
            except VaultError as e:
                logger.error(f"Failed to create transit key {key_name}: {e}")
                raise EncryptionError(f"Transit key creation failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((VaultError,))
    )
    def decrypt_data_key(self, encrypted_key: str, tenant_id: int) -> str:
        """
        Decrypt an encrypted data key using HashiCorp Vault.

        Args:
            encrypted_key: Vault ciphertext
            tenant_id: Unique identifier for the tenant

        Returns:
            Base64 encoded plaintext data key

        Raises:
            KeyNotFoundError: If key cannot be found or decrypted
            EncryptionError: If decryption fails
        """
        try:
            transit_key_name = self.create_transit_key_name(tenant_id)

            # Decrypt using transit engine
            decrypt_response = self.client.secrets.transit.decrypt_data(
                name=transit_key_name,
                ciphertext=encrypted_key,
                mount_point=self.transit_mount
            )

            # Return the decrypted key (already base64 encoded)
            return decrypt_response['data']['plaintext']

        except InvalidPath:
            logger.error(f"Transit key not found for tenant {tenant_id}")
            raise KeyNotFoundError(f"Cannot find key for tenant {tenant_id}")
        except VaultError as e:
            logger.error(f"HashiCorp Vault error decrypting key for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Key decryption failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error decrypting key for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Key decryption failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((VaultError,))
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
            transit_key_name = self.create_transit_key_name(tenant_id)

            # Rotate the transit key
            self.client.secrets.transit.rotate_key(
                name=transit_key_name,
                mount_point=self.transit_mount
            )

            # Generate new data key with rotated transit key
            new_key_data = self.generate_data_key(tenant_id)

            # Update metadata with rotation information
            key_path = self.create_key_path(tenant_id)

            # Get existing metadata
            try:
                existing_secret = self.client.secrets.kv.v2.read_secret_version(
                    path=key_path,
                    mount_point=self.mount_point
                )
                existing_metadata = existing_secret['data']['data']
                rotation_count = existing_metadata.get('rotation_count', 0) + 1
            except (InvalidPath, KeyError):
                rotation_count = 1

            # Update with rotation info
            updated_metadata = {
                **new_key_data,
                'rotated_at': datetime.utcnow().isoformat(),
                'rotation_count': rotation_count,
                'previous_version': existing_metadata.get('version') if 'existing_metadata' in locals() else None
            }

            self.client.secrets.kv.v2.create_or_update_secret(
                path=key_path,
                secret=updated_metadata,
                mount_point=self.mount_point
            )

            logger.info(f"Rotated data key for tenant {tenant_id}")

            return {
                'plaintext_key': new_key_data['plaintext_key'],
                'encrypted_key': new_key_data['encrypted_key'],
                'key_id': transit_key_name,
                'vault_path': key_path,
                'rotated_at': updated_metadata['rotated_at'],
                'rotation_count': rotation_count
            }

        except VaultError as e:
            logger.error(f"Key rotation failed for tenant {tenant_id}: {e}")
            raise KeyRotationError(f"Failed to rotate key for tenant {tenant_id}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during key rotation for tenant {tenant_id}: {str(e)}")
            raise KeyRotationError(f"Key rotation failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((VaultError,))
    )
    def get_key_info(self, tenant_id: int) -> Dict[str, Any]:
        """
        Get information about a tenant's key.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Dictionary containing key metadata

        Raises:
            KeyNotFoundError: If key is not found
            EncryptionError: If operation fails
        """
        try:
            key_path = self.create_key_path(tenant_id)
            transit_key_name = self.create_transit_key_name(tenant_id)

            # Get KV metadata
            try:
                kv_response = self.client.secrets.kv.v2.read_secret_version(
                    path=key_path,
                    mount_point=self.mount_point
                )
                kv_data = kv_response['data']['data']
                kv_metadata = kv_response['data']['metadata']
            except InvalidPath:
                kv_data = {}
                kv_metadata = {}

            # Get transit key info
            try:
                transit_response = self.client.secrets.transit.read_key(
                    name=transit_key_name,
                    mount_point=self.transit_mount
                )
                transit_data = transit_response['data']
            except InvalidPath:
                transit_data = {}

            if not kv_data and not transit_data:
                raise KeyNotFoundError(f"No key found for tenant {tenant_id}")

            return {
                'tenant_id': tenant_id,
                'kv_path': key_path,
                'transit_key': transit_key_name,
                'kv_metadata': kv_metadata,
                'kv_data': {k: v for k, v in kv_data.items() if k != 'encrypted_key'},  # Exclude sensitive data
                'transit_metadata': {
                    'type': transit_data.get('type'),
                    'latest_version': transit_data.get('latest_version'),
                    'min_decryption_version': transit_data.get('min_decryption_version'),
                    'min_encryption_version': transit_data.get('min_encryption_version'),
                    'supports_encryption': transit_data.get('supports_encryption'),
                    'supports_decryption': transit_data.get('supports_decryption')
                } if transit_data else {}
            }

        except VaultError as e:
            logger.error(f"Failed to get key info for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Failed to get key info: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting key info for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Get key info failed: {str(e)}")

    def list_tenant_keys(self) -> Dict[int, Dict[str, Any]]:
        """
        List all tenant keys in Vault.

        Returns:
            Dictionary mapping tenant IDs to key information
        """
        tenant_keys = {}

        try:
            # List all secrets in the mount point
            try:
                secrets_list = self.client.secrets.kv.v2.list_secrets(
                    path='',
                    mount_point=self.mount_point
                )

                for secret_path in secrets_list['data']['keys']:
                    if secret_path.startswith('tenant-') and secret_path.endswith('/'):
                        # Extract tenant ID from path
                        try:
                            tenant_id = int(secret_path.split('-')[1].rstrip('/'))
                            key_info = self.get_key_info(tenant_id)
                            tenant_keys[tenant_id] = key_info
                        except (ValueError, IndexError, KeyNotFoundError):
                            logger.warning(f"Could not parse tenant ID from path: {secret_path}")
                            continue

            except InvalidPath:
                logger.info("No tenant keys found in Vault")

        except Exception as e:
            logger.error(f"Error listing tenant keys: {str(e)}")

        return tenant_keys

    def create_policy(self, tenant_id: int) -> str:
        """
        Create a Vault policy for a specific tenant.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Policy name
        """
        policy_name = f"tenant-{tenant_id}-encryption"
        key_path = self.create_key_path(tenant_id)
        transit_key_name = self.create_transit_key_name(tenant_id)

        policy_rules = f'''
# Allow read/write access to tenant's encryption key
path "{key_path}" {{
  capabilities = ["create", "read", "update", "delete"]
}}

# Allow encrypt/decrypt operations for tenant's transit key
path "{self.transit_mount}/encrypt/{transit_key_name}" {{
  capabilities = ["update"]
}}

path "{self.transit_mount}/decrypt/{transit_key_name}" {{
  capabilities = ["update"]
}}

path "{self.transit_mount}/keys/{transit_key_name}" {{
  capabilities = ["read"]
}}

path "{self.transit_mount}/keys/{transit_key_name}/rotate" {{
  capabilities = ["update"]
}}
'''

        try:
            self.client.sys.create_or_update_policy(
                name=policy_name,
                policy=policy_rules
            )
            logger.info(f"Created Vault policy {policy_name} for tenant {tenant_id}")
            return policy_name

        except VaultError as e:
            logger.error(f"Failed to create policy for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Policy creation failed: {str(e)}")

    def audit_key_access(self, tenant_id: int, operation: str, key_id: str, success: bool) -> None:
        """
        Log key access for audit purposes.

        Args:
            tenant_id: Unique identifier for the tenant
            operation: Operation performed (generate, decrypt, rotate, etc.)
            key_id: Key ID or path
            success: Whether the operation was successful
        """
        audit_data = {
            'provider': 'hashicorp_vault',
            'tenant_id': tenant_id,
            'operation': operation,
            'key_id': key_id,
            'success': success,
            'vault_url': self.vault_url,
            'namespace': self.vault_namespace
        }

        if success:
            logger.info(f"HashiCorp Vault audit: {json.dumps(audit_data)}")
        else:
            logger.warning(f"HashiCorp Vault audit (failed): {json.dumps(audit_data)}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the HashiCorp Vault connection.

        Returns:
            Dictionary containing health status
        """
        try:
            # Check if client is authenticated
            if not self.client.is_authenticated():
                return {
                    'provider': 'hashicorp_vault',
                    'status': 'unhealthy',
                    'vault_url': self.vault_url,
                    'error': 'Authentication failed'
                }

            # Check vault seal status
            seal_status = self.client.sys.read_seal_status()

            # Check if required engines are available
            engines = self.client.sys.list_mounted_secrets_engines()

            return {
                'provider': 'hashicorp_vault',
                'status': 'healthy',
                'vault_url': self.vault_url,
                'namespace': self.vault_namespace,
                'sealed': seal_status['sealed'],
                'version': seal_status.get('version'),
                'engines': {
                    'kv_available': f"{self.mount_point}/" in engines['data'],
                    'transit_available': f"{self.transit_mount}/" in engines['data']
                }
            }

        except Exception as e:
            return {
                'provider': 'hashicorp_vault',
                'status': 'unhealthy',
                'vault_url': self.vault_url,
                'error': str(e)
            }

    def backup_key(self, tenant_id: int) -> Dict[str, Any]:
        """
        Create a backup of a tenant's key information.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Backup data dictionary

        Raises:
            EncryptionError: If backup fails
        """
        try:
            key_info = self.get_key_info(tenant_id)

            # Create backup with timestamp
            backup_data = {
                'tenant_id': tenant_id,
                'backup_timestamp': datetime.utcnow().isoformat(),
                'key_info': key_info,
                'provider': 'hashicorp_vault'
            }

            logger.info(f"Created backup for tenant {tenant_id} key")
            return backup_data

        except Exception as e:
            logger.error(f"Failed to backup key for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Key backup failed: {str(e)}")

    def get_secret_versions(self, tenant_id: int) -> List[Dict[str, Any]]:
        """
        Get all versions of a tenant's secret.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            List of secret versions
        """
        try:
            key_path = self.create_key_path(tenant_id)

            # Get secret metadata including all versions
            metadata_response = self.client.secrets.kv.v2.read_secret_metadata(
                path=key_path,
                mount_point=self.mount_point
            )

            versions = []
            for version, version_data in metadata_response['data']['versions'].items():
                versions.append({
                    'version': int(version),
                    'created_time': version_data['created_time'],
                    'deletion_time': version_data.get('deletion_time'),
                    'destroyed': version_data.get('destroyed', False)
                })

            return sorted(versions, key=lambda x: x['version'], reverse=True)

        except InvalidPath:
            return []
        except VaultError as e:
            logger.error(f"Failed to get secret versions for tenant {tenant_id}: {e}")
            return []