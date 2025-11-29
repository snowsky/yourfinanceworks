"""
Unit tests for Report Cleanup Service

Tests automatic cleanup operations and monitoring functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from core.services.report_cleanup_service import ReportCleanupService, run_scheduled_cleanup, run_weekly_cleanup
from core.services.report_history_service import ReportHistoryError


class TestReportCleanupService:
    """Test cases for ReportCleanupService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def mock_history_service(self):
        """Mock ReportHistoryService"""
        return Mock()
    
    @pytest.fixture
    def cleanup_service(self, mock_db, mock_history_service):
        """ReportCleanupService instance with mocked dependencies"""
        service = ReportCleanupService(mock_db)
        service.history_service = mock_history_service
        return service
    
    def test_run_daily_cleanup_success(self, cleanup_service, mock_history_service):
        """Test successful daily cleanup operation"""
        # Arrange
        expired_stats = {
            "expired_reports_found": 5,
            "files_deleted": 4,
            "records_updated": 5,
            "errors": 0
        }
        orphaned_stats = {
            "files_deleted": 2,
            "errors": 0
        }
        
        mock_history_service.cleanup_expired_reports.return_value = expired_stats
        mock_history_service.cleanup_orphaned_files.return_value = orphaned_stats
        
        # Act
        result = cleanup_service.run_daily_cleanup()
        
        # Assert
        assert result["expired_cleanup"] == expired_stats
        assert result["orphaned_cleanup"] == orphaned_stats
        assert len(result["errors"]) == 0
        assert "started_at" in result
        assert "completed_at" in result
        assert "duration_seconds" in result
        
        # Verify service methods were called
        mock_history_service.cleanup_expired_reports.assert_called_once()
        mock_history_service.cleanup_orphaned_files.assert_called_once()
    
    def test_run_daily_cleanup_with_expired_error(self, cleanup_service, mock_history_service):
        """Test daily cleanup with expired reports cleanup error"""
        # Arrange
        mock_history_service.cleanup_expired_reports.side_effect = ReportHistoryError("Cleanup failed")
        mock_history_service.cleanup_orphaned_files.return_value = {"files_deleted": 1, "errors": 0}
        
        # Act
        result = cleanup_service.run_daily_cleanup()
        
        # Assert
        assert len(result["errors"]) == 1
        assert "Failed to cleanup expired reports" in result["errors"][0]
        assert "orphaned_cleanup" in result  # Should still run orphaned cleanup
    
    def test_run_daily_cleanup_with_orphaned_error(self, cleanup_service, mock_history_service):
        """Test daily cleanup with orphaned files cleanup error"""
        # Arrange
        mock_history_service.cleanup_expired_reports.return_value = {"files_deleted": 2, "errors": 0}
        mock_history_service.cleanup_orphaned_files.side_effect = ReportHistoryError("Orphaned cleanup failed")
        
        # Act
        result = cleanup_service.run_daily_cleanup()
        
        # Assert
        assert len(result["errors"]) == 1
        assert "Failed to cleanup orphaned files" in result["errors"][0]
        assert "expired_cleanup" in result  # Should still run expired cleanup
    
    def test_run_weekly_cleanup_success(self, cleanup_service, mock_history_service):
        """Test successful weekly cleanup operation"""
        # Arrange
        daily_stats = {
            "expired_cleanup": {"files_deleted": 3},
            "orphaned_cleanup": {"files_deleted": 1},
            "errors": []
        }
        storage_stats = {
            "total_reports": 100,
            "total_file_size_mb": 250.5,
            "expired_reports": 5
        }
        
        with patch.object(cleanup_service, 'run_daily_cleanup', return_value=daily_stats):
            mock_history_service.get_storage_stats.return_value = storage_stats
            
            # Act
            result = cleanup_service.run_weekly_cleanup()
            
            # Assert
            assert result["storage_stats"] == storage_stats
            assert result["expired_cleanup"] == daily_stats["expired_cleanup"]
            assert result["orphaned_cleanup"] == daily_stats["orphaned_cleanup"]
    
    def test_run_weekly_cleanup_with_large_storage_warning(self, cleanup_service, mock_history_service):
        """Test weekly cleanup with large storage warning"""
        # Arrange
        daily_stats = {"expired_cleanup": {}, "orphaned_cleanup": {}, "errors": []}
        storage_stats = {"total_file_size_mb": 1500}  # Large storage
        
        with patch.object(cleanup_service, 'run_daily_cleanup', return_value=daily_stats):
            mock_history_service.get_storage_stats.return_value = storage_stats
            
            with patch('services.report_cleanup_service.logger') as mock_logger:
                # Act
                result = cleanup_service.run_weekly_cleanup()
                
                # Assert
                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args[0][0]
                assert "Report storage is large" in warning_call
    
    def test_run_weekly_cleanup_with_many_expired_warning(self, cleanup_service, mock_history_service):
        """Test weekly cleanup with many expired reports warning"""
        # Arrange
        daily_stats = {"expired_cleanup": {}, "orphaned_cleanup": {}, "errors": []}
        storage_stats = {"total_file_size_mb": 100, "expired_reports": 150}  # Many expired
        
        with patch.object(cleanup_service, 'run_daily_cleanup', return_value=daily_stats):
            mock_history_service.get_storage_stats.return_value = storage_stats
            
            with patch('services.report_cleanup_service.logger') as mock_logger:
                # Act
                result = cleanup_service.run_weekly_cleanup()
                
                # Assert
                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args[0][0]
                assert "Many expired reports found" in warning_call
    
    def test_cleanup_old_history_records_success(self, cleanup_service, mock_db):
        """Test successful cleanup of old history records"""
        # Arrange
        old_record1 = Mock()
        old_record1.id = 1
        old_record2 = Mock()
        old_record2.id = 2
        
        mock_query = Mock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_query.all.return_value = [old_record1, old_record2]
        mock_db.delete.return_value = None
        mock_db.commit.return_value = None
        
        # Act
        result = cleanup_service.cleanup_old_history_records(days_to_keep=90)
        
        # Assert
        assert result["records_found"] == 2
        assert result["records_deleted"] == 2
        assert "cutoff_date" in result
        
        # Verify database operations
        assert mock_db.delete.call_count == 2
        mock_db.commit.assert_called_once()
    
    def test_cleanup_old_history_records_with_errors(self, cleanup_service, mock_db):
        """Test cleanup of old history records with some deletion errors"""
        # Arrange
        old_record1 = Mock()
        old_record1.id = 1
        old_record2 = Mock()
        old_record2.id = 2
        
        mock_query = Mock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_query.all.return_value = [old_record1, old_record2]
        
        # First delete succeeds, second fails
        mock_db.delete.side_effect = [None, Exception("Delete failed")]
        mock_db.commit.return_value = None
        
        with patch('services.report_cleanup_service.logger') as mock_logger:
            # Act
            result = cleanup_service.cleanup_old_history_records(days_to_keep=90)
            
            # Assert
            assert result["records_found"] == 2
            assert result["records_deleted"] == 1  # Only one succeeded
            
            # Verify error was logged
            mock_logger.error.assert_called()
    
    def test_cleanup_old_history_records_database_error(self, cleanup_service, mock_db):
        """Test cleanup of old history records with database error"""
        # Arrange
        mock_db.query.side_effect = Exception("Database error")
        
        # Act & Assert
        with pytest.raises(ReportHistoryError, match="Failed to cleanup old history records"):
            cleanup_service.cleanup_old_history_records(days_to_keep=90)
        
        mock_db.rollback.assert_called_once()
    
    def test_get_cleanup_recommendations_no_issues(self, cleanup_service, mock_history_service):
        """Test cleanup recommendations when no issues found"""
        # Arrange
        storage_stats = {
            "expired_reports": 0,
            "total_file_size_mb": 100,
            "total_reports": 50,
            "reports_with_files": 45
        }
        mock_history_service.get_storage_stats.return_value = storage_stats
        
        # Act
        result = cleanup_service.get_cleanup_recommendations()
        
        # Assert
        assert result["storage_stats"] == storage_stats
        assert len(result["recommendations"]) == 0
    
    def test_get_cleanup_recommendations_with_expired_reports(self, cleanup_service, mock_history_service):
        """Test cleanup recommendations with expired reports"""
        # Arrange
        storage_stats = {
            "expired_reports": 10,
            "total_file_size_mb": 100,
            "total_reports": 50,
            "reports_with_files": 45
        }
        mock_history_service.get_storage_stats.return_value = storage_stats
        
        # Act
        result = cleanup_service.get_cleanup_recommendations()
        
        # Assert
        assert len(result["recommendations"]) == 1
        recommendation = result["recommendations"][0]
        assert recommendation["type"] == "expired_reports"
        assert "10 expired reports" in recommendation["message"]
    
    def test_get_cleanup_recommendations_with_large_storage(self, cleanup_service, mock_history_service):
        """Test cleanup recommendations with large storage usage"""
        # Arrange
        storage_stats = {
            "expired_reports": 0,
            "total_file_size_mb": 750,  # Large storage
            "total_reports": 50,
            "reports_with_files": 45
        }
        mock_history_service.get_storage_stats.return_value = storage_stats
        
        # Act
        result = cleanup_service.get_cleanup_recommendations()
        
        # Assert
        assert len(result["recommendations"]) == 1
        recommendation = result["recommendations"][0]
        assert recommendation["type"] == "large_storage"
        assert "750 MB" in recommendation["message"]
    
    def test_get_cleanup_recommendations_with_old_records(self, cleanup_service, mock_history_service):
        """Test cleanup recommendations with many old records"""
        # Arrange
        storage_stats = {
            "expired_reports": 0,
            "total_file_size_mb": 100,
            "total_reports": 200,  # Many total reports
            "reports_with_files": 50  # Few with files = many old records
        }
        mock_history_service.get_storage_stats.return_value = storage_stats
        
        # Act
        result = cleanup_service.get_cleanup_recommendations()
        
        # Assert
        assert len(result["recommendations"]) == 1
        recommendation = result["recommendations"][0]
        assert recommendation["type"] == "old_records"
        assert "150 history records" in recommendation["message"]
    
    def test_get_cleanup_recommendations_multiple_issues(self, cleanup_service, mock_history_service):
        """Test cleanup recommendations with multiple issues"""
        # Arrange
        storage_stats = {
            "expired_reports": 15,
            "total_file_size_mb": 600,
            "total_reports": 300,
            "reports_with_files": 50
        }
        mock_history_service.get_storage_stats.return_value = storage_stats
        
        # Act
        result = cleanup_service.get_cleanup_recommendations()
        
        # Assert
        assert len(result["recommendations"]) == 3
        
        # Check all recommendation types are present
        types = [r["type"] for r in result["recommendations"]]
        assert "expired_reports" in types
        assert "large_storage" in types
        assert "old_records" in types
    
    def test_get_cleanup_recommendations_error(self, cleanup_service, mock_history_service):
        """Test cleanup recommendations with service error"""
        # Arrange
        mock_history_service.get_storage_stats.side_effect = Exception("Stats error")
        
        # Act & Assert
        with pytest.raises(ReportHistoryError, match="Failed to get cleanup recommendations"):
            cleanup_service.get_cleanup_recommendations()


class TestStandaloneFunctions:
    """Test cases for standalone cleanup functions"""
    
    @patch('services.report_cleanup_service.get_db')
    @patch('services.report_cleanup_service.ReportCleanupService')
    def test_run_scheduled_cleanup_success(self, mock_service_class, mock_get_db):
        """Test successful scheduled cleanup execution"""
        # Arrange
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        cleanup_stats = {"files_deleted": 5, "errors": []}
        mock_service.run_daily_cleanup.return_value = cleanup_stats
        
        # Act
        result = run_scheduled_cleanup()
        
        # Assert
        assert result == cleanup_stats
        mock_service_class.assert_called_once_with(mock_db)
        mock_service.run_daily_cleanup.assert_called_once()
        mock_db.close.assert_called_once()
    
    @patch('services.report_cleanup_service.get_db')
    @patch('services.report_cleanup_service.ReportCleanupService')
    def test_run_scheduled_cleanup_error(self, mock_service_class, mock_get_db):
        """Test scheduled cleanup with error"""
        # Arrange
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.run_daily_cleanup.side_effect = Exception("Cleanup failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Cleanup failed"):
            run_scheduled_cleanup()
        
        # Verify database is still closed
        mock_db.close.assert_called_once()
    
    @patch('services.report_cleanup_service.get_db')
    @patch('services.report_cleanup_service.ReportCleanupService')
    def test_run_weekly_cleanup_success(self, mock_service_class, mock_get_db):
        """Test successful weekly cleanup execution"""
        # Arrange
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        cleanup_stats = {"files_deleted": 10, "storage_stats": {}}
        mock_service.run_weekly_cleanup.return_value = cleanup_stats
        
        # Act
        result = run_weekly_cleanup()
        
        # Assert
        assert result == cleanup_stats
        mock_service_class.assert_called_once_with(mock_db)
        mock_service.run_weekly_cleanup.assert_called_once()
        mock_db.close.assert_called_once()
    
    @patch('services.report_cleanup_service.get_db')
    @patch('services.report_cleanup_service.ReportCleanupService')
    def test_run_weekly_cleanup_error(self, mock_service_class, mock_get_db):
        """Test weekly cleanup with error"""
        # Arrange
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.run_weekly_cleanup.side_effect = Exception("Weekly cleanup failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Weekly cleanup failed"):
            run_weekly_cleanup()
        
        # Verify database is still closed
        mock_db.close.assert_called_once()


class TestReportCleanupServiceIntegration:
    """Integration tests for ReportCleanupService"""
    
    @pytest.fixture
    def db_session(self):
        """Real database session for integration tests"""
        # This would use your actual test database setup
        pytest.skip("Integration tests require database setup")
    
    def test_full_cleanup_cycle(self, db_session):
        """Test complete cleanup cycle with real database"""
        # This would test the full cleanup process with real data
        pass
    
    def test_cleanup_performance(self, db_session):
        """Test cleanup performance with large datasets"""
        # This would test performance with many reports and files
        pass
    
    def test_concurrent_cleanup(self, db_session):
        """Test concurrent cleanup operations"""
        # This would test thread safety of cleanup operations
        pass