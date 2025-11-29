"""
File Storage Service for Inventory Attachments

Handles secure file storage, retrieval, and management for inventory attachments.
Provides tenant-scoped storage with proper security measures.

This service now implements the CloudStorageProvider interface for compatibility
with the unified cloud storage abstraction layer.
"""
import os
import uuid
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
import logging
from datetime import datetime

from config import config as app_config
from core.services.file_security_service import file_security_service
from core.utils.file_validation import validate_file_path

# Import cloud storage interfaces
from core.interfaces.storage_provider import (
    CloudStorageProvider, 
    StorageResult, 
    StorageConfig, 
    StorageProvider,
    FileMetadata,
    HealthCheckResult
)

logger = logging.getLogger(__name__)


@dataclass
class FileStorageResult:
    """Result of file storage operation"""
    success: bool
    stored_path: Optional[str] = None
    stored_filename: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    file_hash: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class FileInfo:
    """File information structure"""
    exists: bool
    size: Optional[int] = None
    content_type: Optional[str] = None
    modified_time: Optional[datetime] = None
    file_path: Optional[str] = None


class FileStorageService(CloudStorageProvider):
    """
    Service for secure file storage and retrieval operations.
    Handles tenant-scoped storage with proper security measures.
    
    Now implements CloudStorageProvider interface for compatibility with
    the unified cloud storage abstraction layer.
    """

    def __init__(self, storage_config: Optional[StorageConfig] = None):
        # Initialize CloudStorageProvider if config provided
        if storage_config:
            super().__init__(storage_config)
            provider_config = storage_config.config or {}
            self.base_path = Path(provider_config.get('base_path', app_config.UPLOAD_PATH))
            self.max_file_size = provider_config.get('max_file_size', app_config.MAX_UPLOAD_SIZE)
            self.api_base_url = provider_config.get('api_base_url', 'http://localhost:8000/api/v1')
        else:
            # Legacy initialization for backward compatibility
            self.base_path = Path(app_config.UPLOAD_PATH)
            self.max_file_size = app_config.MAX_UPLOAD_SIZE
            self.api_base_url = 'http://localhost:8000/api/v1'
            self.provider_type = StorageProvider.LOCAL
            self._last_health_check = None
        
        self.ensure_base_directory()

    def ensure_base_directory(self) -> None:
        """Ensure the base attachments directory exists"""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured base attachments directory: {self.base_path}")
        except Exception as e:
            logger.error(f"Failed to create base attachments directory: {e}")
            raise

    def get_storage_path(self, tenant_id: str, attachment_type: str) -> Path:
        """
        Get organized storage path: attachments/tenant_X/inventory/images|documents

        Args:
            tenant_id: Tenant identifier
            attachment_type: 'images' or 'documents'

        Returns:
            Path to the storage directory
        """
        path = self.base_path / f"tenant_{tenant_id}" / "inventory" / attachment_type
        path.mkdir(parents=True, exist_ok=True)
        return path

    def generate_secure_filename(self, original_filename: str, item_id: int) -> str:
        """
        Generate secure filename with UUID and sanitization

        Args:
            original_filename: Original uploaded filename
            item_id: Inventory item ID

        Returns:
            Secure filename
        """
        # Extract file extension
        file_ext = Path(original_filename).suffix.lower()

        # Generate secure components
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create secure filename: item_{item_id}_{timestamp}_{uuid}{ext}
        secure_filename = f"item_{item_id}_{timestamp}_{unique_id}{file_ext}"

        return secure_filename

    def validate_file_type(self, filename: str, allowed_types: list) -> Dict[str, Any]:
        """
        Enhanced file type validation with security checks

        Args:
            filename: Filename to validate
            allowed_types: List of allowed MIME types

        Returns:
            Dict with validation result and details
        """
        try:
            # Use security service for comprehensive validation
            # Since we don't have file content here, we'll do basic checks
            content_type, _ = mimetypes.guess_type(filename)

            if not content_type:
                return {
                    'valid': False,
                    'error': f"Could not determine MIME type for file: {filename}"
                }

            # Check if content type is in allowed types
            is_valid = content_type in allowed_types

            if not is_valid:
                return {
                    'valid': False,
                    'error': f"File type {content_type} not in allowed types {allowed_types}"
                }

            return {
                'valid': True,
                'mime_type': content_type,
                'extension': Path(filename).suffix.lower().lstrip('.')
            }

        except Exception as e:
            logger.error(f"File type validation error: {e}")
            return {
                'valid': False,
                'error': f"Validation error: {str(e)}"
            }

    def calculate_file_hash(self, file_content: bytes) -> str:
        """
        Calculate SHA-256 hash for deduplication

        Args:
            file_content: File content as bytes

        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(file_content).hexdigest()

    def validate_file_size(self, file_size: int) -> Dict[str, Any]:
        """
        Enhanced file size validation with detailed information

        Args:
            file_size: Size of file in bytes

        Returns:
            Dict with validation result and details
        """
        if file_size > self.max_file_size:
            return {
                'valid': False,
                'error': f"File size {file_size} bytes exceeds maximum {self.max_file_size} bytes",
                'file_size': file_size,
                'max_size': self.max_file_size,
                'overage': file_size - self.max_file_size
            }

        if file_size == 0:
            return {
                'valid': False,
                'error': "File is empty",
                'file_size': file_size
            }

        return {
            'valid': True,
            'file_size': file_size,
            'max_size': self.max_file_size,
            'usage_percentage': (file_size / self.max_file_size) * 100
        }

    async def store_file(
        self,
        file_content: bytes,
        tenant_id: str,
        item_id: int,
        attachment_type: str,
        original_filename: str
    ) -> FileStorageResult:
        """
        Store file securely with proper naming and organization

        Args:
            file_content: File content as bytes
            tenant_id: Tenant identifier
            item_id: Inventory item ID
            attachment_type: 'images' or 'documents'
            original_filename: Original filename

        Returns:
            FileStorageResult with operation details
        """
        try:
            # Enhanced file size validation
            size_validation = self.validate_file_size(len(file_content))
            if not size_validation['valid']:
                return FileStorageResult(
                    success=False,
                    error_message=size_validation['error']
                )

            # Enhanced file type validation
            allowed_types = self._get_allowed_types(attachment_type)
            type_validation = self.validate_file_type(original_filename, allowed_types)
            if not type_validation['valid']:
                return FileStorageResult(
                    success=False,
                    error_message=type_validation['error']
                )

            # Generate secure filename
            stored_filename = self.generate_secure_filename(original_filename, item_id)

            # Get storage path
            storage_path = self.get_storage_path(tenant_id, attachment_type)
            full_path = storage_path / stored_filename

            # Calculate file hash for deduplication
            file_hash = self.calculate_file_hash(file_content)

            # Write file to disk
            with open(full_path, 'wb') as f:
                f.write(file_content)

            # Determine content type
            content_type, _ = mimetypes.guess_type(original_filename)

            # Get file size
            file_size = len(file_content)

            logger.info(f"Successfully stored file: {full_path}")

            return FileStorageResult(
                success=True,
                stored_path=str(full_path),
                stored_filename=stored_filename,
                file_size=file_size,
                content_type=content_type,
                file_hash=file_hash
            )

        except Exception as e:
            logger.error(f"Failed to store file: {e}")
            return FileStorageResult(
                success=False,
                error_message=f"Failed to store file: {str(e)}"
            )

    async def delete_file(self, file_path: str) -> bool:
        """
        Delete file from storage

        Args:
            file_path: Path to file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Validate file path
            try:
                safe_path = validate_file_path(file_path)
            except ValueError as e:
                logger.error(f"Invalid file path: {e}")
                return False
            path = Path(safe_path)
            if path.exists():
                path.unlink()
                logger.info(f"Successfully deleted file: {file_path}")
                return True
            else:
                logger.warning(f"File not found for deletion: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    async def get_file_info(self, file_path: str) -> FileInfo:
        """
        Get file metadata and verify existence

        Args:
            file_path: Path to file

        Returns:
            FileInfo with file details
        """
        try:
            # Validate file path
            try:
                safe_path = validate_file_path(file_path)
            except ValueError as e:
                logger.error(f"Invalid file path: {e}")
                return FileInfo(exists=False)
            path = Path(safe_path)

            if not path.exists():
                return FileInfo(exists=False)

            stat = path.stat()

            # Get content type
            content_type, _ = mimetypes.guess_type(str(path))

            return FileInfo(
                exists=True,
                size=stat.st_size,
                content_type=content_type,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
                file_path=str(path)
            )

        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return FileInfo(exists=False)

    def _get_allowed_types(self, attachment_type: str) -> list:
        """
        Get allowed MIME types for attachment type

        Args:
            attachment_type: 'images' or 'documents'

        Returns:
            List of allowed MIME types
        """
        if attachment_type == 'images':
            return [
                'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
                'image/webp', 'image/bmp', 'image/tiff', 'image/svg+xml'
            ]
        elif attachment_type == 'documents':
            return [
                'application/pdf', 'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/plain', 'text/csv'
            ]
        else:
            return []

    def get_tenant_storage_usage(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get storage usage statistics for a tenant

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary with storage usage statistics
        """
        try:
            tenant_path = self.base_path / f"tenant_{tenant_id}"
            if not tenant_path.exists():
                return {
                    'total_files': 0,
                    'total_size': 0,
                    'images_count': 0,
                    'documents_count': 0,
                    'images_size': 0,
                    'documents_size': 0
                }

            total_files = 0
            total_size = 0
            images_count = 0
            documents_count = 0
            images_size = 0
            documents_size = 0

            # Walk through tenant directory
            for root, dirs, files in os.walk(tenant_path):
                for file in files:
                    file_path = Path(root) / file
                    try:
                        stat = file_path.stat()
                        total_files += 1
                        total_size += stat.st_size

                        # Determine if it's an image or document
                        content_type, _ = mimetypes.guess_type(str(file_path))
                        if content_type and content_type.startswith('image/'):
                            images_count += 1
                            images_size += stat.st_size
                        elif content_type:
                            documents_count += 1
                            documents_size += stat.st_size

                    except Exception as e:
                        logger.warning(f"Failed to get stats for {file_path}: {e}")

            return {
                'total_files': total_files,
                'total_size': total_size,
                'images_count': images_count,
                'documents_count': documents_count,
                'images_size': images_size,
                'documents_size': documents_size
            }

        except Exception as e:
            logger.error(f"Failed to get storage usage for tenant {tenant_id}: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'error': str(e)
            }

    # CloudStorageProvider interface methods
    
    def _generate_file_key(
        self, 
        tenant_id: str, 
        item_id: int, 
        attachment_type: str, 
        filename: str
    ) -> str:
        """Generate a file key that matches the existing storage structure."""
        return f"tenant_{tenant_id}/{attachment_type}/{filename}"
    
    def _get_file_path_from_key(self, file_key: str) -> Path:
        """Convert file key to full file path."""
        return self.base_path / file_key
    
    def _generate_file_url(self, file_key: str) -> str:
        """Generate a URL for accessing the file through the API."""
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
        Upload file using CloudStorageProvider interface.
        
        This method provides compatibility with the cloud storage abstraction layer
        while maintaining the existing file storage functionality.
        """
        start_time = datetime.now()
        
        try:
            # Validate file size
            if len(file_content) > self.max_file_size:
                return StorageResult(
                    success=False,
                    error_message=f"File size {len(file_content)} exceeds maximum {self.max_file_size}",
                    provider=self.provider_type.value if hasattr(self, 'provider_type') else 'local'
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
                provider=self.provider_type.value if hasattr(self, 'provider_type') else 'local',
                operation_duration_ms=duration_ms,
                metadata=metadata
            )
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Failed to upload file {file_key} to local storage: {e}")
            
            return StorageResult(
                success=False,
                error_message=f"Failed to upload file: {str(e)}",
                provider=self.provider_type.value if hasattr(self, 'provider_type') else 'local',
                operation_duration_ms=duration_ms
            )

    async def download_file(self, file_key: str) -> StorageResult:
        """Download file using CloudStorageProvider interface."""
        start_time = datetime.now()
        
        try:
            file_path = self._get_file_path_from_key(file_key)
            
            if not file_path.exists():
                return StorageResult(
                    success=False,
                    error_message=f"File not found: {file_key}",
                    provider=self.provider_type.value if hasattr(self, 'provider_type') else 'local'
                )
            
            # For local storage, we return the URL instead of file content
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
                provider=self.provider_type.value if hasattr(self, 'provider_type') else 'local',
                operation_duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Failed to download file {file_key} from local storage: {e}")
            
            return StorageResult(
                success=False,
                error_message=f"Failed to download file: {str(e)}",
                provider=self.provider_type.value if hasattr(self, 'provider_type') else 'local',
                operation_duration_ms=duration_ms
            )

    async def get_file_url(
        self, 
        file_key: str, 
        expiry_seconds: int = 3600
    ) -> Optional[str]:
        """Generate access URL for file."""
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
        """List files with given prefix."""
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
                'has_more': False,
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
        """Check if file exists in storage."""
        try:
            file_path = self._get_file_path_from_key(file_key)
            return file_path.exists()
        except Exception as e:
            logger.error(f"Failed to check if file exists {file_key}: {e}")
            return False

    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """Get metadata for a file."""
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
        """Check provider health status."""
        start_time = datetime.now()
        
        try:
            # Check if base directory exists and is writable
            if not self.base_path.exists():
                return HealthCheckResult(
                    provider=self.provider_type if hasattr(self, 'provider_type') else StorageProvider.LOCAL,
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
                    provider=self.provider_type if hasattr(self, 'provider_type') else StorageProvider.LOCAL,
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
            
            result = HealthCheckResult(
                provider=self.provider_type if hasattr(self, 'provider_type') else StorageProvider.LOCAL,
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
            
            if hasattr(self, '_last_health_check'):
                self._last_health_check = result
            
            return result
            
        except Exception as e:
            result = HealthCheckResult(
                provider=self.provider_type if hasattr(self, 'provider_type') else StorageProvider.LOCAL,
                healthy=False,
                error_message=f"Health check failed: {str(e)}",
                last_check=datetime.now()
            )
            
            if hasattr(self, '_last_health_check'):
                self._last_health_check = result
            
            return result


# Global instance
file_storage_service = FileStorageService()
