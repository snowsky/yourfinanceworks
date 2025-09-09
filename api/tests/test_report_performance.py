"""
Performance Tests for Report Generation

This module contains performance tests and benchmarks for the reporting system,
including caching, query optimization, and large dataset handling.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

from services.report_service import ReportService
from services.report_cache_service import ReportCacheService, CacheConfig, CacheStrategy
from services.report_query_optimizer import ReportQueryOptimizer, OptimizationConfig
from services.report_progress_service import ReportProgressService, ProgressStage
from schemas.report import ReportType, ExportFormat, ClientReportFilters, InvoiceReportFilters


class TestReportCacheService:
    """Test cases for report caching functionality"""
    
    def test_cache_key_generation(self):
        """Test cache key generation consistency"""
        cache_service = ReportCacheService()
        
        filters = {
            'date_from': datetime(2024, 1, 1),
            'date_to': datetime(2024, 12, 31),
            'client_ids': [1, 2, 3]
        }
        
        # Same parameters should generate same key
        key1 = cache_service.get_cache_key(
            ReportType.CLIENT, filters, ExportFormat.JSON, user_id=1
        )
        key2 = cache_service.get_cache_key(
            ReportType.CLIENT, filters, ExportFormat.JSON, user_id=1
        )
        
        assert key1 == key2
        
        # Different parameters should generate different keys
        key3 = cache_service.get_cache_key(
            ReportType.INVOICE, filters, ExportFormat.JSON, user_id=1
        )
        
        assert key1 != key3
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get operations"""
        cache_service = ReportCacheService()
        
        test_data = {'test': 'data', 'numbers': [1, 2, 3]}
        cache_key = 'test_key'
        
        # Set data in cache
        result = cache_service.set(cache_key, test_data)
        assert result is True
        
        # Get data from cache
        cached_data = cache_service.get(cache_key)
        assert cached_data == test_data
        
        # Test cache miss
        missing_data = cache_service.get('nonexistent_key')
        assert missing_data is None
    
    def test_cache_expiration(self):
        """Test cache entry expiration"""
        cache_service = ReportCacheService()
        
        test_data = {'test': 'data'}
        cache_key = 'expiring_key'
        
        # Set data with short TTL
        cache_service.set(cache_key, test_data, ttl=1)  # 1 second
        
        # Should be available immediately
        cached_data = cache_service.get(cache_key)
        assert cached_data == test_data
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired now
        expired_data = cache_service.get(cache_key)
        assert expired_data is None
    
    def test_cache_size_limits(self):
        """Test cache size limiting and LRU eviction"""
        config = CacheConfig(max_memory_size=3)
        cache_service = ReportCacheService(config)
        
        # Fill cache to capacity
        for i in range(3):
            cache_service.set(f'key_{i}', f'data_{i}')
        
        # All items should be present
        for i in range(3):
            assert cache_service.get(f'key_{i}') == f'data_{i}'
        
        # Add one more item (should evict oldest)
        cache_service.set('key_3', 'data_3')
        
        # First item should be evicted
        assert cache_service.get('key_0') is None
        assert cache_service.get('key_1') == 'data_1'
        assert cache_service.get('key_2') == 'data_2'
        assert cache_service.get('key_3') == 'data_3'
    
    def test_cache_invalidation(self):
        """Test cache invalidation patterns"""
        cache_service = ReportCacheService()
        
        # Set up test data
        cache_service.set('client_report_1', 'data1')
        cache_service.set('invoice_report_1', 'data2')
        cache_service.set('client_report_2', 'data3')
        
        # Test pattern invalidation
        invalidated = cache_service.invalidate_pattern('client')
        assert invalidated == 2
        
        # Client reports should be gone
        assert cache_service.get('client_report_1') is None
        assert cache_service.get('client_report_2') is None
        
        # Invoice report should remain
        assert cache_service.get('invoice_report_1') == 'data2'
    
    def test_cache_stats(self):
        """Test cache statistics tracking"""
        cache_service = ReportCacheService()
        
        # Initial stats
        stats = cache_service.get_stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['total_entries'] == 0
        
        # Add some data and access it
        cache_service.set('test_key', 'test_data')
        cache_service.get('test_key')  # Hit
        cache_service.get('missing_key')  # Miss
        
        # Check updated stats
        stats = cache_service.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['total_entries'] == 1
        assert stats['hit_rate'] == 0.5


class TestReportQueryOptimizer:
    """Test cases for query optimization functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def query_optimizer(self, mock_db_session):
        """Query optimizer instance for testing"""
        return ReportQueryOptimizer(mock_db_session)
    
    def test_optimization_config(self):
        """Test optimization configuration"""
        config = OptimizationConfig(
            enable_pagination=True,
            slow_query_threshold=2.0,
            max_result_size=10000
        )
        
        assert config.enable_pagination is True
        assert config.slow_query_threshold == 2.0
        assert config.max_result_size == 10000
    
    def test_query_performance_tracking(self, query_optimizer):
        """Test query performance metrics tracking"""
        mock_query = Mock()
        mock_query.all.return_value = ['result1', 'result2', 'result3']
        
        # Execute query with monitoring
        results, metrics = query_optimizer.execute_with_monitoring(
            mock_query, "test_query"
        )
        
        assert len(results) == 3
        assert metrics.row_count == 3
        assert metrics.execution_time > 0
        assert metrics.query_hash is not None
    
    def test_slow_query_detection(self, query_optimizer):
        """Test slow query detection and logging"""
        mock_query = Mock()
        mock_query.all.return_value = []
        
        # Mock slow execution
        def slow_execution():
            time.sleep(0.1)  # Simulate slow query
            return []
        
        mock_query.all.side_effect = slow_execution
        
        with patch.object(query_optimizer.logger, 'warning') as mock_warning:
            # Set low threshold for testing
            query_optimizer.config.slow_query_threshold = 0.05
            
            results, metrics = query_optimizer.execute_with_monitoring(
                mock_query, "slow_test_query"
            )
            
            # Should log warning for slow query
            mock_warning.assert_called_once()
            assert "Slow query detected" in mock_warning.call_args[0][0]
    
    def test_performance_stats(self, query_optimizer):
        """Test performance statistics aggregation"""
        mock_query = Mock()
        mock_query.all.return_value = ['result']
        
        # Execute multiple queries
        for i in range(5):
            query_optimizer.execute_with_monitoring(mock_query, f"query_{i}")
        
        stats = query_optimizer.get_performance_stats()
        
        assert stats['total_queries'] == 5
        assert stats['average_execution_time'] > 0
        assert stats['total_rows_processed'] == 5
        assert stats['average_rows_per_query'] == 1.0
    
    def test_optimization_recommendations(self, query_optimizer):
        """Test optimization recommendations generation"""
        mock_query = Mock()
        mock_query.statement.compile.return_value.literal_binds = True
        
        # Mock query string with patterns that should trigger recommendations
        query_str = "SELECT * FROM invoices WHERE created_at > '2024-01-01' AND amount > 1000"
        
        with patch('str', return_value=query_str):
            recommendations = query_optimizer.get_optimization_recommendations(mock_query)
            
            # Should have recommendations for date and amount filtering
            assert len(recommendations) > 0
            
            # Check for index recommendations
            index_recs = [r for r in recommendations if r['type'] == 'index']
            assert len(index_recs) > 0


class TestReportProgressService:
    """Test cases for progress tracking functionality"""
    
    def test_task_creation_and_tracking(self):
        """Test basic task creation and progress tracking"""
        progress_service = ReportProgressService(max_concurrent_tasks=2)
        
        # Create a task
        task_id = progress_service.create_task("CLIENT", user_id=1)
        assert task_id is not None
        
        # Get task
        tracker = progress_service.get_task(task_id)
        assert tracker is not None
        assert tracker.report_type == "CLIENT"
        assert tracker.user_id == 1
        
        # Update progress
        success = progress_service.update_task_progress(
            task_id, ProgressStage.QUERYING, 50.0, "Processing data"
        )
        assert success is True
        
        # Check updated progress
        tracker = progress_service.get_task(task_id)
        assert tracker.current_stage == ProgressStage.QUERYING
        assert tracker.stage_progress == 50.0
        assert "Processing data" in tracker.message
    
    def test_task_lifecycle(self):
        """Test complete task lifecycle"""
        progress_service = ReportProgressService()
        
        task_id = progress_service.create_task("INVOICE")
        
        # Start task
        progress_service.start_task(task_id)
        tracker = progress_service.get_task(task_id)
        assert tracker.status.value == "running"
        assert tracker.started_at is not None
        
        # Complete task
        test_result = {"data": "test"}
        progress_service.complete_task(task_id, test_result)
        tracker = progress_service.get_task(task_id)
        assert tracker.status.value == "completed"
        assert tracker.completed_at is not None
        assert tracker.result_data == test_result
    
    def test_task_cancellation(self):
        """Test task cancellation"""
        progress_service = ReportProgressService()
        
        task_id = progress_service.create_task("PAYMENT")
        progress_service.start_task(task_id)
        
        # Request cancellation
        success = progress_service.cancel_task(task_id)
        assert success is True
        
        # Check cancellation status
        is_cancelled = progress_service.is_cancellation_requested(task_id)
        assert is_cancelled is True
        
        tracker = progress_service.get_task(task_id)
        assert tracker.cancellation_requested is True
    
    def test_user_task_filtering(self):
        """Test filtering tasks by user"""
        progress_service = ReportProgressService()
        
        # Create tasks for different users
        task1 = progress_service.create_task("CLIENT", user_id=1)
        task2 = progress_service.create_task("INVOICE", user_id=1)
        task3 = progress_service.create_task("PAYMENT", user_id=2)
        
        # Get tasks for user 1
        user1_tasks = progress_service.get_user_tasks(1)
        assert len(user1_tasks) == 2
        
        # Get tasks for user 2
        user2_tasks = progress_service.get_user_tasks(2)
        assert len(user2_tasks) == 1
    
    def test_task_cleanup(self):
        """Test automatic task cleanup"""
        progress_service = ReportProgressService()
        
        # Create and complete a task
        task_id = progress_service.create_task("EXPENSE")
        progress_service.start_task(task_id)
        progress_service.complete_task(task_id)
        
        # Manually set completion time to past
        tracker = progress_service.get_task(task_id)
        tracker.completed_at = datetime.now() - timedelta(hours=25)
        
        # Run cleanup
        cleaned = progress_service.cleanup_old_tasks(max_age_hours=24)
        assert cleaned == 1
        
        # Task should be gone
        assert progress_service.get_task(task_id) is None
    
    def test_progress_service_stats(self):
        """Test progress service statistics"""
        progress_service = ReportProgressService()
        
        # Create various tasks
        task1 = progress_service.create_task("CLIENT")
        task2 = progress_service.create_task("INVOICE")
        
        progress_service.start_task(task1)
        progress_service.complete_task(task2)
        
        stats = progress_service.get_stats()
        
        assert stats['total_tasks'] == 2
        assert stats['active_tasks'] == 1
        assert stats['completed_tasks'] == 1
        assert stats['failed_tasks'] == 0


class TestReportServicePerformance:
    """Integration tests for report service performance features"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def report_service(self, mock_db_session):
        """Report service instance for testing"""
        with patch('services.report_service.ReportDataAggregator'):
            with patch('services.report_service.ReportExportService'):
                with patch('services.report_service.ReportValidationService'):
                    service = ReportService(mock_db_session)
                    # Mock the validation service to return valid data
                    service.validation_service.validate_report_request.return_value = {
                        'report_type': ReportType.CLIENT,
                        'filters': {},
                        'export_format': ExportFormat.JSON
                    }
                    return service
    
    def test_cached_report_generation(self, report_service):
        """Test report generation with caching"""
        # Mock the internal generation method
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = {'test': 'data'}
        
        with patch.object(report_service.retry_service, 'with_retry') as mock_retry:
            mock_retry.return_value.success = True
            mock_retry.return_value.result = mock_result
            
            # First call should miss cache and generate report
            result1 = report_service.generate_report(
                'CLIENT', {}, 'json', user_id=1, use_cache=True
            )
            
            # Second call should hit cache
            result2 = report_service.generate_report(
                'CLIENT', {}, 'json', user_id=1, use_cache=True
            )
            
            # Should have called retry service only once (first call)
            assert mock_retry.call_count == 1
            
            # Both results should be successful
            assert result1.success is True
            assert result2.success is True
    
    def test_progress_tracking_integration(self, report_service):
        """Test report generation with progress tracking"""
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = {'test': 'data'}
        
        with patch.object(report_service.retry_service, 'with_retry') as mock_retry:
            mock_retry.return_value.success = True
            mock_retry.return_value.result = mock_result
            
            # Generate report with progress tracking
            result = report_service.generate_report(
                'CLIENT', {}, 'json', user_id=1, enable_progress_tracking=True
            )
            
            assert result.success is True
            
            # Should have created a progress task
            user_tasks = report_service.get_user_tasks(1)
            assert len(user_tasks) > 0
    
    def test_cache_invalidation(self, report_service):
        """Test cache invalidation functionality"""
        # Set up some cached data
        report_service.cache_service.set('test_key', 'test_data')
        
        # Invalidate cache
        invalidated = report_service.invalidate_cache(pattern='test')
        assert invalidated == 1
        
        # Data should be gone
        assert report_service.cache_service.get('test_key') is None
    
    def test_performance_stats_collection(self, report_service):
        """Test performance statistics collection"""
        # Get initial stats
        cache_stats = report_service.get_cache_stats()
        perf_stats = report_service.get_performance_stats()
        progress_stats = report_service.get_progress_stats()
        
        # All should return dictionaries with expected keys
        assert isinstance(cache_stats, dict)
        assert 'hits' in cache_stats
        assert 'misses' in cache_stats
        
        assert isinstance(perf_stats, dict)
        assert 'total_queries' in perf_stats
        
        assert isinstance(progress_stats, dict)
        assert 'total_tasks' in progress_stats
    
    def test_optimization_recommendations(self, report_service):
        """Test optimization recommendations"""
        filters = {
            'date_from': datetime(2020, 1, 1),
            'date_to': datetime(2024, 12, 31),
            'client_ids': list(range(200))  # Large client list
        }
        
        recommendations = report_service.get_optimization_recommendations(
            ReportType.CLIENT, filters
        )
        
        # Should have recommendations for large date range and client list
        assert len(recommendations) > 0
        
        # Check for specific recommendation types
        perf_recs = [r for r in recommendations if r['type'] == 'performance']
        assert len(perf_recs) > 0


class TestPerformanceBenchmarks:
    """Performance benchmark tests"""
    
    def test_cache_performance_benchmark(self):
        """Benchmark cache performance with various data sizes"""
        cache_service = ReportCacheService()
        
        # Test data of different sizes
        small_data = {'test': 'data'}
        medium_data = {'data': list(range(1000))}
        large_data = {'data': list(range(10000))}
        
        # Benchmark cache operations
        test_cases = [
            ('small', small_data),
            ('medium', medium_data),
            ('large', large_data)
        ]
        
        results = {}
        
        for name, data in test_cases:
            # Time cache set operation
            start_time = time.time()
            cache_service.set(f'benchmark_{name}', data)
            set_time = time.time() - start_time
            
            # Time cache get operation
            start_time = time.time()
            retrieved_data = cache_service.get(f'benchmark_{name}')
            get_time = time.time() - start_time
            
            results[name] = {
                'set_time': set_time,
                'get_time': get_time,
                'data_matches': retrieved_data == data
            }
        
        # All operations should complete quickly
        for name, metrics in results.items():
            assert metrics['set_time'] < 1.0  # Should be under 1 second
            assert metrics['get_time'] < 0.1   # Should be under 100ms
            assert metrics['data_matches'] is True
    
    def test_concurrent_cache_access(self):
        """Test cache performance under concurrent access"""
        cache_service = ReportCacheService()
        results = []
        errors = []
        
        def cache_worker(worker_id: int):
            try:
                for i in range(100):
                    key = f'worker_{worker_id}_item_{i}'
                    data = {'worker': worker_id, 'item': i}
                    
                    # Set data
                    cache_service.set(key, data)
                    
                    # Get data
                    retrieved = cache_service.get(key)
                    
                    if retrieved != data:
                        errors.append(f'Data mismatch for {key}')
                
                results.append(f'Worker {worker_id} completed')
            except Exception as e:
                errors.append(f'Worker {worker_id} error: {str(e)}')
        
        # Start multiple worker threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=cache_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(results) == 5  # All workers should complete
        assert len(errors) == 0   # No errors should occur
        
        # Cache should have data from all workers
        stats = cache_service.get_stats()
        assert stats['total_entries'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])