"""
Unit tests for Report History Service

Tests report history tracking, file management, and cleanup operations.
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from services.report_history_service import ReportHistoryService, ReportHistoryError
from models.models_per_tenant import ReportHistory
from schemas.report import ReportStatus, ExportFormat


class TestReportHistoryService:
    """Test cases for ReportHistoryService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def temp_storage(self):
        """Temporary storage directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def history_service(self, mock_db, temp_storage):
        """ReportHistoryService instance with mocked dependencies"""
        return ReportHistoryService(mock_db, temp_storage)
    
    @pytest.fixture
    def sample_report_history(self):
        """Sample ReportHistory instance"""
        return ReportHistory(
            id=1,
            report_type="invoice",
            parameters={"filters": {"date_from": "2024-01-01"}},
            status=ReportStatus.PENDING,
            generated_by=1,
            template_id=None,
            file_path=None,
            generated_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=30)
        )
    
    def test_create_report_history_success(self, history_service, mock_db):
        """Test successful report history creation"""
        # Arrange
        mock_report = Mock()
        mock_report.id = 1
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Mock the ReportHistory constructor
        with patch('services.report_history_service.ReportHistory') as mock_history_class:
            mock_history_class.return_value = mock_report
            
            # Act
            result = history_service.create_report_history(
                report_type="invoice",
                parameters={"filters": {}},
                user_id=1,
                template_id=None,
                expires_in_days=30
            )
            
            # Assert
            assert result == mock_report
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once_with(mock_report)
    
    def test_create_report_history_database_error(self, history_service, mock_db):
        """Test report history creation with database error"""
        # Arrange
        mock_db.add.side_effect = Exception("Database error")
        
        # Act & Assert
        with pytest.raises(ReportHistoryError, match="Failed to create report history"):
            history_service.create_report_history(
                report_type="invoice",
                parameters={"filters": {}},
                user_id=1
            )
        
        mock_db.rollback.assert_called_once()
    
    def test_update_report_status_success(self, history_service, mock_db, sample_report_history):
        """Test successful report status update"""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = sample_report_history
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Act
        result = history_service.update_report_status(
            report_id=1,
            status=ReportStatus.COMPLETED,
            file_path="/path/to/file.pdf",
            error_message=None
        )
        
        # Assert
        assert result == sample_report_history
        assert sample_report_history.status == ReportStatus.COMPLETED
        assert sample_report_history.file_path == "/path/to/file.pdf"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_report_history)
    
    def test_update_report_status_not_found(self, history_service, mock_db):
        """Test report status update when report not found"""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Act & Assert
        with pytest.raises(ReportHistoryError, match="Report history not found"):
            history_service.update_report_status(
                report_id=999,
                status=ReportStatus.COMPLETED
            )
    
    def test_get_report_history_success(self, history_service, mock_db, sample_report_history):
        """Test successful report history retrieval"""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = sample_report_history
        
        # Act
        result = history_service.get_report_history(report_id=1, user_id=1)
        
        # Assert
        assert result == sample_report_history
    
    def test_get_report_history_not_found(self, history_service, mock_db):
        """Test report history retrieval when not found"""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Act
        result = history_service.get_report_history(report_id=999, user_id=1)
        
        # Assert
        assert result is None
    
    def test_list_user_reports_success(self, history_service, mock_db, sample_report_history):
        """Test successful user reports listing"""
        # Arrange
        mock_query = Mock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [sample_report_history]
        
        # Act
        result = history_service.list_user_reports(
            user_id=1,
            report_type="invoice",
            status=ReportStatus.COMPLETED,
            limit=10,
            offset=0
        )
        
        # Assert
        assert result == [sample_report_history]
    
    def test_count_user_reports_success(self, history_service, mock_db):
        """Test successful user reports counting"""
        # Arrange
        mock_query = Mock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        
        # Act
        result = history_service.count_user_reports(
            user_id=1,
            report_type="invoice",
            status=ReportStatus.COMPLETED
        )
        
        # Assert
        assert result == 5
    
    def test_store_report_file_success(self, history_service, mock_db, temp_storage):
        """Test successful report file storage"""
        # Arrange
        file_content = b"PDF content here"
        mock_db.query.return_value.filter.return_value.first.return_value = Mock()
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Act
        with patch.object(history_service, 'update_report_status') as mock_update:
            result = history_service.store_report_file(
                report_id=1,
                file_content=file_content,
                export_format=ExportFormat.PDF,
                filename_prefix="test_report"
            )
        
        # Assert
        assert result is not None
        assert os.path.exists(result)
        assert result.endswith('.pdf')
        
        # Check file content
        with open(result, 'rb') as f:
            assert f.read() == file_content
        
        # Check that status was updated
        mock_update.assert_called_once()
    
    def test_store_report_file_write_error(self, history_service, temp_storage):
        """Test report file storage with write error"""
        # Arrange
        file_content = b"PDF content here"
        
        # Make storage directory read-only to cause write error
        os.chmod(temp_storage, 0o444)
        
        # Act & Assert
        with pytest.raises(ReportHistoryError, match="Failed to store report file"):
            history_service.store_report_file(
                report_id=1,
                file_content=file_content,
                export_format=ExportFormat.PDF
            )
        
        # Restore permissions for cleanup
        os.chmod(temp_storage, 0o755)
    
    def test_get_report_file_path_success(self, history_service, mock_db, sample_report_history, temp_storage):
        """Test successful report file path retrieval"""
        # Arrange
        test_file = os.path.join(temp_storage, "test_report.pdf")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        sample_report_history.status = ReportStatus.COMPLETED
        sample_report_history.file_path = test_file
        sample_report_history.expires_at = datetime.now() + timedelta(days=1)  # Not expired
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_report_history
        
        # Act
        result = history_service.get_report_file_path(report_id=1, user_id=1)
        
        # Assert
        assert result == test_file
    
    def test_get_report_file_path_expired(self, history_service, mock_db, sample_report_history, temp_storage):
        """Test report file path retrieval for expired report"""
        # Arrange
        test_file = os.path.join(temp_storage, "test_report.pdf")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        sample_report_history.status = ReportStatus.COMPLETED
        sample_report_history.file_path = test_file
        sample_report_history.expires_at = datetime.now() - timedelta(days=1)  # Expired
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_report_history
        
        # Act
        result = history_service.get_report_file_path(report_id=1, user_id=1)
        
        # Assert
        assert result is None
    
    def test_get_report_file_path_not_completed(self, history_service, mock_db, sample_report_history):
        """Test report file path retrieval for non-completed report"""
        # Arrange
        sample_report_history.status = ReportStatus.PENDING
        mock_db.query.return_value.filter.return_value.first.return_value = sample_report_history
        
        # Act
        result = history_service.get_report_file_path(report_id=1, user_id=1)
        
        # Assert
        assert result is None
    
    def test_delete_report_file_success(self, history_service, mock_db, sample_report_history, temp_storage):
        """Test successful report file deletion"""
        # Arrange
        test_file = os.path.join(temp_storage, "test_report.pdf")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        sample_report_history.file_path = test_file
        mock_db.query.return_value.filter.return_value.first.return_value = sample_report_history
        mock_db.commit.return_value = None
        
        # Act
        result = history_service.delete_report_file(report_id=1, user_id=1)
        
        # Assert
        assert result is True
        assert not os.path.exists(test_file)
        assert sample_report_history.file_path is None
        mock_db.commit.assert_called_once()
    
    def test_delete_report_file_not_found(self, history_service, mock_db):
        """Test report file deletion when report not found"""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Act
        result = history_service.delete_report_file(report_id=999, user_id=1)
        
        # Assert
        assert result is False
    
    def test_cleanup_expired_reports_success(self, history_service, mock_db, temp_storage):
        """Test successful cleanup of expired reports"""
        # Arrange
        expired_report1 = Mock()
        expired_report1.id = 1
        expired_report1.file_path = os.path.join(temp_storage, "expired1.pdf")
        
        expired_report2 = Mock()
        expired_report2.id = 2
        expired_report2.file_path = os.path.join(temp_storage, "expired2.pdf")
        
        # Create test files
        with open(expired_report1.file_path, 'w') as f:
            f.write("expired content 1")
        with open(expired_report2.file_path, 'w') as f:
            f.write("expired content 2")
        
        mock_db.query.return_value.filter.return_value.all.return_value = [expired_report1, expired_report2]
        mock_db.commit.return_value = None
        
        # Act
        result = history_service.cleanup_expired_reports()
        
        # Assert
        assert result["expired_reports_found"] == 2
        assert result["files_deleted"] == 2
        assert result["records_updated"] == 2
        assert result["errors"] == 0
        
        # Check files were deleted
        assert not os.path.exists(expired_report1.file_path)
        assert not os.path.exists(expired_report2.file_path)
        
        # Check file paths were cleared
        assert expired_report1.file_path is None
        assert expired_report2.file_path is None
    
    def test_cleanup_orphaned_files_success(self, history_service, mock_db, temp_storage):
        """Test successful cleanup of orphaned files"""
        # Arrange
        # Create some test files
        orphaned_file = os.path.join(temp_storage, "report_orphaned.pdf")
        valid_file = os.path.join(temp_storage, "report_valid.pdf")
        non_report_file = os.path.join(temp_storage, "other_file.txt")
        
        with open(orphaned_file, 'w') as f:
            f.write("orphaned content")
        with open(valid_file, 'w') as f:
            f.write("valid content")
        with open(non_report_file, 'w') as f:
            f.write("other content")
        
        # Mock database to return only the valid file
        mock_report = Mock()
        mock_report.file_path = valid_file
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_report]
        
        # Act
        result = history_service.cleanup_orphaned_files()
        
        # Assert
        assert result["files_deleted"] == 1
        assert result["errors"] == 0
        
        # Check that orphaned report file was deleted but others remain
        assert not os.path.exists(orphaned_file)
        assert os.path.exists(valid_file)
        assert os.path.exists(non_report_file)  # Non-report files should be left alone
    
    def test_get_storage_stats_success(self, history_service, mock_db, temp_storage):
        """Test successful storage statistics retrieval"""
        # Arrange
        # Create test files
        test_file1 = os.path.join(temp_storage, "report1.pdf")
        test_file2 = os.path.join(temp_storage, "report2.csv")
        
        with open(test_file1, 'w') as f:
            f.write("content1" * 100)  # Make it a bit larger
        with open(test_file2, 'w') as f:
            f.write("content2" * 50)
        
        # Mock database queries
        mock_db.query.return_value.count.side_effect = [10, 5, 2]  # total, with_files, expired
        
        # Act
        result = history_service.get_storage_stats()
        
        # Assert
        assert result["total_reports"] == 10
        assert result["reports_with_files"] == 5
        assert result["expired_reports"] == 2
        assert result["total_file_size"] > 0
        assert result["total_file_size_mb"] > 0
        assert result["storage_path"] == temp_storage
    
    def test_get_file_extension_mapping(self, history_service):
        """Test file extension mapping for different export formats"""
        # Test all export formats
        assert history_service._get_file_extension(ExportFormat.PDF) == "pdf"
        assert history_service._get_file_extension(ExportFormat.CSV) == "csv"
        assert history_service._get_file_extension(ExportFormat.EXCEL) == "xlsx"
        assert history_service._get_file_extension(ExportFormat.JSON) == "json"
    
    def test_regenerate_report_success(self, history_service, mock_db, sample_report_history):
        """Test successful report regeneration"""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = sample_report_history
        
        new_report = Mock()
        new_report.id = 2
        
        with patch.object(history_service, 'create_report_history', return_value=new_report) as mock_create:
            # Act
            result = history_service.regenerate_report(
                report_id=1,
                user_id=1,
                new_parameters={"filters": {"updated": True}}
            )
            
            # Assert
            assert result == new_report
            mock_create.assert_called_once()
            
            # Check that parameters were merged
            call_args = mock_create.call_args
            merged_params = call_args[1]["parameters"]
            assert merged_params["filters"]["updated"] is True
    
    def test_regenerate_report_not_found(self, history_service, mock_db):
        """Test report regeneration when original report not found"""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Act & Assert
        with pytest.raises(ReportHistoryError, match="Original report not found"):
            history_service.regenerate_report(report_id=999, user_id=1)


class TestReportHistoryServiceIntegration:
    """Integration tests for ReportHistoryService with real database operations"""
    
    @pytest.fixture
    def db_session(self):
        """Real database session for integration tests"""
        # This would use your actual test database setup
        # For now, we'll skip these tests in unit test runs
        pytest.skip("Integration tests require database setup")
    
    def test_full_report_lifecycle(self, db_session):
        """Test complete report lifecycle from creation to cleanup"""
        # This would test the full lifecycle with a real database
        pass
    
    def test_concurrent_access(self, db_session):
        """Test concurrent access to report files"""
        # This would test thread safety and concurrent file operations
        pass
    
    def test_large_file_handling(self, db_session):
        """Test handling of large report files"""
        # This would test performance with large files
        pass