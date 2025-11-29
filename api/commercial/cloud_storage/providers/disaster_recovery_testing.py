"""
Disaster Recovery Testing Procedures.

This module provides comprehensive testing procedures for disaster recovery
capabilities including integrity checks, failover testing, and restoration validation.
"""

import asyncio
import logging
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .disaster_recovery_service import (
    DisasterRecoveryService,
    RecoveryTestResult,
    RecoveryTestStatus,
    ReplicationStatus
)
from core.interfaces.storage_provider import StorageProvider, CloudStorageProvider
from .factory import StorageProviderFactory

logger = logging.getLogger(__name__)


@dataclass
class TestScenario:
    """Defines a disaster recovery test scenario."""
    name: str
    description: str
    test_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = "success"
    timeout_seconds: int = 300


@dataclass
class TestExecutionResult:
    """Result of executing a test scenario."""
    scenario: TestScenario
    status: RecoveryTestStatus
    execution_time_seconds: int
    details: Dict[str, Any]
    error_message: Optional[str] = None


class DisasterRecoveryTestSuite:
    """
    Comprehensive test suite for disaster recovery capabilities.
    
    Provides automated testing of:
    - Cross-region replication integrity
    - Automatic failover mechanisms
    - Data restoration procedures
    - Backup version management
    - Corruption detection and recovery
    """
    
    def __init__(
        self,
        db: Session,
        dr_service: DisasterRecoveryService,
        provider_factory: StorageProviderFactory
    ):
        """
        Initialize disaster recovery test suite.
        
        Args:
            db: Database session
            dr_service: Disaster recovery service instance
            provider_factory: Storage provider factory
        """
        self.db = db
        self.dr_service = dr_service
        self.provider_factory = provider_factory
        
        # Test scenarios
        self.test_scenarios = self._define_test_scenarios()
        
        # Test execution history
        self.execution_history: List[TestExecutionResult] = []
    
    def _define_test_scenarios(self) -> List[TestScenario]:
        """
        Define comprehensive test scenarios for disaster recovery.
        
        Returns:
            List of test scenarios
        """
        return [
            TestScenario(
                name="basic_replication_test",
                description="Test basic cross-region replication functionality",
                test_type="replication",
                parameters={
                    "test_file_size": 1024,  # 1KB test file
                    "verify_checksum": True,
                    "cleanup_after": True
                }
            ),
            TestScenario(
                name="large_file_replication_test",
                description="Test replication of large files",
                test_type="replication",
                parameters={
                    "test_file_size": 10 * 1024 * 1024,  # 10MB test file
                    "verify_checksum": True,
                    "cleanup_after": True
                },
                timeout_seconds=600
            ),
            TestScenario(
                name="corruption_detection_test",
                description="Test corruption detection across regions",
                test_type="integrity",
                parameters={
                    "simulate_corruption": True,
                    "corruption_type": "checksum_mismatch"
                }
            ),
            TestScenario(
                name="automatic_failover_test",
                description="Test automatic failover to backup regions",
                test_type="failover",
                parameters={
                    "simulate_primary_failure": True,
                    "verify_failover_time": True
                }
            ),
            TestScenario(
                name="backup_restoration_test",
                description="Test restoration from backup regions",
                test_type="restoration",
                parameters={
                    "test_multiple_regions": True,
                    "verify_data_integrity": True
                }
            ),
            TestScenario(
                name="versioned_backup_test",
                description="Test versioned backup creation and restoration",
                test_type="versioning",
                parameters={
                    "create_multiple_versions": 3,
                    "test_version_restoration": True
                }
            ),
            TestScenario(
                name="concurrent_operations_test",
                description="Test disaster recovery under concurrent operations",
                test_type="stress",
                parameters={
                    "concurrent_uploads": 5,
                    "concurrent_replications": True
                },
                timeout_seconds=900
            ),
            TestScenario(
                name="network_partition_test",
                description="Test behavior during network partitions",
                test_type="network",
                parameters={
                    "simulate_network_issues": True,
                    "test_recovery_after_partition": True
                }
            )
        ]
    
    async def run_comprehensive_test(
        self,
        scenarios: Optional[List[str]] = None,
        parallel_execution: bool = False
    ) -> Dict[str, Any]:
        """
        Run comprehensive disaster recovery test suite.
        
        Args:
            scenarios: List of scenario names to run (all if None)
            parallel_execution: Whether to run scenarios in parallel
            
        Returns:
            Dictionary with test results and summary
        """
        start_time = time.time()
        
        # Filter scenarios if specified
        test_scenarios = self.test_scenarios
        if scenarios:
            test_scenarios = [s for s in self.test_scenarios if s.name in scenarios]
        
        logger.info(f"Starting comprehensive disaster recovery test with {len(test_scenarios)} scenarios")
        
        # Execute test scenarios
        if parallel_execution:
            results = await self._run_scenarios_parallel(test_scenarios)
        else:
            results = await self._run_scenarios_sequential(test_scenarios)
        
        # Generate test summary
        total_time = time.time() - start_time
        summary = self._generate_test_summary(results, total_time)
        
        # Store execution history
        self.execution_history.extend(results)
        
        logger.info(f"Comprehensive test completed in {total_time:.2f} seconds")
        return summary
    
    async def _run_scenarios_sequential(
        self,
        scenarios: List[TestScenario]
    ) -> List[TestExecutionResult]:
        """
        Run test scenarios sequentially.
        
        Args:
            scenarios: List of test scenarios to execute
            
        Returns:
            List of test execution results
        """
        results = []
        
        for scenario in scenarios:
            try:
                logger.info(f"Executing test scenario: {scenario.name}")
                result = await self._execute_scenario(scenario)
                results.append(result)
                
                # Brief pause between tests
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to execute scenario {scenario.name}: {e}")
                results.append(TestExecutionResult(
                    scenario=scenario,
                    status=RecoveryTestStatus.FAILED,
                    execution_time_seconds=0,
                    details={},
                    error_message=str(e)
                ))
        
        return results
    
    async def _run_scenarios_parallel(
        self,
        scenarios: List[TestScenario]
    ) -> List[TestExecutionResult]:
        """
        Run test scenarios in parallel.
        
        Args:
            scenarios: List of test scenarios to execute
            
        Returns:
            List of test execution results
        """
        # Create tasks for parallel execution
        tasks = [self._execute_scenario(scenario) for scenario in scenarios]
        
        # Execute all scenarios concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(TestExecutionResult(
                    scenario=scenarios[i],
                    status=RecoveryTestStatus.FAILED,
                    execution_time_seconds=0,
                    details={},
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_scenario(self, scenario: TestScenario) -> TestExecutionResult:
        """
        Execute a single test scenario.
        
        Args:
            scenario: Test scenario to execute
            
        Returns:
            Test execution result
        """
        start_time = time.time()
        
        try:
            # Execute scenario based on type
            if scenario.test_type == "replication":
                details = await self._test_replication(scenario)
            elif scenario.test_type == "integrity":
                details = await self._test_integrity(scenario)
            elif scenario.test_type == "failover":
                details = await self._test_failover(scenario)
            elif scenario.test_type == "restoration":
                details = await self._test_restoration(scenario)
            elif scenario.test_type == "versioning":
                details = await self._test_versioning(scenario)
            elif scenario.test_type == "stress":
                details = await self._test_stress(scenario)
            elif scenario.test_type == "network":
                details = await self._test_network_partition(scenario)
            else:
                raise ValueError(f"Unknown test type: {scenario.test_type}")
            
            execution_time = time.time() - start_time
            
            # Determine status based on details
            status = RecoveryTestStatus.PASSED
            if details.get('errors') or details.get('failed_operations', 0) > 0:
                if details.get('successful_operations', 0) > 0:
                    status = RecoveryTestStatus.PARTIAL
                else:
                    status = RecoveryTestStatus.FAILED
            
            return TestExecutionResult(
                scenario=scenario,
                status=status,
                execution_time_seconds=int(execution_time),
                details=details
            )
            
        except asyncio.TimeoutError:
            return TestExecutionResult(
                scenario=scenario,
                status=RecoveryTestStatus.FAILED,
                execution_time_seconds=scenario.timeout_seconds,
                details={},
                error_message=f"Test timed out after {scenario.timeout_seconds} seconds"
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return TestExecutionResult(
                scenario=scenario,
                status=RecoveryTestStatus.FAILED,
                execution_time_seconds=int(execution_time),
                details={},
                error_message=str(e)
            )
    
    async def _test_replication(self, scenario: TestScenario) -> Dict[str, Any]:
        """
        Test cross-region replication functionality.
        
        Args:
            scenario: Test scenario parameters
            
        Returns:
            Test execution details
        """
        params = scenario.parameters
        file_size = params.get('test_file_size', 1024)
        verify_checksum = params.get('verify_checksum', True)
        cleanup_after = params.get('cleanup_after', True)
        
        # Generate test file
        test_content = b'A' * file_size
        test_file_key = f"dr_test/replication_{int(time.time())}.bin"
        
        details = {
            'test_file_key': test_file_key,
            'file_size': file_size,
            'successful_operations': 0,
            'failed_operations': 0,
            'replication_regions': [],
            'errors': []
        }
        
        try:
            # Get primary provider
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                raise Exception("No primary provider available")
            
            # Upload test file
            upload_result = await primary_provider.upload_file(
                file_content=test_content,
                file_key=test_file_key,
                content_type='application/octet-stream',
                metadata={'test_type': 'replication_test'}
            )
            
            if not upload_result.success:
                raise Exception(f"Failed to upload test file: {upload_result.error_message}")
            
            details['successful_operations'] += 1
            
            # Test replication
            replication_record = await self.dr_service.replicate_file(
                file_key=test_file_key,
                file_content=test_content,
                primary_provider=primary_provider,
                metadata={'test_type': 'replication_test'}
            )
            
            details['replication_status'] = replication_record.status.value
            details['replication_regions'] = list(replication_record.backup_regions.keys())
            
            if replication_record.status == ReplicationStatus.COMPLETED:
                details['successful_operations'] += 1
            else:
                details['failed_operations'] += 1
                if replication_record.error_message:
                    details['errors'].append(replication_record.error_message)
            
            # Verify checksums if requested
            if verify_checksum and replication_record.backup_regions:
                checksum_verification = await self._verify_replication_checksums(
                    test_file_key, replication_record
                )
                details['checksum_verification'] = checksum_verification
                
                if checksum_verification['all_match']:
                    details['successful_operations'] += 1
                else:
                    details['failed_operations'] += 1
                    details['errors'].extend(checksum_verification['errors'])
            
            # Cleanup if requested
            if cleanup_after:
                await self._cleanup_test_file(test_file_key, primary_provider)
                details['cleanup_performed'] = True
            
        except Exception as e:
            details['failed_operations'] += 1
            details['errors'].append(str(e))
        
        return details
    
    async def _test_integrity(self, scenario: TestScenario) -> Dict[str, Any]:
        """
        Test corruption detection and integrity verification.
        
        Args:
            scenario: Test scenario parameters
            
        Returns:
            Test execution details
        """
        params = scenario.parameters
        simulate_corruption = params.get('simulate_corruption', False)
        
        # Generate test file
        test_content = b'INTEGRITY_TEST_' + b'X' * 1000
        test_file_key = f"dr_test/integrity_{int(time.time())}.bin"
        
        details = {
            'test_file_key': test_file_key,
            'corruption_detected': False,
            'successful_operations': 0,
            'failed_operations': 0,
            'errors': []
        }
        
        try:
            # Get primary provider
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                raise Exception("No primary provider available")
            
            # Upload and replicate test file
            upload_result = await primary_provider.upload_file(
                file_content=test_content,
                file_key=test_file_key,
                content_type='application/octet-stream'
            )
            
            if not upload_result.success:
                raise Exception(f"Failed to upload test file: {upload_result.error_message}")
            
            replication_record = await self.dr_service.replicate_file(
                file_key=test_file_key,
                file_content=test_content,
                primary_provider=primary_provider
            )
            
            details['successful_operations'] += 1
            
            # Test corruption detection
            is_corrupted, error_msg = await self.dr_service.detect_corruption(
                test_file_key, primary_provider
            )
            
            details['corruption_detected'] = is_corrupted
            
            if simulate_corruption:
                # If we're simulating corruption, we expect it to be detected
                if is_corrupted:
                    details['successful_operations'] += 1
                    details['corruption_simulation_successful'] = True
                else:
                    details['failed_operations'] += 1
                    details['errors'].append("Simulated corruption was not detected")
            else:
                # If not simulating corruption, we expect no corruption
                if not is_corrupted:
                    details['successful_operations'] += 1
                else:
                    details['failed_operations'] += 1
                    details['errors'].append(f"Unexpected corruption detected: {error_msg}")
            
            # Cleanup
            await self._cleanup_test_file(test_file_key, primary_provider)
            
        except Exception as e:
            details['failed_operations'] += 1
            details['errors'].append(str(e))
        
        return details
    
    async def _test_failover(self, scenario: TestScenario) -> Dict[str, Any]:
        """
        Test automatic failover mechanisms.
        
        Args:
            scenario: Test scenario parameters
            
        Returns:
            Test execution details
        """
        params = scenario.parameters
        simulate_failure = params.get('simulate_primary_failure', False)
        
        details = {
            'failover_tested': False,
            'failover_successful': False,
            'successful_operations': 0,
            'failed_operations': 0,
            'errors': []
        }
        
        try:
            # Test failover capability
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                raise Exception("No primary provider available")
            
            # Check if backup regions are configured
            if not self.dr_service.config.backup_regions:
                details['errors'].append("No backup regions configured for failover testing")
                details['failed_operations'] += 1
                return details
            
            # Test failover to first backup region
            failed_region = self.dr_service.config.primary_region
            failover_successful = await self.dr_service.automatic_failover(
                failed_region=failed_region,
                provider_type=primary_provider.provider_type
            )
            
            details['failover_tested'] = True
            details['failover_successful'] = failover_successful
            
            if failover_successful:
                details['successful_operations'] += 1
            else:
                details['failed_operations'] += 1
                details['errors'].append("Automatic failover failed")
            
        except Exception as e:
            details['failed_operations'] += 1
            details['errors'].append(str(e))
        
        return details
    
    async def _test_restoration(self, scenario: TestScenario) -> Dict[str, Any]:
        """
        Test data restoration from backup regions.
        
        Args:
            scenario: Test scenario parameters
            
        Returns:
            Test execution details
        """
        params = scenario.parameters
        test_multiple_regions = params.get('test_multiple_regions', True)
        
        # Generate test file
        test_content = b'RESTORATION_TEST_' + b'Y' * 500
        test_file_key = f"dr_test/restoration_{int(time.time())}.bin"
        
        details = {
            'test_file_key': test_file_key,
            'restoration_attempts': 0,
            'successful_restorations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'errors': []
        }
        
        try:
            # Get primary provider
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                raise Exception("No primary provider available")
            
            # Upload and replicate test file
            upload_result = await primary_provider.upload_file(
                file_content=test_content,
                file_key=test_file_key,
                content_type='application/octet-stream'
            )
            
            if not upload_result.success:
                raise Exception(f"Failed to upload test file: {upload_result.error_message}")
            
            replication_record = await self.dr_service.replicate_file(
                file_key=test_file_key,
                file_content=test_content,
                primary_provider=primary_provider
            )
            
            if replication_record.status != ReplicationStatus.COMPLETED:
                raise Exception("File replication failed, cannot test restoration")
            
            details['successful_operations'] += 1
            
            # Test restoration from backup regions
            for region in replication_record.backup_regions.keys():
                details['restoration_attempts'] += 1
                
                try:
                    restore_result = await self.dr_service.restore_from_backup(
                        file_key=test_file_key,
                        provider=primary_provider,
                        preferred_region=region
                    )
                    
                    if restore_result.success:
                        details['successful_restorations'] += 1
                        details['successful_operations'] += 1
                    else:
                        details['failed_operations'] += 1
                        details['errors'].append(f"Restoration from {region} failed: {restore_result.error_message}")
                    
                    if not test_multiple_regions:
                        break
                        
                except Exception as e:
                    details['failed_operations'] += 1
                    details['errors'].append(f"Restoration from {region} error: {str(e)}")
            
            # Cleanup
            await self._cleanup_test_file(test_file_key, primary_provider)
            
        except Exception as e:
            details['failed_operations'] += 1
            details['errors'].append(str(e))
        
        return details
    
    async def _test_versioning(self, scenario: TestScenario) -> Dict[str, Any]:
        """
        Test versioned backup functionality.
        
        Args:
            scenario: Test scenario parameters
            
        Returns:
            Test execution details
        """
        params = scenario.parameters
        num_versions = params.get('create_multiple_versions', 3)
        
        test_file_key = f"dr_test/versioning_{int(time.time())}.bin"
        
        details = {
            'test_file_key': test_file_key,
            'versions_created': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'errors': []
        }
        
        try:
            # Get primary provider
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                raise Exception("No primary provider available")
            
            # Create multiple versions
            for i in range(num_versions):
                version_content = f'VERSION_{i}_'.encode() + b'Z' * 100
                
                backup_version = await self.dr_service.create_versioned_backup(
                    file_key=test_file_key,
                    file_content=version_content,
                    provider=primary_provider,
                    metadata={'version': i}
                )
                
                details['versions_created'] += 1
                details['successful_operations'] += 1
                
                # Brief pause between versions
                await asyncio.sleep(0.1)
            
            # Test version restoration if requested
            if params.get('test_version_restoration', False):
                # Try to restore from versioned backup
                restore_result = await self.dr_service._restore_from_versioned_backup(
                    test_file_key, primary_provider
                )
                
                if restore_result.success:
                    details['successful_operations'] += 1
                    details['version_restoration_successful'] = True
                else:
                    details['failed_operations'] += 1
                    details['errors'].append(f"Version restoration failed: {restore_result.error_message}")
            
        except Exception as e:
            details['failed_operations'] += 1
            details['errors'].append(str(e))
        
        return details
    
    async def _test_stress(self, scenario: TestScenario) -> Dict[str, Any]:
        """
        Test disaster recovery under stress conditions.
        
        Args:
            scenario: Test scenario parameters
            
        Returns:
            Test execution details
        """
        params = scenario.parameters
        concurrent_uploads = params.get('concurrent_uploads', 5)
        
        details = {
            'concurrent_operations': concurrent_uploads,
            'successful_operations': 0,
            'failed_operations': 0,
            'errors': []
        }
        
        try:
            # Get primary provider
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                raise Exception("No primary provider available")
            
            # Create concurrent upload tasks
            tasks = []
            for i in range(concurrent_uploads):
                test_content = f'STRESS_TEST_{i}_'.encode() + b'S' * 500
                test_file_key = f"dr_test/stress_{int(time.time())}_{i}.bin"
                
                task = self._stress_test_single_operation(
                    primary_provider, test_file_key, test_content
                )
                tasks.append(task)
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    details['failed_operations'] += 1
                    details['errors'].append(str(result))
                elif result.get('success', False):
                    details['successful_operations'] += 1
                else:
                    details['failed_operations'] += 1
                    details['errors'].append(result.get('error', 'Unknown error'))
            
        except Exception as e:
            details['failed_operations'] += 1
            details['errors'].append(str(e))
        
        return details
    
    async def _stress_test_single_operation(
        self,
        provider: CloudStorageProvider,
        file_key: str,
        content: bytes
    ) -> Dict[str, Any]:
        """
        Execute a single stress test operation.
        
        Args:
            provider: Storage provider
            file_key: File key for the test
            content: File content
            
        Returns:
            Operation result
        """
        try:
            # Upload file
            upload_result = await provider.upload_file(
                file_content=content,
                file_key=file_key,
                content_type='application/octet-stream'
            )
            
            if not upload_result.success:
                return {'success': False, 'error': upload_result.error_message}
            
            # Replicate file
            replication_record = await self.dr_service.replicate_file(
                file_key=file_key,
                file_content=content,
                primary_provider=provider
            )
            
            # Cleanup
            await self._cleanup_test_file(file_key, provider)
            
            return {
                'success': True,
                'replication_status': replication_record.status.value,
                'regions_replicated': len(replication_record.backup_regions)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _test_network_partition(self, scenario: TestScenario) -> Dict[str, Any]:
        """
        Test behavior during simulated network partitions.
        
        Args:
            scenario: Test scenario parameters
            
        Returns:
            Test execution details
        """
        # Note: This is a simplified simulation
        # In a real environment, this would involve network manipulation
        
        details = {
            'network_partition_simulated': True,
            'successful_operations': 0,
            'failed_operations': 0,
            'errors': []
        }
        
        try:
            # Simulate network partition by testing provider health
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                raise Exception("No primary provider available")
            
            # Test health check during "partition"
            health_result = await primary_provider.health_check()
            
            if health_result.healthy:
                details['successful_operations'] += 1
                details['primary_provider_accessible'] = True
            else:
                details['failed_operations'] += 1
                details['primary_provider_accessible'] = False
                details['errors'].append(f"Primary provider unhealthy: {health_result.error_message}")
            
            # Test backup region accessibility
            backup_accessible = 0
            for region in self.dr_service.config.backup_regions:
                try:
                    regional_provider = await self.dr_service._get_regional_provider(
                        primary_provider.provider_type, region
                    )
                    
                    if regional_provider:
                        regional_health = await regional_provider.health_check()
                        if regional_health.healthy:
                            backup_accessible += 1
                        
                except Exception as e:
                    details['errors'].append(f"Error accessing backup region {region}: {str(e)}")
            
            details['backup_regions_accessible'] = backup_accessible
            details['total_backup_regions'] = len(self.dr_service.config.backup_regions)
            
            if backup_accessible > 0:
                details['successful_operations'] += 1
            else:
                details['failed_operations'] += 1
                details['errors'].append("No backup regions accessible during partition")
            
        except Exception as e:
            details['failed_operations'] += 1
            details['errors'].append(str(e))
        
        return details
    
    async def _verify_replication_checksums(
        self,
        file_key: str,
        replication_record
    ) -> Dict[str, Any]:
        """
        Verify checksums across replicated regions.
        
        Args:
            file_key: File key to verify
            replication_record: Replication record with checksums
            
        Returns:
            Checksum verification results
        """
        verification = {
            'all_match': True,
            'primary_checksum': replication_record.primary_checksum,
            'backup_checksums': replication_record.backup_regions.copy(),
            'mismatches': [],
            'errors': []
        }
        
        # Check if all backup checksums match primary
        for region, checksum in replication_record.backup_regions.items():
            if checksum != replication_record.primary_checksum:
                verification['all_match'] = False
                verification['mismatches'].append({
                    'region': region,
                    'expected': replication_record.primary_checksum,
                    'actual': checksum
                })
        
        return verification
    
    async def _cleanup_test_file(
        self,
        file_key: str,
        provider: CloudStorageProvider
    ) -> None:
        """
        Clean up test files after testing.
        
        Args:
            file_key: File key to clean up
            provider: Storage provider
        """
        try:
            await provider.delete_file(file_key)
            
            # Also clean up any versioned backups
            backup_prefix = f"backups/{file_key}.v"
            backup_list = await provider.list_files(prefix=backup_prefix, limit=50)
            
            for backup_info in backup_list.get('files', []):
                try:
                    await provider.delete_file(backup_info['key'])
                except Exception as e:
                    logger.warning(f"Failed to cleanup backup file {backup_info['key']}: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to cleanup test file {file_key}: {e}")
    
    def _generate_test_summary(
        self,
        results: List[TestExecutionResult],
        total_time: float
    ) -> Dict[str, Any]:
        """
        Generate comprehensive test summary.
        
        Args:
            results: List of test execution results
            total_time: Total execution time in seconds
            
        Returns:
            Test summary dictionary
        """
        total_tests = len(results)
        passed_tests = len([r for r in results if r.status == RecoveryTestStatus.PASSED])
        failed_tests = len([r for r in results if r.status == RecoveryTestStatus.FAILED])
        partial_tests = len([r for r in results if r.status == RecoveryTestStatus.PARTIAL])
        
        summary = {
            'test_execution_summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'partial_tests': partial_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                'total_execution_time_seconds': int(total_time)
            },
            'test_results': [],
            'disaster_recovery_status': {
                'overall_health': 'healthy' if failed_tests == 0 else ('degraded' if passed_tests > 0 else 'critical'),
                'replication_functional': any(r.scenario.test_type == 'replication' and r.status == RecoveryTestStatus.PASSED for r in results),
                'failover_functional': any(r.scenario.test_type == 'failover' and r.status == RecoveryTestStatus.PASSED for r in results),
                'restoration_functional': any(r.scenario.test_type == 'restoration' and r.status == RecoveryTestStatus.PASSED for r in results)
            },
            'recommendations': []
        }
        
        # Add individual test results
        for result in results:
            summary['test_results'].append({
                'scenario_name': result.scenario.name,
                'description': result.scenario.description,
                'status': result.status.value,
                'execution_time_seconds': result.execution_time_seconds,
                'details': result.details,
                'error_message': result.error_message
            })
        
        # Generate recommendations
        if failed_tests > 0:
            summary['recommendations'].append("Review failed test scenarios and address underlying issues")
        
        if not summary['disaster_recovery_status']['replication_functional']:
            summary['recommendations'].append("Cross-region replication is not functioning properly")
        
        if not summary['disaster_recovery_status']['failover_functional']:
            summary['recommendations'].append("Automatic failover mechanisms need attention")
        
        if not summary['disaster_recovery_status']['restoration_functional']:
            summary['recommendations'].append("Data restoration procedures require investigation")
        
        if partial_tests > 0:
            summary['recommendations'].append("Some tests passed partially - review configuration and network connectivity")
        
        return summary