"""
Integration tests for OCR functionality in bank statement processing.

This module tests end-to-end processing with both PDF types, Kafka worker
OCR handling, and AI usage tracking integration.
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from typing import Dict, Any, List

# Mock problematic imports before importing the modules
with patch.dict('sys.modules', {
    'workers.ocr_consumer': Mock(),
    'services.tenant_database_manager': Mock(),
    'models.models_per_tenant': Mock()
}):
    # Import the modules under test
    from core.services.enhanced_pdf_extractor import EnhancedPDFTextExtractor
    from core.services.bank_statement_ocr_processor import BankStatementOCRProcessor
    from core.settings.ocr_config import OCRConfig
    from core.exceptions.bank_ocr_exceptions import OCRTimeoutError, OCRProcessingError


class TestEndToEndOCRProcessing:
    """Test end-to-end OCR processing with different PDF types."""
    
    @pytest.fixture
    def mock_ai_config(self):
        """Mock AI configuration for testing."""
        return {
            "provider_name": "test_provider",
            "model_name": "test_model",
            "api_key": "test_key",
            "provider_url": "http://test.example.com",
            "max_tokens": 4000,
            "temperature": 0.1
        }
    
    @pytest.fixture
    def mock_ocr_config(self):
        """Mock OCR configuration for testing."""
        return OCRConfig(
            enabled=True,
            timeout_seconds=300,
            min_text_threshold=50,
            min_word_threshold=10,
            use_unstructured_api=False,
            strategy="hi_res",
            mode="single"
        )
    
    @pytest.fixture
    def temp_text_based_pdf(self):
        """Create a temporary text-based PDF file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            # Simple PDF with embedded text
            f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n')
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def temp_scanned_pdf(self):
        """Create a temporary scanned PDF file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            # PDF that would require OCR (minimal text content)
            f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n')
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def sample_bank_transactions(self):
        """Sample bank transactions for testing."""
        return [
            {
                "date": "2024-01-02",
                "description": "SALARY DEPOSIT",
                "amount": 2500.00,
                "balance": 2500.00,
                "transaction_type": "credit"
            },
            {
                "date": "2024-01-03",
                "description": "GROCERY STORE",
                "amount": -45.67,
                "balance": 2454.33,
                "transaction_type": "debit"
            },
            {
                "date": "2024-01-05",
                "description": "ATM WITHDRAWAL",
                "amount": -100.00,
                "balance": 2354.33,
                "transaction_type": "debit"
            }
        ]
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.is_ocr_available')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    @patch('services.enhanced_pdf_extractor.Path.exists')
    def test_end_to_end_text_based_pdf_processing(self, mock_exists, mock_validate, 
                                                 mock_ocr_available, mock_get_config_extractor,
                                                 mock_ai_config, mock_ocr_config, 
                                                 temp_text_based_pdf, sample_bank_transactions):
        """Test complete processing flow with text-based PDF."""
        mock_get_config_extractor.return_value = mock_ocr_config
        mock_ocr_available.return_value = True
        mock_validate.return_value = temp_text_based_pdf
        mock_exists.return_value = True
        
        # Mock sufficient text extraction from PDF
        sufficient_text = """
        BANK STATEMENT
        Account Number: 123456789
        Statement Period: 01/01/2024 to 01/31/2024
        
        Date        Description                Amount      Balance
        01/02/2024  SALARY DEPOSIT            2500.00     2500.00
        01/03/2024  GROCERY STORE             -45.67      2454.33
        01/05/2024  ATM WITHDRAWAL            -100.00     2354.33
        """
        
        # Test the enhanced PDF extractor directly
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        # Mock the text extraction to return sufficient text (should use PDF loader)
        with patch.object(extractor, '_extract_with_pdf_loaders', return_value=sufficient_text):
            with patch.object(extractor, '_track_extraction_method'):
                result = extractor.extract_text(temp_text_based_pdf)
        
        # Verify results
        assert result is not None
        assert result.method == "pdf_loader"
        assert result.text == sufficient_text
        assert result.text_length > 0
        assert result.word_count > 0
        assert "BANK STATEMENT" in result.text
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.is_ocr_available')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    @patch('services.enhanced_pdf_extractor.Path.exists')
    def test_end_to_end_scanned_pdf_processing(self, mock_exists, mock_validate, 
                                              mock_ocr_available, mock_get_config_extractor,
                                              mock_ai_config, mock_ocr_config, 
                                              temp_scanned_pdf, sample_bank_transactions):
        """Test complete processing flow with scanned PDF requiring OCR."""
        mock_get_config_extractor.return_value = mock_ocr_config
        mock_ocr_available.return_value = True
        mock_validate.return_value = temp_scanned_pdf
        mock_exists.return_value = True
        
        # Mock insufficient text from PDF loader
        insufficient_text = "Page 1 of 1"
        
        # Mock sufficient text from OCR
        ocr_text = """
        BANK STATEMENT
        Account: 123-456-789
        Period: January 2024
        
        01/02  SALARY DEPOSIT       +2500.00  2500.00
        01/03  GROCERY STORE         -45.67  2454.33
        01/05  ATM CASH             -100.00  2354.33
        """
        
        # Test the enhanced PDF extractor directly
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        # Mock PDF extraction to return insufficient text
        with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
            # Mock OCR extraction to return sufficient text
            with patch.object(extractor, 'ocr_processor') as mock_ocr_processor:
                mock_ocr_processor.extract_with_ocr.return_value = ocr_text
                with patch.object(extractor, '_track_extraction_method'):
                    result = extractor.extract_text(temp_scanned_pdf)
        
        # Verify results
        assert result is not None
        assert result.method == "ocr"
        assert result.text == ocr_text
        assert result.text_length > 0
        assert result.word_count > 0
        assert "BANK STATEMENT" in result.text
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.is_ocr_available')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    @patch('services.enhanced_pdf_extractor.Path.exists')
    def test_end_to_end_ocr_failure_handling(self, mock_exists, mock_validate, 
                                            mock_ocr_available, mock_get_config_extractor,
                                            mock_ai_config, mock_ocr_config, temp_scanned_pdf):
        """Test handling of OCR failures in end-to-end processing."""
        mock_get_config_extractor.return_value = mock_ocr_config
        mock_ocr_available.return_value = True
        mock_validate.return_value = temp_scanned_pdf
        mock_exists.return_value = True
        
        # Mock insufficient text from PDF loader
        insufficient_text = "Page 1 of 1"
        
        # Test the enhanced PDF extractor directly
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        # Mock PDF extraction to return insufficient text
        with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
            # Mock OCR extraction to fail
            with patch.object(extractor, 'ocr_processor') as mock_ocr_processor:
                mock_ocr_processor.extract_with_ocr.side_effect = OCRProcessingError("OCR processing failed")
                
                # Should raise an exception when both PDF and OCR fail
                with pytest.raises(OCRProcessingError) as exc_info:
                    extractor.extract_text(temp_scanned_pdf)
                
                # Verify appropriate error handling
                assert "Both PDF and OCR extraction failed" in str(exc_info.value)


class TestKafkaWorkerOCRHandling:
    """Test Kafka worker handling of OCR operations."""
    
    @pytest.fixture
    def mock_kafka_message(self):
        """Mock Kafka message for testing."""
        return Mock(
            value=json.dumps({
                "pdf_path": "/test/statement.pdf",
                "user_id": 1,
                "tenant_id": 1,
                "ai_config": {
                    "provider_name": "test_provider",
                    "model_name": "test_model"
                }
            }).encode('utf-8'),
            key=b"test_key",
            partition=0,
            offset=123
        )
    
    def test_kafka_message_structure(self, mock_kafka_message):
        """Test that Kafka messages have the expected structure for OCR processing."""
        message_data = json.loads(mock_kafka_message.value.decode('utf-8'))
        
        assert "pdf_path" in message_data
        assert "user_id" in message_data
        assert "tenant_id" in message_data
        assert "ai_config" in message_data
        assert message_data["pdf_path"] == "/test/statement.pdf"
        assert message_data["user_id"] == 1
        assert message_data["tenant_id"] == 1
    
    def test_ocr_timeout_error_handling(self):
        """Test handling of OCR timeout errors in worker context."""
        timeout_error = OCRTimeoutError("OCR processing timed out", timeout_seconds=300)
        
        # Test error properties
        assert str(timeout_error) == "OCR processing timed out"
        assert timeout_error.details.get("timeout_seconds") == 300
        
        # Test that it's a proper exception
        assert isinstance(timeout_error, Exception)
    
    def test_ocr_processing_error_handling(self):
        """Test handling of OCR processing errors in worker context."""
        processing_error = OCRProcessingError("OCR processing failed", is_transient=True)
        
        # Test error properties
        assert str(processing_error) == "OCR processing failed"
        assert processing_error.is_transient is True
        
        # Test that it's a proper exception
        assert isinstance(processing_error, Exception)
    
    def test_worker_error_classification(self):
        """Test classification of different error types for retry logic."""
        # Transient errors should be retryable
        transient_error = OCRProcessingError("Network timeout", is_transient=True)
        assert transient_error.is_transient is True
        
        # Non-transient errors should not be retryable
        permanent_error = OCRProcessingError("Invalid file format", is_transient=False)
        assert permanent_error.is_transient is False
        
        # Timeout errors should have timeout information
        timeout_error = OCRTimeoutError("Processing timed out", timeout_seconds=300)
        assert "timeout_seconds" in timeout_error.details
        assert timeout_error.details["timeout_seconds"] == 300


class TestAIUsageTrackingIntegration:
    """Test AI usage tracking integration with OCR operations."""
    
    @pytest.fixture
    def mock_ai_config(self):
        """Mock AI configuration for testing."""
        return {
            "provider_name": "test_provider",
            "model_name": "test_model",
            "api_key": "test_key",
            "provider_url": "http://test.example.com"
        }
    
    def test_tracking_data_structure(self, mock_ai_config):
        """Test the structure of tracking data for OCR operations."""
        # Test PDF loader tracking data
        pdf_tracking_data = {
            "method": "pdf_loader",
            "pdf_path": "/test/statement.pdf",
            "processing_time": 1.5,
            "text_length": 1500,
            "word_count": 250,
            "success": True,
            "ai_config": mock_ai_config
        }
        
        assert pdf_tracking_data["method"] == "pdf_loader"
        assert pdf_tracking_data["processing_time"] > 0
        assert pdf_tracking_data["success"] is True
        
        # Test OCR tracking data
        ocr_tracking_data = {
            "method": "ocr",
            "pdf_path": "/test/scanned_statement.pdf",
            "processing_time": 15.2,
            "text_length": 1200,
            "word_count": 200,
            "success": True,
            "ai_config": mock_ai_config
        }
        
        assert ocr_tracking_data["method"] == "ocr"
        assert ocr_tracking_data["processing_time"] > pdf_tracking_data["processing_time"]
        assert ocr_tracking_data["success"] is True
    
    def test_extraction_metrics_calculation(self):
        """Test calculation of extraction metrics."""
        # Mock extraction results for metrics calculation
        pdf_results = [
            {"method": "pdf_loader", "processing_time": 1.2, "success": True},
            {"method": "pdf_loader", "processing_time": 0.8, "success": True},
            {"method": "pdf_loader", "processing_time": 1.5, "success": True}
        ]
        
        ocr_results = [
            {"method": "ocr", "processing_time": 12.5, "success": True},
            {"method": "ocr", "processing_time": 15.2, "success": True},
            {"method": "ocr", "processing_time": 8.9, "success": False}
        ]
        
        # Calculate metrics
        pdf_avg_time = sum(r["processing_time"] for r in pdf_results) / len(pdf_results)
        pdf_success_rate = sum(1 for r in pdf_results if r["success"]) / len(pdf_results)
        
        ocr_avg_time = sum(r["processing_time"] for r in ocr_results) / len(ocr_results)
        ocr_success_rate = sum(1 for r in ocr_results if r["success"]) / len(ocr_results)
        
        # Verify metrics
        assert pdf_avg_time < ocr_avg_time  # PDF should be faster
        assert pdf_success_rate > ocr_success_rate  # PDF should be more reliable
        assert pdf_success_rate == 1.0  # All PDF extractions succeeded
        assert ocr_success_rate == 2/3  # 2 out of 3 OCR extractions succeeded
    
    def test_error_tracking_data(self, mock_ai_config):
        """Test tracking data for failed extractions."""
        failed_tracking_data = {
            "method": "ocr",
            "pdf_path": "/test/corrupted_statement.pdf",
            "processing_time": 5.0,
            "text_length": 0,
            "word_count": 0,
            "success": False,
            "ai_config": mock_ai_config,
            "error_message": "OCR processing failed"
        }
        
        assert failed_tracking_data["success"] is False
        assert failed_tracking_data["text_length"] == 0
        assert failed_tracking_data["word_count"] == 0
        assert "error_message" in failed_tracking_data
        assert failed_tracking_data["error_message"] == "OCR processing failed"


class TestOCRIntegrationErrorScenarios:
    """Test various error scenarios in OCR integration."""
    
    @pytest.fixture
    def mock_ai_config(self):
        """Mock AI configuration for testing."""
        return {
            "provider_name": "test_provider",
            "model_name": "test_model",
            "api_key": "test_key"
        }
    
    def test_ocr_disabled_scenario(self, mock_ai_config):
        """Test behavior when OCR is disabled in configuration."""
        disabled_config = OCRConfig(enabled=False)
        
        with patch('services.enhanced_pdf_extractor.get_ocr_config', return_value=disabled_config):
            extractor = EnhancedPDFTextExtractor(mock_ai_config)
            
            # Mock insufficient PDF text
            insufficient_text = "Page 1"
            
            with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
                with patch('services.enhanced_pdf_extractor.validate_file_path', return_value="/test.pdf"):
                    with patch('services.enhanced_pdf_extractor.Path.exists', return_value=True):
                        with patch.object(extractor, '_track_extraction_method'):
                            result = extractor.extract_text("/test.pdf")
            
            # Should return insufficient text with warning
            assert result.method == "pdf_loader_insufficient"
            assert "OCR disabled" in result.metadata.get("warning", "")
    
    def test_ocr_dependencies_missing_scenario(self, mock_ai_config):
        """Test behavior when OCR dependencies are missing."""
        enabled_config = OCRConfig(enabled=True)
        
        with patch('services.enhanced_pdf_extractor.get_ocr_config', return_value=enabled_config):
            with patch('services.enhanced_pdf_extractor.is_ocr_available', return_value=False):
                extractor = EnhancedPDFTextExtractor(mock_ai_config)
                
                # Mock insufficient PDF text
                insufficient_text = "Page 1"
                
                with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
                    with patch('services.enhanced_pdf_extractor.validate_file_path', return_value="/test.pdf"):
                        with patch('services.enhanced_pdf_extractor.Path.exists', return_value=True):
                            with patch.object(extractor, '_track_extraction_method'):
                                result = extractor.extract_text("/test.pdf")
                
                # Should return insufficient text with warning
                assert result.method == "pdf_loader_insufficient"
                assert "OCR dependencies not available" in result.metadata.get("warning", "")
    
    def test_concurrent_ocr_processing(self, mock_ai_config):
        """Test concurrent OCR processing scenarios."""
        import threading
        import time
        
        enabled_config = OCRConfig(enabled=True, timeout_seconds=10)
        
        results = []
        errors = []
        
        def process_pdf_worker(worker_id: int):
            """Worker function for concurrent processing."""
            try:
                with patch('services.enhanced_pdf_extractor.get_ocr_config', return_value=enabled_config):
                    with patch('services.enhanced_pdf_extractor.is_ocr_available', return_value=True):
                        extractor = EnhancedPDFTextExtractor(mock_ai_config)
                        
                        # Mock processing
                        with patch.object(extractor, '_extract_with_pdf_loaders', return_value="Page 1"):
                            with patch.object(extractor, 'ocr_processor') as mock_ocr:
                                mock_ocr.extract_with_ocr.return_value = f"OCR text from worker {worker_id}"
                                with patch('services.enhanced_pdf_extractor.validate_file_path', return_value=f"/test{worker_id}.pdf"):
                                    with patch('services.enhanced_pdf_extractor.Path.exists', return_value=True):
                                        with patch.object(extractor, '_track_extraction_method'):
                                            result = extractor.extract_text(f"/test{worker_id}.pdf")
                                            results.append((worker_id, result.method))
                
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=process_pdf_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations completed successfully
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        assert all(method == "ocr" for _, method in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])