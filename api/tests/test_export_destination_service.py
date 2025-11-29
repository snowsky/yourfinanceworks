"""
Unit tests for ExportDestinationService.

Tests credential encryption/decryption, connection testing for each provider,
and fallback to environment variables.
"""

import pytest
import json
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session

from core.services.export_destination_service import ExportDestinationService
from core.models.models_per_tenant import ExportDestinationConfig
from core.exceptions.encryption_exceptions import EncryptionError, DecryptionError


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def mock_encryption_service():
    """Create a mock encryption service"""
    mock_service = Mock()
    mock_service.encrypt_data.return_value = b"encrypted_credentials"
    mock_service.decrypt_data.return_value = json.dumps({
        "access_key_id": "AKIA123",
        "secret_access_key": "secret123",
        "region": "us-east-1",
        "bucket_name": "test-bucket"
    })
    return mock_service


@pytest.fixture
def destination_service(mock_db, mock_encryption_service):
    """Create ExportDestinationService instance with mocks"""
    with patch('services.export_destination_service.KeyManagementService'):
        with patch('services.export_destination_service.EncryptionService', return_value=mock_encryption_service):
            service = ExportDestinationService(mock_db, tenant_id=1)
            service.encryption_service = mock_encryption_service
            return service


@pytest.fixture
def sample_s3_credentials():
    """Sample S3 credentials"""
    return {
        "access_key_id": "AKIA123456789",
        "secret_access_key": "secret_key_123",
        "region": "us-east-1",
        "bucket_name": "test-bucket",
        "path_prefix": "exports/"
    }


@pytest.fixture
def sample_azure_credentials():
    """Sample Azure credentials"""
    return {
        "connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key123",
        "container_name": "exports",
        "path_prefix": "batch/"
    }


@pytest.fixture
def sample_gcs_credentials():
    """Sample GCS credentials"""
    return {
        "service_account_json": json.dumps({
            "type": "service_account",
            "project_id": "test-project",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n"
        }),
        "bucket_name": "test-bucket",
        "path_prefix": "exports/"
    }


class TestExportDestinationServiceCredentialEncryption:
    """Test credential encryption and decryption"""

    def test_create_destination_encrypts_credentials(self, destination_service, mock_db, mock_encryption_service, sample_s3_credentials):
        """Test that credentials are encrypted when creating destination"""
        # Setup mock
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Create destination
        destination = destination_service.create_destination(
            name="Test S3",
            destination_type="s3",
            credentials=sample_s3_credentials,
            user_id=1
        )
        
        # Verify encryption was called
        mock_encryption_service.encrypt_data.assert_called_once()
        call_args = mock_encryption_service.encrypt_data.call_args
        assert json.loads(call_args[0][0]) == sample_s3_credentials
        assert call_args[0][1] == 1  # tenant_id
        
        # Verify destination was added to db
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_update_destination_re_encrypts_credentials(self, destination_service, mock_db, mock_encryption_service, sample_s3_credentials):
        """Test that credentials are re-encrypted when updating destination"""
        # Create existing destination
        existing_destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test S3",
            destination_type="s3",
            encrypted_credentials=b"old_encrypted_data"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = existing_destination
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Update with new credentials
        new_credentials = {**sample_s3_credentials, "bucket_name": "new-bucket"}
        destination_service.update_destination(
            destination_id=1,
            updates={"credentials": new_credentials}
        )
        
        # Verify re-encryption was called
        assert mock_encryption_service.encrypt_data.called
        call_args = mock_encryption_service.encrypt_data.call_args
        assert json.loads(call_args[0][0]) == new_credentials

    def test_get_decrypted_credentials_success(self, destination_service, mock_db, mock_encryption_service):
        """Test successful credential decryption"""
        # Create destination with encrypted credentials
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test S3",
            destination_type="s3",
            encrypted_credentials=b"encrypted_data"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        
        # Get decrypted credentials
        credentials = destination_service.get_decrypted_credentials(destination_id=1)
        
        # Verify decryption was called
        mock_encryption_service.decrypt_data.assert_called_once_with(
            b"encrypted_data",
            1  # tenant_id
        )
        
        # Verify credentials were returned
        assert "access_key_id" in credentials
        assert credentials["access_key_id"] == "AKIA123"

    def test_get_decrypted_credentials_destination_not_found(self, destination_service, mock_db):
        """Test error when destination not found"""
        # Setup mock to return None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="not found"):
            destination_service.get_decrypted_credentials(destination_id=999)

    def test_get_decrypted_credentials_decryption_fails(self, destination_service, mock_db, mock_encryption_service):
        """Test error handling when decryption fails"""
        # Create destination
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test S3",
            destination_type="s3",
            encrypted_credentials=b"corrupted_data"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        mock_encryption_service.decrypt_data.side_effect = DecryptionError("Decryption failed")
        
        with pytest.raises(DecryptionError):
            destination_service.get_decrypted_credentials(destination_id=1)

    def test_mask_credentials(self, destination_service, sample_s3_credentials):
        """Test credential masking for API responses"""
        masked = destination_service.mask_credentials(sample_s3_credentials)
        
        # Verify all values are masked
        assert masked["access_key_id"] == "****6789"
        assert masked["secret_access_key"] == "****_123"
        assert masked["bucket_name"] == "****cket"
        
        # Short values should be completely masked
        short_creds = {"key": "abc"}
        masked_short = destination_service.mask_credentials(short_creds)
        assert masked_short["key"] == "****"


class TestExportDestinationServiceEnvironmentFallback:
    """Test fallback to environment variables"""

    def test_s3_fallback_to_environment_variables(self, destination_service, mock_db):
        """Test S3 credentials fallback to environment variables"""
        # Create destination without credentials
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test S3",
            destination_type="s3",
            encrypted_credentials=None
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'env_access_key',
            'AWS_SECRET_ACCESS_KEY': 'env_secret_key',
            'AWS_REGION': 'us-west-2',
            'AWS_S3_BUCKET': 'env-bucket',
            'AWS_S3_PATH_PREFIX': 'env-prefix/'
        }):
            credentials = destination_service.get_decrypted_credentials(destination_id=1)
        
        # Verify fallback credentials
        assert credentials["access_key_id"] == "env_access_key"
        assert credentials["secret_access_key"] == "env_secret_key"
        assert credentials["region"] == "us-west-2"
        assert credentials["bucket_name"] == "env-bucket"
        assert credentials["path_prefix"] == "env-prefix/"

    def test_s3_fallback_missing_environment_variables(self, destination_service, mock_db):
        """Test error when S3 environment variables are missing"""
        # Create destination without credentials
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test S3",
            destination_type="s3",
            encrypted_credentials=None
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        
        # Mock environment with missing variables
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'env_access_key',
            # Missing AWS_SECRET_ACCESS_KEY and AWS_S3_BUCKET
        }, clear=True):
            with pytest.raises(ValueError, match="Missing required S3 environment variables"):
                destination_service.get_decrypted_credentials(destination_id=1)

    def test_azure_fallback_to_environment_variables(self, destination_service, mock_db):
        """Test Azure credentials fallback to environment variables"""
        # Create destination without credentials
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test Azure",
            destination_type="azure",
            encrypted_credentials=None
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test',
            'AZURE_STORAGE_CONTAINER': 'env-container',
            'AZURE_STORAGE_PATH_PREFIX': 'env-prefix/'
        }):
            credentials = destination_service.get_decrypted_credentials(destination_id=1)
        
        # Verify fallback credentials
        assert credentials["connection_string"] == 'DefaultEndpointsProtocol=https;AccountName=test'
        assert credentials["container_name"] == "env-container"

    def test_gcs_fallback_to_environment_variables(self, destination_service, mock_db):
        """Test GCS credentials fallback to environment variables"""
        # Create destination without credentials
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test GCS",
            destination_type="gcs",
            encrypted_credentials=None
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        
        # Create temporary service account file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"type": "service_account", "project_id": "test"}, f)
            temp_file = f.name
        
        try:
            # Mock environment variables
            with patch.dict(os.environ, {
                'GOOGLE_APPLICATION_CREDENTIALS': temp_file,
                'GCS_BUCKET_NAME': 'env-bucket',
                'GCS_PATH_PREFIX': 'env-prefix/'
            }):
                credentials = destination_service.get_decrypted_credentials(destination_id=1)
            
            # Verify fallback credentials
            assert "service_account_json" in credentials
            assert credentials["bucket_name"] == "env-bucket"
        finally:
            # Clean up temp file
            os.unlink(temp_file)

    def test_google_drive_no_fallback(self, destination_service, mock_db):
        """Test that Google Drive does not support environment fallback"""
        # Create destination without credentials
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test Drive",
            destination_type="google_drive",
            encrypted_credentials=None
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        
        with pytest.raises(ValueError, match="does not support environment variable fallback"):
            destination_service.get_decrypted_credentials(destination_id=1)


class TestExportDestinationServiceConnectionTesting:
    """Test connection testing for each provider"""

    @pytest.mark.asyncio
    async def test_s3_connection_test_success(self, destination_service, mock_db):
        """Test successful S3 connection test"""
        # Create destination
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test S3",
            destination_type="s3",
            encrypted_credentials=b"encrypted"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        mock_db.commit = Mock()
        
        # Mock get_decrypted_credentials
        with patch.object(destination_service, 'get_decrypted_credentials', return_value={
            'access_key_id': 'AKIA123',
            'secret_access_key': 'secret',
            'region': 'us-east-1',
            'bucket_name': 'test-bucket'
        }):
            # Mock boto3 - patch where it's imported
            with patch('boto3.client') as mock_boto3_client:
                mock_s3_client = Mock()
                mock_s3_client.list_objects_v2.return_value = {}
                mock_boto3_client.return_value = mock_s3_client
                
                success, error = await destination_service.test_connection(destination_id=1)
        
        # Verify success
        assert success is True
        assert error is None
        assert destination.last_test_success is True
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_s3_connection_test_failure(self, destination_service, mock_db):
        """Test S3 connection test failure"""
        # Create destination
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test S3",
            destination_type="s3",
            encrypted_credentials=b"encrypted"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        mock_db.commit = Mock()
        
        # Mock get_decrypted_credentials
        with patch.object(destination_service, 'get_decrypted_credentials', return_value={
            'access_key_id': 'AKIA123',
            'secret_access_key': 'secret',
            'region': 'us-east-1',
            'bucket_name': 'test-bucket'
        }):
            # Mock boto3 to raise error - patch where it's imported
            with patch('boto3.client') as mock_boto3_client:
                from botocore.exceptions import ClientError
                mock_s3_client = Mock()
                mock_s3_client.list_objects_v2.side_effect = ClientError(
                    {'Error': {'Code': 'NoSuchBucket', 'Message': 'Bucket not found'}},
                    'ListObjectsV2'
                )
                mock_boto3_client.return_value = mock_s3_client
                
                success, error = await destination_service.test_connection(destination_id=1)
        
        # Verify failure
        assert success is False
        assert "NoSuchBucket" in error
        assert destination.last_test_success is False
        assert destination.last_test_error is not None

    @pytest.mark.asyncio
    async def test_azure_connection_test_success(self, destination_service, mock_db):
        """Test successful Azure connection test"""
        # Create destination
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test Azure",
            destination_type="azure",
            encrypted_credentials=b"encrypted"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        mock_db.commit = Mock()
        
        # Mock the entire test method since Azure SDK may not be installed
        with patch.object(destination_service, '_test_azure_connection', new_callable=AsyncMock, return_value=(True, None)):
            with patch.object(destination_service, 'get_decrypted_credentials', return_value={
                'connection_string': 'DefaultEndpointsProtocol=https;AccountName=test',
                'container_name': 'test-container'
            }):
                success, error = await destination_service.test_connection(destination_id=1)
        
        # Verify success
        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_gcs_connection_test_success(self, destination_service, mock_db):
        """Test successful GCS connection test"""
        # Create destination
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test GCS",
            destination_type="gcs",
            encrypted_credentials=b"encrypted"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        mock_db.commit = Mock()
        
        # Mock the entire test method since GCS SDK may not be installed
        with patch.object(destination_service, '_test_gcs_connection', new_callable=AsyncMock, return_value=(True, None)):
            with patch.object(destination_service, 'get_decrypted_credentials', return_value={
                'service_account_json': '{"type": "service_account", "project_id": "test"}',
                'bucket_name': 'test-bucket'
            }):
                success, error = await destination_service.test_connection(destination_id=1)
        
        # Verify success
        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_google_drive_connection_test_success(self, destination_service, mock_db):
        """Test successful Google Drive connection test"""
        # Create destination
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test Drive",
            destination_type="google_drive",
            encrypted_credentials=b"encrypted"
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        mock_db.commit = Mock()
        
        # Mock the entire test method since Google Drive SDK may not be installed
        with patch.object(destination_service, '_test_google_drive_connection', new_callable=AsyncMock, return_value=(True, None)):
            with patch.object(destination_service, 'get_decrypted_credentials', return_value={
                'oauth_token': 'token123',
                'refresh_token': 'refresh123',
                'folder_id': 'folder123'
            }):
                success, error = await destination_service.test_connection(destination_id=1)
        
        # Verify success
        assert success is True
        assert error is None


class TestExportDestinationServiceCRUD:
    """Test CRUD operations"""

    def test_create_destination_invalid_type(self, destination_service, mock_db):
        """Test error when creating destination with invalid type"""
        with pytest.raises(ValueError, match="Invalid destination type"):
            destination_service.create_destination(
                name="Test",
                destination_type="invalid_type",
                credentials={}
            )

    def test_create_destination_sets_default(self, destination_service, mock_db):
        """Test that creating default destination unsets other defaults"""
        # Setup mock
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.update = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Create default destination
        destination_service.create_destination(
            name="Test S3",
            destination_type="s3",
            credentials={"access_key_id": "test"},
            is_default=True
        )
        
        # Verify other defaults were unset
        assert mock_query.filter.return_value.update.called

    def test_list_destinations_tenant_isolation(self, destination_service, mock_db):
        """Test that list_destinations filters by tenant_id"""
        # Setup mock
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        
        # List destinations
        destination_service.list_destinations()
        
        # Verify tenant filter was applied
        assert mock_query.filter.called

    def test_delete_destination_soft_delete(self, destination_service, mock_db):
        """Test that delete performs soft delete"""
        # Create destination
        destination = ExportDestinationConfig(
            id=1,
            tenant_id=1,
            name="Test S3",
            destination_type="s3",
            is_active=True
        )
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = destination
        mock_db.commit = Mock()
        
        # Delete destination
        result = destination_service.delete_destination(destination_id=1)
        
        # Verify soft delete
        assert result is True
        assert destination.is_active is False
        assert mock_db.commit.called

    def test_get_destination_tenant_isolation(self, destination_service, mock_db):
        """Test that get_destination enforces tenant isolation"""
        # Setup mock
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        
        # Get destination
        result = destination_service.get_destination(destination_id=1)
        
        # Verify tenant filter was applied
        assert mock_query.filter.called
        assert result is None
