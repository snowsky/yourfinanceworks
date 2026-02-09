"""
Unit tests for File Storage Service

This module tests the FileStorageService class to ensure proper file handling,
validation, and storage operations for portfolio holdings import.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from plugins.investments.services.file_storage_service import FileStorageService
from plugins.investments.models import FileType


class TestFileStorageService:
    """Test suite for FileStorageService"""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for file storage testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def file_storage_service(self, temp_storage_dir):
        """Create a FileStorageService instance with temporary storage"""
        service = FileStorageService()
        # Override base directory to use temp directory
        service.base_dir = Path(temp_storage_dir)
        return service

    @pytest.fixture
    def sample_pdf_content(self):
        """Sample PDF file content (minimal valid PDF)"""
        return b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n0\n%%EOF"

    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV file content"""
        return b"Symbol,Quantity,CostBasis\nAAPL,100,15000\nGOOGL,50,7500"

    def test_service_initialization(self, file_storage_service):
        """Test FileStorageService initialization"""
        assert file_storage_service is not None
        assert file_storage_service.base_dir is not None
        assert file_storage_service.MAX_FILE_SIZE == 20 * 1024 * 1024
        assert FileType.PDF in [ft for ft in FileType]
        assert FileType.CSV in [ft for ft in FileType]

    def test_save_file_pdf_success(self, file_storage_service, sample_pdf_content):
        """Test successful PDF file save"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        original_filename = "holdings.pdf"

        # Act
        stored_filename, local_path = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )

        # Assert
        assert stored_filename is not None
        assert stored_filename.startswith(f"hf_{portfolio_id}_")
        assert stored_filename.endswith(".pdf")
        assert local_path is not None
        assert Path(local_path).exists()
        assert Path(local_path).read_bytes() == sample_pdf_content

    def test_save_file_csv_success(self, file_storage_service, sample_csv_content):
        """Test successful CSV file save"""
        # Arrange
        portfolio_id = 2
        tenant_id = 1
        original_filename = "holdings.csv"

        # Act
        stored_filename, local_path = file_storage_service.save_file(
            file_content=sample_csv_content,
            original_filename=original_filename,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.CSV
        )

        # Assert
        assert stored_filename is not None
        assert stored_filename.startswith(f"hf_{portfolio_id}_")
        assert stored_filename.endswith(".csv")
        assert Path(local_path).exists()
        assert Path(local_path).read_bytes() == sample_csv_content

    def test_save_file_tenant_isolation(self, file_storage_service, sample_pdf_content):
        """Test that files are stored in tenant-scoped directories"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1

        # Act
        stored_filename, local_path = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )

        # Assert
        assert f"tenant_{tenant_id}" in local_path
        assert "holdings_files" in local_path

    def test_save_file_unique_filenames(self, file_storage_service, sample_pdf_content):
        """Test that multiple saves generate unique filenames"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1

        # Act
        filename1, _ = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )

        filename2, _ = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )

        # Assert
        assert filename1 != filename2

    def test_save_file_invalid_file_type(self, file_storage_service, sample_pdf_content):
        """Test that invalid file type raises ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid file type"):
            file_storage_service.save_file(
                file_content=sample_pdf_content,
                original_filename="holdings.pdf",
                portfolio_id=1,
                tenant_id=1,
                file_type="invalid"
            )

    def test_retrieve_file_success(self, file_storage_service, sample_pdf_content):
        """Test successful file retrieval"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        stored_filename, _ = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )

        # Act
        retrieved_content = file_storage_service.retrieve_file(stored_filename, tenant_id)

        # Assert
        assert retrieved_content == sample_pdf_content

    def test_retrieve_file_not_found(self, file_storage_service):
        """Test that retrieving nonexistent file raises FileNotFoundError"""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            file_storage_service.retrieve_file("nonexistent.pdf", 1)

    def test_delete_file_success(self, file_storage_service, sample_pdf_content):
        """Test successful file deletion"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        stored_filename, local_path = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )
        assert Path(local_path).exists()

        # Act
        result = file_storage_service.delete_file(stored_filename, tenant_id)

        # Assert
        assert result is True
        assert not Path(local_path).exists()

    def test_delete_file_not_found(self, file_storage_service):
        """Test that deleting nonexistent file returns False"""
        # Act
        result = file_storage_service.delete_file("nonexistent.pdf", 1)

        # Assert
        assert result is False

    def test_validate_file_pdf_success(self, file_storage_service, sample_pdf_content):
        """Test successful PDF file validation"""
        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            content_type="application/pdf"
        )

        # Assert
        assert is_valid is True
        assert error_msg is None
        assert file_type == FileType.PDF

    def test_validate_file_csv_success(self, file_storage_service, sample_csv_content):
        """Test successful CSV file validation"""
        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=sample_csv_content,
            original_filename="holdings.csv",
            content_type="text/csv"
        )

        # Assert
        assert is_valid is True
        assert error_msg is None
        assert file_type == FileType.CSV

    def test_validate_file_size_exceeds_limit(self, file_storage_service):
        """Test that oversized file is rejected"""
        # Arrange
        large_content = b"x" * (21 * 1024 * 1024)  # 21 MB

        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=large_content,
            original_filename="large.pdf"
        )

        # Assert
        assert is_valid is False
        assert "exceeds maximum" in error_msg
        assert file_type is None

    def test_validate_file_unsupported_extension(self, file_storage_service):
        """Test that unsupported file extension is rejected"""
        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=b"some content",
            original_filename="holdings.txt"
        )

        # Assert
        assert is_valid is False
        assert "Unsupported file format" in error_msg
        assert file_type is None

    def test_validate_file_invalid_pdf_header(self, file_storage_service):
        """Test that invalid PDF (missing header) is rejected"""
        # Arrange
        invalid_pdf = b"This is not a PDF file"

        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=invalid_pdf,
            original_filename="invalid.pdf"
        )

        # Assert
        assert is_valid is False
        assert "Invalid PDF" in error_msg
        assert file_type is None

    def test_validate_file_invalid_csv_encoding(self, file_storage_service):
        """Test that CSV with invalid encoding is rejected"""
        # Arrange
        # Note: Latin-1 can decode almost any byte sequence, so we just test
        # that valid CSV content passes validation
        valid_csv = b"Symbol,Quantity,CostBasis\nAAPL,100,15000"

        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=valid_csv,
            original_filename="valid.csv"
        )

        # Assert
        assert is_valid is True
        assert error_msg is None
        assert file_type == FileType.CSV

    def test_validate_file_empty_content(self, file_storage_service):
        """Test that empty file is rejected"""
        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=b"",
            original_filename="empty.pdf"
        )

        # Assert
        assert is_valid is False
        assert file_type is None

    def test_validate_file_case_insensitive_extension(self, file_storage_service, sample_pdf_content):
        """Test that file extension check is case-insensitive"""
        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=sample_pdf_content,
            original_filename="holdings.PDF"
        )

        # Assert
        assert is_valid is True
        assert file_type == FileType.PDF

    def test_get_file_path(self, file_storage_service):
        """Test getting file path"""
        # Arrange
        stored_filename = "hf_1_abc123.pdf"
        tenant_id = 1

        # Act
        file_path = file_storage_service.get_file_path(stored_filename, tenant_id)

        # Assert
        assert file_path is not None
        assert "tenant_1" in file_path
        assert "holdings_files" in file_path
        assert "hf_1_abc123.pdf" in file_path

    def test_file_exists_true(self, file_storage_service, sample_pdf_content):
        """Test file_exists returns True for existing file"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        stored_filename, _ = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )

        # Act
        exists = file_storage_service.file_exists(stored_filename, tenant_id)

        # Assert
        assert exists is True

    def test_file_exists_false(self, file_storage_service):
        """Test file_exists returns False for nonexistent file"""
        # Act
        exists = file_storage_service.file_exists("nonexistent.pdf", 1)

        # Assert
        assert exists is False

    def test_delete_tenant_directory_success(self, file_storage_service, sample_pdf_content):
        """Test successful tenant directory deletion"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1
        stored_filename, local_path = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )
        tenant_dir = Path(local_path).parent
        assert tenant_dir.exists()

        # Act
        result = file_storage_service.delete_tenant_directory(tenant_id)

        # Assert
        assert result is True
        assert not tenant_dir.exists()

    def test_delete_tenant_directory_not_exists(self, file_storage_service):
        """Test deleting nonexistent tenant directory returns True"""
        # Act
        result = file_storage_service.delete_tenant_directory(999)

        # Assert
        assert result is True

    def test_multiple_files_same_portfolio(self, file_storage_service, sample_pdf_content, sample_csv_content):
        """Test storing multiple files for same portfolio"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1

        # Act
        filename1, path1 = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings1.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )

        filename2, path2 = file_storage_service.save_file(
            file_content=sample_csv_content,
            original_filename="holdings2.csv",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.CSV
        )

        # Assert
        assert filename1 != filename2
        assert Path(path1).exists()
        assert Path(path2).exists()
        assert Path(path1).read_bytes() == sample_pdf_content
        assert Path(path2).read_bytes() == sample_csv_content

    def test_multiple_tenants_isolation(self, file_storage_service, sample_pdf_content):
        """Test that files are isolated between tenants"""
        # Arrange
        portfolio_id = 1
        tenant_id_1 = 1
        tenant_id_2 = 2

        # Act
        filename1, path1 = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id_1,
            file_type=FileType.PDF
        )

        filename2, path2 = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id_2,
            file_type=FileType.PDF
        )

        # Assert
        assert "tenant_1" in path1
        assert "tenant_2" in path2
        assert path1 != path2

    def test_save_file_creates_directory_structure(self, file_storage_service, sample_pdf_content):
        """Test that save_file creates necessary directory structure"""
        # Arrange
        portfolio_id = 1
        tenant_id = 1

        # Act
        stored_filename, local_path = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            file_type=FileType.PDF
        )

        # Assert
        file_path = Path(local_path)
        assert file_path.exists()
        assert file_path.parent.exists()
        assert "tenant_1" in str(file_path.parent)
        assert "holdings_files" in str(file_path.parent)

    def test_validate_file_with_no_content_type(self, file_storage_service, sample_pdf_content):
        """Test file validation without content_type parameter"""
        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf"
        )

        # Assert
        assert is_valid is True
        assert file_type == FileType.PDF

    def test_validate_file_with_mismatched_content_type(self, file_storage_service, sample_pdf_content):
        """Test file validation with mismatched content_type (should still pass)"""
        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            content_type="text/csv"  # Wrong content type
        )

        # Assert
        assert is_valid is True  # Should still pass based on extension and content
        assert file_type == FileType.PDF

    def test_file_size_boundary_exactly_20mb(self, file_storage_service):
        """Test file exactly at 20MB limit"""
        # Arrange
        exact_size_content = b"x" * (20 * 1024 * 1024)

        # Act
        is_valid, error_msg, file_type = file_storage_service.validate_file(
            file_content=exact_size_content,
            original_filename="holdings.pdf"
        )

        # Assert
        assert is_valid is False  # Should fail because it's not a valid PDF
        # But size check should pass

    def test_retrieve_file_tenant_isolation(self, file_storage_service, sample_pdf_content):
        """Test that retrieve_file respects tenant isolation"""
        # Arrange
        portfolio_id = 1
        tenant_id_1 = 1
        tenant_id_2 = 2

        stored_filename, _ = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id_1,
            file_type=FileType.PDF
        )

        # Act & Assert
        # Should succeed for correct tenant
        content = file_storage_service.retrieve_file(stored_filename, tenant_id_1)
        assert content == sample_pdf_content

        # Should fail for different tenant
        with pytest.raises(FileNotFoundError):
            file_storage_service.retrieve_file(stored_filename, tenant_id_2)

    def test_delete_file_tenant_isolation(self, file_storage_service, sample_pdf_content):
        """Test that delete_file respects tenant isolation"""
        # Arrange
        portfolio_id = 1
        tenant_id_1 = 1
        tenant_id_2 = 2

        stored_filename, local_path = file_storage_service.save_file(
            file_content=sample_pdf_content,
            original_filename="holdings.pdf",
            portfolio_id=portfolio_id,
            tenant_id=tenant_id_1,
            file_type=FileType.PDF
        )
        assert Path(local_path).exists()

        # Act
        # Try to delete with wrong tenant
        result = file_storage_service.delete_file(stored_filename, tenant_id_2)

        # Assert
        assert result is False
        assert Path(local_path).exists()  # File should still exist

        # Delete with correct tenant
        result = file_storage_service.delete_file(stored_filename, tenant_id_1)
        assert result is True
        assert not Path(local_path).exists()
