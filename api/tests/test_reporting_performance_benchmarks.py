"""
Performance Benchmark Tests for Reporting Module

This module contains performance benchmarks and stress tests to ensure
the reporting system can handle large datasets and concurrent operations efficiently.

Requirements covered: 9.2, 9.3
"""

import pytest
import time
import threading
import multiprocessing
import psutil
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

from core.services.report_service import ReportService
from core.services.report_data_aggregator import ReportDataAggregator
from core.services.report_exporter import ReportExporter
from core.services.report_cache_service import ReportCacheService
from core.schemas.report import ReportType, ExportFormat
from tests.test_comprehensive_reporting_suite import TestDataFactory


class PerformanceBenchmark:
    """Base class for performance benchmarks"""
    
    def __init__(self):
        self.results = []
        self.process = psutil.Process(os.getpid())
    
    def measure_execution(self, func, *args, **kwargs) -> Dict[str, Any]:
        """Measure execution time and resource usage"""
        # Get initial metrics
        start_time = time.time()
        start_memory = self.process.memory_info().rss
        start_cpu = self.process.cpu_percent()
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
        
        # Get final metrics
        end_time = time.time()
        end_memory = self.process.memory_info().rss
        end_cpu = self.process.cpu_percent()
        
        return {
            'execution_time': end_time - start_time,
            'memory_used': end_memory - start_memory,
            'cpu_usage': end_cpu - start_cpu,
            'success': success,
            'error': error,
            'result': result
        }
    
    def run_benchmark(self, func, iterations: int = 10, *args, **kwargs) -> Dict[str, Any]:
        """Run benchmark multiple times and collect statistics"""
        results = []
        
        for i in range(iterations):
            metrics = self.measure_execution(func, *args, **kwargs)
            results.append(metrics)
        
        # Calculate statistics
        execution_times = [r['execution_time'] for r in results if r['success']]
        memory_usage = [r['memory_used'] for r in results if r['success']]
        
        if execution_times:
            return {
                'iterations': iterations,
                'success_rate': len(execution_times) / iterations,
                'avg_execution_time': statistics.mean(execution_times),
                'min_execution_time': min(execution_times),
                'max_execution_time': max(execution_times),
                'median_execution_time': statistics.median(execution_times),
                'std_execution_time': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
                'avg_memory_usage': statistics.mean(memory_usage),
                'max_memory_usage': max(memory_usage),
                'total_errors': iterations - len(execution_times),
                'raw_results': results
            }
        else:
            return {
                'iterations': iterations,
                'success_rate': 0,
                'total_errors': iterations,
                'raw_results': results
            }


class TestDataAggregationPerformance:
    """Performance tests for data aggregation operations"""
    
    @pytest.fixture
    def benchmark(self):
        return PerformanceBenchmark()
    
    @pytest.fixture
    def mock_db_session(self):
        return Mock()
    
    def test_large_client_dataset_aggregation(self, benchmark, mock_db_session):
        """Test performance with large client datasets"""
        # Create large dataset
        large_clients = [
            TestDataFactory.create_client(i, f"Client {i}", f"client{i}@example.com", 1)
            for i in range(1, 10001)  # 10,000 clients
        ]
        
        aggregator = ReportDataAggregator(mock_db_session)
        
        def aggregate_large_clients():
            with patch.object(aggregator, '_get_client_data', return_value=large_clients):
                return aggregator.aggregate_client_data({})
        
        # Run benchmark
        results = benchmark.run_benchmark(aggregate_large_clients, iterations=5)
        
        # Performance assertions
        assert results['success_rate'] == 1.0  # All iterations should succeed
        assert results['avg_execution_time'] < 10.0  # Should complete within 10 seconds
        assert results['max_memory_usage'] < 500 * 1024 * 1024  # Less than 500MB
        
        print(f"Large client aggregation - Avg time: {results['avg_execution_time']:.2f}s, "
              f"Max memory: {results['max_memory_usage'] / 1024 / 1024:.1f}MB")
    
    def test_complex_invoice_aggregation_performance(self, benchmark, mock_db_session):
        """Test performance with complex invoice aggregation"""
        # Create large invoice dataset with relationships
        large_invoices = []
        for i in range(1, 50001):  # 50,000 invoices
            invoice = TestDataFactory.create_invoice(
                i, (i % 1000) + 1, 500.0 + (i % 5000), 
                ["paid", "pending", "overdue"][i % 3], 1
            )
            invoice.invoice_date = datetime.now() - timedelta(days=i % 365)
            large_invoices.append(invoice)
        
        aggregator = ReportDataAggregator(mock_db_session)
        
        def aggregate_complex_invoices():
            filters = {
                'date_from': datetime.now() - timedelta(days=365),
                'date_to': datetime.now(),
                'status': ['paid', 'pending'],
                'amount_min': 1000.0,
                'group_by': ['status', 'month'],
                'include_totals': True,
                'include_averages': True
            }
            
            with patch.object(aggregator, '_get_invoice_data', return_value=large_invoices):
                return aggregator.aggregate_invoice_data(filters)
        
        # Run benchmark
        results = benchmark.run_benchmark(aggregate_complex_invoices, iterations=3)
        
        # Performance assertions
        assert results['success_rate'] == 1.0
        assert results['avg_execution_time'] < 15.0  # Complex aggregation within 15 seconds
        assert results['max_memory_usage'] < 1024 * 1024 * 1024  # Less than 1GB
        
        print(f"Complex invoice aggregation - Avg time: {results['avg_execution_time']:.2f}s")
    
    def test_concurrent_aggregation_performance(self, benchmark, mock_db_session):
        """Test performance under concurrent aggregation load"""
        # Create moderate dataset for concurrent testing
        clients = [TestDataFactory.create_client(i) for i in range(1, 1001)]
        invoices = [TestDataFactory.create_invoice(i, (i % 100) + 1) for i in range(1, 5001)]
        
        def concurrent_aggregation_worker(worker_id: int) -> Dict[str, Any]:
            aggregator = ReportDataAggregator(mock_db_session)
            
            start_time = time.time()
            
            with patch.object(aggregator, '_get_client_data', return_value=clients):
                with patch.object(aggregator, '_get_invoice_data', return_value=invoices):
                    
                    # Each worker performs different aggregations
                    if worker_id % 3 == 0:
                        result = aggregator.aggregate_client_data({})
                    elif worker_id % 3 == 1:
                        result = aggregator.aggregate_invoice_data({})
                    else:
                        result = aggregator.aggregate_payment_data({})
            
            execution_time = time.time() - start_time
            
            return {
                'worker_id': worker_id,
                'execution_time': execution_time,
                'success': True
            }
        
        # Run concurrent workers
        num_workers = 10
        results = []
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(concurrent_aggregation_worker, i) 
                for i in range(num_workers)
            ]
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception as e:
                    results.append({
                        'worker_id': -1,
                        'execution_time': 30.0,
                        'success': False,
                        'error': str(e)
                    })
        
        # Analyze concurrent performance
        successful_results = [r for r in results if r['success']]
        execution_times = [r['execution_time'] for r in successful_results]
        
        assert len(successful_results) == num_workers  # All workers should succeed
        assert max(execution_times) < 20.0  # No worker should take more than 20 seconds
        assert statistics.mean(execution_times) < 10.0  # Average should be reasonable
        
        print(f"Concurrent aggregation - Workers: {num_workers}, "
              f"Avg time: {statistics.mean(execution_times):.2f}s, "
              f"Max time: {max(execution_times):.2f}s")


class TestExportPerformance:
    """Performance tests for report export operations"""
    
    @pytest.fixture
    def benchmark(self):
        return PerformanceBenchmark()
    
    def test_large_dataset_export_performance(self, benchmark):
        """Test export performance with large datasets"""
        # Create large report data
        large_data = {
            'data': [
                {
                    'id': i,
                    'name': f'Record {i}',
                    'email': f'record{i}@example.com',
                    'amount': 100.0 + (i % 1000),
                    'date': (datetime.now() - timedelta(days=i % 365)).isoformat(),
                    'status': ['active', 'inactive', 'pending'][i % 3],
                    'category': f'Category {i % 10}',
                    'description': f'This is a description for record {i} with some additional text to make it longer'
                }
                for i in range(1, 100001)  # 100,000 records
            ],
            'summary': {
                'total_records': 100000,
                'total_amount': 5000000.0
            }
        }
        
        exporter = ReportExporter()
        
        # Test different export formats
        formats_to_test = [
            (ExportFormat.JSON, 30.0),    # JSON should be fastest
            (ExportFormat.CSV, 45.0),     # CSV should be moderate
            (ExportFormat.EXCEL, 120.0),  # Excel should be slowest but still reasonable
        ]
        
        for export_format, max_time in formats_to_test:
            def export_large_data():
                with patch.object(exporter, '_write_to_file') as mock_write:
                    mock_write.return_value = Mock(
                        success=True,
                        file_path=f"/tmp/large_export.{export_format.value}",
                        file_size=len(large_data['data']) * 100  # Estimate
                    )
                    return exporter.export_report(large_data, export_format)
            
            results = benchmark.run_benchmark(export_large_data, iterations=3)
            
            assert results['success_rate'] == 1.0
            assert results['avg_execution_time'] < max_time
            
            print(f"Large {export_format.value} export - Avg time: {results['avg_execution_time']:.2f}s")
    
    def test_concurrent_export_performance(self, benchmark):
        """Test concurrent export operations"""
        # Create moderate dataset for concurrent testing
        export_data = {
            'data': [
                {'id': i, 'name': f'Item {i}', 'value': i * 10}
                for i in range(1, 10001)  # 10,000 records per export
            ]
        }
        
        def concurrent_export_worker(worker_id: int, export_format: ExportFormat) -> Dict[str, Any]:
            exporter = ReportExporter()
            
            start_time = time.time()
            
            with patch.object(exporter, '_write_to_file') as mock_write:
                mock_write.return_value = Mock(
                    success=True,
                    file_path=f"/tmp/concurrent_export_{worker_id}.{export_format.value}",
                    file_size=len(export_data['data']) * 50
                )
                
                result = exporter.export_report(export_data, export_format)
            
            execution_time = time.time() - start_time
            
            return {
                'worker_id': worker_id,
                'format': export_format.value,
                'execution_time': execution_time,
                'success': result.success if result else False
            }
        
        # Run concurrent exports with different formats
        num_workers = 8
        formats = [ExportFormat.JSON, ExportFormat.CSV, ExportFormat.EXCEL, ExportFormat.PDF]
        results = []
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            
            for i in range(num_workers):
                export_format = formats[i % len(formats)]
                future = executor.submit(concurrent_export_worker, i, export_format)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=60)
                    results.append(result)
                except Exception as e:
                    results.append({
                        'worker_id': -1,
                        'execution_time': 60.0,
                        'success': False,
                        'error': str(e)
                    })
        
        # Analyze results
        successful_results = [r for r in results if r['success']]
        execution_times = [r['execution_time'] for r in successful_results]
        
        assert len(successful_results) == num_workers
        assert max(execution_times) < 45.0  # No export should take more than 45 seconds
        
        # Group by format for analysis
        by_format = {}
        for result in successful_results:
            format_name = result['format']
            if format_name not in by_format:
                by_format[format_name] = []
            by_format[format_name].append(result['execution_time'])
        
        for format_name, times in by_format.items():
            avg_time = statistics.mean(times)
            print(f"Concurrent {format_name} export - Avg time: {avg_time:.2f}s")


class TestCachePerformance:
    """Performance tests for caching operations"""
    
    @pytest.fixture
    def benchmark(self):
        return PerformanceBenchmark()
    
    def test_cache_performance_under_load(self, benchmark):
        """Test cache performance under high load"""
        cache_service = ReportCacheService()
        
        # Test data of various sizes
        test_data_sizes = [
            ('small', {'data': list(range(100))}),
            ('medium', {'data': list(range(10000))}),
            ('large', {'data': list(range(100000))}),
        ]
        
        for size_name, test_data in test_data_sizes:
            # Test cache set performance
            def cache_set_operation():
                return cache_service.set(f'perf_test_{size_name}', test_data)
            
            set_results = benchmark.run_benchmark(cache_set_operation, iterations=10)
            
            # Test cache get performance
            def cache_get_operation():
                return cache_service.get(f'perf_test_{size_name}')
            
            get_results = benchmark.run_benchmark(cache_get_operation, iterations=50)
            
            # Performance assertions
            assert set_results['success_rate'] == 1.0
            assert get_results['success_rate'] == 1.0
            
            # Set operations should be reasonably fast
            max_set_time = {'small': 0.1, 'medium': 1.0, 'large': 5.0}[size_name]
            assert set_results['avg_execution_time'] < max_set_time
            
            # Get operations should be very fast
            assert get_results['avg_execution_time'] < 0.1
            
            print(f"Cache {size_name} - Set: {set_results['avg_execution_time']:.3f}s, "
                  f"Get: {get_results['avg_execution_time']:.3f}s")
    
    def test_cache_concurrent_access_performance(self, benchmark):
        """Test cache performance under concurrent access"""
        cache_service = ReportCacheService()
        
        # Pre-populate cache with test data
        for i in range(100):
            cache_service.set(f'concurrent_test_{i}', {'data': f'test_data_{i}'})
        
        def concurrent_cache_worker(worker_id: int) -> Dict[str, Any]:
            operations = 0
            errors = 0
            start_time = time.time()
            
            # Each worker performs mixed read/write operations
            for i in range(100):
                try:
                    if i % 3 == 0:  # Write operation
                        cache_service.set(f'worker_{worker_id}_item_{i}', {'worker': worker_id, 'item': i})
                    else:  # Read operation
                        cache_service.get(f'concurrent_test_{i % 100}')
                    operations += 1
                except Exception:
                    errors += 1
            
            execution_time = time.time() - start_time
            
            return {
                'worker_id': worker_id,
                'operations': operations,
                'errors': errors,
                'execution_time': execution_time,
                'ops_per_second': operations / execution_time if execution_time > 0 else 0
            }
        
        # Run concurrent workers
        num_workers = 10
        results = []
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(concurrent_cache_worker, i) 
                for i in range(num_workers)
            ]
            
            for future in as_completed(futures):
                result = future.result(timeout=30)
                results.append(result)
        
        # Analyze performance
        total_operations = sum(r['operations'] for r in results)
        total_errors = sum(r['errors'] for r in results)
        avg_ops_per_second = statistics.mean([r['ops_per_second'] for r in results])
        
        assert total_errors == 0  # No errors should occur
        assert avg_ops_per_second > 100  # Should handle at least 100 ops/second per worker
        
        print(f"Concurrent cache access - Workers: {num_workers}, "
              f"Total ops: {total_operations}, Avg ops/sec: {avg_ops_per_second:.1f}")


class TestMemoryUsageOptimization:
    """Tests for memory usage optimization"""
    
    def test_memory_efficient_large_dataset_processing(self):
        """Test memory efficiency when processing large datasets"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Simulate processing very large dataset in chunks
        def process_large_dataset_in_chunks():
            chunk_size = 1000
            total_records = 50000
            
            processed_count = 0
            
            for chunk_start in range(0, total_records, chunk_size):
                chunk_end = min(chunk_start + chunk_size, total_records)
                
                # Simulate processing a chunk
                chunk_data = [
                    TestDataFactory.create_invoice(i, (i % 100) + 1)
                    for i in range(chunk_start, chunk_end)
                ]
                
                # Process chunk (simulate aggregation)
                chunk_totals = sum(inv.total_amount for inv in chunk_data)
                processed_count += len(chunk_data)
                
                # Clear chunk data to free memory
                del chunk_data
            
            return processed_count
        
        # Process the dataset
        processed_count = process_large_dataset_in_chunks()
        
        # Check memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 200MB for 50k records)
        assert memory_increase < 200 * 1024 * 1024
        assert processed_count == 50000
        
        print(f"Large dataset processing - Memory increase: {memory_increase / 1024 / 1024:.1f}MB")
    
    def test_memory_leak_detection(self):
        """Test for memory leaks in repeated operations"""
        process = psutil.Process(os.getpid())
        
        memory_samples = []
        
        # Perform repeated operations and monitor memory
        for iteration in range(20):
            # Simulate report generation
            mock_db = Mock()
            aggregator = ReportDataAggregator(mock_db)
            
            # Create and process data
            test_data = [TestDataFactory.create_client(i) for i in range(100)]
            
            with patch.object(aggregator, '_get_client_data', return_value=test_data):
                result = aggregator.aggregate_client_data({})
            
            # Clear references
            del test_data
            del aggregator
            del result
            
            # Sample memory usage
            current_memory = process.memory_info().rss
            memory_samples.append(current_memory)
        
        # Analyze memory trend
        # Memory should not continuously increase (indicating a leak)
        first_half_avg = statistics.mean(memory_samples[:10])
        second_half_avg = statistics.mean(memory_samples[10:])
        
        memory_increase_rate = (second_half_avg - first_half_avg) / first_half_avg
        
        # Memory increase should be minimal (less than 10%)
        assert memory_increase_rate < 0.1
        
        print(f"Memory leak test - Increase rate: {memory_increase_rate * 100:.2f}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])