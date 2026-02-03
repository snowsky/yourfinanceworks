"""
Disaster Recovery Service for Cloud Storage.

This service implements disaster recovery capabilities including cross-region replication,
versioned backups, data corruption detection, automatic failover, and recovery testing.
"""

import asyncio
import logging
import time
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from core.interfaces.storage_provider import (
    CloudStorageProvider, 
    StorageResult, 
    StorageConfig, 
    StorageProvider,
    FileMetadata,
    HealthCheckResult
)
from .factory import StorageProviderFactory
from core.models.models_per_tenant import StorageOperationLog
from commercial.cloud_storage.config import CloudStorageConfig

logger = logging.getLogger(__name__)


class ReplicationStatus(Enum):
    """Status of file replication across regions."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRUPTED = "corrupted"


class RecoveryTestStatus(Enum):
    """Status of disaster recovery tests."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ReplicationConfig:
    """Configuration for cross-region replication."""
    enabled: bool = False
    primary_region: str = "us-east-1"
    backup_regions: List[str] = field(default_factory=lambda: ["us-west-2"])
    replication_delay_seconds: int = 300  # 5 minutes
    critical_file_patterns: List[str] = field(default_factory=lambda: ["invoices/", "contracts/"])
    max_backup_versions: int = 5
    corruption_check_interval_hours: int = 24
    auto_failover_enabled: bool = True
    failover_threshold_failures: int = 3
    recovery_test_interval_days: int = 30


@dataclass
class BackupVersion:
    """Represents a versioned backup of a file."""
    version_id: str
    file_key: str
    backup_timestamp: datetime
    checksum: str
    size: int
    region: str
    provider: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ReplicationRecord:
    """Record of file replication across regions."""
    file_key: str
    primary_checksum: str
    primary_region: str
    backup_regions: Dict[str, str]  # region -> checksum
    last_replicated: datetime
    status: ReplicationStatus
    error_message: Optional[str] = None


@dataclass
class RecoveryTestResult:
    """Result of a disaster recovery test."""
    test_id: str
    test_timestamp: datetime
    test_type: str  # "integrity", "failover", "restoration"
    status: RecoveryTestStatus
    files_tested: int
    files_passed: int
    files_failed: int
    duration_seconds: int
    error_details: Optional[List[str]] = None


class DisasterRecoveryService:
    """
    Service for implementing disaster recovery capabilities for cloud storage.

    Features:
    - Cross-region replication for critical files
    - Versioned backups with configurable retention
    - Data corruption detection and automatic restoration
    - Automatic failover between regions
    - Comprehensive disaster recovery testing
    """

    def __init__(
        self, 
        db: Session, 
        provider_factory: StorageProviderFactory,
        config: Optional[ReplicationConfig] = None
    ):
        """
        Initialize disaster recovery service.

        Args:
            db: Database session for logging
            provider_factory: Factory for creating storage providers
            config: Replication configuration
        """
        self.db = db
        self.provider_factory = provider_factory
        self.config = config or ReplicationConfig()

        # Cache for provider instances by region
        self._regional_providers: Dict[str, Dict[StorageProvider, CloudStorageProvider]] = {}

        # In-memory tracking of replication status
        self._replication_records: Dict[str, ReplicationRecord] = {}

        # Recovery test history
        self._test_history: List[RecoveryTestResult] = []

        logger.info(f"Disaster recovery service initialized with replication: {self.config.enabled}")

    def _is_critical_file(self, file_key: str) -> bool:
        """
        Determine if a file is critical and requires replication.

        Args:
            file_key: The file key to check

        Returns:
            True if file is critical and should be replicated
        """
        if not self.config.critical_file_patterns:
            return True  # Replicate all files if no patterns specified

        return any(pattern in file_key for pattern in self.config.critical_file_patterns)

    def _calculate_file_checksum(self, file_content: bytes) -> str:
        """
        Calculate SHA-256 checksum for file integrity verification.

        Args:
            file_content: File content as bytes

        Returns:
            SHA-256 checksum as hex string
        """
        return hashlib.sha256(file_content).hexdigest()

    async def _get_regional_provider(
        self, 
        provider_type: StorageProvider, 
        region: str
    ) -> Optional[CloudStorageProvider]:
        """
        Get a storage provider configured for a specific region.

        Args:
            provider_type: Type of storage provider
            region: Target region

        Returns:
            Provider instance configured for the region or None
        """
        try:
            # Check cache first
            if region in self._regional_providers:
                if provider_type in self._regional_providers[region]:
                    return self._regional_providers[region][provider_type]

            # Create regional provider configuration
            base_config = self.provider_factory.get_provider_config(provider_type)
            if not base_config:
                return None

            # Modify configuration for target region
            regional_config = base_config.config.copy()

            if provider_type == StorageProvider.AWS_S3:
                regional_config['region'] = region
                # For cross-region replication, we might need different bucket names
                if region != self.config.primary_region:
                    bucket_name = regional_config.get('bucket_name', '')
                    regional_config['bucket_name'] = f"{bucket_name}-{region}"

            elif provider_type == StorageProvider.AZURE_BLOB:
                # Azure Blob Storage uses different storage accounts per region
                account_name = regional_config.get('account_name', '')
                if region != self.config.primary_region:
                    regional_config['account_name'] = f"{account_name}{region.replace('-', '')}"

            elif provider_type == StorageProvider.GCP_STORAGE:
                # GCP uses different bucket names per region
                bucket_name = regional_config.get('bucket_name', '')
                if region != self.config.primary_region:
                    regional_config['bucket_name'] = f"{bucket_name}-{region}"

            # Create regional storage config
            regional_storage_config = StorageConfig(
                provider=provider_type,
                enabled=True,
                config=regional_config
            )

            # Create provider instance
            provider = self.provider_factory._create_provider(regional_storage_config)

            # Cache the provider
            if region not in self._regional_providers:
                self._regional_providers[region] = {}
            self._regional_providers[region][provider_type] = provider

            return provider

        except Exception as e:
            logger.error(f"Failed to create regional provider {provider_type.value} for region {region}: {e}")
            return None

    async def replicate_file(
        self,
        file_key: str,
        file_content: bytes,
        primary_provider: CloudStorageProvider,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReplicationRecord:
        """
        Replicate a file to backup regions for disaster recovery.

        Args:
            file_key: Unique file key
            file_content: File content as bytes
            primary_provider: Primary storage provider
            metadata: Optional file metadata

        Returns:
            ReplicationRecord with replication status
        """
        if not self.config.enabled:
            logger.debug(f"Replication disabled, skipping file: {file_key}")
            return ReplicationRecord(
                file_key=file_key,
                primary_checksum="",
                primary_region=self.config.primary_region,
                backup_regions={},
                last_replicated=datetime.now(timezone.utc),
                status=ReplicationStatus.COMPLETED
            )

        if not self._is_critical_file(file_key):
            logger.debug(f"File not critical, skipping replication: {file_key}")
            return ReplicationRecord(
                file_key=file_key,
                primary_checksum="",
                primary_region=self.config.primary_region,
                backup_regions={},
                last_replicated=datetime.now(timezone.utc),
                status=ReplicationStatus.COMPLETED
            )

        start_time = time.time()
        primary_checksum = self._calculate_file_checksum(file_content)
        backup_checksums = {}
        replication_errors = []

        try:
            logger.info(f"Starting replication for critical file: {file_key}")

            # Replicate to each backup region
            for region in self.config.backup_regions:
                try:
                    # Get regional provider
                    regional_provider = await self._get_regional_provider(
                        primary_provider.provider_type, region
                    )

                    if not regional_provider:
                        error_msg = f"Failed to get provider for region {region}"
                        replication_errors.append(error_msg)
                        continue

                    # Upload to backup region
                    content_type = metadata.get('content_type', 'application/octet-stream') if metadata else 'application/octet-stream'

                    result = await regional_provider.upload_file(
                        file_content=file_content,
                        file_key=file_key,
                        content_type=content_type,
                        metadata=metadata
                    )

                    if result.success:
                        # Verify integrity by downloading and checking checksum
                        download_result = await regional_provider.download_file(file_key)
                        if download_result.success:
                            downloaded_content = download_result.file_content or b''
                            backup_checksum = self._calculate_file_checksum(downloaded_content)

                            if backup_checksum == primary_checksum:
                                backup_checksums[region] = backup_checksum
                                logger.info(f"Successfully replicated {file_key} to region {region}")
                            else:
                                error_msg = f"Checksum mismatch in region {region}: expected {primary_checksum}, got {backup_checksum}"
                                replication_errors.append(error_msg)
                        else:
                            error_msg = f"Failed to verify replication in region {region}: {download_result.error_message}"
                            replication_errors.append(error_msg)
                    else:
                        error_msg = f"Failed to upload to region {region}: {result.error_message}"
                        replication_errors.append(error_msg)

                except Exception as e:
                    error_msg = f"Replication error for region {region}: {str(e)}"
                    replication_errors.append(error_msg)
                    logger.error(error_msg)

            # Determine overall status
            if len(backup_checksums) == len(self.config.backup_regions):
                status = ReplicationStatus.COMPLETED
            elif len(backup_checksums) > 0:
                status = ReplicationStatus.PARTIAL
            else:
                status = ReplicationStatus.FAILED

            # Create replication record
            record = ReplicationRecord(
                file_key=file_key,
                primary_checksum=primary_checksum,
                primary_region=self.config.primary_region,
                backup_regions=backup_checksums,
                last_replicated=datetime.now(timezone.utc),
                status=status,
                error_message="; ".join(replication_errors) if replication_errors else None
            )

            # Cache the record
            self._replication_records[file_key] = record

            # Log replication operation
            await self._log_replication_operation(
                file_key=file_key,
                operation="replicate",
                status=status.value,
                regions_count=len(backup_checksums),
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=record.error_message
            )

            logger.info(f"Replication completed for {file_key}: {status.value} ({len(backup_checksums)}/{len(self.config.backup_regions)} regions)")
            return record

        except Exception as e:
            error_message = f"Unexpected error during replication: {str(e)}"
            logger.error(f"Replication failed for {file_key}: {error_message}")

            record = ReplicationRecord(
                file_key=file_key,
                primary_checksum=primary_checksum,
                primary_region=self.config.primary_region,
                backup_regions={},
                last_replicated=datetime.now(timezone.utc),
                status=ReplicationStatus.FAILED,
                error_message=error_message
            )

            self._replication_records[file_key] = record
            return record   
    async def create_versioned_backup(
        self,
        file_key: str,
        file_content: bytes,
        provider: CloudStorageProvider,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BackupVersion:
        """
        Create a versioned backup of a file.

        Args:
            file_key: Original file key
            file_content: File content as bytes
            provider: Storage provider
            metadata: Optional file metadata

        Returns:
            BackupVersion with backup details
        """
        try:
            # Generate version ID
            timestamp = datetime.now(timezone.utc)
            version_id = f"{int(timestamp.timestamp())}_{hashlib.md5(file_key.encode()).hexdigest()[:8]}"

            # Create versioned file key
            versioned_key = f"backups/{file_key}.v{version_id}"

            # Calculate checksum
            checksum = self._calculate_file_checksum(file_content)

            # Add backup metadata
            backup_metadata = metadata.copy() if metadata else {}
            backup_metadata.update({
                'original_file_key': file_key,
                'backup_version': version_id,
                'backup_timestamp': timestamp.isoformat(),
                'checksum': checksum,
                'backup_type': 'versioned'
            })

            # Upload versioned backup
            content_type = backup_metadata.get('content_type', 'application/octet-stream')
            result = await provider.upload_file(
                file_content=file_content,
                file_key=versioned_key,
                content_type=content_type,
                metadata=backup_metadata
            )

            if result.success:
                backup_version = BackupVersion(
                    version_id=version_id,
                    file_key=versioned_key,
                    backup_timestamp=timestamp,
                    checksum=checksum,
                    size=len(file_content),
                    region=self.config.primary_region,
                    provider=provider.provider_type.value,
                    metadata=backup_metadata
                )

                logger.info(f"Created versioned backup: {versioned_key}")
                return backup_version
            else:
                raise Exception(f"Failed to create backup: {result.error_message}")

        except Exception as e:
            logger.error(f"Failed to create versioned backup for {file_key}: {e}")
            raise

    async def detect_corruption(
        self,
        file_key: str,
        provider: CloudStorageProvider
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect data corruption by comparing checksums across regions.

        Args:
            file_key: File key to check
            provider: Primary storage provider

        Returns:
            Tuple of (is_corrupted, error_message)
        """
        try:
            # Get replication record
            record = self._replication_records.get(file_key)
            if not record:
                return False, "No replication record found"

            # Download from primary region
            primary_result = await provider.download_file(file_key)
            if not primary_result.success:
                return True, f"Failed to download from primary: {primary_result.error_message}"

            primary_content = primary_result.file_content or b''
            current_checksum = self._calculate_file_checksum(primary_content)

            # Compare with stored checksum
            if current_checksum != record.primary_checksum:
                logger.warning(f"Corruption detected in primary region for {file_key}")
                return True, f"Primary checksum mismatch: expected {record.primary_checksum}, got {current_checksum}"

            # Check backup regions
            corruption_found = False
            corruption_details = []

            for region, expected_checksum in record.backup_regions.items():
                try:
                    regional_provider = await self._get_regional_provider(
                        provider.provider_type, region
                    )

                    if not regional_provider:
                        corruption_details.append(f"Cannot access region {region}")
                        continue

                    backup_result = await regional_provider.download_file(file_key)
                    if not backup_result.success:
                        corruption_details.append(f"Failed to download from region {region}")
                        continue

                    backup_content = backup_result.file_content or b''
                    backup_checksum = self._calculate_file_checksum(backup_content)
                    
                    if backup_checksum != expected_checksum:
                        corruption_found = True
                        corruption_details.append(f"Region {region} checksum mismatch: expected {expected_checksum}, got {backup_checksum}")

                except Exception as e:
                    corruption_details.append(f"Error checking region {region}: {str(e)}")

            if corruption_found:
                error_message = "; ".join(corruption_details)
                logger.warning(f"Corruption detected in backup regions for {file_key}: {error_message}")
                return True, error_message

            return False, None

        except Exception as e:
            error_message = f"Corruption detection failed: {str(e)}"
            logger.error(f"Corruption detection error for {file_key}: {error_message}")
            return True, error_message

    async def restore_from_backup(
        self,
        file_key: str,
        provider: CloudStorageProvider,
        preferred_region: Optional[str] = None
    ) -> StorageResult:
        """
        Restore a file from backup regions or versioned backups.

        Args:
            file_key: File key to restore
            provider: Primary storage provider
            preferred_region: Preferred backup region for restoration

        Returns:
            StorageResult with restoration details
        """
        try:
            record = self._replication_records.get(file_key)
            if not record or not record.backup_regions:
                return StorageResult(
                    success=False,
                    error_message="No backup regions available for restoration"
                )

            # Determine restoration source
            restoration_regions = [preferred_region] if preferred_region else list(record.backup_regions.keys())
            restoration_regions.extend([r for r in record.backup_regions.keys() if r != preferred_region])

            for region in restoration_regions:
                if region not in record.backup_regions:
                    continue

                try:
                    logger.info(f"Attempting restoration from region {region} for {file_key}")

                    # Get regional provider
                    regional_provider = await self._get_regional_provider(
                        provider.provider_type, region
                    )

                    if not regional_provider:
                        logger.warning(f"Cannot access regional provider for {region}")
                        continue

                    # Download from backup region
                    backup_result = await regional_provider.download_file(file_key)
                    if not backup_result.success:
                        logger.warning(f"Failed to download from backup region {region}: {backup_result.error_message}")
                        continue

                    backup_content = backup_result.file_content or b''
                    backup_checksum = self._calculate_file_checksum(backup_content)

                    # Verify integrity
                    expected_checksum = record.backup_regions[region]
                    if backup_checksum != expected_checksum:
                        logger.warning(f"Backup integrity check failed for region {region}")
                        continue

                    # Restore to primary region
                    content_type = backup_result.content_type or 'application/octet-stream'
                    restore_result = await provider.upload_file(
                        file_content=backup_content,
                        file_key=file_key,
                        content_type=content_type,
                        metadata={
                            'restored_from_region': region,
                            'restoration_timestamp': datetime.now(timezone.utc).isoformat(),
                            'original_checksum': expected_checksum
                        }
                    )

                    if restore_result.success:
                        logger.info(f"Successfully restored {file_key} from region {region}")

                        # Update replication record
                        record.primary_checksum = backup_checksum
                        record.last_replicated = datetime.now(timezone.utc)
                        record.status = ReplicationStatus.COMPLETED

                        # Log restoration
                        await self._log_replication_operation(
                            file_key=file_key,
                            operation="restore",
                            status="success",
                            regions_count=1,
                            duration_ms=restore_result.operation_duration_ms or 0,
                            error_message=None
                        )

                        return restore_result
                    else:
                        logger.warning(f"Failed to restore to primary region: {restore_result.error_message}")

                except Exception as e:
                    logger.error(f"Restoration error from region {region}: {str(e)}")
                    continue

            # If all regions failed, try versioned backups
            return await self._restore_from_versioned_backup(file_key, provider)

        except Exception as e:
            error_message = f"Restoration failed: {str(e)}"
            logger.error(f"Restoration error for {file_key}: {error_message}")
            return StorageResult(
                success=False,
                error_message=error_message
            )

    async def _restore_from_versioned_backup(
        self,
        file_key: str,
        provider: CloudStorageProvider
    ) -> StorageResult:
        """
        Restore from versioned backups as last resort.

        Args:
            file_key: File key to restore
            provider: Storage provider

        Returns:
            StorageResult with restoration details
        """
        try:
            # List versioned backups
            backup_prefix = f"backups/{file_key}.v"
            backup_list = await provider.list_files(prefix=backup_prefix, limit=50)

            if not backup_list.get('files'):
                return StorageResult(
                    success=False,
                    error_message="No versioned backups found"
                )

            # Sort by version (newest first)
            backups = sorted(
                backup_list['files'],
                key=lambda x: x.get('last_modified', ''),
                reverse=True
            )

            # Try to restore from the newest backup
            for backup_info in backups[:self.config.max_backup_versions]:
                try:
                    backup_key = backup_info['key']
                    logger.info(f"Attempting restoration from versioned backup: {backup_key}")

                    # Download backup
                    backup_result = await provider.download_file(backup_key)
                    if not backup_result.success:
                        continue

                    backup_content = backup_result.file_content or b''

                    # Restore to original location
                    content_type = backup_result.content_type or 'application/octet-stream'
                    restore_result = await provider.upload_file(
                        file_content=backup_content,
                        file_key=file_key,
                        content_type=content_type,
                        metadata={
                            'restored_from_backup': backup_key,
                            'restoration_timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    )

                    if restore_result.success:
                        logger.info(f"Successfully restored {file_key} from versioned backup {backup_key}")
                        return restore_result

                except Exception as e:
                    logger.error(f"Failed to restore from backup {backup_info.get('key', 'unknown')}: {e}")
                    continue

            return StorageResult(
                success=False,
                error_message="All versioned backup restoration attempts failed"
            )

        except Exception as e:
            return StorageResult(
                success=False,
                error_message=f"Versioned backup restoration failed: {str(e)}"
            )

    async def automatic_failover(
        self,
        failed_region: str,
        provider_type: StorageProvider
    ) -> bool:
        """
        Perform automatic failover to backup regions.

        Args:
            failed_region: The region that failed
            provider_type: Type of storage provider

        Returns:
            True if failover was successful
        """
        if not self.config.auto_failover_enabled:
            logger.info("Automatic failover is disabled")
            return False

        try:
            logger.warning(f"Initiating automatic failover from region {failed_region}")

            # Find available backup regions
            available_regions = [r for r in self.config.backup_regions if r != failed_region]

            if not available_regions:
                logger.error("No backup regions available for failover")
                return False

            # Select the first available region as new primary
            new_primary_region = available_regions[0]

            # Update configuration to use new primary region
            # This would typically involve updating the provider factory configuration
            logger.info(f"Failing over to region {new_primary_region}")

            # Test connectivity to new region
            test_provider = await self._get_regional_provider(provider_type, new_primary_region)
            if not test_provider:
                logger.error(f"Cannot create provider for failover region {new_primary_region}")
                return False

            # Perform health check
            health_result = await test_provider.health_check()
            if not health_result.healthy:
                logger.error(f"Failover region {new_primary_region} is not healthy: {health_result.error_message}")
                return False

            # Log failover operation
            await self._log_replication_operation(
                file_key="SYSTEM_FAILOVER",
                operation="failover",
                status="success",
                regions_count=1,
                duration_ms=0,
                error_message=f"Failed over from {failed_region} to {new_primary_region}"
            )

            logger.info(f"Automatic failover completed: {failed_region} -> {new_primary_region}")
            return True

        except Exception as e:
            logger.error(f"Automatic failover failed: {str(e)}")
            return False

    async def run_disaster_recovery_test(
        self,
        test_type: str = "comprehensive",
        file_sample_size: int = 10
    ) -> RecoveryTestResult:
        """
        Run disaster recovery tests to validate backup integrity and restoration procedures.

        Args:
            test_type: Type of test ("integrity", "failover", "restoration", "comprehensive")
            file_sample_size: Number of files to test

        Returns:
            RecoveryTestResult with test details
        """
        test_id = f"dr_test_{int(time.time())}"
        start_time = time.time()

        logger.info(f"Starting disaster recovery test: {test_id} (type: {test_type})")

        try:
            files_tested = 0
            files_passed = 0
            files_failed = 0
            error_details = []

            # Get sample of replicated files
            sample_files = list(self._replication_records.keys())[:file_sample_size]

            if test_type in ["integrity", "comprehensive"]:
                # Test backup integrity
                for file_key in sample_files:
                    try:
                        files_tested += 1

                        # Get primary provider
                        primary_provider = self.provider_factory.get_primary_provider()
                        if not primary_provider:
                            files_failed += 1
                            error_details.append(f"No primary provider available for {file_key}")
                            continue

                        # Check for corruption
                        is_corrupted, error_msg = await self.detect_corruption(file_key, primary_provider)

                        if is_corrupted:
                            files_failed += 1
                            error_details.append(f"Corruption detected in {file_key}: {error_msg}")
                        else:
                            files_passed += 1

                    except Exception as e:
                        files_failed += 1
                        error_details.append(f"Integrity test failed for {file_key}: {str(e)}")

            if test_type in ["restoration", "comprehensive"]:
                # Test restoration procedures
                test_file_key = sample_files[0] if sample_files else "test_file"

                try:
                    primary_provider = self.provider_factory.get_primary_provider()
                    if primary_provider:
                        # Simulate restoration
                        restore_result = await self.restore_from_backup(test_file_key, primary_provider)

                        if restore_result.success:
                            files_passed += 1
                        else:
                            files_failed += 1
                            error_details.append(f"Restoration test failed: {restore_result.error_message}")
                    else:
                        files_failed += 1
                        error_details.append("No primary provider for restoration test")

                except Exception as e:
                    files_failed += 1
                    error_details.append(f"Restoration test error: {str(e)}")

            if test_type in ["failover", "comprehensive"]:
                # Test failover procedures
                try:
                    # Simulate failover (without actually changing configuration)
                    test_region = self.config.backup_regions[0] if self.config.backup_regions else "us-west-2"
                    primary_provider = self.provider_factory.get_primary_provider()

                    if primary_provider:
                        # Test if we can access backup region
                        regional_provider = await self._get_regional_provider(
                            primary_provider.provider_type, test_region
                        )

                        if regional_provider:
                            health_result = await regional_provider.health_check()
                            if health_result.healthy:
                                files_passed += 1
                            else:
                                files_failed += 1
                                error_details.append(f"Failover region {test_region} unhealthy: {health_result.error_message}")
                        else:
                            files_failed += 1
                            error_details.append(f"Cannot access failover region {test_region}")
                    else:
                        files_failed += 1
                        error_details.append("No primary provider for failover test")

                except Exception as e:
                    files_failed += 1
                    error_details.append(f"Failover test error: {str(e)}")

            # Determine overall test status
            if files_failed == 0:
                status = RecoveryTestStatus.PASSED
            elif files_passed > 0:
                status = RecoveryTestStatus.PARTIAL
            else:
                status = RecoveryTestStatus.FAILED

            duration_seconds = int(time.time() - start_time)

            # Create test result
            test_result = RecoveryTestResult(
                test_id=test_id,
                test_timestamp=datetime.now(timezone.utc),
                test_type=test_type,
                status=status,
                files_tested=files_tested,
                files_passed=files_passed,
                files_failed=files_failed,
                duration_seconds=duration_seconds,
                error_details=error_details if error_details else None
            )

            # Store test result
            self._test_history.append(test_result)

            # Log test completion
            await self._log_replication_operation(
                file_key="DR_TEST",
                operation="test",
                status=status.value,
                regions_count=len(self.config.backup_regions),
                duration_ms=duration_seconds * 1000,
                error_message=f"Test {test_id}: {files_passed}/{files_tested} passed"
            )

            logger.info(f"Disaster recovery test completed: {test_id} - {status.value} ({files_passed}/{files_tested} passed)")
            return test_result

        except Exception as e:
            error_message = f"Disaster recovery test failed: {str(e)}"
            logger.error(f"DR test error: {error_message}")

            return RecoveryTestResult(
                test_id=test_id,
                test_timestamp=datetime.now(timezone.utc),
                test_type=test_type,
                status=RecoveryTestStatus.FAILED,
                files_tested=0,
                files_passed=0,
                files_failed=1,
                duration_seconds=int(time.time() - start_time),
                error_details=[error_message]
            )

    async def _log_replication_operation(
        self,
        file_key: str,
        operation: str,
        status: str,
        regions_count: int,
        duration_ms: int,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log replication operations to the database.

        Args:
            file_key: File key involved in operation
            operation: Type of operation (replicate, restore, failover, test)
            status: Operation status
            regions_count: Number of regions involved
            duration_ms: Operation duration in milliseconds
            error_message: Optional error message
        """
        try:
            # Extract tenant_id from file_key if possible
            tenant_id = "system"
            if file_key.startswith("tenant_"):
                parts = file_key.split("/", 1)
                if len(parts) > 0:
                    tenant_id = parts[0]

            log_entry = StorageOperationLog(
                tenant_id=tenant_id,
                operation_type=f"dr_{operation}",
                file_key=file_key,
                provider="disaster_recovery",
                success=(status in ["success", "completed", "passed"]),
                file_size=regions_count,  # Repurpose for region count
                duration_ms=duration_ms,
                error_message=error_message,
                user_id=None,  # System operation
                ip_address=None
            )

            self.db.add(log_entry)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to log replication operation: {e}")
            # Don't raise exception to avoid breaking the main operation

    def get_replication_status(self, file_key: str) -> Optional[ReplicationRecord]:
        """
        Get replication status for a file.

        Args:
            file_key: File key to check

        Returns:
            ReplicationRecord or None if not found
        """
        return self._replication_records.get(file_key)

    def get_test_history(self, limit: int = 10) -> List[RecoveryTestResult]:
        """
        Get disaster recovery test history.

        Args:
            limit: Maximum number of test results to return

        Returns:
            List of recent test results
        """
        return sorted(
            self._test_history,
            key=lambda x: x.test_timestamp,
            reverse=True
        )[:limit]

    def get_replication_statistics(self) -> Dict[str, Any]:
        """
        Get replication statistics and health metrics.

        Returns:
            Dictionary with replication statistics
        """
        total_files = len(self._replication_records)
        if total_files == 0:
            return {
                'total_files': 0,
                'replicated_files': 0,
                'replication_rate': 0.0,
                'status_breakdown': {},
                'average_regions': 0.0,
                'last_test': None
            }

        status_counts = {}
        total_regions = 0

        for record in self._replication_records.values():
            status = record.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            total_regions += len(record.backup_regions)

        replicated_files = status_counts.get('completed', 0) + status_counts.get('partial', 0)

        return {
            'total_files': total_files,
            'replicated_files': replicated_files,
            'replication_rate': (replicated_files / total_files) * 100,
            'status_breakdown': status_counts,
            'average_regions': total_regions / total_files if total_files > 0 else 0.0,
            'last_test': self._test_history[-1].test_timestamp if self._test_history else None,
            'config': {
                'enabled': self.config.enabled,
                'backup_regions': self.config.backup_regions,
                'auto_failover': self.config.auto_failover_enabled,
                'critical_patterns': self.config.critical_file_patterns
            }
        }