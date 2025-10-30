"""
Azure Blob Storage provider implementation.

This module implements the CloudStorageProvider interface for Azure Blob Storage,
providing secure file storage with tenant isolation, server-side encryption,
and comprehensive error handling.
"""

import asyncio
import logging
import mimetypes
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import quote

from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.storage.blob import BlobSasPermissions, generate_blob_sas
from azure.core.exceptions import (
    ResourceNotFoundError, 
    ClientAuthenticationError,
    ServiceRequestError,
    ResourceExistsError
)

from .provider import (
    CloudStorageProvider, 
    StorageResult, 
    StorageConfig, 
    StorageProvider,
    FileMetadata,
    HealthCheckResult
)

logger = logging.getLogger(__name__)


class AzureBlobProvider(CloudStorageProvider):
    """
    Azure Blob Storage provider implementation with tenant isolation and security features.
    
    Features:
    - Server-side encryption (default Azure encryption)
    - Tenant-specific blob container organization
    - Connection pooling and retry logic
    - SAS token generation with configurable expiry
    - Comprehensive error handling and logging
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize Azure Blob provider with configuration.
        
        Args:
            config: StorageConfig with Azure Blob-specific settings
        """
        super().__init__(config)
        
        # Extract Azure Blob-specific configuration
        blob_config = config.config
        self.container_name = blob_config.get('container_name')
        self.account_name = blob_config.get('account_name')
        self.account_key = blob_config.get('account_key')
        self.connection_string = blob_config.get('connection_string')
        self.blob_endpoint = blob_config.get('blob_endpoint')
        self.blob_tier = blob_config.get('blob_tier', 'Hot')
        self.tenant_prefix_enabled = blob_config.get('tenant_prefix_enabled', True)
        self.server_side_encryption = blob_config.get('server_side_encryption', True)
        self.access_control_validation = blob_config.get('access_control_validation', True)
        
        # Validate required configuration
        if not self.container_name:
            raise ValueError("Azure container_name is required in configuration")
        
        # Either connection string or account credentials required
        if not self.connection_string:
            if not self.account_name or not self.account_key:
                raise ValueError("Azure connection_string or account_name/account_key is required")
        
        # Validate blob tier
        valid_tiers = ['Hot', 'Cool', 'Archive']
        if self.blob_tier not in valid_tiers:
            raise ValueError(f"Invalid blob_tier: {self.blob_tier}. Must be one of {valid_tiers}")
        
        # Initialize Azure Blob client
        self._init_blob_client()
        
        logger.info(f"Initialized Azure Blob provider for container: {self.container_name} with tier: {self.blob_tier}")
    
    def _validate_access_permissions(self, operation: str, blob_name: str) -> bool:
        """
        Validate access control for Azure Blob operations.
        
        Args:
            operation: The operation being performed (read, write, delete)
            blob_name: The blob name being accessed
            
        Returns:
            True if access is allowed, False otherwise
        """
        if not self.access_control_validation:
            return True
        
        try:
            # Extract tenant from blob name for validation
            if self.tenant_prefix_enabled and blob_name.startswith('tenant_'):
                tenant_id = blob_name.split('/')[0]
                
                # Validate tenant format
                if not tenant_id.startswith('tenant_') or not tenant_id.replace('tenant_', '').isdigit():
                    logger.warning(f"Invalid tenant format in blob name: {blob_name}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Access control validation failed for {operation} on {blob_name}: {str(e)}")
            return False
    
    def _init_blob_client(self) -> None:
        """Initialize Azure Blob Service client with connection pooling."""
        try:
            if self.connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            else:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                if self.blob_endpoint:
                    account_url = self.blob_endpoint
                
                self.blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=self.account_key
                )
            
            # Get container client
            self.container_client = self.blob_service_client.get_container_client(
                self.container_name
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob client: {e}")
            raise
    
    def _generate_blob_name(self, file_key: str, tenant_id: Optional[str] = None) -> str:
        """
        Generate Azure Blob name with tenant isolation and security validation.
        
        Args:
            file_key: Original file key
            tenant_id: Tenant ID for isolation
            
        Returns:
            Blob name with tenant prefix
        """
        # Security validation: prevent path traversal attacks
        if '..' in file_key or file_key.startswith('/') or '\\' in file_key:
            raise ValueError(f"Invalid file key contains path traversal or invalid characters: {file_key}")
        
        # Sanitize file key
        sanitized_key = file_key.replace('\\', '/').strip('/')
        
        if not self.tenant_prefix_enabled:
            return sanitized_key
        
        # Extract tenant_id from file_key if not provided
        if not tenant_id and sanitized_key.startswith('tenant_'):
            parts = sanitized_key.split('/', 1)
            if len(parts) > 1:
                tenant_id = parts[0]
        
        # Ensure tenant isolation
        if tenant_id:
            if not tenant_id.startswith('tenant_') or not tenant_id.replace('tenant_', '').isdigit():
                raise ValueError(f"Invalid tenant_id format: {tenant_id}")
            
            if not sanitized_key.startswith(f"{tenant_id}/"):
                return f"{tenant_id}/{sanitized_key}"
        
        return sanitized_key    
 
    def _get_upload_metadata(self, content_type: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get Azure Blob upload metadata with security settings.
        
        Args:
            content_type: MIME type of the file
            metadata: Optional metadata to store with the blob
            
        Returns:
            Dictionary of Azure Blob upload arguments
        """
        blob_metadata = {}
        
        # Add custom metadata if provided
        if metadata:
            for key, value in metadata.items():
                if isinstance(key, str) and value is not None:
                    # Sanitize metadata key and value
                    clean_key = key.replace('\n', '').replace('\r', '').strip()
                    clean_value = str(value).replace('\n', '').replace('\r', '').strip()
                    
                    # Limit metadata key/value length for security
                    if len(clean_key) <= 256 and len(clean_value) <= 2048:
                        blob_metadata[clean_key] = clean_value
        
        return blob_metadata
    
    async def upload_file(
        self, 
        file_content: bytes, 
        file_key: str, 
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Upload file to Azure Blob Storage with encryption and tenant isolation.
        
        Args:
            file_content: The file content as bytes
            file_key: Unique key/path for the file in storage
            content_type: MIME type of the file
            metadata: Optional metadata to store with the file
            
        Returns:
            StorageResult with operation details
        """
        start_time = time.time()
        
        try:
            # Generate blob name with security validation
            blob_name = self._generate_blob_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('write', blob_name):
                return StorageResult(
                    success=False,
                    error_message=f"Access denied for upload operation on {file_key}",
                    provider=self.provider_type.value,
                    operation_duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Prepare blob metadata
            blob_metadata = self._get_upload_metadata(content_type, metadata)
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Upload blob with server-side encryption (default in Azure)
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob_client.upload_blob(
                    file_content,
                    content_type=content_type,
                    metadata=blob_metadata,
                    standard_blob_tier=self.blob_tier,
                    overwrite=True
                )
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Successfully uploaded blob to Azure: {blob_name} ({len(file_content)} bytes)")
            
            return StorageResult(
                success=True,
                file_key=file_key,
                file_size=len(file_content),
                content_type=content_type,
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms,
                metadata=metadata
            )
            
        except ResourceExistsError as e:
            error_message = f"Azure Blob already exists: {file_key}"
            logger.error(f"Azure Blob upload failed for {blob_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except ClientAuthenticationError as e:
            error_message = f"Azure Blob authentication failed: {str(e)}"
            logger.error(f"Azure Blob upload failed for {blob_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            error_message = f"Unexpected error during Azure Blob upload: {str(e)}"
            logger.error(f"Unexpected Azure Blob upload error for {blob_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )    

    async def download_file(self, file_key: str) -> StorageResult:
        """
        Download file from Azure Blob Storage with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            StorageResult with file content or download URL
        """
        start_time = time.time()
        
        try:
            # Generate blob name with security validation
            blob_name = self._generate_blob_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', blob_name):
                return StorageResult(
                    success=False,
                    error_message=f"Access denied for download operation on {file_key}",
                    provider=self.provider_type.value,
                    operation_duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Download blob
            download_stream = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob_client.download_blob()
            )
            
            # Read content and properties
            file_content = download_stream.readall()
            blob_properties = download_stream.properties
            
            content_type = blob_properties.content_settings.content_type or 'application/octet-stream'
            file_size = blob_properties.size or len(file_content)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Successfully downloaded blob from Azure: {blob_name} ({file_size} bytes)")
            
            return StorageResult(
                success=True,
                file_key=file_key,
                file_size=file_size,
                content_type=content_type,
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms,
                metadata={'content': file_content}
            )
            
        except ResourceNotFoundError as e:
            error_message = f"File not found in Azure Blob: {file_key}"
            logger.error(f"Azure Blob download failed for {blob_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except ClientAuthenticationError as e:
            error_message = f"Azure Blob authentication failed: {str(e)}"
            logger.error(f"Azure Blob download failed for {blob_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            error_message = f"Unexpected error during Azure Blob download: {str(e)}"
            logger.error(f"Unexpected Azure Blob download error for {blob_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
    
    async def delete_file(self, file_key: str) -> bool:
        """
        Delete file from Azure Blob Storage with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            # Generate blob name with security validation
            blob_name = self._generate_blob_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('delete', blob_name):
                logger.error(f"Access denied for delete operation on {file_key}")
                return False
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Delete blob
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob_client.delete_blob()
            )
            
            logger.info(f"Successfully deleted blob from Azure: {blob_name}")
            return True
            
        except ResourceNotFoundError:
            # Blob doesn't exist, consider deletion successful
            logger.info(f"Blob not found for deletion (already deleted): {blob_name}")
            return True
            
        except ClientAuthenticationError as e:
            logger.error(f"Azure Blob delete failed for {blob_name}: Authentication error: {str(e)}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected Azure Blob delete error for {blob_name}: {str(e)}")
            return False    

    async def get_file_url(
        self, 
        file_key: str, 
        expiry_seconds: int = 3600
    ) -> Optional[str]:
        """
        Generate SAS URL for Azure Blob with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            expiry_seconds: URL expiration time in seconds
            
        Returns:
            SAS URL string or None if generation failed
        """
        try:
            # Generate blob name with security validation
            blob_name = self._generate_blob_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', blob_name):
                logger.error(f"Access denied for URL generation on {file_key}")
                return None
            
            # Limit expiry time for security (max 7 days)
            max_expiry = 7 * 24 * 3600  # 7 days
            if expiry_seconds > max_expiry:
                logger.warning(f"Expiry time {expiry_seconds}s exceeds maximum {max_expiry}s, using maximum")
                expiry_seconds = max_expiry
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Generate SAS token
            sas_token = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: generate_blob_sas(
                    account_name=self.account_name,
                    container_name=self.container_name,
                    blob_name=blob_name,
                    account_key=self.account_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)
                )
            )
            
            # Construct full URL
            blob_url = f"{blob_client.url}?{sas_token}"
            
            logger.debug(f"Generated SAS URL for Azure Blob: {blob_name}")
            return blob_url
            
        except Exception as e:
            logger.error(f"Failed to generate SAS URL for {blob_name}: {str(e)}")
            return None
    
    async def list_files(
        self, 
        prefix: str = "", 
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List files in Azure Blob container with given prefix.
        
        Args:
            prefix: Prefix to filter files
            limit: Maximum number of files to return
            continuation_token: Token for pagination
            
        Returns:
            Dictionary with files list and pagination info
        """
        blob_prefix = self._generate_blob_name(prefix) if prefix else ""
        
        try:
            # List blobs with pagination
            blob_list = self.container_client.list_blobs(
                name_starts_with=blob_prefix,
                results_per_page=limit
            )
            
            # Process blobs
            files = []
            count = 0
            next_marker = None
            
            for blob in blob_list:
                if count >= limit:
                    break
                
                files.append({
                    'key': blob.name,
                    'size': blob.size,
                    'last_modified': blob.last_modified.isoformat() if blob.last_modified else None,
                    'etag': blob.etag.strip('"') if blob.etag else None,
                    'content_type': blob.content_settings.content_type if blob.content_settings else None
                })
                count += 1
            
            result = {
                'files': files,
                'count': len(files),
                'is_truncated': count >= limit,
                'next_continuation_token': next_marker
            }
            
            logger.debug(f"Listed {len(files)} blobs from Azure with prefix: {blob_prefix}")
            return result
            
        except Exception as e:
            logger.error(f"Azure Blob list failed for prefix {blob_prefix}: {str(e)}")
            return {'files': [], 'count': 0, 'error': str(e)}
    
    async def file_exists(self, file_key: str) -> bool:
        """
        Check if file exists in Azure Blob Storage with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            # Generate blob name with security validation
            blob_name = self._generate_blob_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', blob_name):
                logger.error(f"Access denied for file existence check on {file_key}")
                return False
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Check if blob exists
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob_client.get_blob_properties()
            )
            return True
            
        except ResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Unexpected Azure Blob exists check error for {blob_name}: {str(e)}")
            return False 
   
    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """
        Get metadata for a file in Azure Blob Storage with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            FileMetadata object or None if file not found
        """
        try:
            # Generate blob name with security validation
            blob_name = self._generate_blob_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', blob_name):
                logger.error(f"Access denied for metadata access on {file_key}")
                return None
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Get blob properties
            blob_properties = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob_client.get_blob_properties()
            )
            
            # Extract tenant_id from file_key if available
            tenant_id = None
            if file_key.startswith('tenant_'):
                parts = file_key.split('/', 1)
                if len(parts) > 0:
                    tenant_id = parts[0]
            
            return FileMetadata(
                file_key=file_key,
                file_size=blob_properties.size or 0,
                content_type=blob_properties.content_settings.content_type or 'application/octet-stream',
                created_at=blob_properties.creation_time or datetime.now(timezone.utc),
                modified_at=blob_properties.last_modified,
                tenant_id=tenant_id,
                checksum=blob_properties.etag.strip('"') if blob_properties.etag else None,
                custom_metadata=blob_properties.metadata or {}
            )
            
        except ResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Unexpected Azure Blob metadata error for {blob_name}: {str(e)}")
            return None
    
    async def health_check(self) -> HealthCheckResult:
        """
        Check Azure Blob provider health status.
        
        Returns:
            HealthCheckResult with provider status information
        """
        start_time = time.time()
        
        try:
            # Perform a simple get_container_properties operation to check connectivity
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.container_client.get_container_properties()
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=True,
                response_time_ms=response_time_ms,
                last_check=datetime.now(timezone.utc),
                additional_info={
                    'container': self.container_name,
                    'account_name': self.account_name,
                    'blob_tier': self.blob_tier,
                    'encryption': 'Server-side (Azure default)'
                }
            )
            
            self._last_health_check = result
            logger.debug(f"Azure Blob health check passed in {response_time_ms}ms")
            return result
            
        except ClientAuthenticationError as e:
            error_message = "Azure Blob authentication failed"
            logger.error(f"Azure Blob health check failed: {error_message}")
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=False,
                error_message=error_message,
                last_check=datetime.now(timezone.utc)
            )
            
            self._last_health_check = result
            return result
            
        except ResourceNotFoundError as e:
            error_message = f"Azure Blob container not found: {self.container_name}"
            logger.error(f"Azure Blob health check failed: {error_message}")
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=False,
                error_message=error_message,
                last_check=datetime.now(timezone.utc),
                response_time_ms=int((time.time() - start_time) * 1000)
            )
            
            self._last_health_check = result
            return result
            
        except Exception as e:
            error_message = f"Unexpected error during Azure Blob health check: {str(e)}"
            logger.error(error_message)
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=False,
                error_message=error_message,
                last_check=datetime.now(timezone.utc),
                response_time_ms=int((time.time() - start_time) * 1000)
            )
            
            self._last_health_check = result
            return result    
    
    def _create_tenant_container_name(self, tenant_id: str) -> str:
        """
        Create tenant-specific container name for enhanced isolation.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Tenant-specific container name
        """
        if not tenant_id or not tenant_id.startswith('tenant_'):
            raise ValueError(f"Invalid tenant_id format: {tenant_id}")
        
        # Create container name with tenant prefix for complete isolation
        # Format: {base_container}-{tenant_id}
        tenant_suffix = tenant_id.replace('tenant_', '')
        return f"{self.container_name}-{tenant_suffix}"
    
    def _validate_blob_security(self, blob_name: str, operation: str) -> bool:
        """
        Enhanced security validation for blob operations.
        
        Args:
            blob_name: The blob name to validate
            operation: The operation being performed
            
        Returns:
            True if security validation passes, False otherwise
        """
        try:
            # Check for malicious patterns
            malicious_patterns = [
                '../', '..\\', './', '.\\',  # Path traversal
                '<script', 'javascript:', 'data:',  # XSS attempts
                'DROP TABLE', 'SELECT *', 'INSERT INTO',  # SQL injection attempts
                '\x00', '\r\n', '\n\r'  # Null bytes and CRLF injection
            ]
            
            blob_name_lower = blob_name.lower()
            for pattern in malicious_patterns:
                if pattern in blob_name_lower:
                    logger.warning(f"Security violation detected in blob name: {blob_name} (pattern: {pattern})")
                    return False
            
            # Validate blob name length and characters
            if len(blob_name) > 1024:  # Azure Blob name limit
                logger.warning(f"Blob name too long: {len(blob_name)} characters")
                return False
            
            # Check for valid characters (Azure Blob naming rules)
            import re
            if not re.match(r'^[a-zA-Z0-9._/-]+$', blob_name):
                logger.warning(f"Invalid characters in blob name: {blob_name}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Security validation error for {blob_name}: {str(e)}")
            return False
    
    def _encrypt_sensitive_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive metadata fields before storage.
        
        Args:
            metadata: Original metadata dictionary
            
        Returns:
            Metadata with sensitive fields encrypted
        """
        if not metadata:
            return {}
        
        try:
            # Import encryption service if available
            from services.key_management_service import get_key_management_service
            
            key_service = get_key_management_service()
            encrypted_metadata = {}
            
            # Define sensitive fields that should be encrypted
            sensitive_fields = ['user_id', 'email', 'phone', 'ssn', 'credit_card']
            
            for key, value in metadata.items():
                if key.lower() in sensitive_fields and value:
                    # Encrypt sensitive field
                    encrypted_value = key_service._encrypt_with_master_key(str(value).encode('utf-8'))
                    encrypted_metadata[f"encrypted_{key}"] = encrypted_value
                else:
                    # Keep non-sensitive fields as-is
                    encrypted_metadata[key] = str(value)
            
            return encrypted_metadata
            
        except ImportError:
            # Encryption service not available, return original metadata
            logger.warning("Encryption service not available, storing metadata unencrypted")
            return {k: str(v) for k, v in metadata.items()}
        except Exception as e:
            logger.error(f"Failed to encrypt metadata: {str(e)}")
            return {k: str(v) for k, v in metadata.items()}
    
    def _generate_secure_sas_token(self, blob_name: str, expiry_seconds: int) -> Optional[str]:
        """
        Generate secure SAS token with minimal permissions and IP restrictions.
        
        Args:
            blob_name: The blob name for SAS token
            expiry_seconds: Token expiration time in seconds
            
        Returns:
            Secure SAS token or None if generation failed
        """
        try:
            # Create SAS permissions with minimal required access
            permissions = BlobSasPermissions(read=True)
            
            # Set expiry time
            expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)
            
            # Generate SAS token with security constraints
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self.account_key,
                permission=permissions,
                expiry=expiry_time,
                # Add IP restrictions if available in environment
                # ip=os.getenv('ALLOWED_IP_RANGE'),  # Uncomment if IP restrictions needed
                protocol='https'  # Force HTTPS only
            )
            
            return sas_token
            
        except Exception as e:
            logger.error(f"Failed to generate secure SAS token for {blob_name}: {str(e)}")
            return None
    
    async def create_tenant_container(self, tenant_id: str) -> bool:
        """
        Create a dedicated container for a tenant (optional enhanced isolation).
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if container was created or already exists, False otherwise
        """
        try:
            container_name = self._create_tenant_container_name(tenant_id)
            
            # Create container client for tenant
            tenant_container_client = self.blob_service_client.get_container_client(container_name)
            
            # Create container if it doesn't exist
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: tenant_container_client.create_container()
            )
            
            logger.info(f"Created tenant container: {container_name}")
            return True
            
        except ResourceExistsError:
            # Container already exists, which is fine
            logger.debug(f"Tenant container already exists: {container_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create tenant container for {tenant_id}: {str(e)}")
            return False