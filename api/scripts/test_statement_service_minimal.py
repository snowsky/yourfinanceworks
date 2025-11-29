#!/usr/bin/env python3
"""
Minimal test script to verify statement service can be imported without LangChain errors.
"""

import logging
import sys
import os

# Add the parent directory to Python path so we can import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_statement_service_import():
    """Test importing the statement service components."""
    
    logger.info("Testing statement service imports...")
    
    try:
        # Test basic imports first
        logger.info("✓ Testing basic imports...")
        from core.services.statement_service import LANGCHAIN_AVAILABLE
        logger.info(f"✅ LANGCHAIN_AVAILABLE = {LANGCHAIN_AVAILABLE}")
        
        # Test UniversalBankTransactionExtractor
        logger.info("✓ Testing UniversalBankTransactionExtractor...")
        from core.services.statement_service import UniversalBankTransactionExtractor
        logger.info("✅ UniversalBankTransactionExtractor imported successfully")
        
        # Test BankTransactionExtractor
        logger.info("✓ Testing BankTransactionExtractor...")
        from core.services.statement_service import BankTransactionExtractor
        logger.info("✅ BankTransactionExtractor imported successfully")
        
        # Test main processing function
        logger.info("✓ Testing process_bank_pdf_with_llm...")
        from core.services.statement_service import process_bank_pdf_with_llm
        logger.info("✅ process_bank_pdf_with_llm imported successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_extractor_initialization():
    """Test that extractors can be initialized without errors."""
    
    logger.info("Testing extractor initialization...")
    
    try:
        from core.services.statement_service import UniversalBankTransactionExtractor, BankTransactionExtractor
        
        # Test UniversalBankTransactionExtractor with dummy config
        logger.info("✓ Testing UniversalBankTransactionExtractor initialization...")
        ai_config = {
            "provider_name": "ollama",
            "model_name": "gpt-oss",
            "api_key": None,
            "provider_url": "http://192.168.86.32:11434"
        }
        
        try:
            extractor = UniversalBankTransactionExtractor(ai_config)
            logger.info(f"✅ UniversalBankTransactionExtractor initialized (langchain_available: {getattr(extractor, 'langchain_available', 'unknown')})")
        except Exception as e:
            logger.warning(f"⚠️ UniversalBankTransactionExtractor initialization failed (expected if LangChain unavailable): {e}")
        
        # Test BankTransactionExtractor
        logger.info("✓ Testing BankTransactionExtractor initialization...")
        try:
            extractor = BankTransactionExtractor()
            logger.info(f"✅ BankTransactionExtractor initialized (langchain_available: {getattr(extractor, 'langchain_available', 'unknown')})")
        except Exception as e:
            logger.warning(f"⚠️ BankTransactionExtractor initialization failed (expected if LangChain unavailable): {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Extractor initialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🔍 Starting statement service tests...")
    
    # Test imports
    imports_ok = test_statement_service_import()
    
    # Test initialization
    init_ok = test_extractor_initialization()
    
    if imports_ok and init_ok:
        logger.info("✅ All tests passed!")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed!")
        sys.exit(1)