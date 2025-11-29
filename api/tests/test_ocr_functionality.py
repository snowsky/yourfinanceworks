"""
Unit tests for OCR functionality in bank statement processing.

This module tests the EnhancedPDFTextExtractor, BankStatementOCRProcessor,
and related OCR components to ensure proper functionality and error handling.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Import the modules under test
from core.services.enhanced_pdf_extractor import EnhancedPDFTextExtractor, TextExtractionResult
from core.services.bank_statement_ocr_processor import BankStatementOCRProcessor
from core.utils.text_sufficiency_validator import TextSufficiencyValidator, TextQualityMetrics
from core.settings.ocr_config import OCRConfig, get_ocr_config
from core.exceptions.bank_ocr_exceptions import (
    OCRUnavailableError,
    OCRTimeoutError,
    OCRProcessingError,
    OCRInvalidFileError,
    OCRDependencyMissingError,
    OCRConfigurationError
)


class TestEnhancedPDFTextExtractor:
    """Test cases for EnhancedPDFTextExtractor class."""
    
    @pytest.fixture
    def mock_ai_config(self):
        """Mock AI configuration for testing."""
        return {
            "provider_name": "test_provider",
            "model_name": "test_model",
            "api_key": "test_key",
            "provider_url": "http://test.example.com"
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
            unstructured_api_key=None,
            strategy="hi_res",
            mode="single"
        )
    
    @pytest.fixture
    def temp_pdf_file(self):
        """Create a temporary PDF file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n')
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    def test_initialization_with_ocr_enabled(self, mock_get_config, mock_ai_config, mock_ocr_config):
        """Test EnhancedPDFTextExtractor initialization with OCR enabled."""
        mock_get_config.return_value = mock_ocr_config
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        assert extractor.ai_config == mock_ai_config
        assert extractor.ocr_config == mock_ocr_config
        assert extractor.text_validator is not None
        assert isinstance(extractor.text_validator, TextSufficiencyValidator)
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    def test_initialization_with_ocr_disabled(self, mock_get_config, mock_ai_config):
        """Test EnhancedPDFTextExtractor initialization with OCR disabled."""
        disabled_config = OCRConfig(enabled=False)
        mock_get_config.return_value = disabled_config
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        assert extractor.ocr_config.enabled is False
    
    @patch('services.enhanced_pdf_extractor.LANGCHAIN_AVAILABLE', True)
    @patch('services.enhanced_pdf_extractor.PyMuPDFLoader')
    @patch('services.enhanced_pdf_extractor.PDFPlumberLoader')
    def test_pdf_loader_initialization(self, mock_pdfplumber, mock_pymupdf, mock_ai_config):
        """Test PDF loader initialization."""
        with patch('services.enhanced_pdf_extractor.get_ocr_config') as mock_get_config:
            mock_get_config.return_value = OCRConfig(enabled=True)
            
            extractor = EnhancedPDFTextExtractor(mock_ai_config)
            loaders = extractor.get_available_loaders()
            
            # Should have some loaders available
            assert isinstance(loaders, list)
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    def test_extract_text_invalid_file_path(self, mock_validate, mock_get_config, mock_ai_config):
        """Test text extraction with invalid file path."""
        mock_get_config.return_value = OCRConfig(enabled=True)
        mock_validate.side_effect = ValueError("Invalid path")
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        with pytest.raises(OCRInvalidFileError) as exc_info:
            extractor.extract_text("/invalid/path.pdf")
        
        assert "Invalid PDF path" in str(exc_info.value)
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    def test_extract_text_file_not_found(self, mock_validate, mock_get_config, mock_ai_config):
        """Test text extraction with non-existent file."""
        mock_get_config.return_value = OCRConfig(enabled=True)
        mock_validate.return_value = "/nonexistent/file.pdf"
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        with pytest.raises(OCRInvalidFileError) as exc_info:
            extractor.extract_text("/nonexistent/file.pdf")
        
        assert "PDF file not found" in str(exc_info.value)
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    @patch('services.enhanced_pdf_extractor.Path.exists')
    def test_extract_text_pdf_success_sufficient_text(self, mock_exists, mock_validate, mock_get_config, 
                                                     mock_ai_config, temp_pdf_file):
        """Test successful PDF text extraction with sufficient text."""
        mock_get_config.return_value = OCRConfig(enabled=True)
        mock_validate.return_value = temp_pdf_file
        mock_exists.return_value = True
        
        # Mock sufficient text extraction
        sufficient_text = """
        Bank Statement
        Account Number: 123456789
        Statement Period: 01/01/2024 to 01/31/2024
        
        Date        Description                Amount      Balance
        01/02/2024  SALARY DEPOSIT            2500.00     2500.00
        01/03/2024  GROCERY STORE             -45.67      2454.33
        01/05/2024  ATM WITHDRAWAL            -100.00     2354.33
        """
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        with patch.object(extractor, '_extract_with_pdf_loaders', return_value=sufficient_text):
            with patch.object(extractor, '_track_extraction_method'):
                result = extractor.extract_text(temp_pdf_file)
        
        assert isinstance(result, TextExtractionResult)
        assert result.text == sufficient_text
        assert result.method == "pdf_loader"
        assert result.text_length > 0
        assert result.word_count > 0
        assert result.processing_time >= 0
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    @patch('services.enhanced_pdf_extractor.Path.exists')
    @patch('services.enhanced_pdf_extractor.is_ocr_available')
    def test_extract_text_pdf_insufficient_ocr_fallback(self, mock_ocr_available, mock_exists, 
                                                       mock_validate, mock_get_config, 
                                                       mock_ai_config, temp_pdf_file):
        """Test OCR fallback when PDF extraction yields insufficient text."""
        mock_get_config.return_value = OCRConfig(enabled=True)
        mock_validate.return_value = temp_pdf_file
        mock_exists.return_value = True
        mock_ocr_available.return_value = True
        
        # Mock insufficient PDF text
        insufficient_text = "Page 1 of 1"
        
        # Mock sufficient OCR text
        ocr_text = """
        BANK STATEMENT
        Account: 123-456-789
        Period: January 2024
        
        01/02  DEPOSIT           +2500.00
        01/03  GROCERY STORE      -45.67
        01/05  ATM CASH          -100.00
        """
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
            with patch.object(extractor, 'ocr_processor') as mock_ocr_processor:
                mock_ocr_processor.extract_with_ocr.return_value = ocr_text
                with patch.object(extractor, '_track_extraction_method'):
                    result = extractor.extract_text(temp_pdf_file)
        
        assert isinstance(result, TextExtractionResult)
        assert result.text == ocr_text
        assert result.method == "ocr"
        assert result.text_length > 0
        assert result.word_count > 0
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    @patch('services.enhanced_pdf_extractor.Path.exists')
    @patch('services.enhanced_pdf_extractor.is_ocr_available')
    def test_extract_text_ocr_disabled_fallback(self, mock_ocr_available, mock_exists, 
                                               mock_validate, mock_get_config, 
                                               mock_ai_config, temp_pdf_file):
        """Test behavior when OCR is disabled and PDF text is insufficient."""
        mock_get_config.return_value = OCRConfig(enabled=False)
        mock_validate.return_value = temp_pdf_file
        mock_exists.return_value = True
        mock_ocr_available.return_value = False
        
        insufficient_text = "Page 1 of 1"
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
            with patch.object(extractor, '_track_extraction_method'):
                result = extractor.extract_text(temp_pdf_file)
        
        assert isinstance(result, TextExtractionResult)
        assert result.method == "pdf_loader_insufficient"
        assert "OCR disabled" in result.metadata.get("warning", "")
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    @patch('services.enhanced_pdf_extractor.Path.exists')
    @patch('services.enhanced_pdf_extractor.is_ocr_available')
    def test_extract_text_ocr_unavailable_fallback(self, mock_ocr_available, mock_exists, 
                                                  mock_validate, mock_get_config, 
                                                  mock_ai_config, temp_pdf_file):
        """Test behavior when OCR dependencies are unavailable."""
        mock_get_config.return_value = OCRConfig(enabled=True)
        mock_validate.return_value = temp_pdf_file
        mock_exists.return_value = True
        mock_ocr_available.return_value = False
        
        insufficient_text = "Page 1 of 1"
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
            with patch.object(extractor, '_track_extraction_method'):
                result = extractor.extract_text(temp_pdf_file)
        
        assert isinstance(result, TextExtractionResult)
        assert result.method == "pdf_loader_insufficient"
        assert "OCR dependencies not available" in result.metadata.get("warning", "")
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.validate_file_path')
    @patch('services.enhanced_pdf_extractor.Path.exists')
    @patch('services.enhanced_pdf_extractor.is_ocr_available')
    def test_extract_text_ocr_processing_error(self, mock_ocr_available, mock_exists, 
                                              mock_validate, mock_get_config, 
                                              mock_ai_config, temp_pdf_file):
        """Test handling of OCR processing errors."""
        mock_get_config.return_value = OCRConfig(enabled=True)
        mock_validate.return_value = temp_pdf_file
        mock_exists.return_value = True
        mock_ocr_available.return_value = True
        
        insufficient_text = "Page 1 of 1"
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
            with patch.object(extractor, 'ocr_processor') as mock_ocr_processor:
                mock_ocr_processor.extract_with_ocr.side_effect = OCRProcessingError("OCR failed")
                
                with pytest.raises(OCRProcessingError) as exc_info:
                    extractor.extract_text(temp_pdf_file)
                
                assert "Both PDF and OCR extraction failed" in str(exc_info.value)
    
    def test_get_available_loaders(self, mock_ai_config):
        """Test getting list of available PDF loaders."""
        with patch('services.enhanced_pdf_extractor.get_ocr_config') as mock_get_config:
            mock_get_config.return_value = OCRConfig(enabled=True)
            
            extractor = EnhancedPDFTextExtractor(mock_ai_config)
            loaders = extractor.get_available_loaders()
            
            assert isinstance(loaders, list)
    
    def test_get_loader_info(self, mock_ai_config):
        """Test getting information about a specific PDF loader."""
        with patch('services.enhanced_pdf_extractor.get_ocr_config') as mock_get_config:
            mock_get_config.return_value = OCRConfig(enabled=True)
            
            extractor = EnhancedPDFTextExtractor(mock_ai_config)
            
            # Test with non-existent loader
            info = extractor.get_loader_info("nonexistent")
            assert info is None


class TestBankStatementOCRProcessor:
    """Test cases for BankStatementOCRProcessor class."""
    
    @pytest.fixture
    def mock_ai_config(self):
        """Mock AI configuration for testing."""
        return {
            "provider_name": "test_provider",
            "model_name": "test_model",
            "api_key": "test_key"
        }
    
    @pytest.fixture
    def mock_ocr_config_local(self):
        """Mock OCR configuration for local processing."""
        return OCRConfig(
            enabled=True,
            timeout_seconds=300,
            use_unstructured_api=False,
            strategy="hi_res",
            mode="single"
        )
    
    @pytest.fixture
    def mock_ocr_config_api(self):
        """Mock OCR configuration for API processing."""
        return OCRConfig(
            enabled=True,
            timeout_seconds=300,
            use_unstructured_api=True,
            unstructured_api_key="test_api_key",
            unstructured_api_url="https://api.unstructured.io",
            strategy="hi_res"
        )
    
    @pytest.fixture
    def temp_pdf_file(self):
        """Create a temporary PDF file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n')
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    def test_initialization_local_mode(self, mock_check_deps, mock_get_config, 
                                      mock_ai_config, mock_ocr_config_local):
        """Test OCR processor initialization in local mode."""
        mock_get_config.return_value = mock_ocr_config_local
        mock_check_deps.return_value = {
            "unstructured": True,
            "pytesseract": True,
            "tesseract_binary": True
        }
        
        processor = BankStatementOCRProcessor(mock_ai_config)
        
        assert processor.ai_config == mock_ai_config
        assert processor.ocr_config == mock_ocr_config_local
        assert processor.ocr_loader_factory is not None
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    def test_initialization_api_mode(self, mock_check_deps, mock_get_config, 
                                    mock_ai_config, mock_ocr_config_api):
        """Test OCR processor initialization in API mode."""
        mock_get_config.return_value = mock_ocr_config_api
        mock_check_deps.return_value = {
            "unstructured": True,
            "pytesseract": False,
            "tesseract_binary": False
        }
        
        processor = BankStatementOCRProcessor(mock_ai_config)
        
        assert processor.ai_config == mock_ai_config
        assert processor.ocr_config == mock_ocr_config_api
        assert processor.ocr_loader_factory is not None
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', False)
    def test_initialization_missing_dependencies(self, mock_check_deps, mock_get_config, 
                                                mock_ai_config, mock_ocr_config_local):
        """Test initialization failure with missing dependencies."""
        mock_get_config.return_value = mock_ocr_config_local
        mock_check_deps.return_value = {
            "unstructured": False,
            "pytesseract": False,
            "tesseract_binary": False
        }
        
        with pytest.raises(OCRDependencyMissingError) as exc_info:
            BankStatementOCRProcessor(mock_ai_config)
        
        assert "unstructured package is required" in str(exc_info.value)
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    def test_initialization_api_mode_missing_key(self, mock_check_deps, mock_get_config, mock_ai_config):
        """Test initialization failure in API mode without API key."""
        config = OCRConfig(
            enabled=True,
            use_unstructured_api=True,
            unstructured_api_key=None  # Missing API key
        )
        mock_get_config.return_value = config
        mock_check_deps.return_value = {"unstructured": True}
        
        with pytest.raises(OCRConfigurationError) as exc_info:
            BankStatementOCRProcessor(mock_ai_config)
        
        assert "API key is required" in str(exc_info.value)
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    @patch('services.bank_statement_ocr_processor.validate_file_path')
    @patch('services.bank_statement_ocr_processor.Path.exists')
    def test_extract_with_ocr_success(self, mock_exists, mock_validate, mock_check_deps, 
                                     mock_get_config, mock_ai_config, mock_ocr_config_local, 
                                     temp_pdf_file):
        """Test successful OCR text extraction."""
        mock_get_config.return_value = mock_ocr_config_local
        mock_check_deps.return_value = {
            "unstructured": True,
            "pytesseract": True,
            "tesseract_binary": True
        }
        mock_validate.return_value = temp_pdf_file
        mock_exists.return_value = True
        
        # Mock successful OCR extraction
        mock_document = Mock()
        mock_document.page_content = """
        BANK STATEMENT
        Account Number: 123-456-789
        Statement Period: January 2024
        
        Date        Description           Amount    Balance
        01/02/2024  SALARY DEPOSIT       +2500.00   2500.00
        01/03/2024  GROCERY STORE         -45.67   2454.33
        """
        
        processor = BankStatementOCRProcessor(mock_ai_config)
        
        with patch.object(processor, 'ocr_loader_factory') as mock_factory:
            mock_loader = Mock()
            mock_loader.load.return_value = [mock_document]
            mock_factory.return_value = mock_loader
            
            result = processor.extract_with_ocr(temp_pdf_file)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "BANK STATEMENT" in result
        assert "123-456-789" in result
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    @patch('services.bank_statement_ocr_processor.validate_file_path')
    def test_extract_with_ocr_invalid_file(self, mock_validate, mock_check_deps, 
                                          mock_get_config, mock_ai_config, mock_ocr_config_local):
        """Test OCR extraction with invalid file path."""
        mock_get_config.return_value = mock_ocr_config_local
        mock_check_deps.return_value = {
            "unstructured": True,
            "pytesseract": True,
            "tesseract_binary": True
        }
        mock_validate.side_effect = ValueError("Invalid path")
        
        processor = BankStatementOCRProcessor(mock_ai_config)
        
        with pytest.raises(OCRProcessingError) as exc_info:
            processor.extract_with_ocr("/invalid/path.pdf")
        
        assert "Invalid PDF path" in str(exc_info.value)
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    @patch('services.bank_statement_ocr_processor.validate_file_path')
    @patch('services.bank_statement_ocr_processor.Path.exists')
    def test_extract_with_ocr_timeout(self, mock_exists, mock_validate, mock_check_deps, 
                                     mock_get_config, mock_ai_config, temp_pdf_file):
        """Test OCR extraction timeout handling."""
        config = OCRConfig(
            enabled=True,
            timeout_seconds=1,  # Very short timeout
            use_unstructured_api=False
        )
        mock_get_config.return_value = config
        mock_check_deps.return_value = {
            "unstructured": True,
            "pytesseract": True,
            "tesseract_binary": True
        }
        mock_validate.return_value = temp_pdf_file
        mock_exists.return_value = True
        
        processor = BankStatementOCRProcessor(mock_ai_config)
        
        with patch.object(processor, 'ocr_loader_factory') as mock_factory:
            mock_loader = Mock()
            # Simulate long-running operation
            import time
            mock_loader.load.side_effect = lambda: time.sleep(2)
            mock_factory.return_value = mock_loader
            
            with pytest.raises(OCRTimeoutError) as exc_info:
                processor.extract_with_ocr(temp_pdf_file)
            
            assert "timed out after 1 seconds" in str(exc_info.value)
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    def test_test_ocr_availability_local_mode(self, mock_check_deps, mock_get_config, 
                                             mock_ai_config, mock_ocr_config_local):
        """Test OCR availability testing in local mode."""
        mock_get_config.return_value = mock_ocr_config_local
        mock_check_deps.return_value = {
            "unstructured": True,
            "pytesseract": True,
            "tesseract_binary": True
        }
        
        processor = BankStatementOCRProcessor(mock_ai_config)
        
        with patch('pytesseract.get_tesseract_version', return_value="5.0.0"):
            status = processor.test_ocr_availability()
        
        assert status["available"] is True
        assert status["mode"] == "local"
        assert "tesseract_version" in status
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    def test_test_ocr_availability_api_mode(self, mock_check_deps, mock_get_config, 
                                           mock_ai_config, mock_ocr_config_api):
        """Test OCR availability testing in API mode."""
        mock_get_config.return_value = mock_ocr_config_api
        mock_check_deps.return_value = {"unstructured": True}
        
        processor = BankStatementOCRProcessor(mock_ai_config)
        status = processor.test_ocr_availability()
        
        assert status["available"] is True
        assert status["mode"] == "api"
    
    @patch('services.bank_statement_ocr_processor.get_ocr_config')
    @patch('services.bank_statement_ocr_processor.check_ocr_dependencies')
    @patch('services.bank_statement_ocr_processor.UNSTRUCTURED_AVAILABLE', True)
    def test_get_processing_stats(self, mock_check_deps, mock_get_config, 
                                 mock_ai_config, mock_ocr_config_local):
        """Test getting OCR processing statistics."""
        mock_get_config.return_value = mock_ocr_config_local
        mock_check_deps.return_value = {
            "unstructured": True,
            "pytesseract": True,
            "tesseract_binary": True
        }
        
        processor = BankStatementOCRProcessor(mock_ai_config)
        stats = processor.get_processing_stats()
        
        assert "mode" in stats
        assert "timeout_seconds" in stats
        assert "strategy" in stats
        assert "dependencies_available" in stats
        assert "config_valid" in stats


class TestTextSufficiencyValidator:
    """Test cases for TextSufficiencyValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a TextSufficiencyValidator instance."""
        return TextSufficiencyValidator()
    
    def test_validate_empty_text(self, validator):
        """Test validation of empty text."""
        result = validator.validate_text_sufficiency("")
        
        assert isinstance(result, TextQualityMetrics)
        assert result.is_sufficient is False
        assert result.text_length == 0
        assert result.word_count == 0
        assert result.quality_score == 0.0
    
    def test_validate_insufficient_text_too_short(self, validator):
        """Test validation of text that's too short."""
        short_text = "Page 1 of 1"
        result = validator.validate_text_sufficiency(short_text)
        
        assert result.is_sufficient is False
        assert result.text_length == len(short_text)
        assert result.word_count == 3
        assert result.quality_score < 50.0
    
    def test_validate_insufficient_text_few_words(self, validator):
        """Test validation of text with too few words."""
        few_words_text = "Bank Statement Account"
        result = validator.validate_text_sufficiency(few_words_text)
        
        assert result.is_sufficient is False
        assert result.word_count < 10
    
    def test_validate_sufficient_text(self, validator):
        """Test validation of sufficient text."""
        sufficient_text = """
        Bank Statement
        Account Number: 123456789
        Statement Period: 01/01/2024 to 01/31/2024
        
        Date        Description                Amount      Balance
        01/02/2024  SALARY DEPOSIT            2500.00     2500.00
        01/03/2024  GROCERY STORE             -45.67      2454.33
        01/05/2024  ATM WITHDRAWAL            -100.00     2354.33
        01/10/2024  UTILITY PAYMENT           -125.50     2228.83
        """
        
        result = validator.validate_text_sufficiency(sufficient_text)
        
        assert result.is_sufficient is True
        assert result.text_length > 50
        assert result.word_count > 10
        assert result.quality_score > 50.0
    
    def test_validate_bank_statement_indicators(self, validator):
        """Test validation recognizes bank statement indicators."""
        bank_text = """
        Monthly Statement
        Account: 123456789
        
        Transaction Date    Description         Debit    Credit   Balance
        01/01/2024         Opening Balance                        1000.00
        01/02/2024         Deposit                      500.00    1500.00
        01/03/2024         Payment            100.00              1400.00
        """
        
        result = validator.validate_text_sufficiency(bank_text)
        
        assert result.is_sufficient is True
        # Should have high quality score due to bank indicators
        assert result.quality_score > 70.0


class TestOCRErrorHandling:
    """Test cases for OCR error handling and exception classes."""
    
    def test_ocr_unavailable_error(self):
        """Test OCRUnavailableError exception."""
        error = OCRUnavailableError("OCR not available")
        
        assert str(error) == "OCR not available"
        assert isinstance(error, Exception)
    
    def test_ocr_timeout_error(self):
        """Test OCRTimeoutError exception."""
        error = OCRTimeoutError("Timeout occurred", timeout_seconds=300)
        
        assert str(error) == "Timeout occurred"
        assert error.details.get("timeout_seconds") == 300
        assert error.is_transient is True
        assert error.retry_after == 60
    
    def test_ocr_processing_error(self):
        """Test OCRProcessingError exception."""
        details = {"file": "test.pdf", "error": "Processing failed"}
        error = OCRProcessingError("Processing error", details=details, is_transient=True)
        
        assert str(error) == "Processing error"
        assert error.details == details
        assert error.is_transient is True
    
    def test_ocr_invalid_file_error(self):
        """Test OCRInvalidFileError exception."""
        error = OCRInvalidFileError("Invalid file", file_path="/test/file.pdf")
        
        assert str(error) == "Invalid file"
        assert error.details.get("file_path") == "/test/file.pdf"
        assert error.is_transient is False
    
    def test_ocr_dependency_missing_error(self):
        """Test OCRDependencyMissingError exception."""
        error = OCRDependencyMissingError("Missing dependency", missing_dependency="tesseract")
        
        assert str(error) == "Missing dependency"
        assert error.details.get("missing_dependency") == "tesseract"
        assert error.is_transient is False
    
    def test_ocr_configuration_error(self):
        """Test OCRConfigurationError exception."""
        error = OCRConfigurationError("Config error", config_key="api_key")
        
        assert str(error) == "Config error"
        assert error.details.get("config_key") == "api_key"
        assert error.is_transient is False


class TestExtractionMethodSelection:
    """Test cases for extraction method selection logic."""
    
    @pytest.fixture
    def mock_ai_config(self):
        """Mock AI configuration for testing."""
        return {
            "provider_name": "test_provider",
            "model_name": "test_model"
        }
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    def test_pdf_loader_preferred_when_sufficient(self, mock_get_config, mock_ai_config):
        """Test that PDF loader is preferred when text is sufficient."""
        mock_get_config.return_value = OCRConfig(enabled=True)
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        # Mock sufficient text from PDF
        sufficient_text = "Bank Statement with lots of transaction data and account information"
        
        with patch.object(extractor.text_validator, 'validate_text_sufficiency') as mock_validate:
            mock_validate.return_value = TextQualityMetrics(
                is_sufficient=True,
                text_length=len(sufficient_text),
                word_count=len(sufficient_text.split()),
                line_count=5,
                bank_indicators_found=3,
                numeric_patterns_found=5,
                date_patterns_found=2,
                currency_patterns_found=1,
                quality_score=85.0,
                reasons=["Sufficient length", "Bank indicators found"]
            )
            
            # Should not trigger OCR when PDF text is sufficient
            with patch.object(extractor, '_extract_with_pdf_loaders', return_value=sufficient_text):
                with patch.object(extractor, '_track_extraction_method'):
                    with patch('services.enhanced_pdf_extractor.validate_file_path', return_value="/test.pdf"):
                        with patch('services.enhanced_pdf_extractor.Path.exists', return_value=True):
                            result = extractor.extract_text("/test.pdf")
            
            assert result.method == "pdf_loader"
            assert result.text == sufficient_text
    
    @patch('services.enhanced_pdf_extractor.get_ocr_config')
    @patch('services.enhanced_pdf_extractor.is_ocr_available')
    def test_ocr_fallback_when_insufficient(self, mock_ocr_available, mock_get_config, mock_ai_config):
        """Test that OCR fallback is triggered when PDF text is insufficient."""
        mock_get_config.return_value = OCRConfig(enabled=True)
        mock_ocr_available.return_value = True
        
        extractor = EnhancedPDFTextExtractor(mock_ai_config)
        
        # Mock insufficient text from PDF
        insufficient_text = "Page 1"
        ocr_text = "Bank Statement with OCR extracted transaction data"
        
        with patch.object(extractor.text_validator, 'validate_text_sufficiency') as mock_validate:
            mock_validate.return_value = TextQualityMetrics(
                is_sufficient=False,
                text_length=len(insufficient_text),
                word_count=len(insufficient_text.split()),
                line_count=1,
                bank_indicators_found=0,
                numeric_patterns_found=0,
                date_patterns_found=0,
                currency_patterns_found=0,
                quality_score=15.0,
                reasons=["Text too short", "No bank indicators"]
            )
            
            with patch.object(extractor, '_extract_with_pdf_loaders', return_value=insufficient_text):
                with patch.object(extractor, 'ocr_processor') as mock_ocr_processor:
                    mock_ocr_processor.extract_with_ocr.return_value = ocr_text
                    with patch.object(extractor, '_track_extraction_method'):
                        with patch('services.enhanced_pdf_extractor.validate_file_path', return_value="/test.pdf"):
                            with patch('services.enhanced_pdf_extractor.Path.exists', return_value=True):
                                result = extractor.extract_text("/test.pdf")
            
            assert result.method == "ocr"
            assert result.text == ocr_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])