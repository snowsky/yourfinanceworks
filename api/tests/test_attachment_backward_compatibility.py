"""
Test backward compatibility for attachment service during cloud storage migration.

Tests the mixed storage scenarios and file path resolution functionality
added for task 8.2.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import os

from services.attachment_service import AttachmentService
from models.models_per_tenant import ItemAttachment


class TestAttachmentBackwardCompatibility:
    """Test backward compatibility features for attachment service."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()
    
    @pytest.fixture
    def attachment_service(self, mock_db):
        """Create attachment service instance."""
        with patch('services.attachment_service.get_cloud_storage_config'):
            service = AttachmentService(mock_db)
            service.cloud_storage_service = Mock()
            return service
    
    @pytest.fixture
    def sample_attachment(self):
        """Create sample attachment for testing."""
        attachment = Mock(spec=ItemAttachment)
        attachment.id = 1
        attachment.file_path = "tenant_1/images/test_file.jpg"
        attachment.stored_filename = "test_file.jpg"
        attachment.attachment_type = "image"
        attachment.filename = "original_file.jpg"
        return attachment
    
    def test_is_cloud_storage_path_detection(self, attachment_service):
        """Test detection of cloud storage paths vs local paths."""
        # Cloud storage paths (relative, tenant-scoped)
        assert attachment_service._is_cloud_storage_path("tenant_1/images/file.jpg") == True
        assert attachment_service._is_cloud_storage_path("tenant_2/documents/doc.pdf") == True
        
        # Local storage paths (absolute)
        assert attachment_service._is_cloud_storage_path("/var/uploads/file.jpg") == False
        assert attachment_service._is_cloud_storage_path("/home/user/attachments/file.jpg") == False
        
        # Windows paths
        assert attachment_service._is_cloud_storage_path("C:\\uploads\\file.jpg") == False
        assert attachment_service._is_cloud_storage_path("D:\\data\\file.jpg") == False
        
        # Edge cases
        assert attachment_service._is_cloud_storage_path("") == False
        assert attachment_service._is_cloud_storage_path(None) == False
    
    @pytest.mark.asyncio
    async def test_generate_local_file_url(self, attachment_service, sample_attachment):
        """Test local file URL generation with backward compatibility."""
        with patch.object(attachment_service, '_get_tenant_context', return_value="1"):
            url = await attachment_service._generate_local_file_url(sample_attachment, "1")
            
            assert url is not None
            assert "/api/v1/files/serve/" in url
            assert "tenant_1" in url
    
    @pytest.mark.asyncio
    async def test_check_local_file_exists_multiple_paths(self, attachment_service, sample_attachment):
        """Test local file existence check with multiple possible paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file in one of the possible locations
            test_file_path = Path(temp_dir) / "tenant_1" / "images" / "test_file.jpg"
            test_file_path.parent.mkdir(parents=True, exist_ok=True)
            test_file_path.write_text("test content")
            
            with patch('config.config.UPLOAD_PATH', temp_dir):
                exists = await attachment_service._check_local_file_exists(sample_attachment, "1")
                assert exists == True
    
    @pytest.mark.asyncio
    async def test_get_file_url_cloud_with_local_fallback(self, attachment_service, sample_attachment):
        """Test file URL generation with cloud storage and local fallback."""
        # Mock cloud storage service to fail
        attachment_service.cloud_storage_service.retrieve_file = AsyncMock(
            return_value=Mock(success=False, error_message="Cloud unavailable")
        )
        
        with patch.object(attachment_service, 'get_attachment_by_id', return_value=sample_attachment):
            with patch.object(attachment_service, '_get_tenant_context', return_value="1"):
                with patch.object(attachment_service, '_generate_local_file_url', return_value="http://localhost/file"):
                    url = await attachment_service.get_file_url(1, 123)
                    
                    assert url == "http://localhost/file"
    
    @pytest.mark.asyncio
    async def test_detect_migration_status(self, attachment_service):
        """Test migration status detection."""
        # Mock database query to return sample attachments
        mock_attachments = [
            Mock(file_path="tenant_1/images/cloud_file.jpg"),  # Cloud file
            Mock(file_path="/local/path/local_file.jpg"),      # Local file
        ]
        
        attachment_service.db.query.return_value.filter.return_value.all.return_value = mock_attachments
        
        with patch.object(attachment_service, '_get_tenant_context', return_value="1"):
            with patch.object(attachment_service, '_check_local_file_exists', return_value=False):
                status = await attachment_service.detect_migration_status()
                
                assert 'total_attachments' in status
                assert 'cloud_only' in status
                assert 'local_only' in status
                assert 'mixed_storage' in status
                assert status['total_attachments'] == 2
    
    @pytest.mark.asyncio
    async def test_delete_file_from_all_storage(self, attachment_service, sample_attachment):
        """Test file deletion from both cloud and local storage."""
        # Mock cloud storage deletion
        attachment_service.cloud_storage_service.delete_file = AsyncMock(return_value=True)
        
        with patch.object(attachment_service, '_delete_local_file', return_value=True):
            success = await attachment_service._delete_file_from_all_storage(sample_attachment, "1", 123)
            
            assert success == True
            attachment_service.cloud_storage_service.delete_file.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resolve_file_path(self, attachment_service, sample_attachment):
        """Test file path resolution for debugging."""
        # Mock cloud storage check
        attachment_service.cloud_storage_service.file_exists = AsyncMock(
            return_value=(True, "aws_s3")
        )
        
        with patch.object(attachment_service, 'get_attachment_by_id', return_value=sample_attachment):
            with patch.object(attachment_service, '_get_tenant_context', return_value="1"):
                with patch.object(attachment_service, '_check_local_file_exists', return_value=False):
                    resolution = await attachment_service.resolve_file_path(1)
                    
                    assert resolution is not None
                    assert resolution['attachment_id'] == 1
                    assert resolution['is_cloud_storage_path'] == True
                    assert resolution['status'] == 'cloud_only'
                    assert 'storage_locations' in resolution
    
    def test_convert_local_path_to_key(self, attachment_service):
        """Test conversion of local paths to file keys."""
        with patch('config.config.UPLOAD_PATH', '/var/uploads'):
            # Test relative path conversion
            key = attachment_service._convert_local_path_to_key(
                '/var/uploads/tenant_1/images/file.jpg', '1'
            )
            assert key == 'tenant_1/images/file.jpg'
            
            # Test path with tenant directory
            key = attachment_service._convert_local_path_to_key(
                '/some/other/path/tenant_2/documents/doc.pdf', '2'
            )
            assert key == 'tenant_2/documents/doc.pdf'