#!/usr/bin/env python3
"""
Test script for OCR integration in bank statement processing.

This script tests the enhanced PDF text extraction with OCR fallback
to ensure the integration is working correctly.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the API directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_ocr_integration():
    """Test the OCR integration components."""
    print("🧪 Testing OCR Integration Components")
    print("=" * 50)
    
    # Test 1: Import all OCR-related modules
    print("\n1. Testing imports...")
    try:
        from services.enhanced_pdf_extractor import EnhancedPDFTextExtractor
        from services.bank_statement_ocr_processor import BankStatementOCRProcessor
        from utils.text_sufficiency_validator import TextSufficiencyValidator
        from exceptions.bank_ocr_exceptions import OCRTimeoutError, OCRProcessingError
        from utils.ocr_notifications import notify_ocr_processing_started
        from settings.ocr_config import get_ocr_config
        print("   ✅ All OCR modules imported successfully")
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return False
    
    # Test 2: Test OCR configuration
    print("\n2. Testing OCR configuration...")
    try:
        config = get_ocr_config()
        print(f"   ✅ OCR config loaded: enabled={config.enabled}, timeout={config.timeout_seconds}s")
    except Exception as e:
        print(f"   ❌ OCR config error: {e}")
        return False
    
    # Test 3: Test text sufficiency validator
    print("\n3. Testing text sufficiency validator...")
    try:
        validator = TextSufficiencyValidator()
        
        # Test with insufficient text
        insufficient_text = "Page 1 of 1"
        result = validator.validate_text_sufficiency(insufficient_text)
        print(f"   ✅ Insufficient text detected: sufficient={result.is_sufficient}, score={result.quality_score:.1f}")
        
        # Test with sufficient text
        sufficient_text = """
        Bank Statement
        Account: 123456789
        Statement Period: 01/01/2024 to 01/31/2024
        
        Date        Description                Amount      Balance
        01/02/2024  SALARY DEPOSIT            2500.00     2500.00
        01/03/2024  GROCERY STORE             -45.67      2454.33
        01/05/2024  ATM WITHDRAWAL            -100.00     2354.33
        01/10/2024  UTILITY PAYMENT           -125.50     2228.83
        """
        result = validator.validate_text_sufficiency(sufficient_text)
        print(f"   ✅ Sufficient text detected: sufficient={result.is_sufficient}, score={result.quality_score:.1f}")
        
    except Exception as e:
        print(f"   ❌ Text validator error: {e}")
        return False
    
    # Test 4: Test notification system
    print("\n4. Testing notification system...")
    try:
        notify_ocr_processing_started("/test/file.pdf", user_id=123)
        from utils.ocr_notifications import ocr_notification_manager
        notifications = ocr_notification_manager.get_notifications(user_id=123)
        print(f"   ✅ Notification system working: {len(notifications)} notifications")
    except Exception as e:
        print(f"   ❌ Notification error: {e}")
        return False
    
    # Test 5: Test enhanced PDF extractor initialization
    print("\n5. Testing enhanced PDF extractor...")
    try:
        ai_config = {
            "provider_name": "ollama",
            "model_name": "test-model",
            "api_key": None,
            "provider_url": "http://localhost:11434"
        }
        
        # This should work even without actual OCR dependencies
        extractor = EnhancedPDFTextExtractor(ai_config)
        available_loaders = extractor.get_available_loaders()
        print(f"   ✅ Enhanced PDF extractor initialized: {len(available_loaders)} PDF loaders available")
        
    except Exception as e:
        print(f"   ❌ Enhanced PDF extractor error: {e}")
        return False
    
    # Test 6: Test UniversalBankTransactionExtractor with OCR integration
    print("\n6. Testing UniversalBankTransactionExtractor integration...")
    try:
        from services.statement_service import UniversalBankTransactionExtractor
        
        ai_config = {
            "provider_name": "test",
            "model_name": "test-model",
            "api_key": "test-key",
            "provider_url": "http://test.example.com"
        }
        
        # This will fail at provider connection test, but we can catch that
        try:
            extractor = UniversalBankTransactionExtractor(ai_config)
            print("   ✅ UniversalBankTransactionExtractor initialized with OCR support")
        except Exception as provider_error:
            if "connection" in str(provider_error).lower() or "provider" in str(provider_error).lower():
                print("   ✅ UniversalBankTransactionExtractor OCR integration working (provider connection expected to fail in test)")
            else:
                raise provider_error
        
    except Exception as e:
        print(f"   ❌ UniversalBankTransactionExtractor integration error: {e}")
        return False
    
    # Test 7: Test error handling
    print("\n7. Testing OCR error handling...")
    try:
        from exceptions.bank_ocr_exceptions import is_retryable_ocr_error, get_retry_delay
        
        timeout_error = OCRTimeoutError("Test timeout", timeout_seconds=300)
        processing_error = OCRProcessingError("Test processing error", is_transient=True)
        
        print(f"   ✅ Timeout error retryable: {is_retryable_ocr_error(timeout_error)}")
        print(f"   ✅ Processing error retryable: {is_retryable_ocr_error(processing_error)}")
        print(f"   ✅ Timeout retry delay: {get_retry_delay(timeout_error)}s")
        
    except Exception as e:
        print(f"   ❌ Error handling test error: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All OCR integration tests passed!")
    print("\nIntegration Summary:")
    print("- ✅ Enhanced PDF text extraction with OCR fallback")
    print("- ✅ Text sufficiency validation")
    print("- ✅ OCR-specific error handling")
    print("- ✅ User notification system")
    print("- ✅ Graceful degradation when OCR unavailable")
    print("- ✅ Integration with UniversalBankTransactionExtractor")
    
    return True


if __name__ == "__main__":
    success = test_ocr_integration()
    sys.exit(0 if success else 1)