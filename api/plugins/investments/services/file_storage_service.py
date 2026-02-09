"""
File storage service for portfolio holdings import.

This service handles local and cloud file storage for uploaded holdings files (PDF and CSV).
Files are stored in tenant-scoped directories following the pattern established
by the bank statement import feature.

The service provides methods for:
- Saving files with unique filenames (local + cloud dual storage)
- Retrieving files from storage
- Deleting files from storage (local + cloud)
- Validating file type and size
- Cloud storage fallback to local storage on failure
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import logging
from sqlalchemy.orm import Session

from plugins.investments.models import FileType
from commercial.cloud_storage.service import CloudStorageService
from commercial.cloud_storage.config import get_cloud_storage_config

logger = logging.getLogger(__name__)


class FileStorageService:
    """
    Service for managing local and cloud file storage for portfolio holdings import.

    Implements dual storage pattern:
    - Local storage: attachments/tenant_{tenant_id}/holdings_files/
    - Cloud storage: tenant_{tenant_id}/holdings_files/ (with fallback to local on failure)

    Files are stored in tenant-scoped directories to ensure proper isolation.
    The service validates file types and sizes before storage.

    Storage structure:
        Local:
            attachments/
                tenant_{tenant_id}/
                    holdings_files/
                        hf_{portfolio_id}_{unique_id}.pdf
                        hf_{portfolio_id}_{unique_id}.csv

        Cloud:
            tenant_{tenant_id}/holdings_files/{stored_filename}
    """

    # Configuration constants
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
    ALLOWED_EXTENSIONS = {".pdf", ".csv"}
    BASE_STORAGE_DIR = Path("attachments")
    HOLDINGS_FILES_SUBDIR = "holdings_files"
    ATTACHMENT_TYPE = "holdings_files"

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the file storage service.

        Args:
            db: Optional database session for cloud storage service initialization
        """
        self.base_dir = self.BASE_STORAGE_DIR
        self.db = db
        self.cloud_storage_service: Optional[CloudStorageService] = None

        # Initialize cloud storage service if database session is provided
        if db:
            try:
                cloud_config = get_cloud_storage_config()
                self.cloud_storage_service = CloudStorageService(db, cloud_config)
                logger.info("Cloud storage service initialized for holdings import")
            except Exception as e:
                logger.warning(f"Failed to initialize cloud storage service: {e}. Falling back to local storage only.")

    async def save_file(
        self,
        file_content: bytes,
        original_filename: str,
        portfolio_id: int,
        tenant_id: int,
        file_type: FileType,
        user_id: int
    ) -> Tuple[str, str, Optional[str]]:
        """
        Save a file to local and cloud storage (dual storage pattern).

        Generates a unique filename in the format: hf_{portfolio_id}_{unique_id}.{ext}
        and stores it in:
        - Local: attachments/tenant_{tenant_id}/holdings_files/
        - Cloud: tenant_{tenant_id}/holdings_files/ (with fallback to local on failure)

        Args:
            file_content: The file content as bytes
            original_filename: The original filename for display purposes
            portfolio_id: The portfolio ID associated with the file
            tenant_id: The tenant ID for storage isolation
            file_type: The file type (PDF or CSV)
            user_id: The user ID who uploaded the file

        Returns:
            Tuple of (stored_filename, local_path, cloud_url)
            - stored_filename: The unique filename used for storage
            - local_path: The full path where the file was stored locally
            - cloud_url: The cloud storage URL (None if cloud storage failed or not configured)

        Raises:
            ValueError: If file type is invalid
            IOError: If file storage fails

        Requirements: 3.3, 3.4, 4.1, 4.2, 4.3, 18.1, 18.2, 18.3, 18.4, 18.5
        """
        # Validate file type
        if not isinstance(file_type, FileType):
            raise ValueError(f"Invalid file type: {file_type}")

        # Create tenant-scoped directory
        tenant_folder = f"tenant_{tenant_id}"
        storage_dir = self.base_dir / tenant_folder / self.HOLDINGS_FILES_SUBDIR

        try:
            storage_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create storage directory {storage_dir}: {e}")
            raise IOError(f"Failed to create storage directory: {e}")

        # Generate unique filename
        # Format: hf_{portfolio_id}_{unique_id}.{ext}
        unique_id = uuid.uuid4().hex[:8]
        ext = f".{file_type.value}"
        stored_filename = f"hf_{portfolio_id}_{unique_id}{ext}"

        # Full path for local storage
        file_path = storage_dir / stored_filename

        # Write file to local storage
        try:
            with open(file_path, "wb") as f:
                f.write(file_content)
            logger.info(f"File saved locally: {file_path}")
        except IOError as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            raise IOError(f"Failed to save file: {e}")

        # Attempt cloud storage upload with fallback
        cloud_url = None
        if self.cloud_storage_service:
            try:
                # Generate cloud storage key
                cloud_file_key = f"tenant_{tenant_id}/{self.HOLDINGS_FILES_SUBDIR}/{stored_filename}"

                # Prepare metadata
                metadata = {
                    "original_filename": original_filename,
                    "stored_filename": stored_filename,
                    "file_type": file_type.value,
                    "portfolio_id": str(portfolio_id),
                    "tenant_id": str(tenant_id),
                    "uploaded_at": str(Path(file_path).stat().st_mtime),
                    "file_size": len(file_content),
                    "document_type": "holdings_file",
                    "upload_method": "internal_api",
                }

                # Upload to cloud storage
                storage_result = await self.cloud_storage_service.store_file(
                    file_content=file_content,
                    tenant_id=str(tenant_id),
                    item_id=portfolio_id,
                    attachment_type=self.ATTACHMENT_TYPE,
                    original_filename=original_filename,
                    user_id=user_id,
                    metadata=metadata,
                    file_key=cloud_file_key
                )

                if storage_result.success:
                    cloud_url = storage_result.file_url
                    logger.info(f"File uploaded to cloud storage: {cloud_file_key} -> {cloud_url}")
                else:
                    logger.warning(f"Cloud storage upload failed: {storage_result.error_message}. Falling back to local storage.")

            except Exception as e:
                logger.warning(f"Cloud storage upload failed with exception: {e}. Falling back to local storage.")

        return stored_filename, str(file_path), cloud_url

    async def retrieve_file(
        self,
        stored_filename: str,
        tenant_id: int
    ) -> bytes:
        """
        Retrieve a file from local storage (or cloud if local fails).

        Attempts to retrieve from local storage first, then falls back to cloud storage
        if available and local retrieval fails.

        Args:
            stored_filename: The unique filename to retrieve
            tenant_id: The tenant ID for storage isolation

        Returns:
            The file content as bytes

        Raises:
            FileNotFoundError: If the file does not exist in either storage
            IOError: If file retrieval fails

        Requirements: 4.1, 4.2, 18.1, 18.2, 18.3, 18.4, 18.5
        """
        # Construct the local file path
        tenant_folder = f"tenant_{tenant_id}"
        file_path = self.base_dir / tenant_folder / self.HOLDINGS_FILES_SUBDIR / stored_filename

        # Try local storage first
        if file_path.exists():
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                logger.info(f"File retrieved from local storage: {file_path}")
                return content
            except IOError as e:
                logger.warning(f"Failed to read file from local storage {file_path}: {e}")
                # Fall through to cloud storage attempt

        # Try cloud storage as fallback
        if self.cloud_storage_service:
            try:
                # Generate cloud storage key
                cloud_file_key = f"tenant_{tenant_id}/{self.HOLDINGS_FILES_SUBDIR}/{stored_filename}"

                # Retrieve from cloud storage
                content = await self.cloud_storage_service.retrieve_file(
                    file_key=cloud_file_key,
                    tenant_id=str(tenant_id)
                )
                logger.info(f"File retrieved from cloud storage: {cloud_file_key}")
                return content

            except Exception as e:
                logger.warning(f"Failed to retrieve file from cloud storage: {e}")

        # File not found in either storage
        logger.warning(f"File not found: {stored_filename}")
        raise FileNotFoundError(f"File not found: {stored_filename}")

    async def delete_file(
        self,
        stored_filename: str,
        tenant_id: int,
        user_id: int
    ) -> bool:
        """
        Delete a file from local and cloud storage.

        Deletes the file from both local and cloud storage. If cloud deletion fails,
        the local file is still deleted and a warning is logged.

        Args:
            stored_filename: The unique filename to delete
            tenant_id: The tenant ID for storage isolation
            user_id: The user ID performing the deletion

        Returns:
            True if file was deleted from at least local storage, False if file did not exist

        Raises:
            IOError: If local file deletion fails

        Requirements: 4.1, 4.2, 14.1, 14.2, 18.1, 18.2, 18.3, 18.4, 18.5
        """
        # Construct the local file path
        tenant_folder = f"tenant_{tenant_id}"
        file_path = self.base_dir / tenant_folder / self.HOLDINGS_FILES_SUBDIR / stored_filename

        # Check if local file exists
        local_deleted = False
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"File deleted from local storage: {file_path}")
                local_deleted = True
            except OSError as e:
                logger.error(f"Failed to delete local file {file_path}: {e}")
                raise IOError(f"Failed to delete file: {e}")
        else:
            logger.warning(f"Local file not found for deletion: {file_path}")

        # Attempt cloud storage deletion
        if self.cloud_storage_service:
            try:
                # Generate cloud storage key
                cloud_file_key = f"tenant_{tenant_id}/{self.HOLDINGS_FILES_SUBDIR}/{stored_filename}"

                # Delete from cloud storage
                cloud_deleted = await self.cloud_storage_service.delete_file(
                    file_key=cloud_file_key,
                    tenant_id=str(tenant_id),
                    user_id=user_id
                )

                if cloud_deleted:
                    logger.info(f"File deleted from cloud storage: {cloud_file_key}")
                else:
                    logger.warning(f"File not found in cloud storage: {cloud_file_key}")

            except Exception as e:
                logger.warning(f"Cloud storage deletion failed: {e}. Local file was deleted successfully.")

        return local_deleted

    def validate_file(
        self,
        file_content: bytes,
        original_filename: str,
        content_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[FileType]]:
        """
        Validate a file for upload.

        Checks:
        - File type is PDF or CSV (by extension and content type)
        - File size does not exceed 20 MB
        - File content is readable

        Args:
            file_content: The file content as bytes
            original_filename: The original filename
            content_type: The MIME type of the file (optional)

        Returns:
            Tuple of (is_valid, error_message, file_type)
            - is_valid: True if file is valid, False otherwise
            - error_message: Error message if invalid, None if valid
            - file_type: Detected FileType if valid, None if invalid

        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3
        """
        # Check file size
        if len(file_content) > self.MAX_FILE_SIZE:
            size_mb = len(file_content) / (1024 * 1024)
            max_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File size {size_mb:.1f} MB exceeds maximum of {max_mb:.0f} MB", None

        # Check file extension
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()

        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file format: {ext}. Only PDF and CSV files are supported.", None

        # Determine file type from extension
        if ext == ".pdf":
            file_type = FileType.PDF
        elif ext == ".csv":
            file_type = FileType.CSV
        else:
            return False, f"Unsupported file format: {ext}", None

        # Check MIME type if provided
        if content_type and content_type not in self.ALLOWED_MIME_TYPES:
            logger.warning(f"Unexpected MIME type for {ext} file: {content_type}")
            # Don't fail on MIME type mismatch, just warn

        # Validate file content is readable
        try:
            if file_type == FileType.PDF:
                # Check for PDF magic bytes
                if not file_content.startswith(b"%PDF"):
                    return False, "Invalid PDF file: missing PDF header", None
            elif file_type == FileType.CSV:
                # Try to decode as text
                try:
                    file_content.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        file_content.decode('latin-1')
                    except UnicodeDecodeError:
                        return False, "Invalid CSV file: cannot decode as text", None
        except Exception as e:
            logger.error(f"Error validating file content: {e}")
            return False, f"Error validating file: {str(e)}", None

        return True, None, file_type

    def get_file_path(
        self,
        stored_filename: str,
        tenant_id: int
    ) -> str:
        """
        Get the full path for a stored file.

        Args:
            stored_filename: The unique filename
            tenant_id: The tenant ID for storage isolation

        Returns:
            The full path to the file

        Requirements: 4.1, 4.2
        """
        tenant_folder = f"tenant_{tenant_id}"
        file_path = self.base_dir / tenant_folder / self.HOLDINGS_FILES_SUBDIR / stored_filename
        return str(file_path)

    def file_exists(
        self,
        stored_filename: str,
        tenant_id: int
    ) -> bool:
        """
        Check if a file exists in storage.

        Args:
            stored_filename: The unique filename
            tenant_id: The tenant ID for storage isolation

        Returns:
            True if file exists, False otherwise

        Requirements: 4.1, 4.2
        """
        file_path = Path(self.get_file_path(stored_filename, tenant_id))
        return file_path.exists()

    async def delete_tenant_directory(
        self,
        tenant_id: int,
        user_id: int
    ) -> bool:
        """
        Delete all holdings files for a tenant (for cleanup purposes).

        Deletes files from both local and cloud storage. If cloud deletion fails,
        local files are still deleted and a warning is logged.

        Args:
            tenant_id: The tenant ID
            user_id: The user ID performing the deletion

        Returns:
            True if directory was deleted or didn't exist, False if deletion failed

        Requirements: 14.1, 14.2, 14.3, 18.1, 18.2, 18.3, 18.4, 18.5
        """
        tenant_folder = f"tenant_{tenant_id}"
        tenant_dir = self.base_dir / tenant_folder / self.HOLDINGS_FILES_SUBDIR

        # Delete local directory
        local_deleted = True
        if tenant_dir.exists():
            try:
                shutil.rmtree(tenant_dir)
                logger.info(f"Tenant directory deleted from local storage: {tenant_dir}")
            except OSError as e:
                logger.error(f"Failed to delete tenant directory {tenant_dir}: {e}")
                local_deleted = False

        # Delete cloud storage folder
        if self.cloud_storage_service:
            try:
                # Generate cloud storage folder key
                cloud_folder_key = f"tenant_{tenant_id}/{self.HOLDINGS_FILES_SUBDIR}"

                # Delete folder from cloud storage
                await self.cloud_storage_service.delete_folder(
                    folder_key=cloud_folder_key,
                    tenant_id=str(tenant_id),
                    user_id=user_id
                )
                logger.info(f"Tenant folder deleted from cloud storage: {cloud_folder_key}")

            except Exception as e:
                logger.warning(f"Cloud storage folder deletion failed: {e}. Local files were deleted successfully.")

        return local_deleted
