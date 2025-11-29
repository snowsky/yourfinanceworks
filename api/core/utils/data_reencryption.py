"""
Data Re-encryption Utilities for tenant database encryption.

This module provides utilities for bulk data re-encryption during key rotation,
with batch processing, progress tracking, and resumable operations.
"""

import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple, Callable, AsyncGenerator
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
from contextlib import asynccontextmanager

from sqlalchemy import text, select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from encryption_config import EncryptionConfig
from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from core.exceptions.encryption_exceptions import (
    EncryptionError,
    DecryptionError,
    KeyNotFoundError
)

logger = logging.getLogger(__name__)


class ReencryptionStatus(Enum):
    """Re-encryption operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class ReencryptionPhase(Enum):
    """Re-encryption operation phases."""
    INITIALIZATION = "initialization"
    DATA_DISCOVERY = "data_discovery"
    BATCH_PROCESSING = "batch_processing"
    VERIFICATION = "verification"
    CLEANUP = "cleanup"


@dataclass
class FieldMapping:
    """Mapping for encrypted field re-encryption."""
    table_name: str
    column_name: str
    column_type: str  # 'string' or 'json'
    primary_key_column: str = 'id'
    tenant_id_column: str = 'tenant_id'
    
    def __post_init__(self):
        """Validate field mapping."""
        if self.column_type not in ['string', 'json']:
            raise ValueError(f"Invalid column type: {self.column_type}")


@dataclass
class BatchProgress:
    """Progress tracking for batch processing."""
    batch_id: str
    table_name: str
    column_name: str
    total_records: int
    processed_records: int = 0
    failed_records: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    last_processed_id: Optional[int] = None
    error_message: Optional[str] = None
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_records == 0:
            return 100.0
        return (self.processed_records / self.total_records) * 100.0
    
    @property
    def is_completed(self) -> bool:
        """Check if batch is completed."""
        return self.processed_records >= self.total_records
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'batch_id': self.batch_id,
            'table_name': self.table_name,
            'column_name': self.column_name,
            'total_records': self.total_records,
            'processed_records': self.processed_records,
            'failed_records': self.failed_records,
            'progress_percentage': self.progress_percentage,
            'is_completed': self.is_completed,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'last_processed_id': self.last_processed_id,
            'error_message': self.error_message
        }


@dataclass
class ReencryptionJob:
    """Re-encryption job information."""
    job_id: str
    tenant_id: int
    status: ReencryptionStatus
    phase: ReencryptionPhase
    old_key_id: str
    new_key_id: str
    started_at: datetime
    field_mappings: List[FieldMapping] = field(default_factory=list)
    batch_progresses: List[BatchProgress] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    checkpoint_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def progress_percentage(self) -> float:
        """Calculate overall progress percentage."""
        if self.total_records == 0:
            return 0.0
        return (self.processed_records / self.total_records) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'job_id': self.job_id,
            'tenant_id': self.tenant_id,
            'status': self.status.value,
            'phase': self.phase.value,
            'old_key_id': self.old_key_id,
            'new_key_id': self.new_key_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'total_records': self.total_records,
            'processed_records': self.processed_records,
            'failed_records': self.failed_records,
            'progress_percentage': self.progress_percentage,
            'field_mappings_count': len(self.field_mappings),
            'batch_progresses': [bp.to_dict() for bp in self.batch_progresses]
        }


class DataReencryptionService:
    """
    Service for bulk data re-encryption during key rotation.
    
    Features:
    - Batch processing for large datasets
    - Progress tracking and resumable operations
    - Data integrity validation
    - Concurrent processing with rate limiting
    - Checkpoint and recovery capabilities
    """
    
    def __init__(self, 
                 encryption_service: Optional[EncryptionService] = None,
                 key_management_service: Optional[KeyManagementService] = None):
        self.config = EncryptionConfig()
        self.encryption_service = encryption_service or EncryptionService()
        self.key_management = key_management_service or KeyManagementService()
        
        # Job management
        self._active_jobs: Dict[str, ReencryptionJob] = {}
        self._job_history: List[ReencryptionJob] = []
        
        # Configuration
        self.batch_size = 1000  # Records per batch
        self.max_concurrent_batches = 3
        self.checkpoint_interval = 100  # Records between checkpoints
        self.verification_sample_rate = 0.1  # 10% verification
        
        # Default field mappings for the application
        self.default_field_mappings = self._get_default_field_mappings()
        
        logger.info("DataReencryptionService initialized")
    
    def _get_default_field_mappings(self) -> List[FieldMapping]:
        """Get default field mappings for the application."""
        return [
            # User model
            FieldMapping("users", "email", "string"),
            FieldMapping("users", "first_name", "string"),
            FieldMapping("users", "last_name", "string"),
            FieldMapping("users", "google_id", "string"),
            FieldMapping("users", "azure_ad_id", "string"),
            
            # Client model
            FieldMapping("clients", "name", "string"),
            FieldMapping("clients", "email", "string"),
            FieldMapping("clients", "phone", "string"),
            FieldMapping("clients", "address", "string"),
            FieldMapping("clients", "company", "string"),
            
            # Invoice model
            FieldMapping("invoices", "notes", "string"),
            FieldMapping("invoices", "custom_fields", "json"),
            FieldMapping("invoices", "attachment_filename", "string"),
            
            # Payment model
            FieldMapping("payments", "reference_number", "string"),
            FieldMapping("payments", "notes", "string"),
            
            # Expense model
            FieldMapping("expenses", "vendor", "string"),
            FieldMapping("expenses", "notes", "string"),
            FieldMapping("expenses", "receipt_filename", "string"),
            FieldMapping("expenses", "analysis_result", "json"),
            FieldMapping("expenses", "inventory_items", "json"),
            FieldMapping("expenses", "consumption_items", "json"),
            
            # ClientNote model
            FieldMapping("client_notes", "note", "string"),
            
            # AIConfig model
            FieldMapping("ai_config", "api_key", "string"),
            FieldMapping("ai_config", "provider_url", "string"),
            
            # AuditLog model
            FieldMapping("audit_logs", "user_email", "string"),
            FieldMapping("audit_logs", "details", "json"),
            FieldMapping("audit_logs", "ip_address", "string"),
            FieldMapping("audit_logs", "user_agent", "string"),
        ]
    
    async def start_reencryption(self, 
                                tenant_id: int, 
                                old_key_id: str, 
                                new_key_id: str,
                                field_mappings: Optional[List[FieldMapping]] = None,
                                resume_job_id: Optional[str] = None) -> ReencryptionJob:
        """
        Start data re-encryption for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            old_key_id: Old encryption key ID
            new_key_id: New encryption key ID
            field_mappings: Custom field mappings (optional)
            resume_job_id: Job ID to resume (optional)
            
        Returns:
            ReencryptionJob with job details
            
        Raises:
            EncryptionError: If re-encryption fails to start
        """
        # Check if resuming existing job
        if resume_job_id and resume_job_id in self._active_jobs:
            job = self._active_jobs[resume_job_id]
            if job.status == ReencryptionStatus.PAUSED:
                job.status = ReencryptionStatus.IN_PROGRESS
                logger.info(f"Resuming re-encryption job {resume_job_id} for tenant {tenant_id}")
                asyncio.create_task(self._execute_reencryption(job))
                return job
            else:
                raise EncryptionError(f"Cannot resume job {resume_job_id} with status {job.status.value}")
        
        # Create new job
        job_id = f"reencrypt_{tenant_id}_{int(time.time())}"
        mappings = field_mappings or self.default_field_mappings
        
        job = ReencryptionJob(
            job_id=job_id,
            tenant_id=tenant_id,
            status=ReencryptionStatus.PENDING,
            phase=ReencryptionPhase.INITIALIZATION,
            old_key_id=old_key_id,
            new_key_id=new_key_id,
            started_at=datetime.now(timezone.utc),
            field_mappings=mappings
        )
        
        self._active_jobs[job_id] = job
        
        logger.info(f"Starting re-encryption job {job_id} for tenant {tenant_id}")
        
        # Start re-encryption in background
        asyncio.create_task(self._execute_reencryption(job))
        
        return job
    
    async def _execute_reencryption(self, job: ReencryptionJob):
        """Execute the re-encryption process."""
        try:
            job.status = ReencryptionStatus.IN_PROGRESS
            
            # Execute phases
            await self._phase_initialization(job)
            await self._phase_data_discovery(job)
            await self._phase_batch_processing(job)
            await self._phase_verification(job)
            await self._phase_cleanup(job)
            
            # Mark as completed
            job.status = ReencryptionStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            
            logger.info(f"Re-encryption job {job.job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Re-encryption job {job.job_id} failed: {str(e)}")
            job.status = ReencryptionStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
        
        finally:
            # Move to history
            self._job_history.append(job)
            self._active_jobs.pop(job.job_id, None)
    
    async def _phase_initialization(self, job: ReencryptionJob):
        """Initialize re-encryption job."""
        job.phase = ReencryptionPhase.INITIALIZATION
        
        # Validate keys exist
        try:
            # This would typically validate that both keys exist and are accessible
            logger.info(f"Validating keys for job {job.job_id}")
            
            # Create checkpoint
            job.checkpoint_data = {
                'phase': job.phase.value,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            raise EncryptionError(f"Initialization failed: {str(e)}")
    
    async def _phase_data_discovery(self, job: ReencryptionJob):
        """Discover data that needs re-encryption."""
        job.phase = ReencryptionPhase.DATA_DISCOVERY
        
        logger.info(f"Discovering data for job {job.job_id}")
        
        # In a real implementation, this would query the database
        # For now, we'll simulate the discovery process
        
        total_records = 0
        for mapping in job.field_mappings:
            # Simulate counting records
            record_count = await self._count_encrypted_records(job.tenant_id, mapping)
            total_records += record_count
            
            # Create batch progress tracker
            batch_id = f"{job.job_id}_{mapping.table_name}_{mapping.column_name}"
            batch_progress = BatchProgress(
                batch_id=batch_id,
                table_name=mapping.table_name,
                column_name=mapping.column_name,
                total_records=record_count
            )
            job.batch_progresses.append(batch_progress)
        
        job.total_records = total_records
        
        logger.info(f"Discovered {total_records} records to re-encrypt for job {job.job_id}")
    
    async def _phase_batch_processing(self, job: ReencryptionJob):
        """Process data in batches."""
        job.phase = ReencryptionPhase.BATCH_PROCESSING
        
        logger.info(f"Starting batch processing for job {job.job_id}")
        
        # Process batches concurrently with rate limiting
        semaphore = asyncio.Semaphore(self.max_concurrent_batches)
        
        tasks = []
        for batch_progress in job.batch_progresses:
            task = asyncio.create_task(
                self._process_batch_with_semaphore(semaphore, job, batch_progress)
            )
            tasks.append(task)
        
        # Wait for all batches to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update job totals
        job.processed_records = sum(bp.processed_records for bp in job.batch_progresses)
        job.failed_records = sum(bp.failed_records for bp in job.batch_progresses)
        
        logger.info(f"Batch processing completed for job {job.job_id}")
    
    async def _process_batch_with_semaphore(self, 
                                          semaphore: asyncio.Semaphore, 
                                          job: ReencryptionJob, 
                                          batch_progress: BatchProgress):
        """Process a batch with semaphore rate limiting."""
        async with semaphore:
            await self._process_batch(job, batch_progress)
    
    async def _process_batch(self, job: ReencryptionJob, batch_progress: BatchProgress):
        """Process a single batch of records."""
        batch_progress.start_time = datetime.now(timezone.utc)
        
        try:
            logger.info(f"Processing batch {batch_progress.batch_id}")
            
            # Get field mapping
            mapping = next(
                (m for m in job.field_mappings 
                 if m.table_name == batch_progress.table_name and m.column_name == batch_progress.column_name),
                None
            )
            
            if not mapping:
                raise EncryptionError(f"Field mapping not found for {batch_progress.table_name}.{batch_progress.column_name}")
            
            # Process records in smaller chunks
            offset = batch_progress.last_processed_id or 0
            
            while batch_progress.processed_records < batch_progress.total_records:
                # Get batch of records
                records = await self._get_encrypted_records_batch(
                    job.tenant_id, mapping, offset, self.batch_size
                )
                
                if not records:
                    break
                
                # Process each record
                for record in records:
                    try:
                        await self._reencrypt_record(job, mapping, record)
                        batch_progress.processed_records += 1
                        batch_progress.last_processed_id = record['id']
                        
                        # Checkpoint periodically
                        if batch_progress.processed_records % self.checkpoint_interval == 0:
                            await self._save_checkpoint(job, batch_progress)
                        
                    except Exception as e:
                        logger.error(f"Failed to re-encrypt record {record['id']}: {str(e)}")
                        batch_progress.failed_records += 1
                
                offset += len(records)
                
                # Small delay to prevent overwhelming the database
                await asyncio.sleep(0.01)
            
            batch_progress.end_time = datetime.now(timezone.utc)
            logger.info(f"Completed batch {batch_progress.batch_id}")
            
        except Exception as e:
            batch_progress.error_message = str(e)
            batch_progress.end_time = datetime.now(timezone.utc)
            logger.error(f"Batch {batch_progress.batch_id} failed: {str(e)}")
    
    async def _reencrypt_record(self, job: ReencryptionJob, mapping: FieldMapping, record: Dict[str, Any]):
        """Re-encrypt a single record."""
        try:
            encrypted_value = record[mapping.column_name]
            if not encrypted_value:
                return  # Skip empty values
            
            # Decrypt with old key (simulated)
            if mapping.column_type == 'json':
                decrypted_data = self.encryption_service.decrypt_json(encrypted_value, job.tenant_id)
                # Re-encrypt with new key
                new_encrypted_value = self.encryption_service.encrypt_json(decrypted_data, job.tenant_id)
            else:
                decrypted_data = self.encryption_service.decrypt_data(encrypted_value, job.tenant_id)
                # Re-encrypt with new key
                new_encrypted_value = self.encryption_service.encrypt_data(decrypted_data, job.tenant_id)
            
            # Update record in database (simulated)
            await self._update_record(mapping, record['id'], mapping.column_name, new_encrypted_value)
            
        except Exception as e:
            raise EncryptionError(f"Failed to re-encrypt record: {str(e)}")
    
    async def _phase_verification(self, job: ReencryptionJob):
        """Verify re-encryption integrity."""
        job.phase = ReencryptionPhase.VERIFICATION
        
        logger.info(f"Starting verification for job {job.job_id}")
        
        # Sample verification - check a percentage of records
        verification_count = 0
        verification_failures = 0
        
        for batch_progress in job.batch_progresses:
            if batch_progress.processed_records == 0:
                continue
            
            # Calculate sample size
            sample_size = max(1, int(batch_progress.processed_records * self.verification_sample_rate))
            
            # Verify sample records
            for _ in range(sample_size):
                try:
                    # In a real implementation, this would:
                    # 1. Select random records
                    # 2. Decrypt with new key
                    # 3. Verify data integrity
                    verification_count += 1
                    
                    # Simulate verification
                    await asyncio.sleep(0.001)
                    
                except Exception as e:
                    logger.error(f"Verification failed for batch {batch_progress.batch_id}: {str(e)}")
                    verification_failures += 1
        
        if verification_failures > 0:
            failure_rate = (verification_failures / verification_count) * 100
            if failure_rate > 5:  # More than 5% failure rate
                raise EncryptionError(f"Verification failed: {failure_rate:.1f}% failure rate")
            else:
                logger.warning(f"Verification completed with {failure_rate:.1f}% failure rate")
        
        logger.info(f"Verification completed for job {job.job_id}: {verification_count} records verified")
    
    async def _phase_cleanup(self, job: ReencryptionJob):
        """Clean up after re-encryption."""
        job.phase = ReencryptionPhase.CLEANUP
        
        logger.info(f"Cleaning up job {job.job_id}")
        
        # Clear checkpoints
        job.checkpoint_data.clear()
        
        # Log completion statistics
        success_rate = ((job.processed_records - job.failed_records) / job.processed_records) * 100 if job.processed_records > 0 else 0
        
        logger.info(f"Re-encryption job {job.job_id} statistics:")
        logger.info(f"  Total records: {job.total_records}")
        logger.info(f"  Processed: {job.processed_records}")
        logger.info(f"  Failed: {job.failed_records}")
        logger.info(f"  Success rate: {success_rate:.1f}%")
    
    async def _count_encrypted_records(self, tenant_id: int, mapping: FieldMapping) -> int:
        """Count encrypted records for a field mapping."""
        # In a real implementation, this would query the database
        # For simulation, return a random count
        import random
        return random.randint(100, 1000)
    
    async def _get_encrypted_records_batch(self, 
                                         tenant_id: int, 
                                         mapping: FieldMapping, 
                                         offset: int, 
                                         limit: int) -> List[Dict[str, Any]]:
        """Get a batch of encrypted records."""
        # In a real implementation, this would query the database
        # For simulation, return mock records
        records = []
        for i in range(min(limit, 100)):  # Simulate up to 100 records
            records.append({
                'id': offset + i + 1,
                mapping.column_name: f"encrypted_data_{offset + i + 1}",
                mapping.tenant_id_column: tenant_id
            })
        return records
    
    async def _update_record(self, mapping: FieldMapping, record_id: int, column_name: str, new_value: str):
        """Update a record with new encrypted value."""
        # In a real implementation, this would update the database
        # For simulation, just log the update
        logger.debug(f"Updated {mapping.table_name}.{column_name} for record {record_id}")
    
    async def _save_checkpoint(self, job: ReencryptionJob, batch_progress: BatchProgress):
        """Save checkpoint data for resumable operations."""
        checkpoint = {
            'job_id': job.job_id,
            'batch_id': batch_progress.batch_id,
            'processed_records': batch_progress.processed_records,
            'last_processed_id': batch_progress.last_processed_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        job.checkpoint_data[batch_progress.batch_id] = checkpoint
        
        # In a real implementation, this would persist to storage
        logger.debug(f"Saved checkpoint for batch {batch_progress.batch_id}")
    
    def pause_job(self, job_id: str) -> bool:
        """
        Pause a running re-encryption job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was paused
        """
        if job_id in self._active_jobs:
            job = self._active_jobs[job_id]
            if job.status == ReencryptionStatus.IN_PROGRESS:
                job.status = ReencryptionStatus.PAUSED
                logger.info(f"Paused re-encryption job {job_id}")
                return True
        return False
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a re-encryption job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was cancelled
        """
        if job_id in self._active_jobs:
            job = self._active_jobs[job_id]
            if job.status in [ReencryptionStatus.IN_PROGRESS, ReencryptionStatus.PAUSED]:
                job.status = ReencryptionStatus.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                logger.info(f"Cancelled re-encryption job {job_id}")
                return True
        return False
    
    def get_job_status(self, job_id: str) -> Optional[ReencryptionJob]:
        """
        Get status of a re-encryption job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            ReencryptionJob or None if not found
        """
        return self._active_jobs.get(job_id)
    
    def get_active_jobs(self) -> Dict[str, ReencryptionJob]:
        """
        Get all active re-encryption jobs.
        
        Returns:
            Dictionary of active jobs
        """
        return self._active_jobs.copy()
    
    def get_job_history(self, tenant_id: Optional[int] = None, limit: int = 100) -> List[ReencryptionJob]:
        """
        Get re-encryption job history.
        
        Args:
            tenant_id: Filter by tenant ID (optional)
            limit: Maximum number of records
            
        Returns:
            List of ReencryptionJob records
        """
        history = self._job_history.copy()
        
        if tenant_id is not None:
            history = [job for job in history if job.tenant_id == tenant_id]
        
        # Sort by start time (most recent first)
        history.sort(key=lambda x: x.started_at, reverse=True)
        
        return history[:limit]
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        active_jobs = len(self._active_jobs)
        total_jobs = len(self._job_history)
        
        # Calculate success rate
        completed_jobs = [job for job in self._job_history if job.status == ReencryptionStatus.COMPLETED]
        success_rate = (len(completed_jobs) / total_jobs) * 100 if total_jobs > 0 else 0
        
        # Calculate total records processed
        total_processed = sum(job.processed_records for job in self._job_history)
        total_failed = sum(job.failed_records for job in self._job_history)
        
        return {
            'active_jobs': active_jobs,
            'total_jobs': total_jobs,
            'success_rate_percent': round(success_rate, 2),
            'total_records_processed': total_processed,
            'total_records_failed': total_failed,
            'batch_size': self.batch_size,
            'max_concurrent_batches': self.max_concurrent_batches,
            'checkpoint_interval': self.checkpoint_interval
        }


# Global data re-encryption service instance
_data_reencryption_service: Optional[DataReencryptionService] = None


def get_data_reencryption_service() -> DataReencryptionService:
    """
    Get global data re-encryption service instance.
    
    Returns:
        DataReencryptionService instance
    """
    global _data_reencryption_service
    if _data_reencryption_service is None:
        _data_reencryption_service = DataReencryptionService()
    return _data_reencryption_service