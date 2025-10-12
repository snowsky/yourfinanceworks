"""
File Storage Service for Inventory Attachments

Handles secure file storage, retrieval, and management for inventory attachments.
Provides tenant-scoped storage with proper security measures.
"""
import os
import uuid
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime

from config import config
from services.file_security_service import file_security_service

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


class FileStorageService:
    """
    Service for secure file storage and retrieval operations.
    Handles tenant-scoped storage with proper security measures.
    """

    def __init__(self):
        self.base_path = Path(config.UPLOAD_PATH)
        self.max_file_size = config.MAX_UPLOAD_SIZE
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
            path = Path(file_path)
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
            path = Path(file_path)

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


# Global instance
file_storage_service = FileStorageService()
