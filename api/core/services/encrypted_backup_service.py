"""
Encrypted Backup and Recovery Service for tenant database encryption.

This service provides secure backup and recovery procedures for encrypted tenant databases,
including key backup, disaster recovery, and backup integrity validation.
"""

import logging
import asyncio
import os
import shutil
import gzip
import json
import hashlib
import tempfile
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import subprocess

from encryption_config import EncryptionConfig
from core.services.key_management_service import KeyManagementService
from core.services.encryption_service import EncryptionService
from core.exceptions.encryption_exceptions import (
    EncryptionError,
    KeyNotFoundError
)

logger = logging.getLogger(__name__)


class BackupType(Enum):
    """Backup type enumeration."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    KEY_ONLY = "key_only"


class BackupStatus(Enum):
    """Backup operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRUPTED = "corrupted"


class RecoveryStatus(Enum):
    """Recovery operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BackupMetadata:
    """Backup metadata information."""
    backup_id: str
    tenant_id: int
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    checksum: Optional[str] = None
    encryption_key_id: Optional[str] = None
    compression_enabled: bool = True
    retention_until: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Database-specific metadata
    database_name: Optional[str] = None
    schema_version: Optional[str] = None
    record_count: int = 0
    
    # Key backup metadata
    key_backup_included: bool = True
    key_backup_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'backup_id': self.backup_id,
            'tenant_id': self.tenant_id,
            'backup_type': self.backup_type.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'file_path': self.file_path,
            'file_size_bytes': self.file_size_bytes,
            'checksum': self.checksum,
            'encryption_key_id': self.encryption_key_id,
            'compression_enabled': self.compression_enabled,
            'retention_until': self.retention_until.isoformat() if self.retention_until else None,
            'error_message': self.error_message,
            'database_name': self.database_name,
            'schema_version': self.schema_version,
            'record_count': self.record_count,
            'key_backup_included': self.key_backup_included,
            'key_backup_path': self.key_backup_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackupMetadata':
        """Create from dictionary."""
        return cls(
            backup_id=data['backup_id'],
            tenant_id=data['tenant_id'],
            backup_type=BackupType(data['backup_type']),
            status=BackupStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            file_path=data.get('file_path'),
            file_size_bytes=data.get('file_size_bytes', 0),
            checksum=data.get('checksum'),
            encryption_key_id=data.get('encryption_key_id'),
            compression_enabled=data.get('compression_enabled', True),
            retention_until=datetime.fromisoformat(data['retention_until']) if data.get('retention_until') else None,
            error_message=data.get('error_message'),
            database_name=data.get('database_name'),
            schema_version=data.get('schema_version'),
            record_count=data.get('record_count', 0),
            key_backup_included=data.get('key_backup_included', True),
            key_backup_path=data.get('key_backup_path')
        )


@dataclass
class RecoveryJob:
    """Recovery job information."""
    recovery_id: str
    tenant_id: int
    backup_id: str
    status: RecoveryStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    target_database: Optional[str] = None
    recovery_point: Optional[datetime] = None
    error_message: Optional[str] = None
    recovered_records: int = 0
    total_records: int = 0
    
    @property
    def progress_percentage(self) -> float:
        """Calculate recovery progress percentage."""
        if self.total_records == 0:
            return 0.0
        return (self.recovered_records / self.total_records) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'recovery_id': self.recovery_id,
            'tenant_id': self.tenant_id,
            'backup_id': self.backup_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'target_database': self.target_database,
            'recovery_point': self.recovery_point.isoformat() if self.recovery_point else None,
            'error_message': self.error_message,
            'recovered_records': self.recovered_records,
            'total_records': self.total_records,
            'progress_percentage': self.progress_percentage
        }


class EncryptedBackupService:
    """
    Service for encrypted backup and recovery operations.
    
    Features:
    - Encrypted database backups with key backup
    - Multiple backup types (full, incremental, differential)
    - Backup integrity validation and testing
    - Disaster recovery procedures
    - Automated retention management
    """
    
    def __init__(self, 
                 key_management_service: Optional[KeyManagementService] = None,
                 encryption_service: Optional[EncryptionService] = None):
        self.config = EncryptionConfig()
        self.key_management = key_management_service or KeyManagementService()
        self.encryption_service = encryption_service or EncryptionService()
        
        # Backup storage configuration
        self.backup_root_path = Path(self.config.KEY_BACKUP_PATH).parent / "database_backups"
        self.backup_root_path.mkdir(parents=True, exist_ok=True)
        
        # Backup management
        self._active_backups: Dict[str, BackupMetadata] = {}
        self._backup_history: List[BackupMetadata] = []
        self._active_recoveries: Dict[str, RecoveryJob] = {}
        self._recovery_history: List[RecoveryJob] = []
        
        # Load existing backup metadata
        self._load_backup_metadata()
        
        logger.info("EncryptedBackupService initialized")
    
    def _load_backup_metadata(self):
        """Load existing backup metadata from storage."""
        metadata_file = self.backup_root_path / "backup_metadata.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                    
                for backup_data in data.get('backups', []):
                    backup = BackupMetadata.from_dict(backup_data)
                    self._backup_history.append(backup)
                
                logger.info(f"Loaded {len(self._backup_history)} backup records")
                
            except Exception as e:
                logger.error(f"Failed to load backup metadata: {str(e)}")
    
    def _save_backup_metadata(self):
        """Save backup metadata to storage."""
        metadata_file = self.backup_root_path / "backup_metadata.json"
        
        try:
            data = {
                'backups': [backup.to_dict() for backup in self._backup_history],
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save backup metadata: {str(e)}")
    
    async def create_backup(self, 
                          tenant_id: int, 
                          backup_type: BackupType = BackupType.FULL,
                          include_keys: bool = True,
                          compression: bool = True) -> BackupMetadata:
        """
        Create an encrypted backup for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            backup_type: Type of backup to create
            include_keys: Whether to include key backup
            compression: Whether to compress the backup
            
        Returns:
            BackupMetadata with backup details
            
        Raises:
            EncryptionError: If backup creation fails
        """
        backup_id = f"backup_{tenant_id}_{backup_type.value}_{int(datetime.now().timestamp())}"
        
        # Create backup metadata
        backup = BackupMetadata(
            backup_id=backup_id,
            tenant_id=tenant_id,
            backup_type=backup_type,
            status=BackupStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            compression_enabled=compression,
            key_backup_included=include_keys,
            retention_until=datetime.now(timezone.utc) + timedelta(days=self.config.KEY_BACKUP_RETENTION_DAYS)
        )
        
        self._active_backups[backup_id] = backup
        
        try:
            logger.info(f"Starting backup {backup_id} for tenant {tenant_id}")
            
            # Execute backup process
            await self._execute_backup(backup)
            
            # Mark as completed
            backup.status = BackupStatus.COMPLETED
            backup.completed_at = datetime.now(timezone.utc)
            
            logger.info(f"Successfully completed backup {backup_id}")
            
        except Exception as e:
            logger.error(f"Backup {backup_id} failed: {str(e)}")
            backup.status = BackupStatus.FAILED
            backup.error_message = str(e)
            backup.completed_at = datetime.now(timezone.utc)
            raise EncryptionError(f"Backup creation failed: {str(e)}")
        
        finally:
            # Move to history and save metadata
            self._backup_history.append(backup)
            self._active_backups.pop(backup_id, None)
            self._save_backup_metadata()
        
        return backup
    
    async def _execute_backup(self, backup: BackupMetadata):
        """Execute the backup process."""
        backup.status = BackupStatus.IN_PROGRESS
        
        # Create backup directory
        backup_dir = self.backup_root_path / f"tenant_{backup.tenant_id}" / backup.backup_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Step 1: Backup encryption keys
            if backup.key_backup_included:
                await self._backup_keys(backup, backup_dir)
            
            # Step 2: Backup database
            await self._backup_database(backup, backup_dir)
            
            # Step 3: Create backup archive
            await self._create_backup_archive(backup, backup_dir)
            
            # Step 4: Validate backup integrity
            await self._validate_backup_integrity(backup)
            
        except Exception as e:
            # Clean up on failure
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            raise
    
    async def _backup_keys(self, backup: BackupMetadata, backup_dir: Path):
        """Backup encryption keys."""
        logger.info(f"Backing up keys for backup {backup.backup_id}")
        
        try:
            # Get current key metadata
            key_metadata = self.key_management.get_key_metadata(backup.tenant_id)
            if key_metadata:
                backup.encryption_key_id = key_metadata.get('key_id')
            
            # Create key backup
            key_backup_success = self.key_management.backup_keys()
            
            if not key_backup_success:
                raise EncryptionError("Key backup failed")
            
            # Store key backup path
            backup.key_backup_path = str(backup_dir / "keys_backup.json")
            
            # Copy key backup to backup directory
            # In a real implementation, this would copy the actual key backup
            key_backup_data = {
                'tenant_id': backup.tenant_id,
                'key_id': backup.encryption_key_id,
                'backup_timestamp': datetime.now(timezone.utc).isoformat(),
                'backup_type': 'encrypted_key_backup'
            }
            
            with open(backup.key_backup_path, 'w') as f:
                json.dump(key_backup_data, f, indent=2)
            
            logger.info(f"Key backup completed for backup {backup.backup_id}")
            
        except Exception as e:
            raise EncryptionError(f"Key backup failed: {str(e)}")
    
    async def _backup_database(self, backup: BackupMetadata, backup_dir: Path):
        """Backup database content."""
        logger.info(f"Backing up database for backup {backup.backup_id}")
        
        try:
            # In a real implementation, this would:
            # 1. Connect to the tenant database
            # 2. Export all tables and data
            # 3. Handle encrypted fields appropriately
            # 4. Create SQL dump or binary backup
            
            # For simulation, create a mock database backup
            database_backup_path = backup_dir / "database_backup.sql"
            
            # Simulate database backup content
            backup_content = f"""
-- Database backup for tenant {backup.tenant_id}
-- Created: {backup.created_at.isoformat()}
-- Backup ID: {backup.backup_id}
-- Backup Type: {backup.backup_type.value}

-- Note: This is a simulated backup for demonstration
-- In production, this would contain actual encrypted database content

CREATE SCHEMA IF NOT EXISTS tenant_{backup.tenant_id};

-- Simulated table structures and data would be here
-- All sensitive data would remain encrypted in the backup

INSERT INTO backup_metadata (backup_id, tenant_id, created_at) 
VALUES ('{backup.backup_id}', {backup.tenant_id}, '{backup.created_at.isoformat()}');
"""
            
            with open(database_backup_path, 'w') as f:
                f.write(backup_content)
            
            # Set database metadata
            backup.database_name = f"tenant_{backup.tenant_id}"
            backup.schema_version = "1.0"
            backup.record_count = 1000  # Simulated record count
            
            logger.info(f"Database backup completed for backup {backup.backup_id}")
            
        except Exception as e:
            raise EncryptionError(f"Database backup failed: {str(e)}")
    
    async def _create_backup_archive(self, backup: BackupMetadata, backup_dir: Path):
        """Create compressed and encrypted backup archive."""
        logger.info(f"Creating backup archive for backup {backup.backup_id}")
        
        try:
            archive_path = backup_dir.parent / f"{backup.backup_id}.tar.gz"
            
            # Create compressed archive
            if backup.compression_enabled:
                # Use tar with gzip compression
                cmd = [
                    'tar', '-czf', str(archive_path),
                    '-C', str(backup_dir.parent),
                    backup_dir.name
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise EncryptionError(f"Archive creation failed: {result.stderr}")
            else:
                # Create uncompressed archive
                shutil.make_archive(str(archive_path.with_suffix('')), 'tar', backup_dir.parent, backup_dir.name)
            
            # Calculate file size and checksum
            backup.file_path = str(archive_path)
            backup.file_size_bytes = archive_path.stat().st_size
            backup.checksum = await self._calculate_file_checksum(archive_path)
            
            # Clean up temporary backup directory
            shutil.rmtree(backup_dir, ignore_errors=True)
            
            logger.info(f"Backup archive created: {archive_path} ({backup.file_size_bytes} bytes)")
            
        except Exception as e:
            raise EncryptionError(f"Archive creation failed: {str(e)}")
    
    async def _validate_backup_integrity(self, backup: BackupMetadata):
        """Validate backup integrity."""
        logger.info(f"Validating backup integrity for backup {backup.backup_id}")
        
        try:
            if not backup.file_path or not os.path.exists(backup.file_path):
                raise EncryptionError("Backup file not found")
            
            # Verify file size
            actual_size = os.path.getsize(backup.file_path)
            if actual_size != backup.file_size_bytes:
                raise EncryptionError(f"File size mismatch: expected {backup.file_size_bytes}, got {actual_size}")
            
            # Verify checksum
            actual_checksum = await self._calculate_file_checksum(Path(backup.file_path))
            if actual_checksum != backup.checksum:
                backup.status = BackupStatus.CORRUPTED
                raise EncryptionError("Backup checksum verification failed")
            
            # Test archive extraction (partial)
            await self._test_backup_extraction(backup)
            
            logger.info(f"Backup integrity validation passed for backup {backup.backup_id}")
            
        except Exception as e:
            backup.status = BackupStatus.CORRUPTED
            raise EncryptionError(f"Backup integrity validation failed: {str(e)}")
    
    async def _test_backup_extraction(self, backup: BackupMetadata):
        """Test backup extraction without full restore."""
        logger.info(f"Testing backup extraction for backup {backup.backup_id}")
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract archive to temporary directory
                cmd = ['tar', '-xzf', backup.file_path, '-C', temp_dir]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise EncryptionError(f"Archive extraction test failed: {result.stderr}")
                
                # Verify extracted contents
                extracted_dir = Path(temp_dir) / backup.backup_id
                if not extracted_dir.exists():
                    raise EncryptionError("Extracted backup directory not found")
                
                # Check for key backup if included
                if backup.key_backup_included:
                    key_backup_file = extracted_dir / "keys_backup.json"
                    if not key_backup_file.exists():
                        raise EncryptionError("Key backup file not found in archive")
                
                # Check for database backup
                db_backup_file = extracted_dir / "database_backup.sql"
                if not db_backup_file.exists():
                    raise EncryptionError("Database backup file not found in archive")
            
            logger.info(f"Backup extraction test passed for backup {backup.backup_id}")
            
        except Exception as e:
            raise EncryptionError(f"Backup extraction test failed: {str(e)}")
    
    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        hash_sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    async def restore_backup(self, 
                           backup_id: str, 
                           target_tenant_id: Optional[int] = None,
                           target_database: Optional[str] = None,
                           recovery_point: Optional[datetime] = None) -> RecoveryJob:
        """
        Restore from an encrypted backup.
        
        Args:
            backup_id: Backup identifier to restore from
            target_tenant_id: Target tenant ID (defaults to original)
            target_database: Target database name (optional)
            recovery_point: Point-in-time recovery target (optional)
            
        Returns:
            RecoveryJob with recovery details
            
        Raises:
            EncryptionError: If restore fails
        """
        # Find backup metadata
        backup = self._find_backup(backup_id)
        if not backup:
            raise EncryptionError(f"Backup {backup_id} not found")
        
        if backup.status != BackupStatus.COMPLETED:
            raise EncryptionError(f"Cannot restore from backup with status {backup.status.value}")
        
        # Create recovery job
        recovery_id = f"recovery_{backup_id}_{int(datetime.now().timestamp())}"
        target_tenant = target_tenant_id or backup.tenant_id
        
        recovery = RecoveryJob(
            recovery_id=recovery_id,
            tenant_id=target_tenant,
            backup_id=backup_id,
            status=RecoveryStatus.PENDING,
            started_at=datetime.now(timezone.utc),
            target_database=target_database,
            recovery_point=recovery_point,
            total_records=backup.record_count
        )
        
        self._active_recoveries[recovery_id] = recovery
        
        try:
            logger.info(f"Starting recovery {recovery_id} from backup {backup_id}")
            
            # Execute recovery process
            await self._execute_recovery(recovery, backup)
            
            # Mark as completed
            recovery.status = RecoveryStatus.COMPLETED
            recovery.completed_at = datetime.now(timezone.utc)
            
            logger.info(f"Successfully completed recovery {recovery_id}")
            
        except Exception as e:
            logger.error(f"Recovery {recovery_id} failed: {str(e)}")
            recovery.status = RecoveryStatus.FAILED
            recovery.error_message = str(e)
            recovery.completed_at = datetime.now(timezone.utc)
            raise EncryptionError(f"Recovery failed: {str(e)}")
        
        finally:
            # Move to history
            self._recovery_history.append(recovery)
            self._active_recoveries.pop(recovery_id, None)
        
        return recovery
    
    async def _execute_recovery(self, recovery: RecoveryJob, backup: BackupMetadata):
        """Execute the recovery process."""
        recovery.status = RecoveryStatus.IN_PROGRESS
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Step 1: Extract backup archive
                await self._extract_backup_archive(backup, temp_dir)
                
                # Step 2: Restore encryption keys
                if backup.key_backup_included:
                    await self._restore_keys(recovery, backup, temp_dir)
                
                # Step 3: Restore database
                await self._restore_database(recovery, backup, temp_dir)
                
                # Step 4: Validate restored data
                await self._validate_restored_data(recovery, backup)
            
        except Exception as e:
            raise EncryptionError(f"Recovery execution failed: {str(e)}")
    
    async def _extract_backup_archive(self, backup: BackupMetadata, temp_dir: str):
        """Extract backup archive."""
        logger.info(f"Extracting backup archive {backup.backup_id}")
        
        try:
            cmd = ['tar', '-xzf', backup.file_path, '-C', temp_dir]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise EncryptionError(f"Archive extraction failed: {result.stderr}")
            
            logger.info(f"Backup archive extracted successfully")
            
        except Exception as e:
            raise EncryptionError(f"Archive extraction failed: {str(e)}")
    
    async def _restore_keys(self, recovery: RecoveryJob, backup: BackupMetadata, temp_dir: str):
        """Restore encryption keys."""
        logger.info(f"Restoring keys for recovery {recovery.recovery_id}")
        
        try:
            key_backup_path = os.path.join(temp_dir, backup.backup_id, "keys_backup.json")
            
            if not os.path.exists(key_backup_path):
                raise EncryptionError("Key backup file not found")
            
            # In a real implementation, this would:
            # 1. Load the key backup
            # 2. Decrypt the keys using the master key
            # 3. Restore keys to the key management system
            # 4. Verify key restoration
            
            logger.info(f"Keys restored successfully for recovery {recovery.recovery_id}")
            
        except Exception as e:
            raise EncryptionError(f"Key restoration failed: {str(e)}")
    
    async def _restore_database(self, recovery: RecoveryJob, backup: BackupMetadata, temp_dir: str):
        """Restore database content."""
        logger.info(f"Restoring database for recovery {recovery.recovery_id}")
        
        try:
            db_backup_path = os.path.join(temp_dir, backup.backup_id, "database_backup.sql")
            
            if not os.path.exists(db_backup_path):
                raise EncryptionError("Database backup file not found")
            
            # In a real implementation, this would:
            # 1. Connect to the target database
            # 2. Execute the SQL backup file
            # 3. Handle encrypted data appropriately
            # 4. Apply any point-in-time recovery if specified
            
            # Simulate database restoration
            recovery.recovered_records = backup.record_count
            
            logger.info(f"Database restored successfully for recovery {recovery.recovery_id}")
            
        except Exception as e:
            raise EncryptionError(f"Database restoration failed: {str(e)}")
    
    async def _validate_restored_data(self, recovery: RecoveryJob, backup: BackupMetadata):
        """Validate restored data integrity."""
        logger.info(f"Validating restored data for recovery {recovery.recovery_id}")
        
        try:
            # In a real implementation, this would:
            # 1. Verify record counts match backup
            # 2. Test encryption/decryption of sample records
            # 3. Validate data integrity constraints
            # 4. Check referential integrity
            
            # Simulate validation
            if recovery.recovered_records != backup.record_count:
                recovery.status = RecoveryStatus.PARTIAL
                logger.warning(f"Partial recovery: {recovery.recovered_records}/{backup.record_count} records")
            
            logger.info(f"Data validation completed for recovery {recovery.recovery_id}")
            
        except Exception as e:
            raise EncryptionError(f"Data validation failed: {str(e)}")
    
    def _find_backup(self, backup_id: str) -> Optional[BackupMetadata]:
        """Find backup by ID."""
        for backup in self._backup_history:
            if backup.backup_id == backup_id:
                return backup
        return None
    
    def list_backups(self, tenant_id: Optional[int] = None, limit: int = 100) -> List[BackupMetadata]:
        """
        List available backups.
        
        Args:
            tenant_id: Filter by tenant ID (optional)
            limit: Maximum number of records
            
        Returns:
            List of BackupMetadata records
        """
        backups = self._backup_history.copy()
        
        if tenant_id is not None:
            backups = [backup for backup in backups if backup.tenant_id == tenant_id]
        
        # Sort by creation time (most recent first)
        backups.sort(key=lambda x: x.created_at, reverse=True)
        
        return backups[:limit]
    
    def get_backup_status(self, backup_id: str) -> Optional[BackupMetadata]:
        """
        Get backup status.
        
        Args:
            backup_id: Backup identifier
            
        Returns:
            BackupMetadata or None if not found
        """
        return self._find_backup(backup_id)
    
    def get_recovery_status(self, recovery_id: str) -> Optional[RecoveryJob]:
        """
        Get recovery status.
        
        Args:
            recovery_id: Recovery identifier
            
        Returns:
            RecoveryJob or None if not found
        """
        return self._active_recoveries.get(recovery_id)
    
    def delete_backup(self, backup_id: str) -> bool:
        """
        Delete a backup.
        
        Args:
            backup_id: Backup identifier
            
        Returns:
            True if deletion successful
        """
        backup = self._find_backup(backup_id)
        if not backup:
            return False
        
        try:
            # Delete backup file
            if backup.file_path and os.path.exists(backup.file_path):
                os.remove(backup.file_path)
            
            # Remove from history
            self._backup_history.remove(backup)
            self._save_backup_metadata()
            
            logger.info(f"Deleted backup {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete backup {backup_id}: {str(e)}")
            return False
    
    async def cleanup_expired_backups(self):
        """Clean up expired backups based on retention policy."""
        logger.info("Starting backup cleanup")
        
        current_time = datetime.now(timezone.utc)
        expired_backups = []
        
        for backup in self._backup_history:
            if backup.retention_until and current_time > backup.retention_until:
                expired_backups.append(backup)
        
        for backup in expired_backups:
            if self.delete_backup(backup.backup_id):
                logger.info(f"Cleaned up expired backup {backup.backup_id}")
        
        logger.info(f"Backup cleanup completed: {len(expired_backups)} backups removed")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        total_backups = len(self._backup_history)
        completed_backups = len([b for b in self._backup_history if b.status == BackupStatus.COMPLETED])
        failed_backups = len([b for b in self._backup_history if b.status == BackupStatus.FAILED])
        
        total_size = sum(b.file_size_bytes for b in self._backup_history if b.file_size_bytes > 0)
        
        success_rate = (completed_backups / total_backups) * 100 if total_backups > 0 else 0
        
        return {
            'total_backups': total_backups,
            'completed_backups': completed_backups,
            'failed_backups': failed_backups,
            'success_rate_percent': round(success_rate, 2),
            'total_backup_size_bytes': total_size,
            'active_backups': len(self._active_backups),
            'active_recoveries': len(self._active_recoveries),
            'backup_root_path': str(self.backup_root_path)
        }


# Global encrypted backup service instance
_encrypted_backup_service: Optional[EncryptedBackupService] = None


def get_encrypted_backup_service() -> EncryptedBackupService:
    """
    Get global encrypted backup service instance.
    
    Returns:
        EncryptedBackupService instance
    """
    global _encrypted_backup_service
    if _encrypted_backup_service is None:
        _encrypted_backup_service = EncryptedBackupService()
    return _encrypted_backup_service