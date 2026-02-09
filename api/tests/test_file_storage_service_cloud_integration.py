"""
Unit tests for File Storage Service with Cloud Storage Integration

This module tests the FileStorageService class to ensure proper local and cloud
file storage, retrieval, deletion, and fallback behavior for portfolio holdings import.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add api directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from plugins.investments.services.file_storage_service import FileStorageService
from plugins.investments.models import FileType


class TestFileStorageServiceCloudIntegration:
    """Test suite for FileStorageService with cloud storage integration"""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for file storage testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        return Mock()

    @pytest.fixture
    def mock_cloud_storage_service(self):
        """Create a mock CloudStorageService"""
        service = AsyncMock()
        service.store_file = AsyncMock()
        service.retrieve_file = AsyncMock()
        service.delete_file = AsyncMock()
        service.delete_folder = AsyncMock()
        return service

    @pytest.fixture
    def file_storage_service_with_cloud(self, mock_db_session, mock_cloud_storage_service, temp_storage_dir):
        """Create FileStorageService with mocked cloud storage"""
        with patch('plugins.investments.services.file_storage_service.get_cloud_storage_config'):
            with patch('plugins.investments.services.file_storage_service.CloudStorageService', return_value=mock_cloud_storage_service):
                service = FileStorageService(mock_db_session)
                service.base_dir = Path(temp_storage_dir)
                return service

    @pytest.fixture
    def file_storage_service_local_only(self, temp_storage_dir):
        """Create FileStorageService without cloud storage (local only)"""
        service = FileStorageService(db=None)
        service.base_dir = Path(temp_storage_dir)
        return service

    @pytest.fixture
    def sample_pdf_content(self):
        """Sample PDF file content"""
        return b"%PDF-1.4\n%Sample PDF content"

    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV file content"""
        return b"Symbol,Quantity,CostBasis\nAAPL,100,15000\nGOOGL,50,7500"

    # Tests for save_file with cloud storage

    @pytest.mark.asyncio
    async def test_save_file_local_and_cloud_success(
        self,
        file_storage_service_with_cloud,
        mock_cloud_storage_service,
        sample_pdf_content
    ):
        """Test successful file save to both local and cloud storage"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.pdf"

        # Mock successful cloud storage
        mock_cloud_storage_service.store_file.return_value = MagicMock(
            success=True,
            file_url="https://s3.amazonaws.com/bucket/tenant_1/holdings_files/hf_1_abc123.pdf"
        )

        # Act
        stored_filename, local_path, cloud_url = await file_storage_service_with_cloud.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Assert
        assert stored_filename.startswith("hf_1_")
        assert stored_filename.endswith(".pdf")
        assert Path(local_path).exists()
        assert cloud_url == "https://s3.amazonaws.com/bucket/tenant_1/holdings_files/hf_1_abc123.pdf"

        # Verify cloud storage was called
        mock_cloud_storage_service.store_file.assert_called_once()
        call_args = mock_cloud_storage_service.store_file.call_args
        assert call_args.kwargs["tenant_id"] == "1"
        assert call_args.kwargs["item_id"] == portfolio_id
        assert call_args.kwargs["attachment_type"] == "holdings_files"

    @pytest.mark.asyncio
    async def test_save_file_cloud_failure_fallback_to_local(
        self,
        file_storage_service_with_cloud,
        mock_cloud_storage_service,
        sample_pdf_content
    ):
        """Test that cloud storage failure falls back to local storage"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.pdf"

        # Mock cloud storage failure
        mock_cloud_storage_service.store_file.return_value = MagicMock(
            success=False,
            error_message="Cloud storage unavailable"
        )

        # Act
        stored_filename, local_path, cloud_url = await file_storage_service_with_cloud.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Assert
        assert stored_filename.startswith("hf_1_")
        assert Path(local_path).exists()
        assert cloud_url is None  # Cloud storage failed

    @pytest.mark.asyncio
    async def test_save_file_cloud_exception_fallback_to_local(
        self,
        file_storage_service_with_cloud,
        mock_cloud_storage_service,
        sample_pdf_content
    ):
        """Test that cloud storage exception falls back to local storage"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.pdf"

        # Mock cloud storage exception
        mock_cloud_storage_service.store_file.side_effect = Exception("Connection timeout")

        # Act
        stored_filename, local_path, cloud_url = await file_storage_service_with_cloud.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Assert
        assert stored_filename.startswith("hf_1_")
        assert Path(local_path).exists()
        assert cloud_url is None  # Cloud storage failed

    @pytest.mark.asyncio
    async def test_save_file_local_only_no_cloud(
        self,
        file_storage_service_local_only,
        sample_pdf_content
    ):
        """Test file save with local-only storage (no cloud service)"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.pdf"

        # Act
        stored_filename, local_path, cloud_url = await file_storage_service_local_only.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Assert
        assert stored_filename.startswith("hf_1_")
        assert Path(local_path).exists()
        assert cloud_url is None  # No cloud service

    @pytest.mark.asyncio
    async def test_save_file_tenant_scoped_directory(
        self,
        file_storage_service_local_only,
        sample_pdf_content
    ):
        """Test that files are stored in tenant-scoped directories"""
        # Arrange
        portfolio_id = 1
        tenant_id = 42
        user_id = 100
        original_filename = "holdings.pdf"

        # Act
        stored_filename, local_path, cloud_url = await file_storage_service_local_only.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Assert
        assert f"tenant_{tenant_id}" in local_path
        assert "holdings_files" in local_path

    @pytest.mark.asyncio
    async def test_save_file_csv_format(
        self,
        file_storage_service_local_only,
        sample_csv_content
    ):
        """Test saving CSV files"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.csv"

        # Act
        stored_filename, local_path, cloud_url = await file_storage_service_local_only.save_file(
            file_content=sample_csv_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.CSV,
            user_id=user_id
        )

        # Assert
        assert stored_filename.endswith(".csv")
        assert Path(local_path).exists()

    # Tests for retrieve_file

    @pytest.mark.asyncio
    async def test_retrieve_file_from_local_storage(
        self,
        file_storage_service_local_only,
        sample_pdf_content
    ):
        """Test retrieving file from local storage"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.pdf"

        stored_filename, local_path, _ = await file_storage_service_local_only.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Act
        retrieved_content = await file_storage_service_local_only.retrieve_file(
            stored_filename=stored_filename,
            tenant_id=tenant_id
        )

        # Assert
        assert retrieved_content == sample_pdf_content

    @pytest.mark.asyncio
    async def test_retrieve_file_from_cloud_fallback(
        self,
        file_storage_service_with_cloud,
        mock_cloud_storage_service,
        sample_pdf_content
    ):
        """Test retrieving file from cloud storage when local fails"""
        # Arrange
        stored_filename = "hf_1_abc123.pdf"
        tenant_id = 1

        # Mock cloud storage retrieval
        mock_cloud_storage_service.retrieve_file.return_value = sample_pdf_content

        # Act
        retrieved_content = await file_storage_service_with_cloud.retrieve_file(
            stored_filename=stored_filename,
            tenant_id=tenant_id
        )

        # Assert
        assert retrieved_content == sample_pdf_content
        mock_cloud_storage_service.retrieve_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_file_not_found(
        self,
        file_storage_service_local_only
    ):
        """Test retrieving nonexistent file raises FileNotFoundError"""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            await file_storage_service_local_only.retrieve_file(
                stored_filename="nonexistent.pdf",
                tenant_id=1
            )

    # Tests for delete_file

    @pytest.mark.asyncio
    async def test_delete_file_local_and_cloud_success(
        self,
        file_storage_service_with_cloud,
        mock_cloud_storage_service,
        sample_pdf_content
    ):
        """Test successful file deletion from both local and cloud storage"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.pdf"

        # Mock successful cloud storage
        mock_cloud_storage_service.store_file.return_value = MagicMock(
            success=True,
            file_url="https://s3.amazonaws.com/bucket/tenant_1/holdings_files/hf_1_abc123.pdf"
        )
        mock_cloud_storage_service.delete_file.return_value = True

        # Save file first
        stored_filename, local_path, _ = await file_storage_service_with_cloud.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Act
        result = await file_storage_service_with_cloud.delete_file(
            stored_filename=stored_filename,
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Assert
        assert result is True
        assert not Path(local_path).exists()
        mock_cloud_storage_service.delete_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_file_cloud_failure_still_deletes_local(
        self,
        file_storage_service_with_cloud,
        mock_cloud_storage_service,
        sample_pdf_content
    ):
        """Test that cloud deletion failure doesn't prevent local deletion"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.pdf"

        # Mock successful cloud storage for save
        mock_cloud_storage_service.store_file.return_value = MagicMock(
            success=True,
            file_url="https://s3.amazonaws.com/bucket/tenant_1/holdings_files/hf_1_abc123.pdf"
        )
        # Mock cloud storage failure for delete
        mock_cloud_storage_service.delete_file.side_effect = Exception("Cloud service error")

        # Save file first
        stored_filename, local_path, _ = await file_storage_service_with_cloud.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Act
        result = await file_storage_service_with_cloud.delete_file(
            stored_filename=stored_filename,
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Assert
        assert result is True  # Local deletion succeeded
        assert not Path(local_path).exists()

    @pytest.mark.asyncio
    async def test_delete_file_nonexistent(
        self,
        file_storage_service_local_only
    ):
        """Test deleting nonexistent file returns False"""
        # Act
        result = await file_storage_service_local_only.delete_file(
            stored_filename="nonexistent.pdf",
            tenant_id=1,
            user_id=100
        )

        # Assert
        assert result is False

    # Tests for delete_tenant_directory

    @pytest.mark.asyncio
    async def test_delete_tenant_directory_local_and_cloud(
        self,
        file_storage_service_with_cloud,
        mock_cloud_storage_service,
        sample_pdf_content
    ):
        """Test deleting entire tenant directory from local and cloud storage"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100

        # Mock successful cloud storage
        mock_cloud_storage_service.store_file.return_value = MagicMock(
            success=True,
            file_url="https://s3.amazonaws.com/bucket/tenant_1/holdings_files/hf_1_abc123.pdf"
        )
        mock_cloud_storage_service.delete_folder.return_value = None

        # Save multiple files
        for i in range(3):
            await file_storage_service_with_cloud.save_file(
                file_content=sample_pdf_content,
                original_filename=f"holdings{i}.pdf",
                portfolio_id=portfolio_id,
                tenant_id=tenant_id,
                file_type=FileType.PDF,
                user_id=user_id
            )

        # Act
        result = await file_storage_service_with_cloud.delete_tenant_directory(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Assert
        assert result is True
        tenant_dir = file_storage_service_with_cloud.base_dir / f"tenant_{tenant_id}" / "holdings_files"
        assert not tenant_dir.exists()
        mock_cloud_storage_service.delete_folder.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_tenant_directory_nonexistent(
        self,
        file_storage_service_local_only
    ):
        """Test deleting nonexistent tenant directory returns True"""
        # Act
        result = await file_storage_service_local_only.delete_tenant_directory(
            tenant_id=999,
            user_id=100
        )

        # Assert
        assert result is True

    # Tests for validate_file

    def test_validate_file_pdf_success(
        self,
        file_storage_service_local_only,
        sample_pdf_content
    ):
        """Test validating valid PDF file"""
        # Act
        is_valid, error_msg, file_type = file_storage_service_local_only.validate_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf"
        )

        # Assert
        assert is_valid is True
        assert error_msg is None
        assert file_type == FileType.PDF

    def test_validate_file_csv_success(
        self,
        file_storage_service_local_only,
        sample_csv_content
    ):
        """Test validating valid CSV file"""
        # Act
        is_valid, error_msg, file_type = file_storage_service_local_only.validate_file(
            file_content=sample_csv_content,
            original_filename="holdings.csv"
        )

        # Assert
        assert is_valid is True
        assert error_msg is None
        assert file_type == FileType.CSV

    def test_validate_file_unsupported_format(
        self,
        file_storage_service_local_only
    ):
        """Test validating unsupported file format"""
        # Act
        is_valid, error_msg, file_type = file_storage_service_local_only.validate_file(
            file_content=b"some content",
            original_filename="holdings.txt"
        )

        # Assert
        assert is_valid is False
        assert "Unsupported file format" in error_msg
        assert file_type is None

    def test_validate_file_size_exceeds_limit(
        self,
        file_storage_service_local_only
    ):
        """Test validating file that exceeds size limit"""
        # Arrange
        large_content = b"x" * (21 * 1024 * 1024)  # 21 MB

        # Act
        is_valid, error_msg, file_type = file_storage_service_local_only.validate_file(
            file_content=large_content,
            original_filename="holdings.pdf"
        )

        # Assert
        assert is_valid is False
        assert "exceeds maximum" in error_msg
        assert file_type is None

    def test_validate_file_invalid_pdf_header(
        self,
        file_storage_service_local_only
    ):
        """Test validating invalid PDF file"""
        # Arrange
        invalid_pdf = b"Not a PDF file"

        # Act
        is_valid, error_msg, file_type = file_storage_service_local_only.validate_file(
            file_content=invalid_pdf,
            original_filename="holdings.pdf"
        )

        # Assert
        assert is_valid is False
        assert "Invalid PDF" in error_msg
        assert file_type is None

    # Tests for file_exists

    @pytest.mark.asyncio
    async def test_file_exists_true(
        self,
        file_storage_service_local_only,
        sample_pdf_content
    ):
        """Test file_exists returns True for existing file"""
        # Arrange
        stored_filename, _, _ = await file_storage_service_local_only.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=1,
            tenant_id=1,
            file_type=FileType.PDF,
            user_id=100
        )

        # Act
        exists = file_storage_service_local_only.file_exists(
            stored_filename=stored_filename,
            tenant_id=1
        )

        # Assert
        assert exists is True

    def test_file_exists_false(
        self,
        file_storage_service_local_only
    ):
        """Test file_exists returns False for nonexistent file"""
        # Act
        exists = file_storage_service_local_only.file_exists(
            stored_filename="nonexistent.pdf",
            tenant_id=1
        )

        # Assert
        assert exists is False

    # Tests for get_file_path

    def test_get_file_path(
        self,
        file_storage_service_local_only
    ):
        """Test get_file_path returns correct path"""
        # Act
        path = file_storage_service_local_only.get_file_path(
            stored_filename="hf_1_abc123.pdf",
            tenant_id=1
        )

        # Assert
        assert "tenant_1" in path
        assert "holdings_files" in path
        assert "hf_1_abc123.pdf" in path

    # Tests for cloud storage metadata

    @pytest.mark.asyncio
    async def test_save_file_includes_metadata(
        self,
        file_storage_service_with_cloud,
        mock_cloud_storage_service,
        sample_pdf_content
    ):
        """Test that save_file includes proper metadata for cloud storage"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        user_id = 100
        original_filename = "holdings.pdf"

        mock_cloud_storage_service.store_file.return_value = MagicMock(
            success=True,
            file_url="https://s3.amazonaws.com/bucket/tenant_1/holdings_files/hf_1_abc123.pdf"
        )

        # Act
        await file_storage_service_with_cloud.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF,
            user_id=user_id
        )

        # Assert
        call_args = mock_cloud_storage_service.store_file.call_args
        metadata = call_args.kwargs["metadata"]
        assert metadata["original_filename"] == original_filename
        assert metadata["file_type"] == "pdf"
        assert metadata["portfolio_id"] == "1"
        assert metadata["tenant_id"] == "1"
        assert metadata["document_type"] == "holdings_file"
        assert metadata["upload_method"] == "internal_api"
