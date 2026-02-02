"""
AWS S3 storage provider implementation.

This module implements the CloudStorageProvider interface for AWS S3,
providing secure file storage with tenant isolation, server-side encryption,
and comprehensive error handling.
"""

import asyncio
import logging
import mimetypes
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from botocore.client import BaseClient

from core.interfaces.storage_provider import (
    CloudStorageProvider, 
    StorageResult, 
    StorageConfig, 
    StorageProvider,
    FileMetadata,
    HealthCheckResult
)

logger = logging.getLogger(__name__)


class AWSS3Provider(CloudStorageProvider):
    """
    AWS S3 storage provider implementation with tenant isolation and security features.
    
    Features:
    - Server-side encryption (AES256)
    - Tenant-specific key prefixes for isolation
    - Connection pooling and adaptive retry
    - Presigned URL generation with configurable expiry
    - Comprehensive error handling and logging
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize AWS S3 provider with configuration.
        
        Args:
            config: StorageConfig with S3-specific settings
        """
        super().__init__(config)
        
        # Extract S3-specific configuration
        s3_config = config.config
        self.bucket_name = s3_config.get('bucket_name')
        self.region = s3_config.get('region', 'us-east-1')
        self.access_key_id = s3_config.get('access_key_id')
        self.secret_access_key = s3_config.get('secret_access_key')
        self.server_side_encryption = s3_config.get('server_side_encryption', 'AES256')
        self.tenant_prefix_enabled = s3_config.get('tenant_prefix_enabled', True)
        self.kms_key_id = s3_config.get('kms_key_id')  # For KMS encryption
        self.storage_class = s3_config.get('storage_class', 'STANDARD')
        self.endpoint_url = s3_config.get('endpoint_url')  # For S3-compatible services
        self.use_ssl = s3_config.get('use_ssl', True)
        
        # Security settings
        self.enforce_ssl = s3_config.get('enforce_ssl', True)
        self.validate_checksums = s3_config.get('validate_checksums', True)
        self.access_control_validation = s3_config.get('access_control_validation', True)
        
        # Validate required configuration
        if not self.bucket_name:
            raise ValueError("S3 bucket_name is required in configuration")
        
        # Validate security settings
        if self.server_side_encryption not in ['AES256', 'aws:kms']:
            raise ValueError(f"Invalid server_side_encryption: {self.server_side_encryption}")
        
        if self.server_side_encryption == 'aws:kms' and not self.kms_key_id:
            logger.warning("KMS encryption enabled but no KMS key ID provided, using default key")
        
        # Initialize S3 client with optimized configuration
        self._init_s3_client()
        
        logger.info(f"Initialized AWS S3 provider for bucket: {self.bucket_name} with encryption: {self.server_side_encryption}")
    
    def _validate_access_permissions(self, operation: str, file_key: str) -> bool:
        """
        Validate IAM-based access control for S3 operations.
        
        Args:
            operation: The operation being performed (read, write, delete)
            file_key: The S3 key being accessed
            
        Returns:
            True if access is allowed, False otherwise
        """
        if not self.access_control_validation:
            return True
        
        try:
            # Extract tenant from file key for validation
            if self.tenant_prefix_enabled and file_key.startswith('tenant_'):
                tenant_id = file_key.split('/')[0]
                
                # Validate that the current context has access to this tenant
                # This would integrate with your existing tenant context system
                # For now, we'll do basic validation
                if not tenant_id.startswith('tenant_') or not tenant_id.replace('tenant_', '').isdigit():
                    logger.warning(f"Invalid tenant format in file key: {file_key}")
                    return False
            
            # Additional IAM validation could be added here
            # For example, checking specific IAM policies or roles
            
            return True
            
        except Exception as e:
            logger.error(f"Access control validation failed for {operation} on {file_key}: {str(e)}")
            return False
    
    def _init_s3_client(self) -> None:
        """Initialize S3 client with connection pooling and retry configuration."""
        try:
            # Configure boto3 with connection pooling and adaptive retry
            boto_config = Config(
                region_name=self.region,
                max_pool_connections=20,
                retries={
                    'max_attempts': self.config.max_retry_attempts,
                    'mode': 'adaptive'
                },
                connect_timeout=self.config.timeout_seconds,
                read_timeout=self.config.timeout_seconds
            )
            
            # Create session with credentials if provided
            if self.access_key_id and self.secret_access_key:
                session = boto3.Session(
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=self.region
                )
                self.s3_client = session.client('s3', config=boto_config)
            else:
                # Use default credential chain (IAM roles, environment variables, etc.)
                self.s3_client = boto3.client('s3', config=boto_config)
                
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def _generate_s3_key(self, file_key: str, tenant_id: Optional[str] = None) -> str:
        """
        Generate S3 object key with tenant isolation and security validation.
        
        Args:
            file_key: Original file key
            tenant_id: Tenant ID for isolation (extracted from file_key if not provided)
            
        Returns:
            S3 object key with tenant prefix
            
        Raises:
            ValueError: If file_key contains invalid characters or path traversal attempts
        """
        # Security validation: prevent path traversal attacks
        if '..' in file_key or file_key.startswith('/') or '\\' in file_key:
            raise ValueError(f"Invalid file key contains path traversal or invalid characters: {file_key}")
        
        # Sanitize file key - remove any potentially dangerous characters
        sanitized_key = file_key.replace('\\', '/').strip('/')
        
        if not self.tenant_prefix_enabled:
            return sanitized_key
        
        # Extract tenant_id from file_key if not provided (format: tenant_X/...)
        if not tenant_id and sanitized_key.startswith('tenant_'):
            parts = sanitized_key.split('/', 1)
            if len(parts) > 1:
                tenant_id = parts[0]
        
        # Ensure tenant isolation by prefixing with tenant_id
        if tenant_id:
            # Validate tenant_id format for security
            if not tenant_id.startswith('tenant_') or not tenant_id.replace('tenant_', '').isdigit():
                raise ValueError(f"Invalid tenant_id format: {tenant_id}")
            
            if not sanitized_key.startswith(f"{tenant_id}/"):
                return f"{tenant_id}/{sanitized_key}"
        
        return sanitized_key
    
    def _get_upload_args(self, content_type: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get S3 upload arguments with encryption, security, and metadata.
        
        Args:
            content_type: MIME type of the file
            metadata: Optional metadata to store with the file
            
        Returns:
            Dictionary of S3 upload arguments
        """
        extra_args = {
            'ContentType': content_type,
            'ServerSideEncryption': self.server_side_encryption,
            'StorageClass': self.storage_class
        }
        
        # Add KMS key if using KMS encryption
        if self.server_side_encryption == 'aws:kms' and self.kms_key_id:
            extra_args['SSEKMSKeyId'] = self.kms_key_id
        
        # Add security headers
        if self.enforce_ssl:
            extra_args['BucketKeyEnabled'] = True  # Reduce KMS costs
        
        # Add custom metadata if provided
        if metadata:
            # S3 metadata keys must be strings and values must be strings
            # Also sanitize metadata to prevent injection attacks
            s3_metadata = {}
            for key, value in metadata.items():
                if isinstance(key, str) and value is not None:
                    # Sanitize metadata key and value
                    clean_key = key.replace('\n', '').replace('\r', '').strip()
                    clean_value = str(value).replace('\n', '').replace('\r', '').strip()
                    
                    # Limit metadata key/value length for security
                    if len(clean_key) <= 256 and len(clean_value) <= 2048:
                        s3_metadata[clean_key] = clean_value
            
            if s3_metadata:
                extra_args['Metadata'] = s3_metadata
        
        return extra_args
    
    async def upload_file(
        self, 
        file_content: bytes, 
        file_key: str, 
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Upload file to S3 bucket with encryption, security validation, and tenant isolation.
        
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
            # Generate S3 key with security validation
            s3_key = self._generate_s3_key(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('write', s3_key):
                return StorageResult(
                    success=False,
                    error_message=f"Access denied for upload operation on {file_key}",
                    provider=self.provider_type.value,
                    operation_duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Prepare upload arguments with security settings
            extra_args = self._get_upload_args(content_type, metadata)
            
            # Upload file to S3
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=file_content,
                    **extra_args
                )
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Successfully uploaded file to S3: {s3_key} ({len(file_content)} bytes)")
            
            return StorageResult(
                success=True,
                file_key=file_key,
                file_url=f"s3://{self.bucket_name}/{s3_key}",  # Indicate this is a cloud storage file
                file_size=len(file_content),
                content_type=content_type,
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms,
                metadata=metadata
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = f"S3 upload failed ({error_code}): {str(e)}"
            logger.error(f"S3 upload failed for {s3_key}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            error_message = f"Unexpected error during S3 upload: {str(e)}"
            logger.error(f"Unexpected S3 upload error for {s3_key}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
    
    async def download_file(self, file_key: str) -> StorageResult:
        """
        Download file from S3 bucket with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            StorageResult with file content or download URL
        """
        start_time = time.time()
        
        try:
            # Generate S3 key with security validation
            s3_key = self._generate_s3_key(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', s3_key):
                return StorageResult(
                    success=False,
                    error_message=f"Access denied for download operation on {file_key}",
                    provider=self.provider_type.value,
                    operation_duration_ms=int((time.time() - start_time) * 1000)
                )
            # Get object from S3
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
            )
            
            # Read file content
            file_content = response['Body'].read()
            content_type = response.get('ContentType', 'application/octet-stream')
            file_size = response.get('ContentLength', len(file_content))
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Successfully downloaded file from S3: {s3_key} ({file_size} bytes)")
            
            return StorageResult(
                success=True,
                file_key=file_key,
                file_size=file_size,
                content_type=content_type,
                file_content=file_content,  # Store in dedicated field for sync
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey':
                error_message = f"File not found in S3: {file_key}"
            else:
                error_message = f"S3 download failed ({error_code}): {str(e)}"
            
            logger.error(f"S3 download failed for {s3_key}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            error_message = f"Unexpected error during S3 download: {str(e)}"
            logger.error(f"Unexpected S3 download error for {s3_key}: {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value,
                operation_duration_ms=int((time.time() - start_time) * 1000)
            )
    
    async def delete_file(self, file_key: str) -> bool:
        """
        Delete file from S3 bucket with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            # Generate S3 key with security validation
            s3_key = self._generate_s3_key(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('delete', s3_key):
                logger.error(f"Access denied for delete operation on {file_key}")
                return False
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
            )
            
            logger.info(f"Successfully deleted file from S3: {s3_key}")
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"S3 delete failed for {s3_key} ({error_code}): {str(e)}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected S3 delete error for {s3_key}: {str(e)}")
            return False
    
    async def get_file_url(
        self, 
        file_key: str, 
        expiry_seconds: int = 3600
    ) -> Optional[str]:
        """
        Generate presigned URL for S3 object with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            expiry_seconds: URL expiration time in seconds
            
        Returns:
            Presigned URL string or None if generation failed
        """
        try:
            # Generate S3 key with security validation
            s3_key = self._generate_s3_key(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', s3_key):
                logger.error(f"Access denied for URL generation on {file_key}")
                return None
            
            # Limit expiry time for security (max 7 days)
            max_expiry = 7 * 24 * 3600  # 7 days
            if expiry_seconds > max_expiry:
                logger.warning(f"Expiry time {expiry_seconds}s exceeds maximum {max_expiry}s, using maximum")
                expiry_seconds = max_expiry
            url = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': s3_key},
                    ExpiresIn=expiry_seconds
                )
            )
            
            logger.debug(f"Generated presigned URL for S3 object: {s3_key}")
            return url
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"Failed to generate presigned URL for {s3_key} ({error_code}): {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL for {s3_key}: {str(e)}")
            return None
    
    async def list_files(
        self, 
        prefix: str = "", 
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List files in S3 bucket with given prefix.
        
        Args:
            prefix: Prefix to filter files
            limit: Maximum number of files to return
            continuation_token: Token for pagination
            
        Returns:
            Dictionary with files list and pagination info
        """
        s3_prefix = self._generate_s3_key(prefix) if prefix else ""
        
        try:
            # Prepare list_objects_v2 parameters
            params = {
                'Bucket': self.bucket_name,
                'MaxKeys': limit
            }
            
            if s3_prefix:
                params['Prefix'] = s3_prefix
            
            if continuation_token:
                params['ContinuationToken'] = continuation_token
            
            # List objects in S3
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.list_objects_v2(**params)
            )
            
            # Process response
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag'].strip('"')
                })
            
            result = {
                'files': files,
                'count': len(files),
                'is_truncated': response.get('IsTruncated', False),
                'next_continuation_token': response.get('NextContinuationToken')
            }
            
            logger.debug(f"Listed {len(files)} files from S3 with prefix: {s3_prefix}")
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"S3 list failed for prefix {s3_prefix} ({error_code}): {str(e)}")
            return {'files': [], 'count': 0, 'error': str(e)}
            
        except Exception as e:
            logger.error(f"Unexpected S3 list error for prefix {s3_prefix}: {str(e)}")
            return {'files': [], 'count': 0, 'error': str(e)}
    
    async def file_exists(self, file_key: str) -> bool:
        """
        Check if file exists in S3 bucket with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            # Generate S3 key with security validation
            s3_key = self._generate_s3_key(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', s3_key):
                logger.error(f"Access denied for file existence check on {file_key}")
                return False
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
            )
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey' or error_code == '404':
                return False
            else:
                logger.error(f"S3 head_object failed for {s3_key} ({error_code}): {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected S3 head_object error for {s3_key}: {str(e)}")
            return False
    
    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """
        Get metadata for a file in S3 with security validation.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            FileMetadata object or None if file not found
        """
        try:
            # Generate S3 key with security validation
            s3_key = self._generate_s3_key(file_key)
            
            # Validate access permissions
            if not self._validate_access_permissions('read', s3_key):
                logger.error(f"Access denied for metadata access on {file_key}")
                return None
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
            )
            
            # Extract tenant_id from file_key if available
            tenant_id = None
            if file_key.startswith('tenant_'):
                parts = file_key.split('/', 1)
                if len(parts) > 0:
                    tenant_id = parts[0]
            
            return FileMetadata(
                file_key=file_key,
                file_size=response.get('ContentLength', 0),
                content_type=response.get('ContentType', 'application/octet-stream'),
                created_at=response.get('LastModified', datetime.now(timezone.utc)),
                modified_at=response.get('LastModified'),
                tenant_id=tenant_id,
                checksum=response.get('ETag', '').strip('"'),
                custom_metadata=response.get('Metadata', {})
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey' or error_code == '404':
                return None
            else:
                logger.error(f"S3 head_object failed for {s3_key} ({error_code}): {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected S3 head_object error for {s3_key}: {str(e)}")
            return None
    
    async def health_check(self) -> HealthCheckResult:
        """
        Check S3 provider health status.
        
        Returns:
            HealthCheckResult with provider status information
        """
        start_time = time.time()
        
        try:
            # Perform a simple head_bucket operation to check connectivity
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.head_bucket(Bucket=self.bucket_name)
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=True,
                response_time_ms=response_time_ms,
                last_check=datetime.now(timezone.utc),
                additional_info={
                    'bucket': self.bucket_name,
                    'region': self.region,
                    'encryption': self.server_side_encryption
                }
            )
            
            self._last_health_check = result
            logger.debug(f"S3 health check passed in {response_time_ms}ms")
            return result
            
        except NoCredentialsError as e:
            error_message = "AWS credentials not found or invalid"
            logger.error(f"S3 health check failed: {error_message}")
            
            result = HealthCheckResult(
                provider=self.provider_type,
                healthy=False,
                error_message=error_message,
                last_check=datetime.now(timezone.utc)
            )
            
            self._last_health_check = result
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = f"S3 health check failed ({error_code}): {str(e)}"
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
            
        except Exception as e:
            error_message = f"Unexpected error during S3 health check: {str(e)}"
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

    async def delete_folder(self, folder_prefix: str) -> bool:
        """
        Delete all objects with a given prefix (folder) from AWS S3.
        
        Args:
            folder_prefix: Folder prefix (e.g., "exported/job-id/")
            
        Returns:
            True if folder was deleted successfully, False otherwise
        """
        try:
            # Generate S3 key with security validation
            s3_prefix = self._generate_s3_key(folder_prefix)
            
            logger.info(f"Deleting folder from S3: {s3_prefix}")
            
            # List all objects with the prefix using paginator
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_prefix)
            
            deleted_count = 0
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                # Delete objects in batches (S3 allows up to 1000 objects per request)
                objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                if objects_to_delete:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.s3_client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': objects_to_delete}
                        )
                    )
                    deleted_count += len(objects_to_delete)
                    logger.debug(f"Deleted batch of {len(objects_to_delete)} objects from {s3_prefix}")
            
            logger.info(f"Successfully deleted {deleted_count} objects from folder {s3_prefix}")
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete folder {folder_prefix} from S3: {e}", exc_info=True)
            return False
