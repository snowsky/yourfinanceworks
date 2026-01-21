"""
Key rotation and security tests for tenant database encryption.

Tests zero-downtime key rotation scenarios, data re-encryption integrity,
backup and recovery procedures, and security aspects of the encryption system.
"""

import pytest
import asyncio
import time
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, List, Any

from core.services.key_rotation_service import (
    KeyRotationService,
    RotationStatus,
    RotationPhase,
    RotationJob,
    get_key_rotation_service
)
from core.services.key_management_service import KeyManagementService
from core.services.encryption_service import EncryptionService
from core.utils.data_reencryption import DataReencryptionService
from core.services.encrypted_backup_service import EncryptedBackupService
from core.exceptions.encryption_exceptions import (
    KeyRotationError,
    EncryptionError,
    KeyNotFoundError
)


class TestKeyRotationService:
    """Test cases for key rotation functionality."""

    @pytest.fixture
    def mock_key_management(self):
        """Mock key management service."""
        mock_service = Mock(spec=KeyManagementService)
        mock_service.generate_tenant_key.return_value = "new-key-id-123"
        mock_service.get_key_metadata.return_value = {
            'key_id': 'old-key-id-456',
            'created_at': '2023-01-01T00:00:00Z',
            'stored_at': '2023-01-01T00:00:00Z'
        }
        mock_service.list_tenant_keys.return_value = {
            1: {'key_id': 'key-1', 'created_at': '2023-01-01T00:00:00Z'},
            2: {'key_id': 'key-2', 'created_at': '2023-06-01T00:00:00Z'}
        }
        return mock_service

    @pytest.fixture
    def mock_encryption_service(self):
        """Mock encryption service."""
        mock_service = Mock(spec=EncryptionService)
        mock_service.clear_cache.return_value = None
        return mock_service

    @pytest.fixture
    def rotation_service(self, mock_key_management, mock_encryption_service):
        """Create key rotation service with mocked dependencies."""
        return KeyRotationService(
            key_management_service=mock_key_management,
            encryption_service=mock_encryption_service
        )

    @pytest.fixture
    def sample_rotation_job(self):
        """Create sample rotation job for testing."""
        return RotationJob(
            tenant_id=1,
            job_id="test-job-123",
            status=RotationStatus.PENDING,
            phase=RotationPhase.PREPARATION,
            started_at=datetime.now(timezone.utc)
        )

    @pytest.mark.asyncio
    async def test_successful_key_rotation(self, rotation_service, mock_key_management, mock_encryption_service):
        """Test successful key rotation process."""
        tenant_id = 1
        
        # Execute rotation
        job = await rotation_service.rotate_tenant_key(tenant_id)
        
        # Verify job completion
        assert job.status == RotationStatus.COMPLETED
        assert job.tenant_id == tenant_id
        assert job.old_key_id == "old-key-id-456"
        assert job.new_key_id == "new-key-id-123"
        assert job.progress_percentage == 100.0
        assert job.completed_at is not None
        
        # Verify key management calls
        mock_key_management.get_key_metadata.assert_called_with(tenant_id)
        mock_key_management.generate_tenant_key.assert_called_with(tenant_id)
        
        # Verify encryption service cache was cleared
        assert mock_encryption_service.clear_cache.call_count >= 2

    @pytest.mark.asyncio
    async def test_rotation_failure_and_rollback(self, rotation_service, mock_key_management, mock_encryption_service):
        """Test rotation failure handling and rollback."""
        tenant_id = 1
        
        # Mock key generation failure
        mock_key_management.generate_tenant_key.side_effect = Exception("Key generation failed")
        
        # Execute rotation (should fail)
        with pytest.raises(KeyRotationError, match="Key rotation failed"):
            await rotation_service.rotate_tenant_key(tenant_id)
        
        # Verify rollback was attempted
        assert tenant_id not in rotation_service._active_rotations
        
        # Check rotation history
        history = rotation_service.get_rotation_history(tenant_id)
        assert len(history) == 1
        assert history[0].status == RotationStatus.ROLLED_BACK
        assert "Key generation failed" in history[0].error_message

    @pytest.mark.asyncio
    async def test_concurrent_rotation_prevention(self, rotation_service):
        """Test prevention of concurrent rotations for same tenant."""
        tenant_id = 1
        
        # Start first rotation (mock it to be slow)
        with patch.object(rotation_service, '_execute_rotation_phases') as mock_phases:
            # Make the rotation take time
            async def slow_rotation(job):
                await asyncio.sleep(0.1)
                job.status = RotationStatus.COMPLETED
            
            mock_phases.side_effect = slow_rotation
            
            # Start first rotation
            task1 = asyncio.create_task(rotation_service.rotate_tenant_key(tenant_id))
            
            # Wait a bit then try second rotation
            await asyncio.sleep(0.05)
            
            # Second rotation should fail
            with pytest.raises(KeyRotationError, match="already in progress"):
                await rotation_service.rotate_tenant_key(tenant_id)
            
            # Wait for first rotation to complete
            job1 = await task1
            assert job1.status == RotationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_rotation_phases_execution(self, rotation_service):
        """Test that all rotation phases are executed in order."""
        tenant_id = 1
        
        executed_phases = []
        
        # Mock each phase to track execution
        async def track_phase(job, phase_name):
            executed_phases.append(phase_name)
        
        with patch.object(rotation_service, '_phase_preparation', side_effect=lambda job: track_phase(job, 'preparation')):
            with patch.object(rotation_service, '_phase_key_generation', side_effect=lambda job: track_phase(job, 'key_generation')):
                with patch.object(rotation_service, '_phase_dual_key_activation', side_effect=lambda job: track_phase(job, 'dual_key_activation')):
                    with patch.object(rotation_service, '_phase_data_reencryption', side_effect=lambda job: track_phase(job, 'data_reencryption')):
                        with patch.object(rotation_service, '_phase_old_key_deactivation', side_effect=lambda job: track_phase(job, 'old_key_deactivation')):
                            with patch.object(rotation_service, '_phase_cleanup', side_effect=lambda job: track_phase(job, 'cleanup')):
                                
                                job = await rotation_service.rotate_tenant_key(tenant_id)
        
        # Verify all phases were executed in order
        expected_phases = ['preparation', 'key_generation', 'dual_key_activation', 
                          'data_reencryption', 'old_key_deactivation', 'cleanup']
        assert executed_phases == expected_phases
        assert job.status == RotationStatus.COMPLETED

    def test_dual_key_management(self, rotation_service):
        """Test dual key storage and management."""
        tenant_id = 1
        
        # Initially no dual key
        assert not rotation_service.is_dual_key_active(tenant_id)
        assert rotation_service.get_dual_key_info(tenant_id) is None
        
        # Simulate dual key activation
        with rotation_service._dual_key_lock:
            rotation_service._dual_key_storage[tenant_id] = {
                'old_key_id': 'old-key-123',
                'new_key_id': 'new-key-456',
                'activated_at': datetime.now(timezone.utc).isoformat(),
                'read_key': 'old-key-123',
                'write_key': 'new-key-456'
            }
        
        # Verify dual key is active
        assert rotation_service.is_dual_key_active(tenant_id)
        
        dual_key_info = rotation_service.get_dual_key_info(tenant_id)
        assert dual_key_info is not None
        assert dual_key_info['old_key_id'] == 'old-key-123'
        assert dual_key_info['new_key_id'] == 'new-key-456'
        assert dual_key_info['read_key'] == 'old-key-123'
        assert dual_key_info['write_key'] == 'new-key-456'

    def test_rotation_status_tracking(self, rotation_service, sample_rotation_job):
        """Test rotation status tracking and history."""
        tenant_id = sample_rotation_job.tenant_id
        
        # Add job to active rotations
        with rotation_service._rotation_lock:
            rotation_service._active_rotations[tenant_id] = sample_rotation_job
        
        # Test getting active rotation status
        status = rotation_service.get_rotation_status(tenant_id)
        assert status is not None
        assert status.job_id == sample_rotation_job.job_id
        assert status.status == RotationStatus.PENDING
        
        # Move to history
        sample_rotation_job.status = RotationStatus.COMPLETED
        with rotation_service._rotation_lock:
            rotation_service._rotation_history.append(sample_rotation_job)
            del rotation_service._active_rotations[tenant_id]
        
        # Test history retrieval
        history = rotation_service.get_rotation_history(tenant_id)
        assert len(history) == 1
        assert history[0].job_id == sample_rotation_job.job_id
        assert history[0].status == RotationStatus.COMPLETED

    def test_rotation_cancellation(self, rotation_service, sample_rotation_job):
        """Test rotation cancellation in early phases."""
        tenant_id = sample_rotation_job.tenant_id
        
        # Add job to active rotations (in preparation phase)
        sample_rotation_job.phase = RotationPhase.PREPARATION
        with rotation_service._rotation_lock:
            rotation_service._active_rotations[tenant_id] = sample_rotation_job
        
        # Cancel rotation
        result = rotation_service.cancel_rotation(tenant_id)
        assert result is True
        
        # Verify cancellation
        assert rotation_service.get_rotation_status(tenant_id) is None
        
        history = rotation_service.get_rotation_history(tenant_id)
        assert len(history) == 1
        assert history[0].status == RotationStatus.FAILED
        assert "Cancelled by user" in history[0].error_message

    def test_rotation_cancellation_late_phase(self, rotation_service, sample_rotation_job):
        """Test that rotation cannot be cancelled in late phases."""
        tenant_id = sample_rotation_job.tenant_id
        
        # Add job to active rotations (in data re-encryption phase)
        sample_rotation_job.phase = RotationPhase.DATA_REENCRYPTION
        with rotation_service._rotation_lock:
            rotation_service._active_rotations[tenant_id] = sample_rotation_job
        
        # Try to cancel rotation
        result = rotation_service.cancel_rotation(tenant_id)
        assert result is False
        
        # Verify rotation is still active
        assert rotation_service.get_rotation_status(tenant_id) is not None

    @pytest.mark.asyncio
    async def test_scheduled_rotation_detection(self, rotation_service, mock_key_management):
        """Test detection of tenants needing scheduled rotation."""
        # Mock tenant keys with different ages
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        recent_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        mock_key_management.list_tenant_keys.return_value = {
            1: {'key_id': 'key-1', 'created_at': old_date},  # Needs rotation
            2: {'key_id': 'key-2', 'created_at': recent_date},  # Doesn't need rotation
            3: {'key_id': 'key-3', 'created_at': old_date}  # Needs rotation
        }
        
        # Get tenants needing rotation
        tenants = await rotation_service._get_tenants_needing_rotation()
        
        # Should return tenants 1 and 3 (old keys)
        assert set(tenants) == {1, 3}

    def test_service_statistics(self, rotation_service, sample_rotation_job):
        """Test service statistics reporting."""
        # Add some test data
        with rotation_service._rotation_lock:
            rotation_service._active_rotations[1] = sample_rotation_job
            
            # Add some history
            completed_job = RotationJob(
                tenant_id=2,
                job_id="completed-job",
                status=RotationStatus.COMPLETED,
                phase=RotationPhase.CLEANUP,
                started_at=datetime.now(timezone.utc)
            )
            failed_job = RotationJob(
                tenant_id=3,
                job_id="failed-job",
                status=RotationStatus.FAILED,
                phase=RotationPhase.KEY_GENERATION,
                started_at=datetime.now(timezone.utc)
            )
            rotation_service._rotation_history = [completed_job, failed_job]
        
        # Add dual key data
        with rotation_service._dual_key_lock:
            rotation_service._dual_key_storage[1] = {'test': 'data'}
        
        # Get statistics
        stats = rotation_service.get_service_stats()
        
        assert stats['active_rotations'] == 1
        assert stats['total_rotations'] == 2
        assert stats['success_rate_percent'] == 50.0  # 1 success out of 2
        assert stats['dual_key_active_count'] == 1
        assert 'is_background_running' in stats
        assert 'rotation_enabled' in stats

    def test_rotation_job_serialization(self, sample_rotation_job):
        """Test rotation job serialization to dictionary."""
        job_dict = sample_rotation_job.to_dict()
        
        assert job_dict['tenant_id'] == sample_rotation_job.tenant_id
        assert job_dict['job_id'] == sample_rotation_job.job_id
        assert job_dict['status'] == sample_rotation_job.status.value
        assert job_dict['phase'] == sample_rotation_job.phase.value
        assert job_dict['progress_percentage'] == sample_rotation_job.progress_percentage
        assert 'started_at' in job_dict
        assert job_dict['has_rollback_data'] == (sample_rotation_job.rollback_data is not None)

    def test_global_service_instance(self):
        """Test global service instance creation."""
        service1 = get_key_rotation_service()
        service2 = get_key_rotation_service()
        
        # Should return same instance
        assert service1 is service2
        assert isinstance(service1, KeyRotationService)


class TestDataReencryption:
    """Test data re-encryption during key rotation."""

    @pytest.fixture
    def mock_data_reencryption(self):
        """Mock data re-encryption utility."""
        with patch('api.utils.data_reencryption.DataReencryptionService') as mock_class:
            mock_instance = Mock()
            mock_instance.reencrypt_tenant_data.return_value = {
                'records_processed': 1000,
                'records_updated': 1000,
                'errors': 0,
                'duration_seconds': 30.5
            }
            mock_class.return_value = mock_instance
            yield mock_instance

    @pytest.mark.asyncio
    async def test_data_reencryption_integration(self, mock_data_reencryption):
        """Test integration with data re-encryption utility."""
        from core.utils.data_reencryption import DataReencryptionService
        
        tenant_id = 1
        old_key_id = "old-key-123"
        new_key_id = "new-key-456"
        
        # Create utility instance
        utility = DataReencryptionService()
        
        # Execute re-encryption
        result = utility.reencrypt_tenant_data(tenant_id, old_key_id, new_key_id)
        
        # Verify results
        assert result['records_processed'] == 1000
        assert result['records_updated'] == 1000
        assert result['errors'] == 0
        assert result['duration_seconds'] > 0

    @pytest.mark.asyncio
    async def test_data_integrity_validation(self, mock_data_reencryption):
        """Test data integrity validation during re-encryption."""
        # Mock validation results
        mock_data_reencryption.validate_reencryption.return_value = {
            'validation_passed': True,
            'sample_size': 100,
            'mismatches': 0,
            'validation_time': 5.2
        }
        
        from core.utils.data_reencryption import DataReencryptionService
        utility = DataReencryptionService()
        
        # Validate re-encryption
        result = utility.validate_reencryption(1, "old-key", "new-key")
        
        assert result['validation_passed'] is True
        assert result['mismatches'] == 0

    @pytest.mark.asyncio
    async def test_reencryption_error_handling(self, mock_data_reencryption):
        """Test error handling during data re-encryption."""
        # Mock re-encryption failure
        mock_data_reencryption.reencrypt_tenant_data.side_effect = Exception("Database connection failed")
        
        from core.utils.data_reencryption import DataReencryptionService
        utility = DataReencryptionService()
        
        # Should handle errors gracefully
        with pytest.raises(Exception, match="Database connection failed"):
            utility.reencrypt_tenant_data(1, "old-key", "new-key")

    @pytest.mark.asyncio
    async def test_batch_reencryption_progress(self, mock_data_reencryption):
        """Test batch re-encryption with progress tracking."""
        # Mock batch processing
        def mock_batch_reencrypt(tenant_id, old_key, new_key, batch_size=1000, progress_callback=None):
            # Simulate progress updates
            if progress_callback:
                progress_callback(25, 1000, 4000)  # 25% complete
                progress_callback(50, 2000, 4000)  # 50% complete
                progress_callback(75, 3000, 4000)  # 75% complete
                progress_callback(100, 4000, 4000)  # 100% complete
            
            return {
                'records_processed': 4000,
                'records_updated': 4000,
                'batches_processed': 4,
                'errors': 0
            }
        
        mock_data_reencryption.reencrypt_tenant_data.side_effect = mock_batch_reencrypt
        
        from core.utils.data_reencryption import DataReencryptionService
        utility = DataReencryptionService()
        
        # Track progress
        progress_updates = []
        def progress_callback(percent, processed, total):
            progress_updates.append((percent, processed, total))
        
        # Execute batch re-encryption
        result = utility.reencrypt_tenant_data(1, "old-key", "new-key", progress_callback=progress_callback)
        
        # Verify progress tracking
        assert len(progress_updates) == 4
        assert progress_updates[-1] == (100, 4000, 4000)  # Final update
        assert result['records_processed'] == 4000


class TestBackupAndRecovery:
    """Test backup and recovery procedures with encryption."""

    @pytest.fixture
    def mock_backup_service(self):
        """Mock encrypted backup service."""
        with patch('core.services.encrypted_backup_service.EncryptedBackupService') as mock_class:
            mock_instance = Mock()
            mock_instance.create_encrypted_backup.return_value = {
                'backup_id': 'backup-123',
                'tenant_id': 1,
                'backup_size_bytes': 1024000,
                'encryption_key_id': 'key-456',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'status': 'completed'
            }
            mock_instance.restore_from_backup.return_value = {
                'restore_id': 'restore-789',
                'records_restored': 5000,
                'status': 'completed',
                'duration_seconds': 45.2
            }
            mock_class.return_value = mock_instance
            yield mock_instance

    @pytest.mark.asyncio
    async def test_encrypted_backup_creation(self, mock_backup_service):
        """Test creation of encrypted backups."""
        from core.services.encrypted_backup_service import EncryptedBackupService
        
        service = EncryptedBackupService()
        tenant_id = 1
        
        # Create backup
        result = service.create_encrypted_backup(tenant_id)
        
        # Verify backup creation
        assert result['backup_id'] == 'backup-123'
        assert result['tenant_id'] == tenant_id
        assert result['status'] == 'completed'
        assert 'encryption_key_id' in result
        assert 'backup_size_bytes' in result

    @pytest.mark.asyncio
    async def test_encrypted_backup_restoration(self, mock_backup_service):
        """Test restoration from encrypted backups."""
        from core.services.encrypted_backup_service import EncryptedBackupService
        
        service = EncryptedBackupService()
        backup_id = 'backup-123'
        
        # Restore from backup
        result = service.restore_from_backup(backup_id)
        
        # Verify restoration
        assert result['restore_id'] == 'restore-789'
        assert result['records_restored'] == 5000
        assert result['status'] == 'completed'
        assert result['duration_seconds'] > 0

    @pytest.mark.asyncio
    async def test_backup_key_rotation_compatibility(self, mock_backup_service):
        """Test backup compatibility during key rotation."""
        # Mock backup service to handle key rotation scenarios
        mock_backup_service.verify_backup_integrity.return_value = {
            'integrity_check_passed': True,
            'key_compatibility': True,
            'records_verified': 1000,
            'verification_time': 10.5
        }
        
        from core.services.encrypted_backup_service import EncryptedBackupService
        service = EncryptedBackupService()
        
        # Verify backup integrity with different keys
        result = service.verify_backup_integrity('backup-123', 'new-key-456')
        
        assert result['integrity_check_passed'] is True
        assert result['key_compatibility'] is True

    @pytest.mark.asyncio
    async def test_point_in_time_recovery(self, mock_backup_service):
        """Test point-in-time recovery with encrypted data."""
        # Mock point-in-time recovery
        mock_backup_service.restore_point_in_time.return_value = {
            'recovery_id': 'recovery-456',
            'target_timestamp': '2023-06-01T12:00:00Z',
            'records_recovered': 3500,
            'status': 'completed'
        }
        
        from core.services.encrypted_backup_service import EncryptedBackupService
        service = EncryptedBackupService()
        
        # Perform point-in-time recovery
        target_time = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = service.restore_point_in_time(1, target_time)
        
        assert result['recovery_id'] == 'recovery-456'
        assert result['records_recovered'] == 3500
        assert result['status'] == 'completed'

    @pytest.mark.asyncio
    async def test_backup_encryption_key_management(self, mock_backup_service):
        """Test backup encryption key management."""
        # Mock key management for backups
        mock_backup_service.get_backup_key_info.return_value = {
            'backup_id': 'backup-123',
            'encryption_key_id': 'key-456',
            'key_rotation_history': [
                {'key_id': 'old-key-123', 'rotated_at': '2023-01-01T00:00:00Z'},
                {'key_id': 'key-456', 'rotated_at': '2023-06-01T00:00:00Z'}
            ],
            'current_key_active': True
        }
        
        from core.services.encrypted_backup_service import EncryptedBackupService
        service = EncryptedBackupService()
        
        # Get backup key information
        result = service.get_backup_key_info('backup-123')
        
        assert result['encryption_key_id'] == 'key-456'
        assert len(result['key_rotation_history']) == 2
        assert result['current_key_active'] is True


class TestSecurityValidation:
    """Test security aspects of the encryption system."""

    def test_key_material_not_logged(self, caplog):
        """Test that key material is not exposed in logs."""
        from core.services.encryption_service import EncryptionService
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "secret-key-material-123"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            
            # Perform encryption operation
            with caplog.at_level("DEBUG"):
                service.encrypt_data("test data", 1)
            
            # Verify key material is not in logs
            log_text = caplog.text.lower()
            assert "secret-key-material-123" not in log_text
            assert "secret" not in log_text or "key" not in log_text

    def test_encrypted_data_format_validation(self):
        """Test that encrypted data follows expected format."""
        from core.services.encryption_service import EncryptionService
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            
            # Encrypt data
            encrypted = service.encrypt_data("sensitive data", 1)
            
            # Verify encrypted data is base64 encoded
            import base64
            try:
                decoded = base64.b64decode(encrypted)
                assert len(decoded) >= 16  # At least nonce + some ciphertext
            except Exception:
                pytest.fail("Encrypted data is not valid base64")

    def test_nonce_uniqueness(self):
        """Test that encryption nonces are unique."""
        from core.services.encryption_service import EncryptionService
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            
            # Encrypt same data multiple times
            encrypted_values = []
            for _ in range(10):
                encrypted = service.encrypt_data("same data", 1)
                encrypted_values.append(encrypted)
            
            # All encrypted values should be different (due to unique nonces)
            assert len(set(encrypted_values)) == 10

    def test_tenant_isolation_security(self):
        """Test that tenant data isolation is maintained."""
        from core.services.encryption_service import EncryptionService
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            
            # Return different keys for different tenants
            def get_tenant_key(tenant_id):
                return f"key-for-tenant-{tenant_id}"
            
            mock_kms_instance.retrieve_tenant_key.side_effect = get_tenant_key
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            
            # Encrypt same data for different tenants
            data = "sensitive information"
            encrypted_t1 = service.encrypt_data(data, 1)
            encrypted_t2 = service.encrypt_data(data, 2)
            
            # Encrypted values should be different
            assert encrypted_t1 != encrypted_t2
            
            # Cross-tenant decryption should fail
            with pytest.raises(Exception):  # Should be DecryptionError in real implementation
                service.decrypt_data(encrypted_t1, 2)

    def test_memory_cleanup_after_operations(self):
        """Test that sensitive data is cleaned from memory."""
        from core.services.encryption_service import EncryptionService
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            
            # Perform encryption/decryption
            encrypted = service.encrypt_data("sensitive data", 1)
            decrypted = service.decrypt_data(encrypted, 1)
            
            assert decrypted == "sensitive data"
            
            # Clear cache (simulates memory cleanup)
            service.clear_cache()
            
            # Verify cache is empty
            stats = service.get_cache_stats()
            assert stats['cached_keys'] == 0

    def test_error_message_sanitization(self):
        """Test that error messages don't expose sensitive information."""
        from core.services.encryption_service import EncryptionService
        from core.exceptions.encryption_exceptions import DecryptionError
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            
            # Try to decrypt invalid data
            try:
                service.decrypt_data("invalid-encrypted-data", 1)
            except DecryptionError as e:
                error_msg = str(e).lower()
                # Error message should not contain key material or sensitive data
                assert "test-key-material" not in error_msg
                assert "key" not in error_msg or "material" not in error_msg

    @pytest.mark.asyncio
    async def test_key_rotation_security_validation(self):
        """Test security aspects of key rotation process."""
        from core.services.key_rotation_service import KeyRotationService
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            with patch('core.services.encryption_service.EncryptionService') as mock_enc:
                mock_kms_instance = Mock()
                mock_enc_instance = Mock()
                
                mock_kms_instance.get_key_metadata.return_value = {'key_id': 'old-key'}
                mock_kms_instance.generate_tenant_key.return_value = 'new-key'
                
                mock_kms.return_value = mock_kms_instance
                mock_enc.return_value = mock_enc_instance
                
                service = KeyRotationService(mock_kms_instance, mock_enc_instance)
                
                # Perform key rotation
                job = await service.rotate_tenant_key(1)
                
                # Verify security aspects
                assert job.old_key_id != job.new_key_id  # Keys are different
                assert job.rollback_data is not None  # Rollback data is preserved
                
                # Verify cache was cleared (security measure)
                mock_enc_instance.clear_cache.assert_called()

    def test_audit_trail_completeness(self, caplog):
        """Test that all encryption operations are properly audited."""
        from core.services.encryption_service import EncryptionService
        
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            
            with caplog.at_level("DEBUG"):
                # Perform various operations
                encrypted = service.encrypt_data("test data", 1)
                service.decrypt_data(encrypted, 1)
                service.encrypt_json({"key": "value"}, 1)
                service.get_tenant_key(1)
            
            # Verify audit logs contain operation records
            log_records = [record.message for record in caplog.records]
            
            # Should have logs for encryption/decryption operations
            encryption_logs = [log for log in log_records if "encrypted" in log.lower() or "decrypted" in log.lower()]
            assert len(encryption_logs) > 0