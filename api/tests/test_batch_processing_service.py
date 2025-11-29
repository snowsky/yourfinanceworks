"""
Unit tests for BatchProcessingService.

Tests job creation, progress tracking, completion detection, error handling,
and retry logic for batch file processing operations.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session

from commercial.batch_processing.service import BatchProcessingService
from core.models.models_per_tenant import (
    BatchProcessingJob,
    BatchFileProcessing,
    ExportDestinationConfig
)


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def batch_service(mock_db):
    """Create BatchProcessingService instance with mock db"""
    return BatchProcessingService(mock_db)


@pytest.fixture
def sample_export_destination():
    """Create a sample export destination config"""
    return ExportDestinationConfig(
        id=1,
        tenant_id=1,
        name="Test S3 Destination",
        destination_type="s3",
        is_active=True,
        encrypted_credentials=b"encrypted_data",
        config={"bucket_name": "test-bucket"}
    )


@pytest.fixture
def sample_files():
    """Create sample file data for testing"""
    return [
        {
            "filename": "invoice_001.pdf",
            "content": b"PDF content here",
            "size": 1024
        },
        {
            "filename": "expense_002.jpg",
            "content": b"JPG content here",
            "size": 2048
        },
        {
            "filename": "statement_003.pdf",
            "content": b"PDF content here",
            "size": 1536
        }
    ]


class TestBatchProcessingServiceJobCreation:
    """Test job creation with various file combinations"""

    @pytest.mark.asyncio
    async def test_create_batch_job_success(self, batch_service, mock_db, sample_export_destination, sample_files):
        """Test successful batch job creation"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_export_destination
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock file storage
        with patch.object(batch_service, '_store_file_to_disk', return_value='/path/to/file'):
            # Create batch job
            job = await batch_service.create_batch_job(
                files=sample_files,
                tenant_id=1,
                user_id=1,
                api_client_id="test_client",
                export_destination_id=1
            )
        
        # Verify job was created
        assert mock_db.add.called
        assert mock_db.commit.called
        
        # Verify job properties
        call_args = mock_db.add.call_args_list
        job_arg = call_args[0][0][0]
        assert isinstance(job_arg, BatchProcessingJob)
        assert job_arg.tenant_id == 1
        assert job_arg.user_id == 1
        assert job_arg.total_files == 3
        assert job_arg.status == "pending"

    @pytest.mark.asyncio
    async def test_create_batch_job_exceeds_max_files(self, batch_service, sample_export_destination):
        """Test batch job creation fails when exceeding max files"""
        # Create 51 files (exceeds MAX_FILES_PER_BATCH of 50)
        too_many_files = [
            {"filename": f"file_{i}.pdf", "content": b"content", "size": 1024}
            for i in range(51)
        ]
        
        with pytest.raises(ValueError, match="Batch size must be between"):
            await batch_service.create_batch_job(
                files=too_many_files,
                tenant_id=1,
                user_id=1,
                api_client_id="test_client",
                export_destination_id=1
            )

    @pytest.mark.asyncio
    async def test_create_batch_job_invalid_file_type(self, batch_service, mock_db, sample_export_destination):
        """Test batch job creation fails with invalid file type"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_export_destination
        
        invalid_files = [
            {"filename": "document.exe", "content": b"content", "size": 1024}
        ]
        
        with pytest.raises(ValueError, match="invalid type"):
            await batch_service.create_batch_job(
                files=invalid_files,
                tenant_id=1,
                user_id=1,
                api_client_id="test_client",
                export_destination_id=1
            )

    @pytest.mark.asyncio
    async def test_create_batch_job_file_too_large(self, batch_service, mock_db, sample_export_destination):
        """Test batch job creation fails when file exceeds size limit"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_export_destination
        
        large_files = [
            {"filename": "large.pdf", "content": b"content", "size": 21 * 1024 * 1024}  # 21MB
        ]
        
        with pytest.raises(ValueError, match="exceeds maximum"):
            await batch_service.create_batch_job(
                files=large_files,
                tenant_id=1,
                user_id=1,
                api_client_id="test_client",
                export_destination_id=1
            )

    @pytest.mark.asyncio
    async def test_create_batch_job_destination_not_found(self, batch_service, mock_db):
        """Test batch job creation fails when export destination not found"""
        # Setup mock to return None (destination not found)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        files = [{"filename": "test.pdf", "content": b"content", "size": 1024}]
        
        with pytest.raises(ValueError, match="not found or inactive"):
            await batch_service.create_batch_job(
                files=files,
                tenant_id=1,
                user_id=1,
                api_client_id="test_client",
                export_destination_id=999
            )

    @pytest.mark.asyncio
    async def test_create_batch_job_with_document_types(self, batch_service, mock_db, sample_export_destination, sample_files):
        """Test batch job creation with explicit document types"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_export_destination
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch.object(batch_service, '_store_file_to_disk', return_value='/path/to/file'):
            job = await batch_service.create_batch_job(
                files=sample_files,
                tenant_id=1,
                user_id=1,
                api_client_id="test_client",
                export_destination_id=1,
                document_types=["invoice", "expense"]
            )
        
        # Verify document types were set
        call_args = mock_db.add.call_args_list
        job_arg = call_args[0][0][0]
        assert job_arg.document_types == ["invoice", "expense"]


class TestBatchProcessingServiceProgressTracking:
    """Test progress tracking and completion detection"""

    @pytest.mark.asyncio
    async def test_process_file_completion_success(self, batch_service, mock_db):
        """Test processing file completion with success status"""
        # Create mock batch file and job
        batch_file = BatchFileProcessing(
            id=1,
            job_id="test-job-id",
            original_filename="test.pdf",
            status="processing"
        )
        
        batch_job = BatchProcessingJob(
            job_id="test-job-id",
            tenant_id=1,
            total_files=3,
            processed_files=0,
            successful_files=0,
            failed_files=0,
            progress_percentage=0.0
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.side_effect = [batch_file, batch_job]
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Process completion
        result = await batch_service.process_file_completion(
            file_id=1,
            extracted_data={"vendor": "Test Corp", "amount": 100.00},
            status="completed"
        )
        
        # Verify updates
        assert batch_file.status == "completed"
        assert batch_file.extracted_data == {"vendor": "Test Corp", "amount": 100.00}
        assert batch_job.processed_files == 1
        assert batch_job.successful_files == 1
        assert batch_job.failed_files == 0
        assert batch_job.progress_percentage == pytest.approx(33.33, rel=0.1)
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_process_file_completion_failure(self, batch_service, mock_db):
        """Test processing file completion with failure status"""
        # Create mock batch file and job
        batch_file = BatchFileProcessing(
            id=1,
            job_id="test-job-id",
            original_filename="test.pdf",
            status="processing"
        )
        
        batch_job = BatchProcessingJob(
            job_id="test-job-id",
            tenant_id=1,
            total_files=3,
            processed_files=0,
            successful_files=0,
            failed_files=0,
            progress_percentage=0.0
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.side_effect = [batch_file, batch_job]
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Process completion with error
        result = await batch_service.process_file_completion(
            file_id=1,
            status="failed",
            error_message="OCR extraction failed"
        )
        
        # Verify updates
        assert batch_file.status == "failed"
        assert batch_file.error_message == "OCR extraction failed"
        assert batch_job.processed_files == 1
        assert batch_job.successful_files == 0
        assert batch_job.failed_files == 1
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_process_file_completion_triggers_export(self, batch_service, mock_db):
        """Test that export is triggered when all files are processed"""
        # Create mock batch file and job (last file completing)
        batch_file = BatchFileProcessing(
            id=3,
            job_id="test-job-id",
            original_filename="test3.pdf",
            status="processing"
        )
        
        batch_job = BatchProcessingJob(
            job_id="test-job-id",
            tenant_id=1,
            total_files=3,
            processed_files=2,  # 2 already processed
            successful_files=2,
            failed_files=0,
            progress_percentage=66.67
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.side_effect = [batch_file, batch_job]
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock _trigger_export
        with patch.object(batch_service, '_trigger_export', new_callable=AsyncMock) as mock_trigger:
            result = await batch_service.process_file_completion(
                file_id=3,
                extracted_data={"vendor": "Test Corp"},
                status="completed"
            )
            
            # Verify export was triggered
            assert result["all_processed"] is True
            assert batch_job.processed_files == 3
            assert batch_job.progress_percentage == 100.0
            mock_trigger.assert_called_once_with(batch_job)


class TestBatchProcessingServiceErrorHandling:
    """Test error handling for individual file failures"""

    @pytest.mark.asyncio
    async def test_process_file_completion_file_not_found(self, batch_service, mock_db):
        """Test error handling when file not found"""
        # Setup mock to return None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="not found"):
            await batch_service.process_file_completion(
                file_id=999,
                status="completed"
            )

    @pytest.mark.asyncio
    async def test_create_batch_job_rollback_on_error(self, batch_service, mock_db, sample_export_destination):
        """Test that database is rolled back on error during job creation"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_export_destination
        mock_db.flush = Mock()
        mock_db.commit = Mock(side_effect=Exception("Database error"))
        mock_db.rollback = Mock()
        
        files = [{"filename": "test.pdf", "content": b"content", "size": 1024}]
        
        with patch.object(batch_service, '_store_file_to_disk', return_value='/path/to/file'):
            with pytest.raises(Exception):
                await batch_service.create_batch_job(
                    files=files,
                    tenant_id=1,
                    user_id=1,
                    api_client_id="test_client",
                    export_destination_id=1
                )
        
        # Verify rollback was called
        assert mock_db.rollback.called


class TestBatchProcessingServiceRetryLogic:
    """Test retry logic for failed files"""

    @pytest.mark.asyncio
    async def test_retry_failed_file_success(self, batch_service, mock_db):
        """Test successful retry of a failed file"""
        # Create mock batch file and job
        batch_file = BatchFileProcessing(
            id=1,
            job_id="test-job-id",
            original_filename="test.pdf",
            status="failed",
            retry_count=0,
            error_message="Previous error",
            document_type="invoice",
            file_path="/path/to/file"
        )
        
        batch_job = BatchProcessingJob(
            job_id="test-job-id",
            tenant_id=1,
            total_files=1
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.side_effect = [batch_file, batch_job]
        mock_db.commit = Mock()
        
        # Mock Kafka publishing
        with patch.object(batch_service, '_publish_to_kafka', new_callable=AsyncMock, return_value="msg-123"):
            result = await batch_service.retry_failed_file(file_id=1, max_retries=3)
        
        # Verify retry
        assert result["status"] == "retrying"
        assert result["retry_count"] == 1
        assert batch_file.retry_count == 1
        assert batch_file.status == "processing"
        assert batch_file.error_message is None
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_retry_failed_file_max_retries_reached(self, batch_service, mock_db):
        """Test that file is marked permanently failed after max retries"""
        # Create mock batch file with max retries reached
        batch_file = BatchFileProcessing(
            id=1,
            job_id="test-job-id",
            original_filename="test.pdf",
            status="failed",
            retry_count=3,  # Already at max
            error_message="Previous error"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = batch_file
        mock_db.commit = Mock()
        
        result = await batch_service.retry_failed_file(file_id=1, max_retries=3)
        
        # Verify permanently failed
        assert result["status"] == "permanently_failed"
        assert "Permanently failed" in batch_file.error_message
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_retry_failed_file_exponential_backoff(self, batch_service, mock_db):
        """Test exponential backoff delay calculation"""
        # Test backoff delays
        assert batch_service.get_retry_delay(1) == 1.0  # 2^0 = 1
        assert batch_service.get_retry_delay(2) == 2.0  # 2^1 = 2
        assert batch_service.get_retry_delay(3) == 4.0  # 2^2 = 4

    def test_should_retry_file(self, batch_service):
        """Test should_retry_file logic"""
        # File with retries remaining
        file1 = BatchFileProcessing(status="failed", retry_count=1)
        assert batch_service.should_retry_file(file1, max_retries=3) is True
        
        # File at max retries
        file2 = BatchFileProcessing(status="failed", retry_count=3)
        assert batch_service.should_retry_file(file2, max_retries=3) is False
        
        # File not failed
        file3 = BatchFileProcessing(status="completed", retry_count=0)
        assert batch_service.should_retry_file(file3, max_retries=3) is False


class TestBatchProcessingServiceHelperMethods:
    """Test helper methods"""

    def test_generate_job_id(self, batch_service):
        """Test job ID generation"""
        job_id = batch_service.generate_job_id()
        
        # Verify it's a valid UUID
        assert isinstance(job_id, str)
        assert len(job_id) == 36  # UUID format
        uuid.UUID(job_id)  # Should not raise

    def test_determine_document_type(self, batch_service):
        """Test document type determination from filename"""
        assert batch_service.determine_document_type("invoice_001.pdf") == "invoice"
        assert batch_service.determine_document_type("INV-2024-001.pdf") == "invoice"
        assert batch_service.determine_document_type("expense_receipt.jpg") == "expense"
        assert batch_service.determine_document_type("bank_statement.pdf") == "statement"
        assert batch_service.determine_document_type("unknown_file.pdf") == "expense"  # Default

    def test_validate_file_type(self, batch_service):
        """Test file type validation"""
        assert batch_service.validate_file_type("document.pdf") is True
        assert batch_service.validate_file_type("image.png") is True
        assert batch_service.validate_file_type("photo.jpg") is True
        assert batch_service.validate_file_type("data.csv") is True
        assert batch_service.validate_file_type("program.exe") is False
        assert batch_service.validate_file_type("script.sh") is False

    def test_validate_file_size(self, batch_service):
        """Test file size validation"""
        assert batch_service.validate_file_size(1024) is True  # 1KB
        assert batch_service.validate_file_size(10 * 1024 * 1024) is True  # 10MB
        assert batch_service.validate_file_size(20 * 1024 * 1024) is True  # 20MB (at limit)
        assert batch_service.validate_file_size(21 * 1024 * 1024) is False  # 21MB (exceeds)

    def test_validate_batch_size(self, batch_service):
        """Test batch size validation"""
        assert batch_service.validate_batch_size(1) is True
        assert batch_service.validate_batch_size(25) is True
        assert batch_service.validate_batch_size(50) is True  # At limit
        assert batch_service.validate_batch_size(51) is False  # Exceeds
        assert batch_service.validate_batch_size(0) is False  # Too few

    def test_get_file_extension(self, batch_service):
        """Test file extension extraction"""
        assert batch_service.get_file_extension("document.pdf") == ".pdf"
        assert batch_service.get_file_extension("IMAGE.PNG") == ".png"
        assert batch_service.get_file_extension("file.tar.gz") == ".gz"
        assert batch_service.get_file_extension("noextension") == ""
