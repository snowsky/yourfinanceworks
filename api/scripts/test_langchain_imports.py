#!/usr/bin/env python3
"""
Test script to verify LangChain imports work correctly in the OCR worker container.
"""

import logging
import sys
import os

# Add the parent directory to Python path so we can import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_langchain_imports():
    """Test all LangChain imports used in the statement service."""
    
    logger.info("Testing LangChain imports...")
    
    try:
        # Test langchain_community imports
        logger.info("✓ Testing langchain_community.document_loaders...")
        from langchain_community.document_loaders import (
            PyPDFLoader, 
            PyMuPDFLoader, 
            PDFMinerLoader,
            PyPDFium2Loader,
            PDFPlumberLoader,
            UnstructuredPDFLoader,
            CSVLoader,
        )
        logger.info("✅ langchain_community.document_loaders imported successfully")
        
        # Test langchain_text_splitters
        logger.info("✓ Testing langchain_text_splitters...")
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        logger.info("✅ langchain_text_splitters imported successfully")
        
        # Test langchain_core imports
        logger.info("✓ Testing langchain_core imports...")
        from langchain_core.documents import Document
        from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
        from langchain_core.output_parsers import PydanticOutputParser
        from langchain_core.callbacks import BaseCallbackHandler
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        logger.info("✅ langchain_core imports successful")
        
        # Note: LLMChain is deprecated in LangChain v1.0+, using direct LLM calls instead
        logger.info("✓ Skipping deprecated langchain.chains.llm.LLMChain (using direct LLM calls)")
        logger.info("✅ LangChain chains handling updated for v1.0+")
        
        # Test langchain_community LLM imports
        logger.info("✓ Testing langchain_community LLMs...")
        from langchain_community.llms import Ollama
        from langchain_community.chat_models import ChatOllama
        logger.info("✅ langchain_community LLMs imported successfully")
        
        logger.info("🎉 All LangChain imports successful!")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def test_statement_service_import():
    """Test importing the statement service itself."""
    
    logger.info("Testing statement service import...")
    
    try:
        from services.statement_service import UniversalBankTransactionExtractor
        logger.info("✅ UniversalBankTransactionExtractor imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to import UniversalBankTransactionExtractor: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔍 Starting LangChain import tests...")
    
    # Test individual imports
    imports_ok = test_langchain_imports()
    
    # Test statement service import
    service_ok = test_statement_service_import()
    
    if imports_ok and service_ok:
        logger.info("✅ All tests passed!")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed!")
        sys.exit(1)