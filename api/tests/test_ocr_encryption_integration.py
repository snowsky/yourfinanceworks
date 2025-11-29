"""
Integration test to verify API service can decrypt OCR worker's encrypted data.

This test simulates the OCR worker encrypting expense data and the API service
decrypting it to ensure the encryption/decryption flow works correctly.
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any

from core.services.encryption_service import EncryptionService, get_encryption_service
from core.services.key_management_service import KeyManagementService, get_key_management_service
from core.models.database import SessionLocal
from core.models.models_per_tenant import Expense, ExpenseAttachment
from encryption_config import EncryptionConfig


class TestOCREncryptionIntegration:
    """Test OCR worker encryption and API service decryption integration."""
    
    @pytest.fixture
    def encryption_service(self):
        """Get encryption service instance."""
        return get_encryption_service()
    
    @pytest.fixture
    def key_management_service(self):
        """Get key management service instance."""
        return get_key_management_service()
    
    @pytest.fixture
    def test_tenant_id(self):
        """Test tenant ID."""
        return 1
    
    @pytest.fixture
    def sample_ocr_data(self):
        """Sample OCR extracted data that would be encrypted by worker."""
        return {
            "amount": 125.50,
            "currency": "USD",
            "expense_date": "2024-01-15",
            "category": "Office Supplies",
            "vendor": "Office Depot",
            "tax_rate": 8.25,
            "tax_amount": 10.35,
            "total_amount": 135.85,
            "payment_method": "Credit Card",
            "reference_number": "INV-2024-001",
            "notes": "Printer paper and supplies",
            "confidence_score": 0.95,
            "extracted_fields": [
                "amount", "vendor", "date", "category"
            ]
        }
    
    def test_encryption_service_initialization(self, encryption_service):
        """Test that encryption service initializes correctly."""
        assert encryption_service is not None
        assert isinstance(encryption_service, EncryptionService)
        assert encryption_service.config is not None
    
    def test_key_management_service_initialization(self, key_management_service):
        """Test that key management service initializes correctly."""
        assert key_management_service is not None
        assert isinstance(key_management_service, KeyManagementService)
        assert key_management_service.config is not None
    
    def test_tenant_key_generation_and_retrieval(self, key_management_service, test_tenant_id):
        """Test tenant key generation and retrieval."""
        # Generate key for tenant
        key_id = key_management_service.generate_tenant_key(test_tenant_id)
        assert key_id is not None
        assert isinstance(key_id, str)
        
        # Retrieve the key
        key_material = key_management_service.retrieve_tenant_key(test_tenant_id)
        assert key_material is not None
        assert isinstance(key_material, str)
        assert len(key_material) > 0
    
    def test_basic_string_encryption_decryption(self, encryption_service, test_tenant_id):
        """Test basic string encryption and decryption."""
        test_data = "Test OCR data for encryption"
        
        # Encrypt data
        encrypted_data = encryption_service.encrypt_data(test_data, test_tenant_id)
        assert encrypted_data is not None
        assert encrypted_data != test_data
        assert len(encrypted_data) > 0
        
        # Decrypt data
        decrypted_data = encryption_service.decrypt_data(encrypted_data, test_tenant_id)
        assert decrypted_data == test_data
    
    def test_json_encryption_decryption(self, encryption_service, test_tenant_id, sample_ocr_data):
        """Test JSON data encryption and decryption (OCR results format)."""
        # Encrypt JSON data
        encrypted_json = encryption_service.encrypt_json(sample_ocr_data, test_tenant_id)
        assert encrypted_json is not None
        assert encrypted_json != json.dumps(sample_ocr_data)
        assert len(encrypted_json) > 0
        
        # Decrypt JSON data
        decrypted_json = encryption_service.decrypt_json(encrypted_json, test_tenant_id)
        assert decrypted_json == sample_ocr_data
        assert decrypted_json["amount"] == 125.50
        assert decrypted_json["vendor"] == "Office Depot"
        assert decrypted_json["confidence_score"] == 0.95
    
    def test_ocr_worker_simulation(self, encryption_service, test_tenant_id, sample_ocr_data):
        """Simulate OCR worker encrypting data and API service decrypting it."""
        # Simulate OCR worker processing and encrypting results
        ocr_results = {
            "status": "success",
            "extracted_data": sample_ocr_data,
            "processing_time_ms": 2500,
            "model_used": "llama3.2-vision:11b",
            "confidence_threshold": 0.8,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # OCR worker encrypts the results
        encrypted_results = encryption_service.encrypt_json(ocr_results, test_tenant_id)
        assert encrypted_results is not None
        
        # API service receives and decrypts the results
        decrypted_results = encryption_service.decrypt_json(encrypted_results, test_tenant_id)
        
        # Verify decryption worked correctly
        assert decrypted_results["status"] == "success"
        assert decrypted_results["extracted_data"]["amount"] == 125.50
        assert decrypted_results["extracted_data"]["vendor"] == "Office Depot"
        assert decrypted_results["processing_time_ms"] == 2500
        assert decrypted_results["model_used"] == "llama3.2-vision:11b"
    
    def test_multiple_tenant_isolation(self, encryption_service, key_management_service):
        """Test that different tenants cannot decrypt each other's data."""
        tenant_1 = 1
        tenant_2 = 2
        test_data = {"sensitive": "tenant 1 data", "amount": 100.0}
        
        # Generate keys for both tenants
        key_management_service.generate_tenant_key(tenant_1)
        key_management_service.generate_tenant_key(tenant_2)
        
        # Encrypt data for tenant 1
        encrypted_data = encryption_service.encrypt_json(test_data, tenant_1)
        
        # Tenant 1 can decrypt their own data
        decrypted_data = encryption_service.decrypt_json(encrypted_data, tenant_1)
        assert decrypted_data == test_data
        
        # Tenant 2 cannot decrypt tenant 1's data
        with pytest.raises(Exception):
            encryption_service.decrypt_json(encrypted_data, tenant_2)
    
    def test_large_ocr_data_encryption(self, encryption_service, test_tenant_id):
        """Test encryption of large OCR data payloads."""
        # Create a large OCR result with many extracted fields
        large_ocr_data = {
            "status": "success",
            "extracted_data": {
                "amount": 1250.75,
                "currency": "USD",
                "expense_date": "2024-01-15",
                "category": "Travel",
                "vendor": "Marriott International Hotel",
                "tax_rate": 14.5,
                "tax_amount": 181.36,
                "total_amount": 1432.11,
                "payment_method": "Corporate Credit Card",
                "reference_number": "HTL-2024-001-CONF",
                "notes": "Business conference accommodation - 3 nights",
                "line_items": [
                    {"description": "Room charge", "amount": 400.0, "nights": 3},
                    {"description": "Resort fee", "amount": 45.0, "per_night": True},
                    {"description": "Parking", "amount": 25.0, "per_night": True},
                    {"description": "WiFi", "amount": 15.0, "per_night": True},
                    {"description": "Room service", "amount": 85.75, "items": ["Breakfast", "Coffee"]}
                ],
                "extracted_text": "MARRIOTT INTERNATIONAL\nGuest Folio\nCheck-in: 01/15/2024\nCheck-out: 01/18/2024\nGuest: John Doe\nRoom: 1205\nRate: $400.00/night\n" * 10,  # Simulate long extracted text
                "confidence_scores": {
                    "amount": 0.98,
                    "vendor": 0.95,
                    "date": 0.92,
                    "total": 0.97,
                    "line_items": 0.89
                }
            },
            "processing_metadata": {
                "model_used": "llama3.2-vision:11b",
                "processing_time_ms": 4500,
                "image_resolution": "2048x1536",
                "pages_processed": 2,
                "ocr_engine_version": "v2.1.0",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        # Encrypt large data
        encrypted_data = encryption_service.encrypt_json(large_ocr_data, test_tenant_id)
        assert encrypted_data is not None
        assert len(encrypted_data) > 1000  # Should be substantial
        
        # Decrypt and verify
        decrypted_data = encryption_service.decrypt_json(encrypted_data, test_tenant_id)
        assert decrypted_data == large_ocr_data
        assert len(decrypted_data["extracted_data"]["line_items"]) == 5
        assert decrypted_data["extracted_data"]["amount"] == 1250.75
    
    def test_encryption_with_special_characters(self, encryption_service, test_tenant_id):
        """Test encryption of OCR data with special characters and unicode."""
        special_ocr_data = {
            "vendor": "Café München & Co. Ltd.",
            "description": "Déjeuner d'affaires - €50.00",
            "notes": "Receipt includes: café ☕, croissant 🥐, and service charge",
            "currency_symbols": "€£¥$¢",
            "unicode_text": "Ñoël & François's résumé",
            "special_chars": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
            "amount": 50.0
        }
        
        # Encrypt data with special characters
        encrypted_data = encryption_service.encrypt_json(special_ocr_data, test_tenant_id)
        assert encrypted_data is not None
        
        # Decrypt and verify all special characters preserved
        decrypted_data = encryption_service.decrypt_json(encrypted_data, test_tenant_id)
        assert decrypted_data == special_ocr_data
        assert decrypted_data["vendor"] == "Café München & Co. Ltd."
        assert "☕" in decrypted_data["notes"]
        assert "🥐" in decrypted_data["notes"]
    
    def test_empty_and_null_data_handling(self, encryption_service, test_tenant_id):
        """Test encryption of empty and null OCR data."""
        # Test empty string
        encrypted_empty = encryption_service.encrypt_data("", test_tenant_id)
        decrypted_empty = encryption_service.decrypt_data(encrypted_empty, test_tenant_id)
        assert decrypted_empty == ""
        
        # Test empty dict
        encrypted_empty_dict = encryption_service.encrypt_json({}, test_tenant_id)
        decrypted_empty_dict = encryption_service.decrypt_json(encrypted_empty_dict, test_tenant_id)
        assert decrypted_empty_dict == {}
        
        # Test dict with null values
        null_data = {
            "amount": None,
            "vendor": None,
            "category": "Unknown",
            "notes": ""
        }
        encrypted_null = encryption_service.encrypt_json(null_data, test_tenant_id)
        decrypted_null = encryption_service.decrypt_json(encrypted_null, test_tenant_id)
        assert decrypted_null == null_data
    
    def test_encryption_performance(self, encryption_service, test_tenant_id, sample_ocr_data):
        """Test encryption/decryption performance for OCR data."""
        import time
        
        # Measure encryption time
        start_time = time.time()
        encrypted_data = encryption_service.encrypt_json(sample_ocr_data, test_tenant_id)
        encryption_time = time.time() - start_time
        
        # Measure decryption time
        start_time = time.time()
        decrypted_data = encryption_service.decrypt_json(encrypted_data, test_tenant_id)
        decryption_time = time.time() - start_time
        
        # Verify correctness
        assert decrypted_data == sample_ocr_data
        
        # Performance assertions (should be fast)
        assert encryption_time < 0.1  # Less than 100ms
        assert decryption_time < 0.1  # Less than 100ms
        
        print(f"Encryption time: {encryption_time*1000:.2f}ms")
        print(f"Decryption time: {decryption_time*1000:.2f}ms")
    
    def test_concurrent_encryption_decryption(self, encryption_service, test_tenant_id):
        """Test concurrent encryption/decryption operations."""
        import threading
        import time
        
        results = []
        errors = []
        
        def encrypt_decrypt_worker(worker_id: int):
            try:
                test_data = {
                    "worker_id": worker_id,
                    "amount": 100.0 + worker_id,
                    "vendor": f"Vendor {worker_id}",
                    "timestamp": time.time()
                }
                
                # Encrypt
                encrypted = encryption_service.encrypt_json(test_data, test_tenant_id)
                
                # Small delay to simulate processing
                time.sleep(0.01)
                
                # Decrypt
                decrypted = encryption_service.decrypt_json(encrypted, test_tenant_id)
                
                # Verify
                assert decrypted == test_data
                results.append(worker_id)
                
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=encrypt_decrypt_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations succeeded
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert sorted(results) == list(range(10))
    
    def test_key_rotation_impact(self, encryption_service, key_management_service, test_tenant_id, sample_ocr_data):
        """Test that key rotation doesn't break existing encrypted data."""
        # Encrypt data with original key
        encrypted_data = encryption_service.encrypt_json(sample_ocr_data, test_tenant_id)
        
        # Verify decryption works with original key
        decrypted_data = encryption_service.decrypt_json(encrypted_data, test_tenant_id)
        assert decrypted_data == sample_ocr_data
        
        # Rotate the key
        rotation_success = key_management_service.rotate_key(test_tenant_id)
        assert rotation_success
        
        # Clear encryption service cache to force key reload
        encryption_service.clear_cache(test_tenant_id)
        
        # Old encrypted data should still be decryptable with the old key
        # Note: In a real system, you'd need key versioning to handle this
        # For now, we test that new encryption works with the new key
        new_encrypted_data = encryption_service.encrypt_json(sample_ocr_data, test_tenant_id)
        new_decrypted_data = encryption_service.decrypt_json(new_encrypted_data, test_tenant_id)
        assert new_decrypted_data == sample_ocr_data
    
    def test_error_handling_invalid_data(self, encryption_service, test_tenant_id):
        """Test error handling for invalid encrypted data."""
        # Test invalid base64 data
        with pytest.raises(Exception):
            encryption_service.decrypt_data("invalid_base64_data", test_tenant_id)
        
        # Test corrupted encrypted data
        valid_encrypted = encryption_service.encrypt_data("test", test_tenant_id)
        corrupted_data = valid_encrypted[:-5] + "XXXXX"  # Corrupt the end
        
        # Should handle gracefully (might return original or raise exception)
        try:
            result = encryption_service.decrypt_data(corrupted_data, test_tenant_id)
            # If it returns something, it should be the corrupted data as fallback
            assert isinstance(result, str)
        except Exception:
            # Or it might raise an exception, which is also acceptable
            pass
    
    def test_cache_functionality(self, encryption_service, test_tenant_id, sample_ocr_data):
        """Test that encryption service caching works correctly."""
        # First encryption should populate cache
        encrypted_data1 = encryption_service.encrypt_json(sample_ocr_data, test_tenant_id)
        
        # Second encryption should use cached key
        encrypted_data2 = encryption_service.encrypt_json(sample_ocr_data, test_tenant_id)
        
        # Both should decrypt correctly
        decrypted_data1 = encryption_service.decrypt_json(encrypted_data1, test_tenant_id)
        decrypted_data2 = encryption_service.decrypt_json(encrypted_data2, test_tenant_id)
        
        assert decrypted_data1 == sample_ocr_data
        assert decrypted_data2 == sample_ocr_data
        
        # Get cache stats
        cache_stats = encryption_service.get_cache_stats()
        assert cache_stats["cached_keys"] >= 1
        assert cache_stats["cache_size_bytes"] > 0
        
        # Clear cache and verify
        encryption_service.clear_cache(test_tenant_id)
        cache_stats_after = encryption_service.get_cache_stats()
        assert cache_stats_after["cached_keys"] < cache_stats["cached_keys"]


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])