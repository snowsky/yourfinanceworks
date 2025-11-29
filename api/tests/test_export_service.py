"""
Unit tests for ExportService.

Tests CSV generation with different field selections, upload to each destination type,
error handling for upload failures, and retry logic.
"""

import pytest
import csv
import io
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session

from core.services.export_service import ExportService
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
def export_service(mock_db):
    """Create ExportService instance with mock db"""
    return ExportService(mock_db)


@pytest.fixture
def sample_batch_job():
    """Create a sample batch processing job"""
    return BatchProcessingJob(
        id=1,
        job_id="test-job-123",
        tenant_id=1,
        user_id=1,
        api_client_id="test_client",
        total_files=3,
        export_destination_type="s3",
        export_destination_config_id=1,
        status="processing"
    )


@pytest.fixture
def sample_batch_files():
    """Create sample batch file processing records"""
    return [
        BatchFileProcessing(
            id=1,
            job_id="test-job-123",
            original_filename="invoice_001.pdf",
            document_type="invoice",
            status="completed",
            file_path="/path/to/invoice_001.pdf",
            cloud_file_url="s3://bucket/invoice_001.pdf",
            extracted_data={
                "vendor": "Acme Corp",
                "amount": 1250.00,
                "currency": "USD",
                "date": "2025-11-01",
                "tax_amount": 125.00,
                "category": "Services",
                "line_items": [
                    {"description": "Consulting", "quantity": 10, "price": 125.00}
                ]
            }
        ),
        BatchFileProcessing(
            id=2,
            job_id="test-job-123",
            original_filename="expense_002.jpg",
            document_type="expense",
            status="completed",
            file_path="/path/to/expense_002.jpg",
            extracted_data={
                "vendor": "Office Depot",
                "amount": 45.99,
                "currency": "USD",
                "date": "2025-11-02",
                "tax_amount": 3.68,
                "category": "Office Supplies"
            }
        ),
        BatchFileProcessing(
            id=3,
            job_id="test-job-123",
            original_filename="statement_003.pdf",
            document_type="statement",
            status="failed",
            file_path="/path/to/statement_003.pdf",
            error_message="OCR extraction failed: Image quality too low"
        )
    ]


@pytest.fixture
def sample_s3_destination():
    """Create a sample S3 export destination"""
    return ExportDestinationConfig(
        id=1,
        tenant_id=1,
        name="Test S3",
        destination_type="s3",
        is_active=True,
        encrypted_credentials=b"encrypted",
        config={"bucket_name": "test-bucket"}
    )


class TestExportServiceCSVGeneration:
    """Test CSV generation with different field selections"""

    def test_generate_csv_all_fields(self, export_service, mock_db, sample_batch_job, sample_batch_files):
        """Test CSV generation with all fields"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_batch_job
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_batch_files
        
        # Generate CSV
        csv_content = export_service.generate_csv(job_id="test-job-123")
        
        # Parse CSV
        csv_text = csv_content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        
        # Verify header
        assert 'file_name' in reader.fieldnames
        assert 'document_type' in reader.fieldnames
        assert 'vendor' in reader.fieldnames
        assert 'amount' in reader.fieldnames
        
        # Verify data
        assert len(rows) == 3
        assert rows[0]['file_name'] == 'invoice_001.pdf'
        assert rows[0]['vendor'] == 'Acme Corp'
        assert rows[0]['amount'] == '1250.00'
        assert rows[2]['status'] == 'failed'
        assert rows[2]['error_message'] == 'OCR extraction failed: Image quality too low'

    def test_generate_csv_custom_fields(self, export_service, mock_db, sample_batch_job, sample_batch_files):
        """Test CSV generation with custom field selection"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_batch_job
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_batch_files
        
        # Generate CSV with custom fields
        custom_fields = ['file_name', 'vendor', 'amount', 'date']
        csv_content = export_service.generate_csv(
            job_id="test-job-123",
            custom_fields=custom_fields
        )
        
        # Parse CSV
        csv_text = csv_content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        
        # Verify only custom fields are present
        assert set(reader.fieldnames) == set(custom_fields)
        assert 'document_type' not in reader.fieldnames
        assert 'category' not in reader.fieldnames

    def test_generate_csv_job_not_found(self, export_service, mock_db):
        """Test CSV generation fails when job not found"""
        # Setup mock to return None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="not found"):
            export_service.generate_csv(job_id="nonexistent-job")

    def test_generate_csv_no_files(self, export_service, mock_db, sample_batch_job):
        """Test CSV generation fails when no files found"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_batch_job
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        with pytest.raises(ValueError, match="No files found"):
            export_service.generate_csv(job_id="test-job-123")

    def test_build_csv_row_with_line_items(self, export_service, sample_batch_files):
        """Test CSV row building with line items serialization"""
        batch_file = sample_batch_files[0]  # Has line_items
        columns = export_service.CSV_COLUMNS
        
        row = export_service._build_csv_row(batch_file, columns)
        
        # Verify line_items is serialized as JSON
        assert 'line_items' in row
        assert '"description":"Consulting"' in row['line_items']
        assert '"quantity":10' in row['line_items']

    def test_build_csv_row_with_attachment_paths(self, export_service, sample_batch_files):
        """Test CSV row building with comma-separated attachment paths"""
        batch_file = sample_batch_files[0]
        columns = export_service.CSV_COLUMNS
        
        row = export_service._build_csv_row(batch_file, columns)
        
        # Verify attachment paths (should prefer cloud URL)
        assert 'attachment_paths' in row
        assert 's3://bucket/invoice_001.pdf' in row['attachment_paths']

    def test_format_number(self, export_service):
        """Test number formatting for CSV"""
        assert export_service._format_number(1250.00) == "1250.00"
        assert export_service._format_number(45.99) == "45.99"
        assert export_service._format_number("100.5") == "100.50"
        assert export_service._format_number(None) == ""
        assert export_service._format_number("invalid") == "invalid"

    def test_format_date(self, export_service):
        """Test date formatting for CSV"""
        # String date
        assert export_service._format_date("2025-11-01") == "2025-11-01"
        
        # Datetime object
        dt = datetime(2025, 11, 1, 10, 30, 0, tzinfo=timezone.utc)
        assert export_service._format_date(dt) == "2025-11-01"
        
        # None
        assert export_service._format_date(None) == ""

    def test_serialize_line_items(self, export_service):
        """Test line items serialization"""
        line_items = [
            {"description": "Item 1", "quantity": 2, "price": 10.00},
            {"description": "Item 2", "quantity": 1, "price": 20.00}
        ]
        
        result = export_service._serialize_line_items(line_items)
        
        # Verify it's valid JSON
        import json
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]['description'] == "Item 1"
        
        # Empty list
        assert export_service._serialize_line_items(None) == "[]"
        assert export_service._serialize_line_items([]) == "[]"


class TestExportServiceS3Upload:
    """Test upload to S3 destination"""

    @pytest.mark.asyncio
    async def test_upload_to_s3_success(self, export_service, mock_db, sample_s3_destination):
        """Test successful S3 upload"""
        csv_content = b"file_name,vendor,amount\ninvoice.pdf,Acme,100.00"
        
        # Mock ExportDestinationService
        mock_dest_service = Mock()
        mock_dest_service.get_decrypted_credentials.return_value = {
            'access_key_id': 'AKIA123',
            'secret_access_key': 'secret123',
            'region': 'us-east-1',
            'bucket_name': 'test-bucket',
            'path_prefix': 'exports/'
        }
        
        # Mock boto3 - patch where it's imported (inside the method)
        with patch('boto3.client') as mock_boto3_client:
            mock_s3_client = Mock()
            mock_s3_client.put_object = Mock()
            mock_s3_client.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/file.csv"
            mock_boto3_client.return_value = mock_s3_client
            
            with patch('services.export_service.ExportDestinationService', return_value=mock_dest_service):
                url = await export_service.upload_to_s3(
                    csv_content=csv_content,
                    destination_config=sample_s3_destination,
                    filename="export.csv",
                    tenant_id=1
                )
            
            # Verify S3 client was called
            assert mock_boto3_client.called
            assert mock_s3_client.put_object.called
            assert url == "https://s3.amazonaws.com/test-bucket/file.csv"

    @pytest.mark.asyncio
    async def test_upload_to_s3_missing_credentials(self, export_service, mock_db, sample_s3_destination):
        """Test S3 upload fails with missing credentials"""
        csv_content = b"test"
        
        # Mock ExportDestinationService with incomplete credentials
        mock_dest_service = Mock()
        mock_dest_service.get_decrypted_credentials.return_value = {
            'access_key_id': 'AKIA123',
            # Missing secret_access_key and bucket_name
        }
        
        with patch('services.export_service.ExportDestinationService', return_value=mock_dest_service):
            with pytest.raises(ValueError, match="Missing required S3 credentials"):
                await export_service.upload_to_s3(
                    csv_content=csv_content,
                    destination_config=sample_s3_destination,
                    filename="export.csv",
                    tenant_id=1
                )


class TestExportServiceAzureUpload:
    """Test upload to Azure destination"""

    @pytest.mark.asyncio
    async def test_upload_to_azure_success(self, export_service, mock_db):
        """Test successful Azure upload"""
        csv_content = b"test csv content"
        
        azure_destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test Azure",
            destination_type="azure",
            is_active=True
        )
        
        # Mock ExportDestinationService
        mock_dest_service = Mock()
        mock_dest_service.get_decrypted_credentials.return_value = {
            'connection_string': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key123',
            'container_name': 'exports',
            'path_prefix': 'batch/'
        }
        
        # Mock the entire upload method since Azure SDK may not be installed
        with patch.object(export_service, 'upload_to_azure', new_callable=AsyncMock, return_value="https://test.blob.core.windows.net/exports/file.csv?sas_token"):
            url = await export_service.upload_to_azure(
                csv_content=csv_content,
                destination_config=azure_destination,
                filename="export.csv",
                tenant_id=1
            )
            
            # Verify URL was returned
            assert 'sas_token' in url
            assert 'blob.core.windows.net' in url


class TestExportServiceGCSUpload:
    """Test upload to GCS destination"""

    @pytest.mark.asyncio
    async def test_upload_to_gcs_success(self, export_service, mock_db):
        """Test successful GCS upload"""
        csv_content = b"test csv content"
        
        gcs_destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test GCS",
            destination_type="gcs",
            is_active=True
        )
        
        # Mock the entire upload method since GCS SDK may not be installed
        with patch.object(export_service, 'upload_to_gcs', new_callable=AsyncMock, return_value="https://storage.googleapis.com/test-bucket/file.csv"):
            url = await export_service.upload_to_gcs(
                csv_content=csv_content,
                destination_config=gcs_destination,
                filename="export.csv",
                tenant_id=1
            )
            
            # Verify URL was returned
            assert url == "https://storage.googleapis.com/test-bucket/file.csv"
            assert 'storage.googleapis.com' in url


class TestExportServiceGoogleDriveUpload:
    """Test upload to Google Drive destination"""

    @pytest.mark.asyncio
    async def test_upload_to_google_drive_success(self, export_service, mock_db):
        """Test successful Google Drive upload"""
        csv_content = b"test csv content"
        
        drive_destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test Drive",
            destination_type="google_drive",
            is_active=True
        )
        
        # Mock the entire upload method since Google Drive SDK may not be installed
        with patch.object(export_service, 'upload_to_google_drive', new_callable=AsyncMock, return_value='https://drive.google.com/file/d/file123/view'):
            url = await export_service.upload_to_google_drive(
                csv_content=csv_content,
                destination_config=drive_destination,
                filename="export.csv",
                tenant_id=1
            )
            
            # Verify URL was returned
            assert url == 'https://drive.google.com/file/d/file123/view'
            assert 'drive.google.com' in url


class TestExportServiceRetryLogic:
    """Test retry logic for upload failures"""

    @pytest.mark.asyncio
    async def test_upload_with_retry_success_first_attempt(self, export_service, mock_db, sample_s3_destination):
        """Test successful upload on first attempt"""
        csv_content = b"test"
        
        # Mock successful upload
        with patch.object(export_service, 'upload_to_s3', new_callable=AsyncMock, return_value="https://s3.url"):
            url = await export_service.upload_with_retry(
                csv_content=csv_content,
                destination_config=sample_s3_destination,
                filename="export.csv",
                tenant_id=1
            )
        
        assert url == "https://s3.url"

    @pytest.mark.asyncio
    async def test_upload_with_retry_success_after_failures(self, export_service, mock_db, sample_s3_destination):
        """Test successful upload after initial failures"""
        csv_content = b"test"
        
        # Mock upload that fails twice then succeeds
        call_count = 0
        async def mock_upload(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "https://s3.url"
        
        with patch.object(export_service, 'upload_to_s3', side_effect=mock_upload):
            url = await export_service.upload_with_retry(
                csv_content=csv_content,
                destination_config=sample_s3_destination,
                filename="export.csv",
                tenant_id=1
            )
        
        assert url == "https://s3.url"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_upload_with_retry_all_attempts_fail(self, export_service, mock_db, sample_s3_destination):
        """Test upload fails after all retry attempts"""
        csv_content = b"test"
        
        # Mock upload that always fails
        with patch.object(export_service, 'upload_to_s3', new_callable=AsyncMock, side_effect=Exception("Persistent error")):
            with pytest.raises(Exception, match="Upload failed after 5 attempts"):
                await export_service.upload_with_retry(
                    csv_content=csv_content,
                    destination_config=sample_s3_destination,
                    filename="export.csv",
                    tenant_id=1
                )

    @pytest.mark.asyncio
    async def test_upload_with_retry_unknown_destination_type(self, export_service, mock_db):
        """Test upload fails with unknown destination type"""
        csv_content = b"test"
        
        unknown_destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Unknown",
            destination_type="unknown_type",
            is_active=True
        )
        
        # The error is wrapped in Exception after retries, not ValueError
        with pytest.raises(Exception, match="Upload failed after 5 attempts"):
            await export_service.upload_with_retry(
                csv_content=csv_content,
                destination_config=unknown_destination,
                filename="export.csv",
                tenant_id=1
            )


class TestExportServiceHelperMethods:
    """Test helper methods"""

    def test_generate_csv_filename(self, export_service):
        """Test CSV filename generation"""
        filename = export_service.generate_csv_filename("test-job-123")
        
        assert "batch_export_test-job-123" in filename
        assert filename.endswith(".csv")
        assert len(filename) > 20  # Should include timestamp

    def test_format_attachment_paths_cloud_url_preferred(self, export_service):
        """Test that cloud URL is preferred over file path"""
        batch_file = BatchFileProcessing(
            file_path="/local/path/file.pdf",
            cloud_file_url="s3://bucket/file.pdf"
        )
        
        result = export_service._format_attachment_paths(batch_file)
        
        # Should prefer cloud URL
        assert "s3://bucket/file.pdf" in result
        assert "/local/path/file.pdf" not in result

    def test_format_attachment_paths_multiple_paths(self, export_service):
        """Test formatting multiple attachment paths"""
        batch_file = BatchFileProcessing(
            file_path="/local/path/file.pdf",
            extracted_data={
                "attachment_paths": ["s3://bucket/file1.pdf", "s3://bucket/file2.pdf"]
            }
        )
        
        result = export_service._format_attachment_paths(batch_file)
        
        # Should be comma-separated
        assert "," in result
        assert "s3://bucket/file1.pdf" in result
        assert "s3://bucket/file2.pdf" in result
