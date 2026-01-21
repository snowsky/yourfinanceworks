"""
Performance and load tests for tenant database encryption.

Tests encryption impact on database operations, memory usage,
resource consumption, and high-volume encrypted data operations.
"""

import pytest
import time
import asyncio
import threading
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from unittest.mock import Mock, patch
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import psutil
import gc

from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from core.utils.column_encryptor import EncryptedColumn, EncryptedJSON
from core.models.database import Base, set_tenant_context, clear_tenant_context
from encryption_config import EncryptionConfig


# Test models for performance testing
class PerformanceTestUser(Base):
    """Test user model for performance testing."""
    __tablename__ = "perf_test_users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(EncryptedColumn(), nullable=False)
    first_name = Column(EncryptedColumn(), nullable=True)
    last_name = Column(EncryptedColumn(), nullable=True)
    phone = Column(EncryptedColumn(), nullable=True)
    address = Column(EncryptedColumn(), nullable=True)
    # Non-encrypted fields for comparison
    user_id = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)


class PerformanceTestDocument(Base):
    """Test document model with JSON fields for performance testing."""
    __tablename__ = "perf_test_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(EncryptedColumn(), nullable=False)
    content = Column(EncryptedColumn(), nullable=True)
    doc_metadata = Column(EncryptedJSON(), nullable=True)
    tags = Column(EncryptedJSON(), nullable=True)
    # Non-encrypted fields
    document_type = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime)


class TestEncryptionPerformance:
    """Performance tests for encryption operations."""

    @pytest.fixture
    def encryption_service(self):
        """Create encryption service with real cryptographic operations."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "performance-test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            return EncryptionService()

    @pytest.fixture
    def tenant_context(self):
        """Set up tenant context for performance testing."""
        tenant_id = 1
        set_tenant_context(tenant_id)
        yield tenant_id
        clear_tenant_context()

    def test_encryption_throughput(self, encryption_service, tenant_context):
        """Test encryption throughput with various data sizes."""
        data_sizes = [
            ("small", "A" * 100),      # 100 bytes
            ("medium", "B" * 1000),    # 1KB
            ("large", "C" * 10000),    # 10KB
            ("xlarge", "D" * 100000),  # 100KB
        ]
        
        results = {}
        
        for size_name, data in data_sizes:
            # Measure encryption performance
            start_time = time.time()
            iterations = 100 if len(data) <= 10000 else 10  # Fewer iterations for large data
            
            for _ in range(iterations):
                encrypted = encryption_service.encrypt_data(data, tenant_context)
                decrypted = encryption_service.decrypt_data(encrypted, tenant_context)
                assert decrypted == data
            
            end_time = time.time()
            duration = end_time - start_time
            
            results[size_name] = {
                'data_size_bytes': len(data),
                'iterations': iterations,
                'total_time_seconds': duration,
                'ops_per_second': (iterations * 2) / duration,  # 2 ops per iteration (encrypt + decrypt)
                'bytes_per_second': (len(data) * iterations * 2) / duration
            }
        
        # Log performance results
        for size_name, metrics in results.items():
            print(f"\n{size_name.upper()} DATA PERFORMANCE:")
            print(f"  Data size: {metrics['data_size_bytes']:,} bytes")
            print(f"  Operations per second: {metrics['ops_per_second']:.2f}")
            print(f"  Throughput: {metrics['bytes_per_second']:,.0f} bytes/sec")
        
        # Basic performance assertions
        assert results['small']['ops_per_second'] > 100  # Should handle small data quickly
        assert results['medium']['ops_per_second'] > 50   # Medium data should be reasonable
        assert results['large']['bytes_per_second'] > 100000  # Should maintain good throughput

    def test_json_encryption_performance(self, encryption_service, tenant_context):
        """Test JSON encryption performance with complex structures."""
        # Create complex JSON structures of different sizes
        json_data_sets = [
            ("simple", {"id": 1, "name": "test", "active": True}),
            ("nested", {
                "user": {"id": 1, "profile": {"name": "test", "settings": {"theme": "dark"}}},
                "permissions": ["read", "write"],
                "metadata": {"created": "2023-01-01", "tags": ["important"]}
            }),
            ("large_array", {
                "items": [{"id": i, "name": f"item_{i}", "value": i * 10} for i in range(100)]
            }),
            ("deep_nested", {
                f"level_{i}": {f"sublevel_{j}": f"value_{i}_{j}" for j in range(10)}
                for i in range(10)
            })
        ]
        
        results = {}
        
        for data_name, json_data in json_data_sets:
            start_time = time.time()
            iterations = 50
            
            for _ in range(iterations):
                encrypted = encryption_service.encrypt_json(json_data, tenant_context)
                decrypted = encryption_service.decrypt_json(encrypted, tenant_context)
                assert decrypted == json_data
            
            end_time = time.time()
            duration = end_time - start_time
            
            json_size = len(json.dumps(json_data))
            results[data_name] = {
                'json_size_bytes': json_size,
                'iterations': iterations,
                'total_time_seconds': duration,
                'ops_per_second': (iterations * 2) / duration,
                'json_bytes_per_second': (json_size * iterations * 2) / duration
            }
        
        # Log JSON performance results
        for data_name, metrics in results.items():
            print(f"\n{data_name.upper()} JSON PERFORMANCE:")
            print(f"  JSON size: {metrics['json_size_bytes']:,} bytes")
            print(f"  Operations per second: {metrics['ops_per_second']:.2f}")
            print(f"  JSON throughput: {metrics['json_bytes_per_second']:,.0f} bytes/sec")
        
        # Performance assertions
        assert results['simple']['ops_per_second'] > 50
        assert results['nested']['ops_per_second'] > 20

    def test_concurrent_encryption_performance(self, encryption_service, tenant_context):
        """Test encryption performance under concurrent load."""
        def encrypt_decrypt_worker(worker_id: int, iterations: int) -> Dict[str, Any]:
            """Worker function for concurrent encryption testing."""
            start_time = time.time()
            data = f"Worker {worker_id} test data " * 10  # ~200 bytes per operation
            
            for i in range(iterations):
                encrypted = encryption_service.encrypt_data(f"{data} iteration {i}", tenant_context)
                decrypted = encryption_service.decrypt_data(encrypted, tenant_context)
                assert f"{data} iteration {i}" in decrypted
            
            end_time = time.time()
            return {
                'worker_id': worker_id,
                'iterations': iterations,
                'duration': end_time - start_time,
                'ops_per_second': (iterations * 2) / (end_time - start_time)
            }
        
        # Test with different numbers of concurrent workers
        worker_counts = [1, 2, 4, 8]
        iterations_per_worker = 50
        
        for num_workers in worker_counts:
            print(f"\nTesting with {num_workers} concurrent workers...")
            
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [
                    executor.submit(encrypt_decrypt_worker, worker_id, iterations_per_worker)
                    for worker_id in range(num_workers)
                ]
                
                results = [future.result() for future in as_completed(futures)]
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Calculate aggregate metrics
            total_operations = sum(r['iterations'] * 2 for r in results)  # 2 ops per iteration
            aggregate_ops_per_second = total_operations / total_duration
            avg_worker_ops_per_second = statistics.mean(r['ops_per_second'] for r in results)
            
            print(f"  Total operations: {total_operations}")
            print(f"  Total time: {total_duration:.2f} seconds")
            print(f"  Aggregate ops/sec: {aggregate_ops_per_second:.2f}")
            print(f"  Average worker ops/sec: {avg_worker_ops_per_second:.2f}")
            
            # Performance should scale reasonably with workers
            if num_workers == 1:
                baseline_ops_per_second = aggregate_ops_per_second
            else:
                # Should achieve at least 50% of linear scaling
                expected_min = baseline_ops_per_second * num_workers * 0.5
                assert aggregate_ops_per_second >= expected_min, \
                    f"Concurrent performance degraded too much: {aggregate_ops_per_second} < {expected_min}"

    def test_key_cache_performance_impact(self, encryption_service, tenant_context):
        """Test performance impact of key caching."""
        data = "Test data for cache performance analysis"
        
        # Test with cold cache (first access)
        encryption_service.clear_cache()
        
        cold_cache_times = []
        for _ in range(10):
            start_time = time.time()
            encrypted = encryption_service.encrypt_data(data, tenant_context)
            decrypted = encryption_service.decrypt_data(encrypted, tenant_context)
            end_time = time.time()
            cold_cache_times.append(end_time - start_time)
            encryption_service.clear_cache()  # Clear cache each time
        
        # Test with warm cache (subsequent accesses)
        encryption_service.clear_cache()
        encryption_service.get_tenant_key(tenant_context)  # Prime the cache
        
        warm_cache_times = []
        for _ in range(10):
            start_time = time.time()
            encrypted = encryption_service.encrypt_data(data, tenant_context)
            decrypted = encryption_service.decrypt_data(encrypted, tenant_context)
            end_time = time.time()
            warm_cache_times.append(end_time - start_time)
        
        # Calculate statistics
        cold_avg = statistics.mean(cold_cache_times)
        warm_avg = statistics.mean(warm_cache_times)
        cache_speedup = cold_avg / warm_avg
        
        print(f"\nKEY CACHE PERFORMANCE IMPACT:")
        print(f"  Cold cache average: {cold_avg:.6f} seconds")
        print(f"  Warm cache average: {warm_avg:.6f} seconds")
        print(f"  Cache speedup: {cache_speedup:.2f}x")
        
        # Cache should provide meaningful speedup
        assert cache_speedup > 1.2, f"Cache speedup too low: {cache_speedup:.2f}x"

    @pytest.mark.slow
    def test_memory_usage_under_load(self, encryption_service, tenant_context):
        """Test memory usage patterns under encryption load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Baseline memory usage
        gc.collect()  # Force garbage collection
        baseline_memory = process.memory_info().rss
        
        # Generate load with various data sizes
        large_data_sets = [
            "Small data " * 100,      # ~1KB
            "Medium data " * 1000,    # ~10KB  
            "Large data " * 10000,    # ~100KB
        ]
        
        memory_measurements = []
        
        for i, data in enumerate(large_data_sets * 10):  # 30 total operations
            # Perform encryption/decryption
            encrypted = encryption_service.encrypt_data(data, tenant_context)
            decrypted = encryption_service.decrypt_data(encrypted, tenant_context)
            
            # Measure memory every few operations
            if i % 5 == 0:
                current_memory = process.memory_info().rss
                memory_measurements.append(current_memory - baseline_memory)
        
        # Force garbage collection and final measurement
        gc.collect()
        final_memory = process.memory_info().rss
        
        # Calculate memory statistics
        max_memory_increase = max(memory_measurements)
        final_memory_increase = final_memory - baseline_memory
        
        print(f"\nMEMORY USAGE ANALYSIS:")
        print(f"  Baseline memory: {baseline_memory / 1024 / 1024:.2f} MB")
        print(f"  Max memory increase: {max_memory_increase / 1024 / 1024:.2f} MB")
        print(f"  Final memory increase: {final_memory_increase / 1024 / 1024:.2f} MB")
        
        # Memory usage should be reasonable (less than 50MB increase)
        assert max_memory_increase < 50 * 1024 * 1024, \
            f"Memory usage too high: {max_memory_increase / 1024 / 1024:.2f} MB"
        
        # Memory should not continuously grow (memory leak check)
        assert final_memory_increase < max_memory_increase * 1.5, \
            "Potential memory leak detected"


class TestDatabasePerformance:
    """Performance tests for database operations with encryption."""

    @pytest.fixture
    def db_engine(self):
        """Create in-memory SQLite database engine for performance testing."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False  # Disable SQL logging for performance tests
        )
        return engine

    @pytest.fixture
    def db_session(self, db_engine):
        """Create database session with performance test tables."""
        Base.metadata.create_all(bind=db_engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(bind=db_engine)

    @pytest.fixture
    def tenant_context(self):
        """Set up tenant context for database performance testing."""
        tenant_id = 1
        set_tenant_context(tenant_id)
        yield tenant_id
        clear_tenant_context()

    @pytest.fixture
    def mock_encryption_service(self):
        """Mock encryption service optimized for performance testing."""
        with patch('api.utils.column_encryptor.get_encryption_service') as mock_get_service:
            mock_service = Mock(spec=EncryptionService)
            
            # Fast mock encryption (just add prefix/suffix)
            mock_service.encrypt_data.side_effect = lambda data, tenant_id: f"enc_{data}"
            mock_service.decrypt_data.side_effect = lambda data, tenant_id: data[4:] if data.startswith("enc_") else data
            mock_service.encrypt_json.side_effect = lambda data, tenant_id: f"enc_json_{json.dumps(data)}"
            mock_service.decrypt_json.side_effect = lambda data, tenant_id: json.loads(data[9:]) if data.startswith("enc_json_") else {}
            
            mock_get_service.return_value = mock_service
            yield mock_service

    @pytest.mark.slow
    def test_bulk_insert_performance(self, db_session, tenant_context, mock_encryption_service):
        """Test bulk insert performance with encrypted columns."""
        record_counts = [100, 500, 1000, 2000]
        
        for count in record_counts:
            print(f"\nTesting bulk insert of {count} records...")
            
            # Generate test data
            users = []
            for i in range(count):
                user = PerformanceTestUser(
                    email=f"user{i}@example.com",
                    first_name=f"FirstName{i}",
                    last_name=f"LastName{i}",
                    phone=f"555-{i:04d}",
                    address=f"{i} Main Street, City, State",
                    user_id=i,
                    is_active=True
                )
                users.append(user)
            
            # Measure bulk insert time
            start_time = time.time()
            db_session.add_all(users)
            db_session.commit()
            end_time = time.time()
            
            duration = end_time - start_time
            records_per_second = count / duration
            
            print(f"  Insert time: {duration:.3f} seconds")
            print(f"  Records per second: {records_per_second:.1f}")
            print(f"  Encryption calls: {mock_encryption_service.encrypt_data.call_count}")
            
            # Performance assertions
            assert records_per_second > 50, f"Insert performance too slow: {records_per_second:.1f} records/sec"
            
            # Verify encryption was called for each encrypted field
            expected_calls = count * 5  # 5 encrypted fields per user
            assert mock_encryption_service.encrypt_data.call_count >= expected_calls
            
            # Clean up for next iteration
            db_session.query(PerformanceTestUser).delete()
            db_session.commit()
            mock_encryption_service.reset_mock()

    @pytest.mark.slow
    def test_bulk_query_performance(self, db_session, tenant_context, mock_encryption_service):
        """Test bulk query performance with encrypted columns."""
        # Insert test data
        record_count = 1000
        users = []
        for i in range(record_count):
            user = PerformanceTestUser(
                email=f"user{i}@example.com",
                first_name=f"FirstName{i}",
                last_name=f"LastName{i}",
                phone=f"555-{i:04d}",
                address=f"{i} Main Street",
                user_id=i,
                is_active=i % 2 == 0  # Half active, half inactive
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        mock_encryption_service.reset_mock()
        
        # Test different query patterns
        query_tests = [
            ("select_all", lambda: db_session.query(PerformanceTestUser).all()),
            ("select_active", lambda: db_session.query(PerformanceTestUser).filter(PerformanceTestUser.is_active == True).all()),
            ("select_limited", lambda: db_session.query(PerformanceTestUser).limit(100).all()),
            ("select_ordered", lambda: db_session.query(PerformanceTestUser).order_by(PerformanceTestUser.user_id).all()),
        ]
        
        for test_name, query_func in query_tests:
            print(f"\nTesting {test_name} query...")
            
            start_time = time.time()
            results = query_func()
            end_time = time.time()
            
            duration = end_time - start_time
            records_retrieved = len(results)
            records_per_second = records_retrieved / duration if duration > 0 else float('inf')
            
            print(f"  Query time: {duration:.3f} seconds")
            print(f"  Records retrieved: {records_retrieved}")
            print(f"  Records per second: {records_per_second:.1f}")
            print(f"  Decryption calls: {mock_encryption_service.decrypt_data.call_count}")
            
            # Verify data integrity
            if results:
                assert results[0].email.startswith("user")
                assert results[0].first_name.startswith("FirstName")
            
            # Performance assertions
            assert records_per_second > 100, f"Query performance too slow: {records_per_second:.1f} records/sec"
            
            mock_encryption_service.reset_mock()

    def test_json_field_performance(self, db_session, tenant_context, mock_encryption_service):
        """Test performance with encrypted JSON fields."""
        # Create documents with varying JSON complexity
        documents = []
        
        for i in range(100):
            # Create increasingly complex JSON structures
            metadata = {
                "document_id": i,
                "author": f"Author {i}",
                "created_date": f"2023-01-{(i % 28) + 1:02d}",
                "tags": [f"tag{j}" for j in range(i % 10 + 1)],
                "properties": {
                    f"prop_{j}": f"value_{j}" for j in range(i % 5 + 1)
                }
            }
            
            tags = [f"category_{i % 5}", f"priority_{i % 3}", f"status_{i % 4}"]
            
            doc = PerformanceTestDocument(
                title=f"Document {i}",
                content=f"Content for document {i} " * (i % 10 + 1),  # Varying content length
                doc_metadata=metadata,
                tags=tags,
                document_type=f"type_{i % 3}",
                size_bytes=len(f"Content for document {i}") * (i % 10 + 1)
            )
            documents.append(doc)
        
        # Measure insert performance
        start_time = time.time()
        db_session.add_all(documents)
        db_session.commit()
        insert_time = time.time() - start_time
        
        print(f"\nJSON FIELD PERFORMANCE:")
        print(f"  Insert time for 100 documents: {insert_time:.3f} seconds")
        print(f"  JSON encryption calls: {mock_encryption_service.encrypt_json.call_count}")
        
        # Reset mock for query testing
        mock_encryption_service.reset_mock()
        
        # Measure query performance
        start_time = time.time()
        all_docs = db_session.query(PerformanceTestDocument).all()
        query_time = time.time() - start_time
        
        print(f"  Query time for 100 documents: {query_time:.3f} seconds")
        print(f"  JSON decryption calls: {mock_encryption_service.decrypt_json.call_count}")
        
        # Verify data integrity
        assert len(all_docs) == 100
        assert all_docs[0].doc_metadata["document_id"] == 0
        assert isinstance(all_docs[0].tags, list)
        
        # Performance assertions
        assert insert_time < 5.0, f"JSON insert too slow: {insert_time:.3f} seconds"
        assert query_time < 2.0, f"JSON query too slow: {query_time:.3f} seconds"

    def test_update_performance(self, db_session, tenant_context, mock_encryption_service):
        """Test update performance with encrypted fields."""
        # Insert initial data
        users = []
        for i in range(500):
            user = PerformanceTestUser(
                email=f"user{i}@example.com",
                first_name=f"FirstName{i}",
                last_name=f"LastName{i}",
                phone=f"555-{i:04d}",
                user_id=i
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        mock_encryption_service.reset_mock()
        
        # Test different update patterns
        update_tests = [
            ("single_field", lambda u: setattr(u, 'first_name', f"Updated_{u.user_id}")),
            ("multiple_fields", lambda u: [
                setattr(u, 'first_name', f"NewFirst_{u.user_id}"),
                setattr(u, 'last_name', f"NewLast_{u.user_id}")
            ]),
            ("all_fields", lambda u: [
                setattr(u, 'email', f"new{u.user_id}@example.com"),
                setattr(u, 'first_name', f"AllNew_{u.user_id}"),
                setattr(u, 'last_name', f"AllNewLast_{u.user_id}"),
                setattr(u, 'phone', f"999-{u.user_id:04d}")
            ])
        ]
        
        for test_name, update_func in update_tests:
            print(f"\nTesting {test_name} updates...")
            
            # Get subset of users to update
            users_to_update = db_session.query(PerformanceTestUser).limit(100).all()
            
            start_time = time.time()
            
            for user in users_to_update:
                update_func(user)
            
            db_session.commit()
            end_time = time.time()
            
            duration = end_time - start_time
            updates_per_second = len(users_to_update) / duration
            
            print(f"  Update time: {duration:.3f} seconds")
            print(f"  Updates per second: {updates_per_second:.1f}")
            print(f"  Encryption calls: {mock_encryption_service.encrypt_data.call_count}")
            
            # Performance assertions
            assert updates_per_second > 20, f"Update performance too slow: {updates_per_second:.1f} updates/sec"
            
            mock_encryption_service.reset_mock()

    @pytest.mark.slow
    def test_concurrent_database_operations(self, db_engine, tenant_context, mock_encryption_service):
        """Test concurrent database operations with encryption."""
        def worker_operations(worker_id: int, operation_count: int) -> Dict[str, Any]:
            """Worker function for concurrent database operations."""
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
            session = SessionLocal()
            
            try:
                start_time = time.time()
                
                # Mix of operations: insert, query, update
                for i in range(operation_count):
                    if i % 3 == 0:  # Insert
                        user = PerformanceTestUser(
                            email=f"worker{worker_id}_user{i}@example.com",
                            first_name=f"Worker{worker_id}First{i}",
                            last_name=f"Worker{worker_id}Last{i}",
                            user_id=worker_id * 1000 + i
                        )
                        session.add(user)
                        session.commit()
                    
                    elif i % 3 == 1:  # Query
                        users = session.query(PerformanceTestUser).limit(10).all()
                        # Access encrypted fields to trigger decryption
                        for user in users:
                            _ = user.email
                    
                    else:  # Update
                        user = session.query(PerformanceTestUser).first()
                        if user:
                            user.first_name = f"Updated_Worker{worker_id}_{i}"
                            session.commit()
                
                end_time = time.time()
                
                return {
                    'worker_id': worker_id,
                    'operations': operation_count,
                    'duration': end_time - start_time,
                    'ops_per_second': operation_count / (end_time - start_time)
                }
                
            finally:
                session.close()
        
        # Test with different numbers of concurrent workers
        worker_counts = [1, 2, 4]
        operations_per_worker = 50
        
        for num_workers in worker_counts:
            print(f"\nTesting {num_workers} concurrent database workers...")
            
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [
                    executor.submit(worker_operations, worker_id, operations_per_worker)
                    for worker_id in range(num_workers)
                ]
                
                results = [future.result() for future in as_completed(futures)]
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Calculate metrics
            total_operations = sum(r['operations'] for r in results)
            aggregate_ops_per_second = total_operations / total_duration
            avg_worker_ops_per_second = statistics.mean(r['ops_per_second'] for r in results)
            
            print(f"  Total operations: {total_operations}")
            print(f"  Total time: {total_duration:.2f} seconds")
            print(f"  Aggregate ops/sec: {aggregate_ops_per_second:.2f}")
            print(f"  Average worker ops/sec: {avg_worker_ops_per_second:.2f}")
            
            # Performance assertions
            assert aggregate_ops_per_second > 10, f"Concurrent DB performance too slow: {aggregate_ops_per_second:.2f} ops/sec"
            
            # Clean up data for next test
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
            cleanup_session = SessionLocal()
            try:
                cleanup_session.query(PerformanceTestUser).delete()
                cleanup_session.commit()
            finally:
                cleanup_session.close()


class TestResourceConsumption:
    """Test resource consumption patterns."""

    def test_cpu_usage_under_encryption_load(self):
        """Test CPU usage patterns during encryption operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            set_tenant_context(1)
            
            # Measure CPU usage during encryption load
            cpu_measurements = []
            
            # Baseline CPU measurement
            baseline_cpu = process.cpu_percent()
            time.sleep(0.1)  # Let CPU measurement stabilize
            
            start_time = time.time()
            
            # Generate encryption load
            for i in range(100):
                data = f"CPU test data {i} " * 100  # ~1.5KB per operation
                encrypted = service.encrypt_data(data, 1)
                decrypted = service.decrypt_data(encrypted, 1)
                
                # Measure CPU every 10 operations
                if i % 10 == 0:
                    cpu_percent = process.cpu_percent()
                    cpu_measurements.append(cpu_percent)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Calculate CPU statistics
            avg_cpu = statistics.mean(cpu_measurements) if cpu_measurements else 0
            max_cpu = max(cpu_measurements) if cpu_measurements else 0
            
            print(f"\nCPU USAGE ANALYSIS:")
            print(f"  Test duration: {duration:.2f} seconds")
            print(f"  Baseline CPU: {baseline_cpu:.1f}%")
            print(f"  Average CPU during load: {avg_cpu:.1f}%")
            print(f"  Peak CPU during load: {max_cpu:.1f}%")
            
            # CPU usage should be reasonable (not pegging the CPU)
            assert max_cpu < 80, f"CPU usage too high: {max_cpu:.1f}%"
            
            clear_tenant_context()

    def test_encryption_scalability_limits(self):
        """Test encryption system behavior at scale limits."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            set_tenant_context(1)
            
            # Test with increasingly large data sizes
            data_sizes = [1024, 10240, 102400, 1024000]  # 1KB to 1MB
            
            performance_metrics = {}
            
            for size in data_sizes:
                data = "X" * size
                
                # Measure encryption time
                start_time = time.time()
                encrypted = service.encrypt_data(data, 1)
                encryption_time = time.time() - start_time
                
                # Measure decryption time
                start_time = time.time()
                decrypted = service.decrypt_data(encrypted, 1)
                decryption_time = time.time() - start_time
                
                assert decrypted == data
                
                performance_metrics[size] = {
                    'encryption_time': encryption_time,
                    'decryption_time': decryption_time,
                    'total_time': encryption_time + decryption_time,
                    'throughput_mbps': (size * 2) / (encryption_time + decryption_time) / 1024 / 1024
                }
            
            # Analyze scalability
            print(f"\nSCALABILITY ANALYSIS:")
            for size, metrics in performance_metrics.items():
                print(f"  {size:,} bytes:")
                print(f"    Encryption: {metrics['encryption_time']:.4f}s")
                print(f"    Decryption: {metrics['decryption_time']:.4f}s")
                print(f"    Throughput: {metrics['throughput_mbps']:.2f} MB/s")
            
            # Verify reasonable performance scaling
            small_throughput = performance_metrics[1024]['throughput_mbps']
            large_throughput = performance_metrics[1024000]['throughput_mbps']
            
            # Large data should maintain at least 50% of small data throughput
            assert large_throughput >= small_throughput * 0.5, \
                f"Throughput degradation too severe: {large_throughput:.2f} vs {small_throughput:.2f} MB/s"
            
            clear_tenant_context()

    def test_cache_efficiency_under_load(self):
        """Test cache efficiency under various load patterns."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            
            # Test cache efficiency with multiple tenants
            tenant_ids = [1, 2, 3, 4, 5]
            operations_per_tenant = 20
            
            # Clear cache and measure cache misses
            service.clear_cache()
            initial_call_count = mock_kms_instance.retrieve_tenant_key.call_count
            
            # Perform operations for each tenant
            for tenant_id in tenant_ids:
                set_tenant_context(tenant_id)
                
                for i in range(operations_per_tenant):
                    data = f"Cache test data for tenant {tenant_id} operation {i}"
                    encrypted = service.encrypt_data(data, tenant_id)
                    decrypted = service.decrypt_data(encrypted, tenant_id)
                    assert decrypted == data
                
                clear_tenant_context()
            
            # Calculate cache efficiency
            total_operations = len(tenant_ids) * operations_per_tenant * 2  # encrypt + decrypt
            key_retrievals = mock_kms_instance.retrieve_tenant_key.call_count - initial_call_count
            cache_hit_rate = (total_operations - key_retrievals) / total_operations * 100
            
            print(f"\nCACHE EFFICIENCY ANALYSIS:")
            print(f"  Total operations: {total_operations}")
            print(f"  Key retrievals: {key_retrievals}")
            print(f"  Cache hit rate: {cache_hit_rate:.1f}%")
            
            # Cache should be highly effective
            assert cache_hit_rate > 90, f"Cache hit rate too low: {cache_hit_rate:.1f}%"
            
            # Verify cache stats
            stats = service.get_cache_stats()
            assert stats['cached_keys'] == len(tenant_ids)
            assert stats['cache_size_bytes'] > 0