#!/usr/bin/env python3
"""
Simple test script to verify only LangChain imports work correctly.
"""

import logging
import sys

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
        
        # Test langchain_ollama LLM imports
        logger.info("✓ Testing langchain_ollama LLMs...")
        from langchain_ollama import OllamaLLM
        from langchain_ollama import ChatOllama
        logger.info("✅ langchain_ollama LLMs imported successfully")
        
        logger.info("🎉 All LangChain imports successful!")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def test_basic_functionality():
    """Test basic LangChain functionality."""
    
    logger.info("Testing basic LangChain functionality...")
    
    try:
        from langchain_core.documents import Document
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.prompts import PromptTemplate
        
        # Test Document creation
        doc = Document(page_content="Test content", metadata={"source": "test"})
        logger.info(f"✅ Document created: {len(doc.page_content)} chars")
        
        # Test text splitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)
        chunks = splitter.split_text("This is a test document with some content that should be split into chunks.")
        logger.info(f"✅ Text splitter created {len(chunks)} chunks")
        
        # Test prompt template
        prompt = PromptTemplate(template="Process this text: {text}", input_variables=["text"])
        formatted = prompt.format(text="test input")
        logger.info(f"✅ Prompt template formatted: {len(formatted)} chars")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Functionality test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔍 Starting LangChain-only tests...")
    
    # Test imports
    imports_ok = test_langchain_imports()
    
    # Test basic functionality
    functionality_ok = test_basic_functionality()
    
    if imports_ok and functionality_ok:
        logger.info("✅ All LangChain tests passed!")
        sys.exit(0)
    else:
        logger.error("❌ Some LangChain tests failed!")
        sys.exit(1)