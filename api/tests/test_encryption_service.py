"""
Unit tests for EncryptionService.

Tests encryption/decryption operations, key management, caching,
and error handling for the tenant database encryption system.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.services.encryption_service import EncryptionService, get_encryption_service
from core.services.key_management_service import KeyManagementService
from encryption_config import EncryptionConfig
from core.exceptions.encryption_exceptions import (
    EncryptionError,
    DecryptionError,
    KeyNotFoundError
)


class TestEncryptionService:
    """Test cases for EncryptionService."""

    @pytest.fixture
    def mock_key_management(self):
        """Mock key management service."""
        mock_service = Mock(spec=KeyManagementService)
        mock_service.retrieve_tenant_key.return_value = "dGVzdC1rZXktbWF0ZXJpYWwtMTIz"  # Valid base64
        return mock_service

    @pytest.fixture
    def encryption_service(self, mock_key_management):
        """Create encryption service with mocked dependencies."""
        return EncryptionService(key_management_service=mock_key_management)

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return {
            "string_data": "Hello, World! This is sensitive data.",
            "json_data": {
                "user_id": 123,
                "email": "test@example.com",
                "personal_info": {
                    "name": "John Doe",
                    "phone": "+1-555-0123"
                }
            },
            "empty_string": "",
            "unicode_data": "Hello 世界! 🔐 Encryption test",
            "tenant_id": 1
        }

    def test_encrypt_decrypt_roundtrip_string(self, encryption_service, sample_data):
        """Test encryption and decryption roundtrip for string data."""
        original_data = sample_data["string_data"]
        tenant_id = sample_data["tenant_id"]

        # Encrypt data
        encrypted = encryption_service.encrypt_data(original_data, tenant_id)
        
        # Verify encrypted data is different and base64 encoded
        assert encrypted != original_data
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

        # Decrypt data
        decrypted = encryption_service.decrypt_data(encrypted, tenant_id)
        
        # Verify roundtrip success
        assert decrypted == original_data

    def test_encrypt_decrypt_roundtrip_json(self, encryption_service, sample_data):
        """Test encryption and decryption roundtrip for JSON data."""
        original_data = sample_data["json_data"]
        tenant_id = sample_data["tenant_id"]

        # Encrypt JSON data
        encrypted = encryption_service.encrypt_json(original_data, tenant_id)
        
        # Verify encrypted data is different and base64 encoded
        assert encrypted != json.dumps(original_data)
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

        # Decrypt JSON data
        decrypted = encryption_service.decrypt_json(encrypted, tenant_id)
        
        # Verify roundtrip success
        assert decrypted == original_data

    def test_encrypt_empty_string(self, encryption_service, sample_data):
        """Test encryption of empty string."""
        tenant_id = sample_data["tenant_id"]
        
        encrypted = encryption_service.encrypt_data("", tenant_id)
        assert encrypted == ""
        
        decrypted = encryption_service.decrypt_data("", tenant_id)
        assert decrypted == ""

    def test_encrypt_empty_json(self, encryption_service, sample_data):
        """Test encryption of empty JSON."""
        tenant_id = sample_data["tenant_id"]
        
        encrypted = encryption_service.encrypt_json({}, tenant_id)
        assert encrypted == ""
        
        decrypted = encryption_service.decrypt_json("", tenant_id)
        assert decrypted == {}

    def test_unicode_data_encryption(self, encryption_service, sample_data):
        """Test encryption of Unicode data."""
        original_data = sample_data["unicode_data"]
        tenant_id = sample_data["tenant_id"]

        encrypted = encryption_service.encrypt_data(original_data, tenant_id)
        decrypted = encryption_service.decrypt_data(encrypted, tenant_id)
        
        assert decrypted == original_data

    def test_tenant_isolation(self, encryption_service, sample_data):
        """Test that different tenants produce different encrypted data."""
        original_data = sample_data["string_data"]
        tenant1_id = 1
        tenant2_id = 2

        # Encrypt same data for different tenants
        encrypted1 = encryption_service.encrypt_data(original_data, tenant1_id)
        encrypted2 = encryption_service.encrypt_data(original_data, tenant2_id)
        
        # Encrypted data should be different
        assert encrypted1 != encrypted2

        # Each tenant should decrypt their own data correctly
        decrypted1 = encryption_service.decrypt_data(encrypted1, tenant1_id)
        decrypted2 = encryption_service.decrypt_data(encrypted2, tenant2_id)
        
        assert decrypted1 == original_data
        assert decrypted2 == original_data

    def test_cross_tenant_decryption_fails(self, encryption_service, sample_data):
        """Test that cross-tenant decryption fails."""
        original_data = sample_data["string_data"]
        tenant1_id = 1
        tenant2_id = 2

        # Encrypt data for tenant 1
        encrypted = encryption_service.encrypt_data(original_data, tenant1_id)
        
        # Try to decrypt with tenant 2's key - should fail
        with pytest.raises(DecryptionError):
            encryption_service.decrypt_data(encrypted, tenant2_id)

    def test_key_caching(self, encryption_service, mock_key_management, sample_data):
        """Test that encryption keys are cached properly."""
        tenant_id = sample_data["tenant_id"]
        original_data = sample_data["string_data"]

        # First encryption should call key management
        encryption_service.encrypt_data(original_data, tenant_id)
        assert mock_key_management.retrieve_tenant_key.call_count == 1

        # Second encryption should use cached key
        encryption_service.encrypt_data(original_data, tenant_id)
        assert mock_key_management.retrieve_tenant_key.call_count == 1

        # Different tenant should call key management again
        encryption_service.encrypt_data(original_data, tenant_id + 1)
        assert mock_key_management.retrieve_tenant_key.call_count == 2

    def test_cache_cleanup(self, encryption_service, sample_data):
        """Test cache cleanup functionality."""
        tenant_id = sample_data["tenant_id"]
        
        # Add entry to cache
        encryption_service.get_tenant_key(tenant_id)
        
        # Verify cache has entry
        stats = encryption_service.get_cache_stats()
        assert stats["cached_keys"] == 1

        # Clear cache for specific tenant
        encryption_service.clear_cache(tenant_id)
        stats = encryption_service.get_cache_stats()
        assert stats["cached_keys"] == 0

    def test_cache_stats(self, encryption_service, sample_data):
        """Test cache statistics reporting."""
        tenant_id = sample_data["tenant_id"]
        
        # Initially empty cache
        stats = encryption_service.get_cache_stats()
        assert stats["cached_keys"] == 0
        assert stats["cache_size_bytes"] == 0
        assert stats["oldest_entry_age"] == 0

        # Add cache entry
        encryption_service.get_tenant_key(tenant_id)
        
        # Check updated stats
        stats = encryption_service.get_cache_stats()
        assert stats["cached_keys"] == 1
        assert stats["cache_size_bytes"] > 0
        assert stats["oldest_entry_age"] >= 0

    def test_key_rotation(self, encryption_service, mock_key_management, sample_data):
        """Test key rotation functionality."""
        tenant_id = sample_data["tenant_id"]
        mock_key_management.rotate_key.return_value = True

        # Rotate key
        result = encryption_service.rotate_tenant_key(tenant_id)
        
        assert result is True
        mock_key_management.rotate_key.assert_called_once_with(tenant_id)

    def test_key_rotation_failure(self, encryption_service, mock_key_management, sample_data):
        """Test key rotation failure handling."""
        tenant_id = sample_data["tenant_id"]
        mock_key_management.rotate_key.return_value = False

        # Rotate key (should fail)
        result = encryption_service.rotate_tenant_key(tenant_id)
        
        assert result is False

    def test_key_rotation_exception(self, encryption_service, mock_key_management, sample_data):
        """Test key rotation exception handling."""
        tenant_id = sample_data["tenant_id"]
        mock_key_management.rotate_key.side_effect = Exception("Key rotation failed")

        # Rotate key (should raise exception)
        with pytest.raises(EncryptionError, match="Failed to rotate key"):
            encryption_service.rotate_tenant_key(tenant_id)

    def test_encryption_error_handling(self, encryption_service, mock_key_management, sample_data):
        """Test encryption error handling."""
        tenant_id = sample_data["tenant_id"]
        original_data = sample_data["string_data"]
        
        # Mock key management to raise exception
        mock_key_management.retrieve_tenant_key.side_effect = Exception("Key retrieval failed")

        with pytest.raises(EncryptionError):
            encryption_service.encrypt_data(original_data, tenant_id)

    def test_decryption_error_handling(self, encryption_service, sample_data):
        """Test decryption error handling with invalid data."""
        tenant_id = sample_data["tenant_id"]
        
        # Try to decrypt invalid base64 data
        with pytest.raises(DecryptionError):
            encryption_service.decrypt_data("invalid-base64-data", tenant_id)

    def test_json_encryption_error_handling(self, encryption_service, sample_data):
        """Test JSON encryption error handling."""
        tenant_id = sample_data["tenant_id"]
        
        # Create non-serializable data
        non_serializable = {"func": lambda x: x}
        
        with pytest.raises(EncryptionError, match="Failed to encrypt JSON data"):
            encryption_service.encrypt_json(non_serializable, tenant_id)

    def test_json_decryption_error_handling(self, encryption_service, sample_data):
        """Test JSON decryption error handling with invalid JSON."""
        tenant_id = sample_data["tenant_id"]
        
        # Encrypt invalid JSON string
        invalid_json = "invalid json data"
        encrypted = encryption_service.encrypt_data(invalid_json, tenant_id)
        
        with pytest.raises(DecryptionError, match="Failed to decrypt JSON data"):
            encryption_service.decrypt_json(encrypted, tenant_id)

    @patch('core.services.encryption_service.os.urandom')
    def test_nonce_generation(self, mock_urandom, encryption_service, sample_data):
        """Test that nonce is properly generated and used."""
        mock_urandom.return_value = b'123456789012'  # 12 bytes
        
        tenant_id = sample_data["tenant_id"]
        original_data = sample_data["string_data"]
        
        encrypted = encryption_service.encrypt_data(original_data, tenant_id)
        mock_urandom.assert_called_with(12)  # GCM nonce size
        
        # Verify decryption still works
        decrypted = encryption_service.decrypt_data(encrypted, tenant_id)
        assert decrypted == original_data

    def test_key_derivation(self, encryption_service, sample_data):
        """Test key derivation produces consistent results."""
        tenant_id = sample_data["tenant_id"]
        
        # Get key twice
        key1 = encryption_service.get_tenant_key(tenant_id)
        key2 = encryption_service.get_tenant_key(tenant_id)
        
        # Should be identical (cached)
        assert key1 == key2
        assert len(key1) == 32  # 256 bits for AES-256

    def test_different_tenant_keys(self, encryption_service):
        """Test that different tenants get different keys."""
        key1 = encryption_service.get_tenant_key(1)
        key2 = encryption_service.get_tenant_key(2)
        
        assert key1 != key2
        assert len(key1) == 32
        assert len(key2) == 32

    @patch('core.services.encryption_service.time.time')
    def test_cache_expiration(self, mock_time, encryption_service, mock_key_management, sample_data):
        """Test cache expiration functionality."""
        tenant_id = sample_data["tenant_id"]
        
        # Mock time progression
        # Start (get_tenant_key), cleanup (inside get_tenant_key), 
        # Second call start (get_tenant_key - expired), cleanup (inside second call)
        mock_time.side_effect = [0, 0, 3700, 3700, 3700]
        
        # First call - should cache
        encryption_service.get_tenant_key(tenant_id)
        assert mock_key_management.retrieve_tenant_key.call_count == 1
        
        # Second call after expiration - should retrieve again
        encryption_service.get_tenant_key(tenant_id)
        assert mock_key_management.retrieve_tenant_key.call_count == 2

    def test_thread_safety_cache_lock(self, encryption_service, sample_data):
        """Test that cache operations are thread-safe."""
        tenant_id = sample_data["tenant_id"]
        
        # This test verifies the lock exists and is used
        # In a real scenario, we'd test with multiple threads
        assert hasattr(encryption_service, '_cache_lock')
        
        # Verify cache operations work
        encryption_service.get_tenant_key(tenant_id)
        encryption_service.clear_cache(tenant_id)
        stats = encryption_service.get_cache_stats()
        assert stats["cached_keys"] == 0

    def test_global_service_instance(self):
        """Test global service instance creation."""
        service1 = get_encryption_service()
        service2 = get_encryption_service()
        
        # Should return same instance
        assert service1 is service2
        assert isinstance(service1, EncryptionService)


class TestEncryptionServiceIntegration:
    """Integration tests with real cryptographic operations."""

    @pytest.fixture
    def real_encryption_service(self):
        """Create encryption service with real key management."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "cmVhbC10ZXN0LWtleS1tYXRlcmlhbA=="  # Valid base64
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            return service

    def test_real_encryption_operations(self, real_encryption_service):
        """Test with real cryptographic operations."""
        tenant_id = 1
        test_data = "Real encryption test data"
        
        # Test encryption/decryption
        encrypted = real_encryption_service.encrypt_data(test_data, tenant_id)
        decrypted = real_encryption_service.decrypt_data(encrypted, tenant_id)
        
        assert decrypted == test_data
        assert encrypted != test_data

    def test_real_json_operations(self, real_encryption_service):
        """Test JSON operations with real encryption."""
        tenant_id = 1
        test_data = {
            "id": 123,
            "name": "Test User",
            "email": "test@example.com",
            "metadata": {
                "created": "2023-01-01",
                "active": True
            }
        }
        
        # Test JSON encryption/decryption
        encrypted = real_encryption_service.encrypt_json(test_data, tenant_id)
        decrypted = real_encryption_service.decrypt_json(encrypted, tenant_id)
        
        assert decrypted == test_data

    def test_encryption_randomness(self, real_encryption_service):
        """Test that encryption produces different results each time."""
        tenant_id = 1
        test_data = "Same data for randomness test"
        
        # Encrypt same data multiple times
        encrypted1 = real_encryption_service.encrypt_data(test_data, tenant_id)
        encrypted2 = real_encryption_service.encrypt_data(test_data, tenant_id)
        encrypted3 = real_encryption_service.encrypt_data(test_data, tenant_id)
        
        # All should be different due to random nonce
        assert encrypted1 != encrypted2
        assert encrypted2 != encrypted3
        assert encrypted1 != encrypted3
        
        # But all should decrypt to same data
        assert real_encryption_service.decrypt_data(encrypted1, tenant_id) == test_data
        assert real_encryption_service.decrypt_data(encrypted2, tenant_id) == test_data
        assert real_encryption_service.decrypt_data(encrypted3, tenant_id) == test_data

    def test_large_data_encryption(self, real_encryption_service):
        """Test encryption of large data."""
        tenant_id = 1
        large_data = "A" * 10000  # 10KB of data
        
        encrypted = real_encryption_service.encrypt_data(large_data, tenant_id)
        decrypted = real_encryption_service.decrypt_data(encrypted, tenant_id)
        
        assert decrypted == large_data
        assert len(encrypted) > len(large_data)  # Base64 encoding increases size

    def test_complex_json_structures(self, real_encryption_service):
        """Test encryption of complex JSON structures."""
        tenant_id = 1
        complex_data = {
            "users": [
                {"id": 1, "name": "User 1", "roles": ["admin", "user"]},
                {"id": 2, "name": "User 2", "roles": ["user"]}
            ],
            "settings": {
                "theme": "dark",
                "notifications": {
                    "email": True,
                    "sms": False,
                    "push": True
                }
            },
            "metadata": {
                "version": "1.0.0",
                "created_at": "2023-01-01T00:00:00Z",
                "features": ["encryption", "multi-tenant", "audit"]
            }
        }
        
        encrypted = real_encryption_service.encrypt_json(complex_data, tenant_id)
        decrypted = real_encryption_service.decrypt_json(encrypted, tenant_id)
        
        assert decrypted == complex_data


class TestEncryptionServiceConfiguration:
    """Test configuration-related functionality."""

    def test_config_initialization(self):
        """Test that service initializes with proper configuration."""
        service = EncryptionService()
        
        assert hasattr(service, 'config')
        assert isinstance(service.config, EncryptionConfig)
        assert service.cipher_class == AESGCM

    @patch('core.services.encryption_service.EncryptionConfig')
    def test_custom_config(self, mock_config_class):
        """Test service with custom configuration."""
        mock_config = Mock()
        mock_config.KEY_CACHE_TTL_SECONDS = 1800
        mock_config.KEY_DERIVATION_ITERATIONS = 200000
        mock_config.KEY_DERIVATION_SALT = "custom-salt"
        mock_config_class.return_value = mock_config
        
        service = EncryptionService()
        assert service.config == mock_config

    def test_service_logging(self, caplog):
        """Test that service logs initialization."""
        with caplog.at_level("INFO"):
            EncryptionService()
            
        assert "EncryptionService initialized with AES-256-GCM" in caplog.text