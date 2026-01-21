#!/usr/bin/env python3
"""
Test OCR Setup Script

This script tests the OCR infrastructure setup for bank statement processing.
It checks dependencies, configuration, and basic functionality.
"""

import sys
import os
import logging

# Add the parent directory to the path so we can import from api
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commercial.ai.services.ocr_service import initialize_ocr_dependencies, validate_ocr_setup
from commercial.ai.settings.ocr_config import get_ocr_config, log_ocr_status
from commercial.ai.exceptions.bank_ocr_exceptions import OCRError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Test OCR setup and report status."""
    print("=" * 60)
    print("Bank Statement OCR Setup Test")
    print("=" * 60)
    
    try:
        # Test configuration loading
        print("\n1. Testing OCR Configuration...")
        config = get_ocr_config()
        print(f"   ✓ Configuration loaded successfully")
        print(f"   - Enabled: {config.enabled}")
        print(f"   - Timeout: {config.timeout_seconds}s")
        print(f"   - Min text threshold: {config.min_text_threshold}")
        print(f"   - Use API: {config.use_unstructured_api}")
        
        # Test dependency initialization
        print("\n2. Testing Dependency Initialization...")
        init_result = initialize_ocr_dependencies()
        
        if init_result["status"] == "success":
            print(f"   ✓ Dependencies initialized successfully")
            print(f"   - Available: {init_result['available']}")
            
            deps = init_result["dependencies"]
            print(f"   - unstructured: {deps['unstructured']}")

            print(f"   - pytesseract: {deps['pytesseract']}")
            print(f"   - tesseract_binary: {deps['tesseract_binary']}")
            
            if init_result["components"]:
                print(f"   - Components: {list(init_result['components'].keys())}")
        else:
            print(f"   ✗ Dependency initialization failed: {init_result.get('error')}")
        
        # Test validation
        print("\n3. Testing OCR Validation...")
        try:
            validate_ocr_setup()
            print("   ✓ OCR validation passed")
        except OCRError as e:
            print(f"   ✗ OCR validation failed: {e.message}")
            print(f"     Error code: {e.error_code.value}")
            if e.details:
                print(f"     Details: {e.details}")
        
        # Log overall status
        print("\n4. Overall OCR Status:")
        log_ocr_status()
        
        # Summary
        print("\n" + "=" * 60)
        if init_result.get("available", False):
            print("✓ OCR setup is ready for bank statement processing")
            return 0
        else:
            print("✗ OCR setup has issues that need to be resolved")
            return 1
            
    except Exception as e:
        logger.error(f"OCR setup test failed: {e}", exc_info=True)
        print(f"\n✗ OCR setup test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())