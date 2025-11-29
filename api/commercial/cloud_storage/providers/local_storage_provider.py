"""
Local file storage provider implementation.

This provider implements the CloudStorageProvider interface for local file storage,
maintaining compatibility with the existing FileStorageService while providing
the unified cloud storage interface.
"""

import os
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import hashlib
import asyncio

from core.interfaces.storage_provider import (
    CloudStorageProvider, 
    StorageResult, 
    StorageConfig, 
    StorageProvider,
    FileMetadata,
    HealthCheckResult
)
from config import config as app_config
from core.utils.file_validation import validate_file_path

logger = logging.getLogger(__name__)


class LocalStorageProvider(CloudStorageProvider):
    """
    Local file storage provider that implements the CloudStorageProvider interface.
    
    This provider maintains compatibility with the existing file storage system
    while providing the unified cloud storage interface for seamless integration
    with the cloud storage abstraction layer.
    """
    
    def __init__(self, storage_config: StorageConfig):
        """Initialize the local storage provider."""
        super().__init__(storage_config)
        
        # Get configuration from storage config or fall back to global config
        provider_config = storage_config.config or {}
        self.base_path = Path(provider_config.get('base_path', app_config.UPLOAD_PATH))
        self.max_file_size = provider_config.get('max_file_size', app_config.MAX_UPLOAD_SIZE)
        self.api_base_url = provider_config.get('api_base_url', 'http://localhost:8000/api/v1')
        
        # Ensure base directory exists
        self._ensure_base_directory()
        
        logger.info(f"Initialized LocalStorageProvider with base_path: {self.base_path}")
    
    def _ensure_base_directory(self) -> None:
        """Ensure the base attachments directory exists."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured base directory exists: {self.base_path}")
        except Exception as e:
            logger.error(f"Failed to create base directory {self.base_path}: {e}")
            raise
    
    def _generate_file_key(
        self, 
        tenant_id: str, 
        item_id: int, 
        attachment_type: str, 
        filename: str
    ) -> str:
        """
        Generate a file key that matches the existing storage structure.
        
        Args:
            tenant_id: Tenant identifier
            item_id: Item ID (invoice, expense, etc.)
            attachment_type: Type of attachment (images, documents, etc.)
            filename: Original filename
            
        Returns:
            File key in the format: tenant_X/attachment_type/filename
        """
        return f"tenant_{tenant_id}/{attachment_type}/{filename}"
    
    def _get_file_path_from_key(self, file_key: str) -> Path:
        """
        Convert file key to full file path.
        
        Args:
            file_key: File key in cloud storage format
            
        Returns:
            Full path to the file
        """
        return self.base_path / file_key
    
    def _generate_file_url(self, file_key: str) -> str:
        """
        Generate a URL for accessing the file through the API.
        
        Args:
            file_key: File key in cloud storage format
            
        Returns:
            URL for accessing the file
        """
        # Create a URL that can be handled by a file serving endpoint
        # The URL format: /api/v1/files/serve/{encoded_file_key}
        import urllib.parse
        encoded_key = urllib.parse.quote(file_key, safe='')
        return f"{self.api_base_url}/files/serve/{encoded_key}"
    
    async def upload_file(
        self, 
        file_content: bytes, 
        file_key: str, 
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Upload file to local storage.
        
        Args:
            file_content: The file content as bytes
            file_key: Unique key/path for the file in storage
            content_type: MIME type of the file
            metadata: Optional metadata to store with the file
            
        Returns:
            StorageResult with operation details
        """
        start_time = datetime.now()
        
        try:
            # Validate file size
            if len(file_content) > self.max_file_size:
                return StorageResult(
                    success=False,
                    error_message=f"File size {len(file_content)} exceeds maximum {self.max_file_size}",
                    provider=self.provider_type.value
                )
            
            # Get full file path
            file_path = self._get_file_path_from_key(file_key)
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file to disk
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Calculate operation duration
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Generate file URL
            file_url = self._generate_file_url(file_key)
            
            logger.info(f"Successfully uploaded file to local storage: {file_key}")
            
            return StorageResult(
                success=True,
                file_url=file_url,
                file_key=file_key,
                file_size=len(file_content),
                content_type=content_type,
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms,
                metadata=metadata
            )
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Failed to upload file {file_key} to local storage: {e}")
            
            return StorageResult(
                success=False,
                error_message=f"Failed to upload file: {str(e)}",
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms
            )
    
    async def download_file(self, file_key: str) -> StorageResult:
        """
        Download file from local storage.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            StorageResult with file content or download URL
        """
        start_time = datetime.now()
        
        try:
            file_path = self._get_file_path_from_key(file_key)
            
            if not file_path.exists():
                return StorageResult(
                    success=False,
                    error_message=f"File not found: {file_key}",
                    provider=self.provider_type.value
                )
            
            # For local storage, we return the URL instead of file content
            # to maintain consistency with cloud providers
            file_url = self._generate_file_url(file_key)
            
            # Get file metadata
            stat = file_path.stat()
            content_type, _ = mimetypes.guess_type(str(file_path))
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return StorageResult(
                success=True,
                file_url=file_url,
                file_key=file_key,
                file_size=stat.st_size,
                content_type=content_type,
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Failed to download file {file_key} from local storage: {e}")
            
            return StorageResult(
                success=False,
                error_message=f"Failed to download file: {str(e)}",
                provider=self.provider_type.value,
                operation_duration_ms=duration_ms
            )
    
    async def delete_file(self, file_key: str) -> bool:
        """
        Delete file from local storage.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            file_path = self._get_file_path_from_key(file_key)
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Successfully deleted file from local storage: {file_key}")
                return True
            else:
                logger.warning(f"File not found for deletion: {file_key}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete file {file_key} from local storage: {e}")
            return False
    
    async def get_file_url(
        self, 
        file_key: str, 
        expiry_seconds: int = 3600
    ) -> Optional[str]:
        """
        Generate temporary access URL for file.
        
        For local storage, we don't implement expiry but return a URL
        that can be used to access the file through the API.
        
        Args:
            file_key: Unique key/path for the file in storage
            expiry_seconds: URL expiration time (ignored for local storage)
            
        Returns:
            URL string or None if file doesn't exist
        """
        try:
            file_path = self._get_file_path_from_key(file_key)
            
            if not file_path.exists():
                return None
            
            return self._generate_file_url(file_key)
            
        except Exception as e:
            logger.error(f"Failed to generate URL for file {file_key}: {e}")
            return None
    
    async def list_files(
        self, 
        prefix: str = "", 
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List files with given prefix.
        
        Args:
            prefix: Prefix to filter files (e.g., "tenant_1/images/")
            limit: Maximum number of files to return
            continuation_token: Token for pagination (not implemented for local)
            
        Returns:
            Dictionary with files list and pagination info
        """
        try:
            files = []
            search_path = self.base_path
            
            if prefix:
                search_path = self.base_path / prefix
            
            if not search_path.exists():
                return {
                    'files': [],
                    'count': 0,
                    'has_more': False,
                    'continuation_token': None
                }
            
            # Walk through directory structure
            for root, dirs, filenames in os.walk(search_path):
                for filename in filenames:
                    file_path = Path(root) / filename
                    
                    # Generate file key relative to base path
                    try:
                        relative_path = file_path.relative_to(self.base_path)
                        file_key = str(relative_path).replace('\\', '/')
                        
                        # Apply prefix filter
                        if prefix and not file_key.startswith(prefix):
                            continue
                        
                        # Get file metadata
                        stat = file_path.stat()
                        content_type, _ = mimetypes.guess_type(str(file_path))
                        
                        files.append({
                            'key': file_key,
                            'size': stat.st_size,
                            'content_type': content_type,
                            'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'url': self._generate_file_url(file_key)
                        })
                        
                        # Apply limit
                        if len(files) >= limit:
                            break
                            
                    except ValueError:
                        # Skip files outside base path
                        continue
                
                if len(files) >= limit:
                    break
            
            return {
                'files': files,
                'count': len(files),
                'has_more': False,  # Simple implementation without pagination
                'continuation_token': None
            }
            
        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return {
                'files': [],
                'count': 0,
                'has_more': False,
                'continuation_token': None,
                'error': str(e)
            }
    
    async def file_exists(self, file_key: str) -> bool:
        """
        Check if file exists in storage.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            file_path = self._get_file_path_from_key(file_key)
            return file_path.exists()
        except Exception as e:
            logger.error(f"Failed to check if file exists {file_key}: {e}")
            return False
    
    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """
        Get metadata for a file.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            FileMetadata object or None if file not found
        """
        try:
            file_path = self._get_file_path_from_key(file_key)
            
            if not file_path.exists():
                return None
            
            stat = file_path.stat()
            content_type, _ = mimetypes.guess_type(str(file_path))
            
            # Calculate file checksum
            with open(file_path, 'rb') as f:
                file_content = f.read()
                checksum = hashlib.sha256(file_content).hexdigest()
            
            # Extract tenant_id from file_key if possible
            tenant_id = None
            if file_key.startswith('tenant_'):
                parts = file_key.split('/')
                if len(parts) > 0:
                    tenant_part = parts[0]  # e.g., "tenant_1"
                    tenant_id = tenant_part.replace('tenant_', '')
            
            return FileMetadata(
                file_key=file_key,
                file_size=stat.st_size,
                content_type=content_type or 'application/octet-stream',
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                tenant_id=tenant_id,
                checksum=checksum
            )
            
        except Exception as e:
            logger.error(f"Failed to get metadata for file {file_key}: {e}")
            return None
    
    async def health_check(self) -> HealthCheckResult:
        """
        Check provider health status.
        
        Returns:
            HealthCheckResult with provider status information
        """
        start_time = datetime.now()
        
        try:
            # Check if base directory exists and is writable
            if not self.base_path.exists():
                return HealthCheckResult(
                    provider=self.provider_type,
                    healthy=False,
                    error_message=f"Base directory does not exist: {self.base_path}",
                    last_check=datetime.now()
                )
            
            # Test write access by creating a temporary file
            test_file = self.base_path / '.health_check_test'
            try:
                with open(test_file, 'w') as f:
                    f.write('health_check')
                test_file.unlink()  # Clean up
            except Exception as e:
                return HealthCheckResult(
                    provider=self.provider_type,
                    healthy=False,
                    error_message=f"Cannot write to base directory: {str(e)}",
                    last_check=datetime.now()
                )
            
            # Calculate response time
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Get storage statistics
            total_size = 0
            file_count = 0
            
            try:
                for root, dirs, files in os.walk(self.base_path):
                    for file in files:
                        file_path = Path(root) / file
                        try:
                            total_size += file_path.stat().st_size
                            file_count += 1
                        except:
                            pass  # Skip files we can't access
            except:
                pass  # Don't fail health check if we can't get stats
            
            self._last_health_check = HealthCheckResult(
                provider=self.provider_type,
                healthy=True,
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                additional_info={
                    'base_path': str(self.base_path),
                    'total_files': file_count,
                    'total_size_bytes': total_size,
                    'max_file_size': self.max_file_size
                }
            )
            
            return self._last_health_check
            
        except Exception as e:
            self._last_health_check = HealthCheckResult(
                provider=self.provider_type,
                healthy=False,
                error_message=f"Health check failed: {str(e)}",
                last_check=datetime.now()
            )
            
            return self._last_health_check