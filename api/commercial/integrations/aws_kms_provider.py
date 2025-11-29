"""
AWS KMS Key Vault Provider for Tenant Database Encryption

This module provides AWS KMS integration for secure key management
in the tenant database encryption system with sync and async support.
"""

import boto3
from botocore.config import Config as boto3Config
import base64
import json
import logging
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError, BotoCoreError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from encryption_config import EncryptionConfig
from core.exceptions.encryption_exceptions import (
    KeyNotFoundError,
    EncryptionError,
    KeyRotationError
)
from commercial.integrations.circuit_breaker import (
    CloudProviderCircuitBreaker,
    CircuitBreakerOpenException
)

try:
    import aioboto3
    HAS_AIOBOTOCORE = True
except ImportError:
    HAS_AIOBOTOCORE = False

logger = logging.getLogger(__name__)


class AWSKMSProvider:
    """AWS KMS provider for encryption key management."""

    def __init__(self, config: EncryptionConfig):
        """Initialize AWS KMS provider with configuration, connection pooling, and circuit breakers."""
        self.config = config
        self.region = config.AWS_REGION
        self.master_key_id = config.AWS_KMS_MASTER_KEY_ID

        # Initialize circuit breakers for different operations
        self._init_circuit_breakers()

        # Initialize KMS client with connection pooling and session management
        try:
            # Create a session for connection pooling and efficient resource management
            self.session = boto3.Session(
                aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
                region_name=self.region
            )

            # Configure client with connection pooling
            # max_pool_connections: Maximum number of connections to keep in the connection pool (default 10)
            # retries: Configure retry behavior
            self.kms_client = self.session.client(
                'kms',
                config=boto3Config(
                    region_name=self.region,
                    max_pool_connections=20,  # Increased from default for better performance
                    retries={
                        'max_attempts': 3,
                        'mode': 'adaptive'  # Use adaptive retry mode for better performance
                    },
                    # Connection timeout and read timeout
                    connect_timeout=5,
                    read_timeout=60
                )
            )

            logger.info(f"AWS KMS client initialized with connection pooling and circuit breakers for region: {self.region}")
        except Exception as e:
            logger.error(f"Failed to initialize AWS KMS client: {str(e)}")
            raise EncryptionError(f"AWS KMS initialization failed: {str(e)}")

    def _init_circuit_breakers(self) -> None:
        """Initialize circuit breakers for different AWS KMS operations."""
        # Circuit breakers for AWS KMS operations
        self.generate_key_breaker = CloudProviderCircuitBreaker(
            provider_name="aws_kms",
            operation_name="generate_key",
            failure_threshold=3,  # Open circuit after 3 failures
            recovery_timeout=30.0,  # Wait 30 seconds before attempting recovery
            success_threshold=2  # Need 2 successes in HALF_OPEN to close circuit
        )

        self.decrypt_key_breaker = CloudProviderCircuitBreaker(
            provider_name="aws_kms",
            operation_name="decrypt_key",
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2
        )

        self.key_management_breaker = CloudProviderCircuitBreaker(
            provider_name="aws_kms",
            operation_name="key_management",  # For rotate, create, get_info operations
            failure_threshold=3,
            recovery_timeout=60.0,  # Longer recovery for management operations
            success_threshold=2
        )

        logger.info("AWS KMS circuit breakers initialized")

    def generate_data_key(self, tenant_id: int, key_spec: str = "AES_256") -> Dict[str, str]:
        """
        Generate a new data encryption key for a tenant using AWS KMS.

        Uses circuit breaker pattern for resilience against provider failures.

        Args:
            tenant_id: Unique identifier for the tenant
            key_spec: Key specification (AES_256, AES_128)

        Returns:
            Dictionary containing plaintext and encrypted data keys

        Raises:
            CircuitBreakerOpenException: If circuit breaker is OPEN
            EncryptionError: If key generation fails
        """
        return self.generate_key_breaker.call(
            self._generate_data_key_internal, tenant_id, key_spec
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    def _generate_data_key_internal(self, tenant_id: int, key_spec: str = "AES_256") -> Dict[str, str]:
        """Internal implementation of generate_data_key (wrapped by circuit breaker)."""
        try:
            # Create encryption context for audit and access control
            encryption_context = {
                'tenant_id': str(tenant_id),
                'purpose': 'database_encryption',
                'service': 'invoice_management'
            }

            response = self.kms_client.generate_data_key(
                KeyId=self.master_key_id,
                KeySpec=key_spec,
                EncryptionContext=encryption_context
            )

            # Return base64 encoded keys for storage
            return {
                'plaintext_key': base64.b64encode(response['Plaintext']).decode('utf-8'),
                'encrypted_key': base64.b64encode(response['CiphertextBlob']).decode('utf-8'),
                'key_id': response['KeyId']
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"AWS KMS generate_data_key failed for tenant {tenant_id}: {error_code}")
            raise EncryptionError(f"Failed to generate data key: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error generating data key for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Data key generation failed: {str(e)}")

    def decrypt_data_key(self, encrypted_key: str, tenant_id: int) -> str:
        """
        Decrypt an encrypted data key using AWS KMS.

        Uses circuit breaker pattern for resilience against provider failures.

        Args:
            encrypted_key: Base64 encoded encrypted data key
            tenant_id: Unique identifier for the tenant

        Returns:
            Base64 encoded plaintext data key

        Raises:
            CircuitBreakerOpenException: If circuit breaker is OPEN
            KeyNotFoundError: If key cannot be found or decrypted
            EncryptionError: If decryption fails
        """
        return self.decrypt_key_breaker.call(
            self._decrypt_data_key_internal, encrypted_key, tenant_id
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    def _decrypt_data_key_internal(self, encrypted_key: str, tenant_id: int) -> str:
        """Internal implementation of decrypt_data_key (wrapped by circuit breaker)."""
        try:
            # Decode the encrypted key
            encrypted_blob = base64.b64decode(encrypted_key.encode('utf-8'))

            # Create encryption context for verification
            encryption_context = {
                'tenant_id': str(tenant_id),
                'purpose': 'database_encryption',
                'service': 'invoice_management'
            }

            response = self.kms_client.decrypt(
                CiphertextBlob=encrypted_blob,
                EncryptionContext=encryption_context
            )

            return base64.b64encode(response['Plaintext']).decode('utf-8')

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['InvalidCiphertextException', 'KeyUnavailableException']:
                logger.error(f"Key not found or invalid for tenant {tenant_id}: {error_code}")
                raise KeyNotFoundError(f"Cannot decrypt key for tenant {tenant_id}: {error_code}")
            else:
                logger.error(f"AWS KMS decrypt failed for tenant {tenant_id}: {error_code}")
                raise EncryptionError(f"Key decryption failed: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error decrypting key for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Key decryption failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    def rotate_master_key(self) -> bool:
        """
        Rotate the AWS KMS master key.

        Returns:
            True if rotation was successful

        Raises:
            KeyRotationError: If rotation fails
        """
        try:
            # Enable automatic key rotation
            self.kms_client.enable_key_rotation(KeyId=self.master_key_id)

            # Get rotation status to verify
            response = self.kms_client.get_key_rotation_status(KeyId=self.master_key_id)

            if response['KeyRotationEnabled']:
                logger.info(f"Key rotation enabled for master key: {self.master_key_id}")
                return True
            else:
                raise KeyRotationError("Failed to enable key rotation")

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"AWS KMS key rotation failed: {error_code}")
            raise KeyRotationError(f"Master key rotation failed: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error during key rotation: {str(e)}")
            raise KeyRotationError(f"Key rotation failed: {str(e)}")

    def create_key_alias(self, tenant_id: int) -> str:
        """
        Create a key alias for a tenant.

        Args:
            tenant_id: Unique identifier for the tenant

        Returns:
            Key alias string
        """
        return f"alias/tenant-{tenant_id}-encryption-key"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    def create_tenant_key(self, tenant_id: int, description: Optional[str] = None) -> str:
        """
        Create a dedicated KMS key for a tenant.

        Args:
            tenant_id: Unique identifier for the tenant
            description: Optional description for the key

        Returns:
            Key ID of the created key

        Raises:
            EncryptionError: If key creation fails
        """
        try:
            if not description:
                description = f"Encryption key for tenant {tenant_id}"

            # Create the key
            response = self.kms_client.create_key(
                Description=description,
                Usage='ENCRYPT_DECRYPT',
                KeySpec='SYMMETRIC_DEFAULT',
                Origin='AWS_KMS',
                Tags=[
                    {
                        'TagKey': 'TenantId',
                        'TagValue': str(tenant_id)
                    },
                    {
                        'TagKey': 'Purpose',
                        'TagValue': 'DatabaseEncryption'
                    },
                    {
                        'TagKey': 'Service',
                        'TagValue': 'InvoiceManagement'
                    }
                ]
            )

            key_id = response['KeyMetadata']['KeyId']

            # Create an alias for easier management
            alias = self.create_key_alias(tenant_id)
            try:
                self.kms_client.create_alias(
                    AliasName=alias,
                    TargetKeyId=key_id
                )
                logger.info(f"Created key alias {alias} for tenant {tenant_id}")
            except ClientError as e:
                if e.response['Error']['Code'] != 'AlreadyExistsException':
                    logger.warning(f"Failed to create alias {alias}: {e}")

            logger.info(f"Created KMS key {key_id} for tenant {tenant_id}")
            return key_id

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"AWS KMS key creation failed for tenant {tenant_id}: {error_code}")
            raise EncryptionError(f"Failed to create tenant key: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error creating key for tenant {tenant_id}: {str(e)}")
            raise EncryptionError(f"Tenant key creation failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    def get_key_info(self, key_id: str) -> Dict[str, Any]:
        """
        Get information about a KMS key.

        Args:
            key_id: KMS key ID or alias

        Returns:
            Dictionary containing key metadata

        Raises:
            KeyNotFoundError: If key is not found
            EncryptionError: If operation fails
        """
        try:
            response = self.kms_client.describe_key(KeyId=key_id)
            return response['KeyMetadata']

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NotFoundException':
                raise KeyNotFoundError(f"KMS key not found: {key_id}")
            else:
                logger.error(f"Failed to get key info for {key_id}: {error_code}")
                raise EncryptionError(f"Failed to get key info: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error getting key info for {key_id}: {str(e)}")
            raise EncryptionError(f"Get key info failed: {str(e)}")

    def audit_key_access(self, tenant_id: int, operation: str, key_id: str, success: bool) -> None:
        """
        Log key access for audit purposes.

        Args:
            tenant_id: Unique identifier for the tenant
            operation: Operation performed (generate, decrypt, rotate, etc.)
            key_id: KMS key ID
            success: Whether the operation was successful
        """
        audit_data = {
            'provider': 'aws_kms',
            'tenant_id': tenant_id,
            'operation': operation,
            'key_id': key_id,
            'success': success,
            'region': self.region
        }

        if success:
            logger.info(f"AWS KMS audit: {json.dumps(audit_data)}")
        else:
            logger.warning(f"AWS KMS audit (failed): {json.dumps(audit_data)}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the AWS KMS connection and circuit breakers.

        Returns:
            Dictionary containing health status and circuit breaker information
        """
        try:
            # Try to describe the master key (lightweight operation)
            response = self.kms_client.describe_key(KeyId=self.master_key_id)
            kms_healthy = True
            kms_error = None
        except Exception as e:
            kms_healthy = False
            kms_error = str(e)
            response = None

        # Collect circuit breaker status
        circuit_breakers = {
            'generate_key_breaker': self.generate_key_breaker.get_health_status(),
            'decrypt_key_breaker': self.decrypt_key_breaker.get_health_status(),
            'key_management_breaker': self.key_management_breaker.get_health_status()
        }

        return {
            'provider': 'aws_kms',
            'status': 'healthy' if kms_healthy else 'unhealthy',
            'region': self.region,
            'master_key_id': self.master_key_id,
            'key_state': response['KeyMetadata']['KeyState'] if response else None,
            'error': kms_error,
            'circuit_breakers': circuit_breakers,
            'connection_pooling': {
                'max_connections': 20,
                'adaptive_retry': True,
                'timeout_configured': True
            }
        }

    # Async methods for improved I/O performance

    async def _get_async_client(self):
        """Get async KMS client using aioboto3 with connection pooling."""
        if not HAS_AIOBOTOCORE:
            raise EncryptionError("aioboto3 not installed. Install with: pip install aioboto3")

        # Create an async session for connection pooling (aioboto3.Session)
        session = aioboto3.Session(
            aws_access_key_id=self.config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.config.AWS_SECRET_ACCESS_KEY
        )

        # Create client with connection pooling configuration
        return session.client(
            'kms',
            region_name=self.region,
            config=boto3Config(
                max_pool_connections=20,  # Match synchronous pool size
                retries={
                    'max_attempts': 3,
                    'mode': 'adaptive'
                },
                connect_timeout=5,
                read_timeout=60
            )
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    async def generate_data_key_async(self, tenant_id: int, key_spec: str = "AES_256") -> Dict[str, str]:
        """
        Asynchronously generate a new data encryption key for a tenant using AWS KMS.

        Args:
            tenant_id: Unique identifier for the tenant
            key_spec: Key specification (AES_256, AES_128)

        Returns:
            Dictionary containing plaintext and encrypted data keys

        Raises:
            EncryptionError: If key generation fails
        """
        async with await self._get_async_client() as kms_client:
            try:
                # Create encryption context for audit and access control
                encryption_context = {
                    'tenant_id': str(tenant_id),
                    'purpose': 'database_encryption',
                    'service': 'invoice_management'
                }

                response = await kms_client.generate_data_key(
                    KeyId=self.master_key_id,
                    KeySpec=key_spec,
                    EncryptionContext=encryption_context
                )

                # Return base64 encoded keys for storage
                return {
                    'plaintext_key': base64.b64encode(response['Plaintext']).decode('utf-8'),
                    'encrypted_key': base64.b64encode(response['CiphertextBlob']).decode('utf-8'),
                    'key_id': response['KeyId']
                }

            except ClientError as e:
                error_code = e.response['Error']['Code']
                logger.error(f"AWS KMS async generate_data_key failed for tenant {tenant_id}: {error_code}")
                raise EncryptionError(f"Failed to generate data key: {error_code}")
            except Exception as e:
                logger.error(f"Unexpected error generating data key for tenant {tenant_id}: {str(e)}")
                raise EncryptionError(f"Data key generation failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    async def decrypt_data_key_async(self, encrypted_key: str, tenant_id: int) -> str:
        """
        Asynchronously decrypt an encrypted data key using AWS KMS.

        Args:
            encrypted_key: Base64 encoded encrypted data key
            tenant_id: Unique identifier for the tenant

        Returns:
            Base64 encoded plaintext data key

        Raises:
            KeyNotFoundError: If key cannot be found or decrypted
            EncryptionError: If decryption fails
        """
        async with await self._get_async_client() as kms_client:
            try:
                # Decode the encrypted key
                encrypted_blob = base64.b64decode(encrypted_key.encode('utf-8'))

                # Create encryption context for verification
                encryption_context = {
                    'tenant_id': str(tenant_id),
                    'purpose': 'database_encryption',
                    'service': 'invoice_management'
                }

                response = await kms_client.decrypt(
                    CiphertextBlob=encrypted_blob,
                    EncryptionContext=encryption_context
                )

                return base64.b64encode(response['Plaintext']).decode('utf-8')

            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code in ['InvalidCiphertextException', 'KeyUnavailableException']:
                    logger.error(f"Key not found or invalid for tenant {tenant_id}: {error_code}")
                    raise KeyNotFoundError(f"Cannot decrypt key for tenant {tenant_id}: {error_code}")
                else:
                    logger.error(f"AWS KMS async decrypt failed for tenant {tenant_id}: {error_code}")
                    raise EncryptionError(f"Key decryption failed: {error_code}")
            except Exception as e:
                logger.error(f"Unexpected error decrypting key for tenant {tenant_id}: {str(e)}")
                raise EncryptionError(f"Key decryption failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    async def rotate_master_key_async(self) -> bool:
        """
        Asynchronously rotate the AWS KMS master key.

        Returns:
            True if rotation was successful

        Raises:
            KeyRotationError: If rotation fails
        """
        async with await self._get_async_client() as kms_client:
            try:
                # Enable automatic key rotation
                await kms_client.enable_key_rotation(KeyId=self.master_key_id)

                # Get rotation status to verify
                response = await kms_client.get_key_rotation_status(KeyId=self.master_key_id)

                if response['KeyRotationEnabled']:
                    logger.info(f"Key rotation enabled for master key: {self.master_key_id}")
                    return True
                else:
                    raise KeyRotationError("Failed to enable key rotation")

            except ClientError as e:
                error_code = e.response['Error']['Code']
                logger.error(f"AWS KMS async key rotation failed: {error_code}")
                raise KeyRotationError(f"Master key rotation failed: {error_code}")
            except Exception as e:
                logger.error(f"Unexpected error during async key rotation: {str(e)}")
                raise KeyRotationError(f"Key rotation failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    async def create_tenant_key_async(self, tenant_id: int, description: Optional[str] = None) -> str:
        """
        Asynchronously create a dedicated KMS key for a tenant.

        Args:
            tenant_id: Unique identifier for the tenant
            description: Optional description for the key

        Returns:
            Key ID of the created key

        Raises:
            EncryptionError: If key creation fails
        """
        async with await self._get_async_client() as kms_client:
            try:
                if not description:
                    description = f"Encryption key for tenant {tenant_id}"

                # Create the key
                response = await kms_client.create_key(
                    Description=description,
                    Usage='ENCRYPT_DECRYPT',
                    KeySpec='SYMMETRIC_DEFAULT',
                    Origin='AWS_KMS',
                    Tags=[
                        {
                            'TagKey': 'TenantId',
                            'TagValue': str(tenant_id)
                        },
                        {
                            'TagKey': 'Purpose',
                            'TagValue': 'DatabaseEncryption'
                        },
                        {
                            'TagKey': 'Service',
                            'TagValue': 'InvoiceManagement'
                        }
                    ]
                )

                key_id = response['KeyMetadata']['KeyId']

                # Create an alias for easier management
                alias = self.create_key_alias(tenant_id)
                try:
                    await kms_client.create_alias(
                        AliasName=alias,
                        TargetKeyId=key_id
                    )
                    logger.info(f"Created async key alias {alias} for tenant {tenant_id}")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'AlreadyExistsException':
                        logger.warning(f"Failed to create async alias {alias}: {e}")

                logger.info(f"Asynchronously created KMS key {key_id} for tenant {tenant_id}")
                return key_id

            except ClientError as e:
                error_code = e.response['Error']['Code']
                logger.error(f"AWS KMS async key creation failed for tenant {tenant_id}: {error_code}")
                raise EncryptionError(f"Failed to create tenant key: {error_code}")
            except Exception as e:
                logger.error(f"Unexpected error async creating key for tenant {tenant_id}: {str(e)}")
                raise EncryptionError(f"Tenant key creation failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, BotoCoreError))
    )
    async def get_key_info_async(self, key_id: str) -> Dict[str, Any]:
        """
        Asynchronously get information about a KMS key.

        Args:
            key_id: KMS key ID or alias

        Returns:
            Dictionary containing key metadata

        Raises:
            KeyNotFoundError: If key is not found
            EncryptionError: If operation fails
        """
        async with await self._get_async_client() as kms_client:
            try:
                response = await kms_client.describe_key(KeyId=key_id)
                return response['KeyMetadata']

            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NotFoundException':
                    raise KeyNotFoundError(f"KMS key not found: {key_id}")
                else:
                    logger.error(f"Failed to async get key info for {key_id}: {error_code}")
                    raise EncryptionError(f"Failed to get key info: {error_code}")
            except Exception as e:
                logger.error(f"Unexpected error async getting key info for {key_id}: {str(e)}")
                raise EncryptionError(f"Get key info failed: {str(e)}")

    async def health_check_async(self) -> Dict[str, Any]:
        """
        Asynchronously perform a health check on the AWS KMS connection.

        Returns:
            Dictionary containing health status
        """
        async with await self._get_async_client() as kms_client:
            try:
                # Try to describe the master key
                response = await kms_client.describe_key(KeyId=self.master_key_id)

                return {
                    'provider': 'aws_kms',
                    'status': 'healthy',
                    'region': self.region,
                    'master_key_id': self.master_key_id,
                    'key_state': response['KeyMetadata']['KeyState']
                }

            except Exception as e:
                return {
                    'provider': 'aws_kms',
                    'status': 'unhealthy',
                    'region': self.region,
                    'error': str(e)
                }
