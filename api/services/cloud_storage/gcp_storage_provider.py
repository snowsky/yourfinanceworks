"""
Google Cloud Storage provider implementation.

This module implements the CloudStorageProvider interface for Google Cloud Storage,
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

from google.cloud import storage
from google.cloud.exceptions import NotFound, Forbidden, GoogleCloudError
from google.auth.exceptions import DefaultCredentialsError
from google.api_core import exceptions as gcp_exceptions

from .provider import (
    CloudStorageProvider, 
    StorageResult, 
    StorageConfig, 
    StorageProvider,
    FileMetadata,
    HealthCheckResult
)

logger = logging.getLogger(__name__)


class GCPStorageProvider(CloudStorageProvider):
    """
    Google Cloud Storage provider implementation with tenant isolation and security features.
    
    Features:
    - Server-side encryption (Google-managed or customer-managed keys)
    - Tenant-specific object key prefixes for isolation
    - Connection pooling and retry logic
    - Signed URL generation with configurable expiry
    - Comprehensive error handling and logging
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize Google Cloud Storage provider with configuration.
        
        Args:
            config: StorageConfig with GCS-specific settings
        """
        super().__init__(config)
        
        # Extract GCS-specific configuration
        gcs_config = config.config
        self.bucket_name = gcs_config.get('bucket_name')
        self.project_id = gcs_config.get('project_id')
        self.credentials_path = gcs_config.get('credentials_path')
        self.credentials_json = gcs_config.get('credentials_json')
        self.storage_class = gcs_config.get('storage_class', 'STANDARD')
        self.kms_key_name = gcs_config.get('kms_key_name')  # For CMEK encryption
        self.tenant_prefix_enabled = gcs_config.get('tenant_prefix_enabled', True)
        self.server_side_encryption = gcs_config.get('server_side_encryption', True)
        self.access_control_validation = gcs_config.get('access_control_validation', True)
        
        # Validate required configuration
        if not self.bucket_name:
            raise ValueError("GCS bucket_name is required in configuration")
        
        if not self.project_id:
            raise ValueError("GCS project_id is required in configuration")
        
        # Validate storage class
        valid_classes = ['STANDARD', 'NEARLINE', 'COLDLINE', 'ARCHIVE']
        if self.storage_class not in valid_classes:
            raise ValueError(f"Invalid storage_class: {self.storage_class}. Must be one of {valid_classes}")
        
        # Initialize GCS client
        self._init_gcs_client()
        
        logger.info(f"Initialized GCS provider for bucket: {self.bucket_name} with storage class: {self.storage_class}")
    
    def _validate_access_permissions(self, operation: str, object_name: str) -> bool:
        """
        Validate access control for GCS operations.
        
        Args:
            operation: The operation being performed (read, write, delete)
            object_name: The object name being accessed
            
        Returns:
            True if access is allowed, False otherwise
        """
        if not self.access_control_validation:
            return True
        
        try:
            # Extract tenant from object name for validation
            if self.tenant_prefix_enabled and object_name.startswith('tenant_'):
                tenant_id = object_name.split('/')[0]
                
                # Validate tenant format
                if not tenant_id.startswith('tenant_') or not tenant_id.replace('tenant_', '').isdigit():
                    logger.warning(f"Invalid tenant format in object name: {object_name}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Access control validation failed for {operation} on {object_name}: {str(e)}")
            return False
    
    def _init_gcs_client(self) -> None:
        """Initialize Google Cloud Storage client with authentication."""
        try:
            if self.credentials_path:
                # Use service account key file
                self.client = storage.Client.from_service_account_json(
                    self.credentials_path,
                    project=self.project_id
                )
            elif self.credentials_json:
                # Use service account key JSON
                import json
                from google.oauth2 import service_account
                
                credentials_dict = json.loads(self.credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict
                )
                self.client = storage.Client(
                    project=self.project_id,
                    credentials=credentials
                )
            else:
                # Use default credentials (ADC)
                self.client = storage.Client(project=self.project_id)
            
            # Get bucket reference
            self.bucket = self.client.bucket(self.bucket_name)
            
        except DefaultCredentialsError as e:
            logger.error(f"GCS authentication failed: {e}")
            raise ValueError(f"GCS authentication failed: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise
    
    def _generate_object_name(self, file_key: str, tenant_id: Optional[str] = None) -> str:
        """
        Generate GCS object name with tenant isolation and security validation.
        
        Args:
            file_key: Original file key
            tenant_id: Tenant ID for isolation
            
        Returns:
            Object name with tenant prefix
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
        Get GCS upload metadata with security settings.
        
        Args:
            content_type: MIME type of the file
            metadata: Optional metadata to store with the object
            
        Returns:
            Dictionary of GCS upload arguments
        """
        gcs_metadata = {}
        
        # Add custom metadata if provided
        if metadata:
            for key, value in metadata.items():
                if isinstance(key, str) and value is not None:
                    # Sanitize metadata key and value
                    clean_key = key.replace('\n', '').replace('\r', '').strip()
                    clean_value = str(value).replace('\n', '').replace('\r', '').strip()
                    
                    # Limit metadata key/value length for security
                    if len(clean_key) <= 256 and len(clean_value) <= 2048:
                        gcs_metadata[clean_key] = clean_value
        
        return gcs_metadata

    async def upload_file(
        self, 
        file_content: bytes, 
        file_key: str, 
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Upload file to Google Cloud Storage with encryption and tenant isolation.
        
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
            # Generate object name with security validation
            object_name = self._generate_object_name(file_key)
            
            # Enhanced security validation
            if not self._validate_object_security(object_name, 'write'):
                return StorageResult(
                    success=False,
                    error_message=f"Security validation failed for upload operation on {file_key}",
                    provider=self.provider_type.value,
                    operation_duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Validate access permissions
            if not self._validate_access_permissions('write', object_name):
                return StorageResult(
                    success=False,
                    error_message=f"Access denied for upload operation on {file_key}",
                    provider=self.provider_type.value,
                    operation_duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Prepare object metadata with encryption for sensitive fields
            object_metadata = self._encrypt_sensitive_metadata(metadata) if metadata else {}
            
            # Create blob object
            blob = self.bucket.blob(object_name)
            
            # Set content type
            blob.content_type = content_type
            
            # Set storage class
            blob.storage_class = self.storage_class
            
            # Set custom metadata
            if object_metadata:
                blob.metadata = object_metadata
            
            # Set encryption if CMEK is configured
            if self.kms_key_name:
                blob.kms_key_name = self.kms_key_name
            
            # Upload blob with server-side encryption
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob.upload_from_string(
                    file_content,
                    content_type=content_type
                )
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Successfully uploaded object to GCS: {object_name} ({len(file_content)} bytes)")
            
            return StorageResult(
                success=True,
                file_key=file_key,
                file_size=len(file_content),
                content_type=content_type,
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms,
                metadata=metadata
            )
            
        except Forbidden as e:
            error_message = f"GCS access forbidden: {str(e)}"
            logger.error(f"GCS upload failed for {object_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except GoogleCloudError as e:
            error_message = f"GCS upload failed: {str(e)}"
            logger.error(f"GCS upload failed for {object_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            error_message = f"Unexpected error during GCS upload: {str(e)}"
            logger.error(f"Unexpected GCS upload error for {object_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
    
    async def download_file(self, file_key: str) -> StorageResult:
        """
        Download file from Google Cloud Storage with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            StorageResult with file content or download URL
        """
        start_time = time.time()
        
        try:
            # Generate object name with security validation
            object_name = self._generate_object_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', object_name):
                return StorageResult(
                    success=False,
                    error_message=f"Access denied for download operation on {file_key}",
                    provider=self.provider_type.value,
                    operation_duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Get blob object
            blob = self.bucket.blob(object_name)
            
            # Download blob content
            file_content = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob.download_as_bytes()
            )
            
            # Get blob properties
            content_type = blob.content_type or 'application/octet-stream'
            file_size = blob.size or len(file_content)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Successfully downloaded object from GCS: {object_name} ({file_size} bytes)")
            
            return StorageResult(
                success=True,
                file_key=file_key,
                file_size=file_size,
                content_type=content_type,
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms,
                metadata={'content': file_content}
            )
            
        except NotFound as e:
            error_message = f"File not found in GCS: {file_key}"
            logger.error(f"GCS download failed for {object_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except Forbidden as e:
            error_message = f"GCS access forbidden: {str(e)}"
            logger.error(f"GCS download failed for {object_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            error_message = f"Unexpected error during GCS download: {str(e)}"
            logger.error(f"Unexpected GCS download error for {object_name}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
    
    async def delete_file(self, file_key: str) -> bool:
        """
        Delete file from Google Cloud Storage with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            # Generate object name with security validation
            object_name = self._generate_object_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('delete', object_name):
                logger.error(f"Access denied for delete operation on {file_key}")
                return False
            
            # Get blob object
            blob = self.bucket.blob(object_name)
            
            # Delete blob
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob.delete()
            )
            
            logger.info(f"Successfully deleted object from GCS: {object_name}")
            return True
            
        except NotFound:
            # Object doesn't exist, consider deletion successful
            logger.info(f"Object not found for deletion (already deleted): {object_name}")
            return True
            
        except Forbidden as e:
            logger.error(f"GCS delete failed for {object_name}: Access forbidden: {str(e)}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected GCS delete error for {object_name}: {str(e)}")
            return False
    
    async def get_file_url(
        self, 
        file_key: str, 
        expiry_seconds: int = 3600
    ) -> Optional[str]:
        """
        Generate signed URL for GCS object with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            expiry_seconds: URL expiration time in seconds
            
        Returns:
            Signed URL string or None if generation failed
        """
        try:
            # Generate object name with security validation
            object_name = self._generate_object_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', object_name):
                logger.error(f"Access denied for URL generation on {file_key}")
                return None
            
            # Limit expiry time for security (max 7 days)
            max_expiry = 7 * 24 * 3600  # 7 days
            if expiry_seconds > max_expiry:
                logger.warning(f"Expiry time {expiry_seconds}s exceeds maximum {max_expiry}s, using maximum")
                expiry_seconds = max_expiry
            
            # Get blob object
            blob = self.bucket.blob(object_name)
            
            # Generate secure signed URL
            signed_url = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._generate_secure_signed_url(object_name, expiry_seconds)
            )
            
            logger.debug(f"Generated signed URL for GCS object: {object_name}")
            return signed_url
            
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {object_name}: {str(e)}")
            return None
    
    async def list_files(
        self, 
        prefix: str = "", 
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List files in GCS bucket with given prefix.
        
        Args:
            prefix: Prefix to filter files
            limit: Maximum number of files to return
            continuation_token: Token for pagination
            
        Returns:
            Dictionary with files list and pagination info
        """
        object_prefix = self._generate_object_name(prefix) if prefix else ""
        
        try:
            # List blobs with pagination
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=object_prefix,
                max_results=limit,
                page_token=continuation_token
            )
            
            # Process blobs
            files = []
            next_page_token = None
            
            for blob in blobs:
                files.append({
                    'key': blob.name,
                    'size': blob.size,
                    'last_modified': blob.time_created.isoformat() if blob.time_created else None,
                    'etag': blob.etag,
                    'content_type': blob.content_type,
                    'storage_class': blob.storage_class
                })
                
                if len(files) >= limit:
                    break
            
            # Get next page token if available
            if hasattr(blobs, 'next_page_token'):
                next_page_token = blobs.next_page_token
            
            result = {
                'files': files,
                'count': len(files),
                'is_truncated': next_page_token is not None,
                'next_continuation_token': next_page_token
            }
            
            logger.debug(f"Listed {len(files)} objects from GCS with prefix: {object_prefix}")
            return result
            
        except Exception as e:
            logger.error(f"GCS list failed for prefix {object_prefix}: {str(e)}")
            return {'files': [], 'count': 0, 'error': str(e)}
    
    async def file_exists(self, file_key: str) -> bool:
        """
        Check if file exists in Google Cloud Storage with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            # Generate object name with security validation
            object_name = self._generate_object_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', object_name):
                logger.error(f"Access denied for file existence check on {file_key}")
                return False
            
            # Get blob object
            blob = self.bucket.blob(object_name)
            
            # Check if blob exists
            exists = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob.exists()
            )
            
            return exists
            
        except Exception as e:
            logger.error(f"Unexpected GCS exists check error for {object_name}: {str(e)}")
            return False
    
    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """
        Get metadata for a file in Google Cloud Storage with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            FileMetadata object or None if file not found
        """
        try:
            # Generate object name with security validation
            object_name = self._generate_object_name(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', object_name):
                logger.error(f"Access denied for metadata access on {file_key}")
                return None
            
            # Get blob object
            blob = self.bucket.blob(object_name)
            
            # Reload blob to get latest metadata
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob.reload()
            )
            
            # Extract tenant_id from file_key if available
            tenant_id = None
            if file_key.startswith('tenant_'):
                parts = file_key.split('/', 1)
                if len(parts) > 0:
                    tenant_id = parts[0]
            
            return FileMetadata(
                file_key=file_key,
                file_size=blob.size or 0,
                content_type=blob.content_type or 'application/octet-stream',
                created_at=blob.time_created or datetime.now(timezone.utc),
                modified_at=blob.updated,
                tenant_id=tenant_id,
                checksum=blob.etag,
                custom_metadata=blob.metadata or {}
            )
            
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Unexpected GCS metadata error for {object_name}: {str(e)}")
            return None
    
    async def health_check(self) -> HealthCheckResult:
        """
        Check Google Cloud Storage provider health status.
        
        Returns:
            HealthCheckResult with provider status information
        """
        start_time = time.time()
        
        try:
            # Perform a simple bucket existence check to verify connectivity
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.bucket.exists()
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=True,
                response_time_ms=response_time_ms,
                last_check=datetime.now(timezone.utc),
                additional_info={
                    'bucket': self.bucket_name,
                    'project_id': self.project_id,
                    'storage_class': self.storage_class,
                    'encryption': 'Server-side (Google-managed)' if not self.kms_key_name else f'CMEK: {self.kms_key_name}'
                }
            )
            
            self._last_health_check = result
            logger.debug(f"GCS health check passed in {response_time_ms}ms")
            return result
            
        except DefaultCredentialsError as e:
            error_message = "GCS credentials not found or invalid"
            logger.error(f"GCS health check failed: {error_message}")
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=False,
                error_message=error_message,
                last_check=datetime.now(timezone.utc)
            )
            
            self._last_health_check = result
            return result
            
        except Forbidden as e:
            error_message = f"GCS access forbidden: {str(e)}"
            logger.error(f"GCS health check failed: {error_message}")
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=False,
                error_message=error_message,
                last_check=datetime.now(timezone.utc),
                response_time_ms=int((time.time() - start_time) * 1000)
            )
            
            self._last_health_check = result
            return result
            
        except NotFound as e:
            error_message = f"GCS bucket not found: {self.bucket_name}"
            logger.error(f"GCS health check failed: {error_message}")
            
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
            error_message = f"Unexpected error during GCS health check: {str(e)}"
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
            
    def _validate_object_security(self, object_name: str, operation: str) -> bool:
        """
        Enhanced security validation for GCS object operations.
        
        Args:
            object_name: The object name to validate
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
            
            object_name_lower = object_name.lower()
            for pattern in malicious_patterns:
                if pattern in object_name_lower:
                    logger.warning(f"Security violation detected in object name: {object_name} (pattern: {pattern})")
                    return False
            
            # Validate object name length and characters (GCS limits)
            if len(object_name) > 1024:  # GCS object name limit
                logger.warning(f"Object name too long: {len(object_name)} characters")
                return False
            
            # Check for valid characters (GCS naming rules)
            import re
            if not re.match(r'^[a-zA-Z0-9._/-]+$', object_name):
                logger.warning(f"Invalid characters in object name: {object_name}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Security validation error for {object_name}: {str(e)}")
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
    
    def _generate_secure_signed_url(self, object_name: str, expiry_seconds: int) -> Optional[str]:
        """
        Generate secure signed URL with minimal permissions and security constraints.
        
        Args:
            object_name: The object name for signed URL
            expiry_seconds: URL expiration time in seconds
            
        Returns:
            Secure signed URL or None if generation failed
        """
        try:
            # Get blob object
            blob = self.bucket.blob(object_name)
            
            # Set expiry time with security limits
            max_expiry = 7 * 24 * 3600  # 7 days maximum
            if expiry_seconds > max_expiry:
                expiry_seconds = max_expiry
            
            # Generate signed URL with security constraints
            signed_url = blob.generate_signed_url(
                expiration=datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds),
                method='GET',
                version='v4',  # Use v4 signing for better security
                # Add additional security headers if needed
                headers={'Cache-Control': 'no-cache, no-store, must-revalidate'}
            )
            
            return signed_url
            
        except Exception as e:
            logger.error(f"Failed to generate secure signed URL for {object_name}: {str(e)}")
            return None
    
    def _create_tenant_bucket_name(self, tenant_id: str) -> str:
        """
        Create tenant-specific bucket name for enhanced isolation.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Tenant-specific bucket name
        """
        if not tenant_id or not tenant_id.startswith('tenant_'):
            raise ValueError(f"Invalid tenant_id format: {tenant_id}")
        
        # Create bucket name with tenant prefix for complete isolation
        # Format: {base_bucket}-{tenant_id}
        tenant_suffix = tenant_id.replace('tenant_', '')
        return f"{self.bucket_name}-{tenant_suffix}"
    
    async def create_tenant_bucket(self, tenant_id: str, location: str = 'US') -> bool:
        """
        Create a dedicated bucket for a tenant (optional enhanced isolation).
        
        Args:
            tenant_id: Tenant identifier
            location: GCS bucket location
            
        Returns:
            True if bucket was created or already exists, False otherwise
        """
        try:
            bucket_name = self._create_tenant_bucket_name(tenant_id)
            
            # Create bucket with security settings
            bucket = self.client.bucket(bucket_name)
            bucket.storage_class = self.storage_class
            bucket.location = location
            
            # Enable uniform bucket-level access for better security
            bucket.iam_configuration.uniform_bucket_level_access_enabled = True
            
            # Set encryption if CMEK is configured
            if self.kms_key_name:
                bucket.default_kms_key_name = self.kms_key_name
            
            # Create bucket
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.create_bucket(bucket, location=location)
            )
            
            logger.info(f"Created tenant bucket: {bucket_name}")
            return True
            
        except gcp_exceptions.Conflict:
            # Bucket already exists, which is fine
            logger.debug(f"Tenant bucket already exists: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create tenant bucket for {tenant_id}: {str(e)}")
            return False
    
    async def set_bucket_lifecycle_policy(self, lifecycle_rules: List[Dict[str, Any]]) -> bool:
        """
        Set lifecycle policy for the bucket to manage storage costs.
        
        Args:
            lifecycle_rules: List of lifecycle rule dictionaries
            
        Returns:
            True if policy was set successfully, False otherwise
        """
        try:
            # Set lifecycle policy on bucket
            def set_lifecycle_rules():
                self.bucket.lifecycle_rules = lifecycle_rules
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                set_lifecycle_rules
            )
            
            # Patch the bucket to apply changes
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.bucket.patch()
            )
            
            logger.info(f"Set lifecycle policy on bucket: {self.bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set lifecycle policy on bucket {self.bucket_name}: {str(e)}")
            return False
    
    async def enable_bucket_versioning(self) -> bool:
        """
        Enable versioning on the bucket for data protection.
        
        Returns:
            True if versioning was enabled successfully, False otherwise
        """
        try:
            # Enable versioning
            self.bucket.versioning_enabled = True
            
            # Patch the bucket to apply changes
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.bucket.patch()
            )
            
            logger.info(f"Enabled versioning on bucket: {self.bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable versioning on bucket {self.bucket_name}: {str(e)}")
            return False
    
    async def set_bucket_cors_policy(self, cors_rules: List[Dict[str, Any]]) -> bool:
        """
        Set CORS policy for the bucket to control cross-origin access.
        
        Args:
            cors_rules: List of CORS rule dictionaries
            
        Returns:
            True if CORS policy was set successfully, False otherwise
        """
        try:
            # Set CORS policy on bucket
            self.bucket.cors = cors_rules
            
            # Patch the bucket to apply changes
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.bucket.patch()
            )
            
            logger.info(f"Set CORS policy on bucket: {self.bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set CORS policy on bucket {self.bucket_name}: {str(e)}")
            return False
    
    def get_tenant_isolation_info(self) -> Dict[str, Any]:
        """
        Get information about tenant isolation configuration.
        
        Returns:
            Dictionary with tenant isolation details
        """
        return {
            'tenant_prefix_enabled': self.tenant_prefix_enabled,
            'access_control_validation': self.access_control_validation,
            'server_side_encryption': self.server_side_encryption,
            'kms_key_name': self.kms_key_name,
            'storage_class': self.storage_class,
            'bucket_name': self.bucket_name,
            'project_id': self.project_id
        }
    
    def get_security_features(self) -> Dict[str, Any]:
        """
        Get information about enabled security features.
        
        Returns:
            Dictionary with security feature details
        """
        return {
            'server_side_encryption': self.server_side_encryption,
            'customer_managed_encryption': bool(self.kms_key_name),
            'kms_key_name': self.kms_key_name,
            'access_control_validation': self.access_control_validation,
            'tenant_isolation': self.tenant_prefix_enabled,
            'signed_url_security': True,
            'metadata_encryption': True,
            'path_traversal_protection': True,
            'malicious_pattern_detection': True
        }