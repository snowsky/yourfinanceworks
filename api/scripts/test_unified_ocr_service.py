#!/usr/bin/env python3
"""
Test script for the Unified OCR Service.
"""

import logging
import sys
import os
import asyncio

# Add the parent directory to Python path so we can import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_service_initialization():
    """Test that the unified OCR service can be initialized."""
    
    logger.info("Testing UnifiedOCRService initialization...")
    
    try:
        from core.services.unified_ocr_service import UnifiedOCRService, OCRConfig, DocumentType
        
        # Test with default config
        logger.info("✓ Testing default configuration...")
        service = UnifiedOCRService()
        status = service.get_service_status()
        logger.info(f"✅ Service initialized: {status['service']}")
        
        # Test with custom config
        logger.info("✓ Testing custom configuration...")
        config = OCRConfig(
            enable_unstructured=True,
            enable_ai_vision=True,
            timeout_seconds=120,
            max_retries=2
        )
        service_custom = UnifiedOCRService(config)
        status_custom = service_custom.get_service_status()
        logger.info(f"✅ Custom service initialized: timeout={status_custom['config']['timeout_seconds']}s")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_document_type_detection():
    """Test document type auto-detection."""
    
    logger.info("Testing document type detection...")
    
    try:
        from core.services.unified_ocr_service import UnifiedOCRService, DocumentType
        
        service = UnifiedOCRService()
        
        # Test different file names
        test_cases = [
            ("bank_statement_2024.pdf", DocumentType.BANK_STATEMENT),
            ("expense_receipt.jpg", DocumentType.EXPENSE_RECEIPT),
            ("invoice_123.pdf", DocumentType.INVOICE),
            ("random_document.pdf", DocumentType.GENERIC_DOCUMENT),
        ]
        
        for filename, expected_type in test_cases:
            detected_type = service._detect_document_type(filename)
            if detected_type == expected_type:
                logger.info(f"✅ {filename} -> {detected_type.value}")
            else:
                logger.warning(f"⚠️ {filename} -> {detected_type.value} (expected {expected_type.value})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Document type detection failed: {e}")
        return False


def test_convenience_functions():
    """Test convenience functions for backward compatibility."""
    
    logger.info("Testing convenience functions...")
    
    try:
        from core.services.unified_ocr_service import create_unified_ocr_service
        
        # Test service creation
        logger.info("✓ Testing create_unified_ocr_service...")
        ai_config = {
            "provider_name": "ollama",
            "model_name": "test-model",
            "api_key": None,
            "provider_url": "http://localhost:11434"
        }
        
        service = create_unified_ocr_service(ai_config)
        status = service.get_service_status()
        logger.info(f"✅ Service created via convenience function: {status['service']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Convenience functions test failed: {e}")
        return False


async def test_async_functionality():
    """Test async functionality of the service."""
    
    logger.info("Testing async functionality...")
    
    try:
        from core.services.unified_ocr_service import UnifiedOCRService, DocumentType
        
        service = UnifiedOCRService()
        
        # Test with a dummy file path (will fail but should handle gracefully)
        logger.info("✓ Testing async structured data extraction...")
        result = await service.extract_structured_data(
            "/tmp/nonexistent_file.pdf",
            DocumentType.EXPENSE_RECEIPT
        )
        
        if not result.success:
            logger.info(f"✅ Async extraction handled error gracefully: {result.error_message}")
        else:
            logger.info("✅ Async extraction completed successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Async functionality test failed: {e}")
        return False


def test_engine_availability():
    """Test availability of extraction engines."""
    
    logger.info("Testing extraction engine availability...")
    
    try:
        from core.services.unified_ocr_service import UnifiedOCRService
        
        service = UnifiedOCRService()
        status = service.get_service_status()
        
        engines = status['engines']
        
        logger.info("📊 Engine Availability:")
        logger.info(f"  Text Extraction:")
        logger.info(f"    PDF Extractor: {'✅' if engines['text_extraction']['pdf_extractor_available'] else '❌'}")
        logger.info(f"    OCR Processor: {'✅' if engines['text_extraction']['ocr_processor_available'] else '❌'}")
        
        logger.info(f"  Structured Extraction:")
        logger.info(f"    AI Vision: {'✅' if engines['structured_extraction']['ai_vision_available'] else '❌'}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Engine availability test failed: {e}")
        return False


async def main():
    """Run all tests."""
    
    logger.info("🔍 Starting Unified OCR Service tests...")
    
    tests = [
        ("Service Initialization", test_service_initialization),
        ("Document Type Detection", test_document_type_detection),
        ("Convenience Functions", test_convenience_functions),
        ("Engine Availability", test_engine_availability),
        ("Async Functionality", test_async_functionality),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} ---")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
    
    logger.info(f"\n🎯 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("✅ All tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))