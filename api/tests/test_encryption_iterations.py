
import pytest
from unittest.mock import MagicMock
from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from encryption_config import EncryptionConfig
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import os

class TestEncryptionIterations:
    @pytest.fixture
    def mock_kms(self):
        kms = MagicMock(spec=KeyManagementService)
        # Random key material for testing
        kms.retrieve_tenant_key.return_value = base64.b64encode(os.urandom(32)).decode('ascii')
        return kms

    @pytest.fixture
    def encryption_service(self, mock_kms):
        service = EncryptionService(key_management_service=mock_kms)
        # Ensure we have both iterations in config
        service.config.KEY_DERIVATION_ITERATIONS = 100000
        service.config.KEY_DERIVATION_ITERATIONS_FALLBACK = [10000]
        return service

    def test_decryption_fallback(self, encryption_service):
        tenant_id = 1
        data = "Sensitive test data"
        
        # 1. Manually encrypt with 10,000 iterations
        key_10k = encryption_service.get_tenant_key(tenant_id, iterations=10000)
        cipher_10k = AESGCM(key_10k)
        nonce = os.urandom(12)
        encrypted_10k = cipher_10k.encrypt(nonce, data.encode('utf-8'), None)
        encoded_10k = base64.b64encode(nonce + encrypted_10k).decode('ascii')
        
        # 2. Decrypt using service (defaults to 100k, should fallback to 10k)
        decrypted = encryption_service.decrypt_data(encoded_10k, tenant_id)
        assert decrypted == data
        
    def test_decryption_primary(self, encryption_service):
        tenant_id = 1
        data = "Primary iteration data"
        
        # 1. Encrypt with service (uses primary 100k)
        encoded = encryption_service.encrypt_data(data, tenant_id)
        
        # 2. Decrypt with service (uses primary 100k)
        decrypted = encryption_service.decrypt_data(encoded, tenant_id)
        assert decrypted == data

    def test_decryption_failure(self, encryption_service):
        tenant_id = 1
        # Data that isn't encrypted with ANY expected iteration
        invalid_data = base64.b64encode(os.urandom(12) + os.urandom(20)).decode('ascii')
        
        from core.exceptions.encryption_exceptions import DecryptionError
        with pytest.raises(DecryptionError) as excinfo:
            encryption_service.decrypt_data(invalid_data, tenant_id)
        assert "Authentication tag verification failed" in str(excinfo.value)
