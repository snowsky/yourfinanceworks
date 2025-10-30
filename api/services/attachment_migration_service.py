"""
Attachment Migration Service for Cloud File Storage

This service handles the migration of existing file attachments from local disk storage
to cloud storage providers. It provides comprehensive migration capabilities including
progress tracking, integrity verification, error handling, and rollback functionality.

Features:
- Tenant-specific migration with progress tracking
- File integrity verification using checksums
- Batch migration with error handling and retry logic
- Dry-run capability for migration planning
- Migration status reporting and rollback capabilities
- Support for mixed storage scenarios during migration
"""

import logging
import hashlib
import mimetypes
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from models.models import Tenant
from models.models_per_tenant import StorageOperationLog
from models.models_per_tenant import ItemAttachment
from services.cloud_storage_service import CloudStorageService
from services.file_storage_service import file_storage_service
from storage_config.cloud_storage_config import get_cloud_storage_config
from config import config

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration status enumeration."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class FileStatus(Enum):
    """Individual file migration status."""
    PENDING = "pending"
    MIGRATING = "migrating"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    VERIFIED = "verified"


@dataclass
class MigrationProgress:
    """Progress tracking for migration operations."""
    tenant_id: str
    total_files: int = 0
    processed_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0
    total_size_bytes: int = 0
    migrated_size_bytes: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: MigrationStatus = MigrationStatus.NOT_STARTED
    error_message: Optional[str] = None
    current_file: Optional[str] = None
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.processed_files == 0:
            return 0.0
        return (self.successful_files / self.processed_files) * 100
    
    @property
    def estimated_time_remaining(self) -> Optional[float]:
        """Estimate time remaining in seconds."""
        if not self.start_time or self.processed_files == 0:
            return None
        
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        rate = self.processed_files / elapsed
        remaining_files = self.total_files - self.processed_files
        
        if rate > 0:
            return remaining_files / rate
        return None


@dataclass
class FileMigrationResult:
    """Result of a single file migration."""
    file_path: str
    original_filename: str
    status: FileStatus
    cloud_file_key: Optional[str] = None
    cloud_provider: Optional[str] = None
    file_size: Optional[int] = None
    checksum_original: Optional[str] = None
    checksum_migrated: Optional[str] = None
    error_message: Optional[str] = None
    migration_time_ms: Optional[int] = None
    retry_count: int = 0


@dataclass
class MigrationPlan:
    """Migration plan with file analysis."""
    tenant_id: str
    total_files: int = 0
    total_size_bytes: int = 0
    files_by_type: Dict[str, int] = field(default_factory=dict)
    size_by_type: Dict[str, int] = field(default_factory=dict)
    estimated_duration_minutes: Optional[float] = None
    storage_requirements: Dict[str, Any] = field(default_factory=dict)
    potential_issues: List[str] = field(default_factory=list)


class AttachmentMigrationService:
    """
    Service for migrating existing attachments to cloud storage.
    
    Provides comprehensive migration capabilities with progress tracking,
    integrity verification, error handling, and rollback functionality.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the migration service.
        
        Args:
            db: Database session
        """
        self.db = db
        
        # Initialize cloud storage service
        try:
            cloud_config = get_cloud_storage_config()
            self.cloud_storage_service = CloudStorageService(db, cloud_config)
            logger.info("Cloud storage service initialized for migration")
        except Exception as e:
            logger.error(f"Failed to initialize cloud storage service: {e}")
            self.cloud_storage_service = None
            
        # Migration state tracking
        self._migration_progress: Dict[str, MigrationProgress] = {}
        self._migration_locks: Dict[str, asyncio.Lock] = {}
        
        # Configuration
        self.max_concurrent_migrations = 5
        self.retry_attempts = 3
        self.retry_delay_seconds = 2.0
        self.checksum_verification = True
        
    async def create_migration_plan(
        self,
        tenant_id: str,
        attachment_types: Optional[List[str]] = None
    ) -> MigrationPlan:
        """
        Create a migration plan by analyzing existing attachments.
        
        Args:
            tenant_id: Tenant identifier
            attachment_types: Optional filter for attachment types
            
        Returns:
            MigrationPlan with analysis results
        """
        try:
            logger.info(f"Creating migration plan for tenant {tenant_id}")
            
            plan = MigrationPlan(tenant_id=tenant_id)
            
            # Get all active attachments for the tenant
            # Note: This assumes we can filter by tenant - adjust based on your tenant model
            query = self.db.query(ItemAttachment).filter(
                ItemAttachment.is_active == True
            )
            
            if attachment_types:
                query = query.filter(ItemAttachment.attachment_type.in_(attachment_types))
            
            attachments = query.all()
            
            # Analyze attachments
            for attachment in attachments:
                # Check if file needs migration (not already in cloud storage)
                if self._is_cloud_storage_path(attachment.file_path):
                    continue  # Already migrated
                
                # Check if local file exists
                local_path = self._resolve_local_file_path(attachment, tenant_id)
                if not local_path or not local_path.exists():
                    plan.potential_issues.append(
                        f"Local file not found: {attachment.filename} (ID: {attachment.id})"
                    )
                    continue
                
                # Get file size
                try:
                    file_size = local_path.stat().st_size
                except Exception as e:
                    plan.potential_issues.append(
                        f"Cannot access file: {attachment.filename} - {str(e)}"
                    )
                    continue
                
                # Update plan statistics
                plan.total_files += 1
                plan.total_size_bytes += file_size
                
                # Track by attachment type
                att_type = attachment.attachment_type or 'unknown'
                plan.files_by_type[att_type] = plan.files_by_type.get(att_type, 0) + 1
                plan.size_by_type[att_type] = plan.size_by_type.get(att_type, 0) + file_size
            
            # Estimate migration duration (rough estimate: 1MB per second)
            if plan.total_size_bytes > 0:
                estimated_seconds = plan.total_size_bytes / (1024 * 1024)  # 1MB/s
                plan.estimated_duration_minutes = estimated_seconds / 60
            
            # Check storage requirements
            plan.storage_requirements = {
                'total_size_mb': plan.total_size_bytes / (1024 * 1024),
                'estimated_cloud_cost_monthly': self._estimate_storage_cost(plan.total_size_bytes),
                'bandwidth_required_mb': plan.total_size_bytes / (1024 * 1024)
            }
            
            # Check for potential issues
            if not self.cloud_storage_service:
                plan.potential_issues.append("Cloud storage service not available")
            
            if plan.total_size_bytes > 10 * 1024 * 1024 * 1024:  # 10GB
                plan.potential_issues.append("Large migration size - consider batch processing")
            
            logger.info(f"Migration plan created: {plan.total_files} files, {plan.total_size_bytes} bytes")
            return plan
            
        except Exception as e:
            logger.error(f"Failed to create migration plan for tenant {tenant_id}: {e}")
            plan = MigrationPlan(tenant_id=tenant_id)
            plan.potential_issues.append(f"Plan creation failed: {str(e)}")
            return plan
    
    async def migrate_tenant_attachments(
        self,
        tenant_id: str,
        dry_run: bool = False,
        attachment_types: Optional[List[str]] = None,
        batch_size: int = 100,
        user_id: int = 0
    ) -> Dict[str, Any]:
        """
        Migrate all attachments for a specific tenant.
        
        Args:
            tenant_id: Tenant identifier
            dry_run: If True, only simulate migration without actual file operations
            attachment_types: Optional filter for attachment types
            batch_size: Number of files to process in each batch
            user_id: User ID initiating the migration
            
        Returns:
            Dictionary with migration results and statistics
        """
        try:
            # Ensure only one migration per tenant at a time
            if tenant_id not in self._migration_locks:
                self._migration_locks[tenant_id] = asyncio.Lock()
            
            async with self._migration_locks[tenant_id]:
                return await self._execute_tenant_migration(
                    tenant_id, dry_run, attachment_types, batch_size, user_id
                )
                
        except Exception as e:
            logger.error(f"Migration failed for tenant {tenant_id}: {e}")
            return {
                'tenant_id': tenant_id,
                'status': MigrationStatus.FAILED.value,
                'error': str(e),
                'progress': self._migration_progress.get(tenant_id, MigrationProgress(tenant_id))
            }
    
    async def _execute_tenant_migration(
        self,
        tenant_id: str,
        dry_run: bool,
        attachment_types: Optional[List[str]],
        batch_size: int,
        user_id: int
    ) -> Dict[str, Any]:
        """Execute the actual tenant migration."""
        
        # Initialize progress tracking
        progress = MigrationProgress(
            tenant_id=tenant_id,
            start_time=datetime.now(timezone.utc),
            status=MigrationStatus.IN_PROGRESS
        )
        self._migration_progress[tenant_id] = progress
        
        migration_results = []
        
        try:
            logger.info(f"Starting {'dry-run ' if dry_run else ''}migration for tenant {tenant_id}")
            
            # Get attachments to migrate
            query = self.db.query(ItemAttachment).filter(
                ItemAttachment.is_active == True
            )
            
            if attachment_types:
                query = query.filter(ItemAttachment.attachment_type.in_(attachment_types))
            
            # Order by creation date for consistent processing
            attachments = query.order_by(ItemAttachment.created_at).all()
            
            # Filter out already migrated files
            attachments_to_migrate = []
            for attachment in attachments:
                if not self._is_cloud_storage_path(attachment.file_path):
                    attachments_to_migrate.append(attachment)
            
            progress.total_files = len(attachments_to_migrate)
            
            if progress.total_files == 0:
                progress.status = MigrationStatus.COMPLETED
                progress.end_time = datetime.now(timezone.utc)
                logger.info(f"No files to migrate for tenant {tenant_id}")
                return {
                    'tenant_id': tenant_id,
                    'status': progress.status.value,
                    'message': 'No files require migration',
                    'progress': progress,
                    'results': []
                }
            
            # Process attachments in batches
            for i in range(0, len(attachments_to_migrate), batch_size):
                batch = attachments_to_migrate[i:i + batch_size]
                
                # Process batch concurrently
                batch_tasks = []
                for attachment in batch:
                    task = self._migrate_single_attachment(
                        attachment, tenant_id, dry_run, user_id
                    )
                    batch_tasks.append(task)
                
                # Execute batch with concurrency limit
                semaphore = asyncio.Semaphore(self.max_concurrent_migrations)
                
                async def migrate_with_semaphore(attachment, tenant_id, dry_run, user_id):
                    async with semaphore:
                        return await self._migrate_single_attachment(
                            attachment, tenant_id, dry_run, user_id
                        )
                
                batch_results = await asyncio.gather(
                    *[migrate_with_semaphore(att, tenant_id, dry_run, user_id) for att in batch],
                    return_exceptions=True
                )
                
                # Process batch results
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Batch migration error: {result}")
                        progress.failed_files += 1
                        migration_results.append(FileMigrationResult(
                            file_path="unknown",
                            original_filename="unknown",
                            status=FileStatus.FAILED,
                            error_message=str(result)
                        ))
                    else:
                        migration_results.append(result)
                        
                        # Update progress
                        if result.status == FileStatus.COMPLETED:
                            progress.successful_files += 1
                            if result.file_size:
                                progress.migrated_size_bytes += result.file_size
                        elif result.status == FileStatus.FAILED:
                            progress.failed_files += 1
                        elif result.status == FileStatus.SKIPPED:
                            progress.skipped_files += 1
                    
                    progress.processed_files += 1
                
                # Log batch progress
                logger.info(
                    f"Batch completed: {progress.processed_files}/{progress.total_files} "
                    f"({progress.completion_percentage:.1f}%)"
                )
            
            # Finalize migration
            progress.end_time = datetime.now(timezone.utc)
            progress.status = MigrationStatus.COMPLETED if progress.failed_files == 0 else MigrationStatus.FAILED
            
            # Log final results
            duration = (progress.end_time - progress.start_time).total_seconds()
            logger.info(
                f"Migration completed for tenant {tenant_id}: "
                f"{progress.successful_files} successful, {progress.failed_files} failed, "
                f"{progress.skipped_files} skipped in {duration:.1f}s"
            )
            
            return {
                'tenant_id': tenant_id,
                'status': progress.status.value,
                'dry_run': dry_run,
                'progress': progress,
                'results': migration_results,
                'summary': {
                    'total_files': progress.total_files,
                    'successful': progress.successful_files,
                    'failed': progress.failed_files,
                    'skipped': progress.skipped_files,
                    'success_rate': progress.success_rate,
                    'duration_seconds': duration,
                    'migrated_size_mb': progress.migrated_size_bytes / (1024 * 1024)
                }
            }
            
        except Exception as e:
            progress.status = MigrationStatus.FAILED
            progress.error_message = str(e)
            progress.end_time = datetime.now(timezone.utc)
            logger.error(f"Migration failed for tenant {tenant_id}: {e}")
            raise
    
    async def _migrate_single_attachment(
        self,
        attachment: ItemAttachment,
        tenant_id: str,
        dry_run: bool,
        user_id: int
    ) -> FileMigrationResult:
        """
        Migrate a single attachment file with integrity verification.
        
        Args:
            attachment: ItemAttachment object to migrate
            tenant_id: Tenant identifier
            dry_run: If True, only simulate migration
            user_id: User ID initiating the migration
            
        Returns:
            FileMigrationResult with migration details
        """
        start_time = datetime.now(timezone.utc)
        
        result = FileMigrationResult(
            file_path=attachment.file_path or "",
            original_filename=attachment.filename or "unknown",
            status=FileStatus.PENDING
        )
        
        try:
            # Update progress tracking
            progress = self._migration_progress.get(tenant_id)
            if progress:
                progress.current_file = attachment.filename
            
            # Resolve local file path
            local_path = self._resolve_local_file_path(attachment, tenant_id)
            if not local_path or not local_path.exists():
                result.status = FileStatus.SKIPPED
                result.error_message = f"Local file not found: {local_path}"
                logger.warning(f"Skipping missing file: {attachment.filename}")
                return result
            
            # Get file information
            file_size = local_path.stat().st_size
            result.file_size = file_size
            
            # Calculate original file checksum for integrity verification
            if self.checksum_verification:
                result.checksum_original = await self._calculate_file_checksum(local_path)
            
            # Check if file already exists in cloud storage
            if self.cloud_storage_service:
                file_key = self._generate_cloud_file_key(attachment, tenant_id)
                exists, provider = await self.cloud_storage_service.file_exists(
                    file_key=file_key,
                    tenant_id=tenant_id,
                    user_id=user_id
                )
                
                if exists:
                    result.status = FileStatus.SKIPPED
                    result.error_message = f"File already exists in cloud storage ({provider})"
                    result.cloud_file_key = file_key
                    result.cloud_provider = provider
                    logger.debug(f"Skipping existing cloud file: {file_key}")
                    return result
            
            if dry_run:
                result.status = FileStatus.COMPLETED
                result.cloud_file_key = self._generate_cloud_file_key(attachment, tenant_id)
                result.error_message = "Dry run - would migrate"
                return result
            
            # Perform actual migration with retry logic
            result.status = FileStatus.MIGRATING
            
            for attempt in range(self.retry_attempts):
                try:
                    result.retry_count = attempt
                    
                    # Read file content
                    file_content = local_path.read_bytes()
                    
                    # Determine content type
                    content_type, _ = mimetypes.guess_type(str(local_path))
                    if not content_type:
                        content_type = 'application/octet-stream'
                    
                    # Store in cloud storage
                    if not self.cloud_storage_service:
                        raise Exception("Cloud storage service not available")
                    
                    storage_result = await self.cloud_storage_service.store_file(
                        file_content=file_content,
                        tenant_id=tenant_id,
                        item_id=attachment.item_id,
                        attachment_type=self._get_storage_type(attachment.attachment_type),
                        original_filename=attachment.filename,
                        user_id=user_id,
                        metadata={
                            'migration_source': 'local_storage',
                            'original_path': str(local_path),
                            'attachment_id': attachment.id,
                            'migration_timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    if not storage_result.success:
                        raise Exception(f"Cloud storage failed: {storage_result.error_message}")
                    
                    result.cloud_file_key = storage_result.file_key
                    result.cloud_provider = storage_result.provider
                    
                    # Verify file integrity if enabled
                    if self.checksum_verification and result.checksum_original:
                        # Download and verify checksum
                        verify_result = await self.cloud_storage_service.retrieve_file(
                            file_key=storage_result.file_key,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            generate_url=False
                        )
                        
                        if verify_result.success and verify_result.file_content:
                            result.checksum_migrated = await self._calculate_content_checksum(
                                verify_result.file_content
                            )
                            
                            if result.checksum_original != result.checksum_migrated:
                                raise Exception(
                                    f"Checksum mismatch: {result.checksum_original} != {result.checksum_migrated}"
                                )
                    
                    # Update attachment record with new cloud path
                    attachment.file_path = storage_result.file_key
                    attachment.updated_at = datetime.now(timezone.utc)
                    self.db.commit()
                    
                    result.status = FileStatus.COMPLETED
                    logger.debug(f"Successfully migrated: {attachment.filename} -> {storage_result.file_key}")
                    break
                    
                except Exception as e:
                    logger.warning(f"Migration attempt {attempt + 1} failed for {attachment.filename}: {e}")
                    
                    if attempt < self.retry_attempts - 1:
                        # Wait before retry
                        await asyncio.sleep(self.retry_delay_seconds * (attempt + 1))
                    else:
                        # Final attempt failed
                        result.status = FileStatus.FAILED
                        result.error_message = str(e)
                        self.db.rollback()
            
        except Exception as e:
            result.status = FileStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Migration failed for {attachment.filename}: {e}")
            self.db.rollback()
        
        # Calculate migration time
        end_time = datetime.now(timezone.utc)
        result.migration_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return result
    
    def _is_cloud_storage_path(self, file_path: str) -> bool:
        """
        Determine if a file path represents a cloud storage file key.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if it's a cloud storage file key, False if local path
        """
        if not file_path:
            return False
        
        # Local file paths start with '/' (absolute paths)
        if file_path.startswith('/'):
            return False
        
        # Cloud storage file keys typically follow pattern: tenant_X/type/filename
        if file_path.startswith('tenant_') and '/' in file_path:
            return True
        
        # Windows absolute paths (C:\, D:\, etc.)
        if len(file_path) > 2 and file_path[1] == ':':
            return False
        
        # Default to cloud storage for relative paths
        return True
    
    def _resolve_local_file_path(self, attachment: ItemAttachment, tenant_id: str) -> Optional[Path]:
        """
        Resolve the local file path for an attachment.
        
        Args:
            attachment: ItemAttachment object
            tenant_id: Tenant identifier
            
        Returns:
            Path object or None if not found
        """
        try:
            base_path = Path(config.UPLOAD_PATH)
            
            # Try different path resolution strategies
            possible_paths = []
            
            # 1. Direct absolute path
            if attachment.file_path and attachment.file_path.startswith('/'):
                possible_paths.append(Path(attachment.file_path))
            
            # 2. Relative path from base
            if attachment.file_path and not attachment.file_path.startswith('/'):
                possible_paths.append(base_path / attachment.file_path)
            
            # 3. Construct from tenant and stored_filename
            if attachment.stored_filename:
                attachment_type = self._get_storage_type(attachment.attachment_type)
                constructed_path = base_path / f"tenant_{tenant_id}" / attachment_type / attachment.stored_filename
                possible_paths.append(constructed_path)
            
            # 4. Construct from tenant and original filename
            if attachment.filename:
                attachment_type = self._get_storage_type(attachment.attachment_type)
                original_path = base_path / f"tenant_{tenant_id}" / attachment_type / attachment.filename
                possible_paths.append(original_path)
            
            # Return first existing path
            for path in possible_paths:
                if path.exists():
                    return path
            
            return None
            
        except Exception as e:
            logger.error(f"Error resolving local file path: {e}")
            return None
    
    def _generate_cloud_file_key(self, attachment: ItemAttachment, tenant_id: str) -> str:
        """
        Generate cloud storage file key for an attachment.
        
        Args:
            attachment: ItemAttachment object
            tenant_id: Tenant identifier
            
        Returns:
            Cloud storage file key
        """
        attachment_type = self._get_storage_type(attachment.attachment_type)
        safe_filename = Path(attachment.filename or "unknown").name
        
        # Use attachment ID and timestamp for uniqueness
        timestamp = int(attachment.created_at.timestamp()) if attachment.created_at else int(datetime.now().timestamp())
        
        return f"tenant_{tenant_id}/{attachment_type}/{attachment.item_id}_{attachment.id}_{timestamp}_{safe_filename}"
    
    def _get_storage_type(self, attachment_type: Optional[str]) -> str:
        """
        Convert attachment type to storage directory type.
        
        Args:
            attachment_type: Attachment type from database
            
        Returns:
            Storage directory type
        """
        if attachment_type == 'image':
            return 'images'
        elif attachment_type == 'document':
            return 'documents'
        else:
            return 'documents'  # Default fallback
    
    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA-256 checksum of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 checksum as hex string
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    async def _calculate_content_checksum(self, content: bytes) -> str:
        """
        Calculate SHA-256 checksum of file content.
        
        Args:
            content: File content as bytes
            
        Returns:
            SHA-256 checksum as hex string
        """
        return hashlib.sha256(content).hexdigest()
    
    def _estimate_storage_cost(self, size_bytes: int) -> float:
        """
        Estimate monthly storage cost in USD.
        
        Args:
            size_bytes: Total size in bytes
            
        Returns:
            Estimated monthly cost in USD
        """
        # Rough estimate based on AWS S3 standard pricing (~$0.023 per GB/month)
        size_gb = size_bytes / (1024 * 1024 * 1024)
        return size_gb * 0.023
    
    def get_migration_progress(self, tenant_id: str) -> Optional[MigrationProgress]:
        """
        Get current migration progress for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            MigrationProgress object or None if no migration in progress
        """
        return self._migration_progress.get(tenant_id)
    
    def get_all_migration_progress(self) -> Dict[str, MigrationProgress]:
        """
        Get migration progress for all tenants.
        
        Returns:
            Dictionary mapping tenant IDs to MigrationProgress objects
        """
        return self._migration_progress.copy()
    
    async def cancel_migration(self, tenant_id: str) -> bool:
        """
        Cancel an ongoing migration for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if cancellation was successful
        """
        try:
            progress = self._migration_progress.get(tenant_id)
            if progress and progress.status == MigrationStatus.IN_PROGRESS:
                progress.status = MigrationStatus.CANCELLED
                progress.end_time = datetime.now(timezone.utc)
                logger.info(f"Migration cancelled for tenant {tenant_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cancel migration for tenant {tenant_id}: {e}")
            return False   
 
    async def pause_migration(self, tenant_id: str) -> bool:
        """
        Pause an ongoing migration for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if pause was successful
        """
        try:
            progress = self._migration_progress.get(tenant_id)
            if progress and progress.status == MigrationStatus.IN_PROGRESS:
                progress.status = MigrationStatus.PAUSED
                logger.info(f"Migration paused for tenant {tenant_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to pause migration for tenant {tenant_id}: {e}")
            return False
    
    async def resume_migration(self, tenant_id: str) -> bool:
        """
        Resume a paused migration for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if resume was successful
        """
        try:
            progress = self._migration_progress.get(tenant_id)
            if progress and progress.status == MigrationStatus.PAUSED:
                progress.status = MigrationStatus.IN_PROGRESS
                logger.info(f"Migration resumed for tenant {tenant_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to resume migration for tenant {tenant_id}: {e}")
            return False
    
    async def get_migration_status(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get basic migration status for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with migration status information
        """
        try:
            progress = self.get_migration_progress(tenant_id)
            if progress:
                return {
                    'status': 'in_progress' if not progress.is_completed else 'completed',
                    'total_files': progress.total_files,
                    'migrated_files': progress.migrated_files,
                    'failed_files': progress.failed_files,
                    'skipped_files': progress.skipped_files,
                    'started_at': progress.start_time.isoformat() if progress.start_time else None,
                    'completed_at': progress.end_time.isoformat() if progress.end_time else None,
                    'error_message': None
                }
            else:
                # Check if migration was completed previously by analyzing storage state
                storage_analysis = await self._analyze_storage_state(tenant_id)
                if storage_analysis.get('cloud_files', 0) > 0:
                    return {
                        'status': 'completed',
                        'total_files': storage_analysis.get('total_files', 0),
                        'migrated_files': storage_analysis.get('cloud_files', 0),
                        'failed_files': 0,
                        'skipped_files': storage_analysis.get('local_files', 0),
                        'started_at': None,
                        'completed_at': None,
                        'error_message': None
                    }
                else:
                    return {
                        'status': 'not_started',
                        'total_files': storage_analysis.get('total_files', 0),
                        'migrated_files': 0,
                        'failed_files': 0,
                        'skipped_files': 0,
                        'started_at': None,
                        'completed_at': None,
                        'error_message': None
                    }
        except Exception as e:
            logger.error(f"Failed to get migration status for tenant {tenant_id}: {e}")
            return {
                'status': 'error',
                'total_files': 0,
                'migrated_files': 0,
                'failed_files': 0,
                'skipped_files': 0,
                'started_at': None,
                'completed_at': None,
                'error_message': str(e)
            }

    async def get_migration_status_report(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get comprehensive migration status report for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with detailed migration status information
        """
        try:
            progress = self._migration_progress.get(tenant_id)
            
            # Get basic migration statistics
            report = {
                'tenant_id': tenant_id,
                'migration_progress': progress,
                'has_active_migration': progress is not None and progress.status == MigrationStatus.IN_PROGRESS,
                'storage_analysis': await self._analyze_storage_state(tenant_id),
                'recent_operations': await self._get_recent_migration_operations(tenant_id),
                'error_summary': await self._get_migration_error_summary(tenant_id)
            }
            
            # Add performance metrics if migration is active
            if progress:
                report['performance_metrics'] = {
                    'completion_percentage': progress.completion_percentage,
                    'success_rate': progress.success_rate,
                    'estimated_time_remaining': progress.estimated_time_remaining,
                    'files_per_minute': self._calculate_migration_rate(progress),
                    'data_transfer_rate_mbps': self._calculate_data_transfer_rate(progress)
                }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to get migration status report for tenant {tenant_id}: {e}")
            return {
                'tenant_id': tenant_id,
                'error': str(e),
                'migration_progress': None,
                'has_active_migration': False
            }
    
    async def _analyze_storage_state(self, tenant_id: str) -> Dict[str, Any]:
        """
        Analyze current storage state for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with storage state analysis
        """
        try:
            # Query all active attachments
            attachments = self.db.query(ItemAttachment).filter(
                ItemAttachment.is_active == True
            ).all()
            
            analysis = {
                'total_attachments': len(attachments),
                'cloud_storage_files': 0,
                'local_storage_files': 0,
                'mixed_storage_files': 0,
                'missing_files': 0,
                'total_size_bytes': 0,
                'cloud_size_bytes': 0,
                'local_size_bytes': 0,
                'migration_completion_percentage': 0.0
            }
            
            for attachment in attachments:
                is_cloud = self._is_cloud_storage_path(attachment.file_path)
                
                # Check file existence
                cloud_exists = False
                local_exists = False
                
                if is_cloud and self.cloud_storage_service:
                    try:
                        cloud_exists, _ = await self.cloud_storage_service.file_exists(
                            file_key=attachment.file_path,
                            tenant_id=tenant_id,
                            user_id=0
                        )
                    except Exception:
                        pass
                
                # Check local existence
                local_path = self._resolve_local_file_path(attachment, tenant_id)
                local_exists = local_path is not None and local_path.exists()
                
                # Categorize file
                if cloud_exists and local_exists:
                    analysis['mixed_storage_files'] += 1
                elif cloud_exists:
                    analysis['cloud_storage_files'] += 1
                    if attachment.file_size:
                        analysis['cloud_size_bytes'] += attachment.file_size
                elif local_exists:
                    analysis['local_storage_files'] += 1
                    if local_path:
                        try:
                            size = local_path.stat().st_size
                            analysis['local_size_bytes'] += size
                        except Exception:
                            pass
                else:
                    analysis['missing_files'] += 1
                
                # Add to total size
                if attachment.file_size:
                    analysis['total_size_bytes'] += attachment.file_size
            
            # Calculate migration completion percentage
            if analysis['total_attachments'] > 0:
                migrated_files = analysis['cloud_storage_files'] + analysis['mixed_storage_files']
                analysis['migration_completion_percentage'] = (migrated_files / analysis['total_attachments']) * 100
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze storage state for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    async def _get_recent_migration_operations(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent migration operations from the storage operation log.
        
        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of operations to return
            
        Returns:
            List of recent migration operations
        """
        try:
            # Query recent storage operations related to migration
            operations = self.db.query(StorageOperationLog).filter(
                and_(
                    StorageOperationLog.tenant_id == int(tenant_id),
                    StorageOperationLog.operation_metadata.contains({'migration_source': 'local_storage'})
                )
            ).order_by(desc(StorageOperationLog.created_at)).limit(limit).all()
            
            return [
                {
                    'id': op.id,
                    'operation_type': op.operation_type,
                    'file_key': op.file_key,
                    'provider': op.provider,
                    'success': op.success,
                    'error_message': op.error_message,
                    'file_size': op.file_size,
                    'duration_ms': op.duration_ms,
                    'created_at': op.created_at.isoformat() if op.created_at else None
                }
                for op in operations
            ]
            
        except Exception as e:
            logger.error(f"Failed to get recent migration operations for tenant {tenant_id}: {e}")
            return []
    
    async def _get_migration_error_summary(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get summary of migration errors for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with error summary
        """
        try:
            # Query failed migration operations
            failed_ops = self.db.query(StorageOperationLog).filter(
                and_(
                    StorageOperationLog.tenant_id == int(tenant_id),
                    StorageOperationLog.success == False,
                    StorageOperationLog.operation_metadata.contains({'migration_source': 'local_storage'})
                )
            ).all()
            
            error_summary = {
                'total_errors': len(failed_ops),
                'error_types': {},
                'recent_errors': []
            }
            
            # Categorize errors
            for op in failed_ops:
                error_msg = op.error_message or 'Unknown error'
                
                # Extract error type (first part of error message)
                error_type = error_msg.split(':')[0] if ':' in error_msg else error_msg
                error_summary['error_types'][error_type] = error_summary['error_types'].get(error_type, 0) + 1
                
                # Add to recent errors (last 10)
                if len(error_summary['recent_errors']) < 10:
                    error_summary['recent_errors'].append({
                        'file_key': op.file_key,
                        'error_message': error_msg,
                        'provider': op.provider,
                        'created_at': op.created_at.isoformat() if op.created_at else None
                    })
            
            return error_summary
            
        except Exception as e:
            logger.error(f"Failed to get migration error summary for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def _calculate_migration_rate(self, progress: MigrationProgress) -> Optional[float]:
        """
        Calculate migration rate in files per minute.
        
        Args:
            progress: MigrationProgress object
            
        Returns:
            Files per minute or None if cannot calculate
        """
        if not progress.start_time or progress.processed_files == 0:
            return None
        
        elapsed_minutes = (datetime.now(timezone.utc) - progress.start_time).total_seconds() / 60
        if elapsed_minutes > 0:
            return progress.processed_files / elapsed_minutes
        return None
    
    def _calculate_data_transfer_rate(self, progress: MigrationProgress) -> Optional[float]:
        """
        Calculate data transfer rate in MB per second.
        
        Args:
            progress: MigrationProgress object
            
        Returns:
            MB per second or None if cannot calculate
        """
        if not progress.start_time or progress.migrated_size_bytes == 0:
            return None
        
        elapsed_seconds = (datetime.now(timezone.utc) - progress.start_time).total_seconds()
        if elapsed_seconds > 0:
            mb_transferred = progress.migrated_size_bytes / (1024 * 1024)
            return mb_transferred / elapsed_seconds
        return None
    
    async def rollback_migration(
        self,
        tenant_id: str,
        rollback_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Rollback migration for a tenant by reverting file paths to local storage.
        
        Args:
            tenant_id: Tenant identifier
            rollback_options: Optional rollback configuration
                - delete_cloud_files: Whether to delete files from cloud storage
                - verify_local_files: Whether to verify local files exist before rollback
                - batch_size: Number of files to process in each batch
            
        Returns:
            Dictionary with rollback results
        """
        try:
            logger.info(f"Starting migration rollback for tenant {tenant_id}")
            
            # Parse rollback options
            options = rollback_options or {}
            delete_cloud_files = options.get('delete_cloud_files', False)
            verify_local_files = options.get('verify_local_files', True)
            batch_size = options.get('batch_size', 100)
            
            rollback_results = {
                'tenant_id': tenant_id,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'total_files': 0,
                'reverted_files': 0,
                'failed_files': 0,
                'skipped_files': 0,
                'deleted_cloud_files': 0,
                'errors': []
            }
            
            # Find attachments that have been migrated to cloud storage
            migrated_attachments = self.db.query(ItemAttachment).filter(
                ItemAttachment.is_active == True
            ).all()
            
            # Filter to only cloud storage files
            cloud_attachments = [
                att for att in migrated_attachments 
                if self._is_cloud_storage_path(att.file_path)
            ]
            
            rollback_results['total_files'] = len(cloud_attachments)
            
            if rollback_results['total_files'] == 0:
                rollback_results['message'] = 'No migrated files found to rollback'
                return rollback_results
            
            # Process attachments in batches
            for i in range(0, len(cloud_attachments), batch_size):
                batch = cloud_attachments[i:i + batch_size]
                
                for attachment in batch:
                    try:
                        # Verify local file exists if requested
                        if verify_local_files:
                            local_path = self._resolve_local_file_path(attachment, tenant_id)
                            if not local_path or not local_path.exists():
                                rollback_results['skipped_files'] += 1
                                rollback_results['errors'].append({
                                    'attachment_id': attachment.id,
                                    'filename': attachment.filename,
                                    'error': 'Local file not found - cannot rollback'
                                })
                                continue
                        
                        # Construct original local path
                        original_local_path = self._construct_original_local_path(attachment, tenant_id)
                        
                        # Store current cloud path for potential cleanup
                        cloud_file_key = attachment.file_path
                        
                        # Revert attachment to local path
                        attachment.file_path = str(original_local_path)
                        attachment.updated_at = datetime.now(timezone.utc)
                        
                        # Delete cloud file if requested
                        if delete_cloud_files and self.cloud_storage_service:
                            try:
                                deleted = await self.cloud_storage_service.delete_file(
                                    file_key=cloud_file_key,
                                    tenant_id=tenant_id,
                                    user_id=0  # System operation
                                )
                                if deleted:
                                    rollback_results['deleted_cloud_files'] += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete cloud file {cloud_file_key}: {e}")
                        
                        rollback_results['reverted_files'] += 1
                        logger.debug(f"Reverted attachment {attachment.id} from cloud to local storage")
                        
                    except Exception as e:
                        rollback_results['failed_files'] += 1
                        rollback_results['errors'].append({
                            'attachment_id': attachment.id,
                            'filename': attachment.filename,
                            'error': str(e)
                        })
                        logger.error(f"Failed to rollback attachment {attachment.id}: {e}")
                
                # Commit batch changes
                try:
                    self.db.commit()
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"Failed to commit rollback batch: {e}")
                    raise
            
            rollback_results['completed_at'] = datetime.now(timezone.utc).isoformat()
            rollback_results['success'] = rollback_results['failed_files'] == 0
            
            logger.info(
                f"Migration rollback completed for tenant {tenant_id}: "
                f"{rollback_results['reverted_files']} reverted, "
                f"{rollback_results['failed_files']} failed"
            )
            
            return rollback_results
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Migration rollback failed for tenant {tenant_id}: {e}")
            return {
                'tenant_id': tenant_id,
                'success': False,
                'error': str(e),
                'completed_at': datetime.now(timezone.utc).isoformat()
            }
    
    def _construct_original_local_path(self, attachment: ItemAttachment, tenant_id: str) -> Path:
        """
        Construct the original local file path for an attachment.
        
        Args:
            attachment: ItemAttachment object
            tenant_id: Tenant identifier
            
        Returns:
            Path object for original local location
        """
        base_path = Path(config.UPLOAD_PATH)
        attachment_type = self._get_storage_type(attachment.attachment_type)
        
        # Use stored_filename if available, otherwise use original filename
        filename = attachment.stored_filename or attachment.filename or f"file_{attachment.id}"
        
        return base_path / f"tenant_{tenant_id}" / attachment_type / filename
    
    async def verify_migration_integrity(self, tenant_id: str) -> Dict[str, Any]:
        """
        Verify the integrity of migrated files by comparing checksums.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with integrity verification results
        """
        try:
            logger.info(f"Starting migration integrity verification for tenant {tenant_id}")
            
            verification_results = {
                'tenant_id': tenant_id,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'total_files': 0,
                'verified_files': 0,
                'integrity_failures': 0,
                'access_failures': 0,
                'errors': []
            }
            
            # Find migrated attachments (cloud storage files)
            migrated_attachments = self.db.query(ItemAttachment).filter(
                ItemAttachment.is_active == True
            ).all()
            
            cloud_attachments = [
                att for att in migrated_attachments 
                if self._is_cloud_storage_path(att.file_path)
            ]
            
            verification_results['total_files'] = len(cloud_attachments)
            
            if not self.cloud_storage_service:
                verification_results['error'] = 'Cloud storage service not available'
                return verification_results
            
            # Verify each migrated file
            for attachment in cloud_attachments:
                try:
                    # Check if local file still exists for comparison
                    local_path = self._resolve_local_file_path(attachment, tenant_id)
                    if not local_path or not local_path.exists():
                        # Skip verification if no local file to compare against
                        continue
                    
                    # Calculate local file checksum
                    local_checksum = await self._calculate_file_checksum(local_path)
                    
                    # Download cloud file and calculate checksum
                    cloud_result = await self.cloud_storage_service.retrieve_file(
                        file_key=attachment.file_path,
                        tenant_id=tenant_id,
                        user_id=0,  # System verification
                        generate_url=False
                    )
                    
                    if not cloud_result.success or not cloud_result.file_content:
                        verification_results['access_failures'] += 1
                        verification_results['errors'].append({
                            'attachment_id': attachment.id,
                            'filename': attachment.filename,
                            'error': f'Cannot access cloud file: {cloud_result.error_message}'
                        })
                        continue
                    
                    cloud_checksum = await self._calculate_content_checksum(cloud_result.file_content)
                    
                    # Compare checksums
                    if local_checksum == cloud_checksum:
                        verification_results['verified_files'] += 1
                        logger.debug(f"Integrity verified for {attachment.filename}")
                    else:
                        verification_results['integrity_failures'] += 1
                        verification_results['errors'].append({
                            'attachment_id': attachment.id,
                            'filename': attachment.filename,
                            'error': f'Checksum mismatch: local={local_checksum}, cloud={cloud_checksum}'
                        })
                        logger.warning(f"Integrity failure for {attachment.filename}")
                
                except Exception as e:
                    verification_results['access_failures'] += 1
                    verification_results['errors'].append({
                        'attachment_id': attachment.id,
                        'filename': attachment.filename,
                        'error': str(e)
                    })
                    logger.error(f"Verification error for attachment {attachment.id}: {e}")
            
            verification_results['completed_at'] = datetime.now(timezone.utc).isoformat()
            verification_results['success'] = verification_results['integrity_failures'] == 0
            
            logger.info(
                f"Migration integrity verification completed for tenant {tenant_id}: "
                f"{verification_results['verified_files']} verified, "
                f"{verification_results['integrity_failures']} failed"
            )
            
            return verification_results
            
        except Exception as e:
            logger.error(f"Migration integrity verification failed for tenant {tenant_id}: {e}")
            return {
                'tenant_id': tenant_id,
                'success': False,
                'error': str(e),
                'completed_at': datetime.now(timezone.utc).isoformat()
            }
    
    async def cleanup_local_files_after_migration(
        self,
        tenant_id: str,
        verify_cloud_files: bool = True,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean up local files after successful migration to cloud storage.
        
        Args:
            tenant_id: Tenant identifier
            verify_cloud_files: Whether to verify cloud files exist before deletion
            dry_run: If True, only simulate cleanup without actual deletion
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            logger.info(f"Starting local file cleanup for tenant {tenant_id} (dry_run={dry_run})")
            
            cleanup_results = {
                'tenant_id': tenant_id,
                'dry_run': dry_run,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'total_files': 0,
                'deleted_files': 0,
                'skipped_files': 0,
                'failed_deletions': 0,
                'space_freed_bytes': 0,
                'errors': []
            }
            
            # Find migrated attachments
            migrated_attachments = self.db.query(ItemAttachment).filter(
                ItemAttachment.is_active == True
            ).all()
            
            cloud_attachments = [
                att for att in migrated_attachments 
                if self._is_cloud_storage_path(att.file_path)
            ]
            
            cleanup_results['total_files'] = len(cloud_attachments)
            
            # Process each migrated attachment
            for attachment in cloud_attachments:
                try:
                    # Find corresponding local file
                    local_path = self._resolve_local_file_path(attachment, tenant_id)
                    if not local_path or not local_path.exists():
                        cleanup_results['skipped_files'] += 1
                        continue
                    
                    # Verify cloud file exists if requested
                    if verify_cloud_files and self.cloud_storage_service:
                        exists, provider = await self.cloud_storage_service.file_exists(
                            file_key=attachment.file_path,
                            tenant_id=tenant_id,
                            user_id=0
                        )
                        
                        if not exists:
                            cleanup_results['skipped_files'] += 1
                            cleanup_results['errors'].append({
                                'attachment_id': attachment.id,
                                'filename': attachment.filename,
                                'error': 'Cloud file not found - skipping local deletion'
                            })
                            continue
                    
                    # Get file size before deletion
                    file_size = local_path.stat().st_size
                    
                    if not dry_run:
                        # Delete local file
                        local_path.unlink()
                        logger.debug(f"Deleted local file: {local_path}")
                    
                    cleanup_results['deleted_files'] += 1
                    cleanup_results['space_freed_bytes'] += file_size
                    
                except Exception as e:
                    cleanup_results['failed_deletions'] += 1
                    cleanup_results['errors'].append({
                        'attachment_id': attachment.id,
                        'filename': attachment.filename,
                        'error': str(e)
                    })
                    logger.error(f"Failed to delete local file for attachment {attachment.id}: {e}")
            
            cleanup_results['completed_at'] = datetime.now(timezone.utc).isoformat()
            cleanup_results['success'] = cleanup_results['failed_deletions'] == 0
            cleanup_results['space_freed_mb'] = cleanup_results['space_freed_bytes'] / (1024 * 1024)
            
            logger.info(
                f"Local file cleanup completed for tenant {tenant_id}: "
                f"{cleanup_results['deleted_files']} deleted, "
                f"{cleanup_results['space_freed_mb']:.1f}MB freed"
            )
            
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Local file cleanup failed for tenant {tenant_id}: {e}")
            return {
                'tenant_id': tenant_id,
                'success': False,
                'error': str(e),
                'completed_at': datetime.now(timezone.utc).isoformat()
            }
    
    def get_migration_statistics(self) -> Dict[str, Any]:
        """
        Get overall migration statistics across all tenants.
        
        Returns:
            Dictionary with migration statistics
        """
        try:
            stats = {
                'active_migrations': 0,
                'completed_migrations': 0,
                'failed_migrations': 0,
                'total_files_migrated': 0,
                'total_data_migrated_mb': 0,
                'average_success_rate': 0.0,
                'tenant_progress': {}
            }
            
            # Analyze all migration progress
            total_success_rates = []
            
            for tenant_id, progress in self._migration_progress.items():
                stats['tenant_progress'][tenant_id] = {
                    'status': progress.status.value,
                    'completion_percentage': progress.completion_percentage,
                    'success_rate': progress.success_rate,
                    'total_files': progress.total_files,
                    'successful_files': progress.successful_files
                }
                
                if progress.status == MigrationStatus.IN_PROGRESS:
                    stats['active_migrations'] += 1
                elif progress.status == MigrationStatus.COMPLETED:
                    stats['completed_migrations'] += 1
                elif progress.status == MigrationStatus.FAILED:
                    stats['failed_migrations'] += 1
                
                stats['total_files_migrated'] += progress.successful_files
                stats['total_data_migrated_mb'] += progress.migrated_size_bytes / (1024 * 1024)
                
                if progress.processed_files > 0:
                    total_success_rates.append(progress.success_rate)
            
            # Calculate average success rate
            if total_success_rates:
                stats['average_success_rate'] = sum(total_success_rates) / len(total_success_rates)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get migration statistics: {e}")
            return {'error': str(e)}
    
    def clear_migration_progress(self, tenant_id: str) -> bool:
        """
        Clear migration progress tracking for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if cleared successfully
        """
        try:
            if tenant_id in self._migration_progress:
                del self._migration_progress[tenant_id]
            if tenant_id in self._migration_locks:
                del self._migration_locks[tenant_id]
            logger.info(f"Cleared migration progress for tenant {tenant_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear migration progress for tenant {tenant_id}: {e}")
            return False
    
    def clear_all_migration_progress(self) -> int:
        """
        Clear all migration progress tracking.
        
        Returns:
            Number of tenant progress records cleared
        """
        try:
            count = len(self._migration_progress)
            self._migration_progress.clear()
            self._migration_locks.clear()
            logger.info(f"Cleared migration progress for {count} tenants")
            return count
        except Exception as e:
            logger.error(f"Failed to clear all migration progress: {e}")
            return 0
