#!/usr/bin/env python3
"""
Example: Unified OCR Service Integration

This example demonstrates how to integrate the Unified OCR Service
into your application for different document types.
"""

import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_expense_processing():
    """Example: Process expense receipts using unified OCR service."""
    
    logger.info("=== Expense Receipt Processing Example ===")
    
    try:
        from services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
        
        # Configure OCR service
        ai_config = {
            "provider_name": "openai",  # or "ollama", "anthropic", etc.
            "model_name": "gpt-4-vision-preview",
            "api_key": "your-api-key-here",
            "provider_url": "https://api.openai.com/v1"
        }
        
        config = OCRConfig(
            ai_config=ai_config,
            enable_ai_vision=True,
            timeout_seconds=120
        )
        
        service = UnifiedOCRService(config)
        
        # Process expense receipt
        file_path = "/path/to/expense_receipt.jpg"  # Replace with actual file
        
        result = await service.extract_structured_data(
            file_path=file_path,
            document_type=DocumentType.EXPENSE_RECEIPT
        )
        
        if result.success:
            logger.info("✅ Expense data extracted successfully!")
            logger.info(f"Processing time: {result.processing_time:.2f}s")
            logger.info(f"Method used: {result.method.value}")
            
            # Access structured data
            expense_data = result.structured_data
            if expense_data:
                logger.info(f"Amount: {expense_data.get('amount')}")
                logger.info(f"Vendor: {expense_data.get('vendor')}")
                logger.info(f"Date: {expense_data.get('expense_date')}")
                logger.info(f"Category: {expense_data.get('category')}")
        else:
            logger.error(f"❌ Failed to extract expense data: {result.error_message}")
            
    except Exception as e:
        logger.error(f"❌ Example failed: {e}")


async def example_bank_statement_processing():
    """Example: Process bank statements using unified OCR service."""
    
    logger.info("=== Bank Statement Processing Example ===")
    
    try:
        from services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
        
        # Configure OCR service for text extraction
        config = OCRConfig(
            enable_unstructured=True,
            enable_tesseract_fallback=True,
            timeout_seconds=300
        )
        
        service = UnifiedOCRService(config)
        
        # Process bank statement
        file_path = "/path/to/bank_statement.pdf"  # Replace with actual file
        
        result = service.extract_text(
            file_path=file_path,
            document_type=DocumentType.BANK_STATEMENT
        )
        
        if result.success:
            logger.info("✅ Bank statement text extracted successfully!")
            logger.info(f"Processing time: {result.processing_time:.2f}s")
            logger.info(f"Method used: {result.method.value}")
            logger.info(f"Text length: {result.text_length} characters")
            logger.info(f"Word count: {result.word_count} words")
            
            # Show first 200 characters of extracted text
            if result.text:
                preview = result.text[:200] + "..." if len(result.text) > 200 else result.text
                logger.info(f"Text preview: {preview}")
        else:
            logger.error(f"❌ Failed to extract text: {result.error_message}")
            
    except Exception as e:
        logger.error(f"❌ Example failed: {e}")


async def example_invoice_processing():
    """Example: Process invoices using unified OCR service."""
    
    logger.info("=== Invoice Processing Example ===")
    
    try:
        from services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
        
        # Configure OCR service
        ai_config = {
            "provider_name": "anthropic",
            "model_name": "claude-3-haiku-20240307",
            "api_key": "your-anthropic-api-key",
        }
        
        config = OCRConfig(
            ai_config=ai_config,
            enable_ai_vision=True,
            min_confidence_threshold=0.8
        )
        
        service = UnifiedOCRService(config)
        
        # Process invoice
        file_path = "/path/to/invoice.pdf"  # Replace with actual file
        
        result = await service.extract_structured_data(
            file_path=file_path,
            document_type=DocumentType.INVOICE
        )
        
        if result.success:
            logger.info("✅ Invoice data extracted successfully!")
            logger.info(f"Processing time: {result.processing_time:.2f}s")
            
            # Access structured data
            invoice_data = result.structured_data
            if invoice_data:
                logger.info(f"Invoice Number: {invoice_data.get('invoice_number')}")
                logger.info(f"Amount: {invoice_data.get('amount')}")
                logger.info(f"Vendor: {invoice_data.get('vendor')}")
                logger.info(f"Due Date: {invoice_data.get('due_date')}")
        else:
            logger.error(f"❌ Failed to extract invoice data: {result.error_message}")
            
    except Exception as e:
        logger.error(f"❌ Example failed: {e}")


def example_service_status():
    """Example: Check OCR service status and capabilities."""
    
    logger.info("=== Service Status Example ===")
    
    try:
        from services.unified_ocr_service import UnifiedOCRService
        
        service = UnifiedOCRService()
        status = service.get_service_status()
        
        logger.info("📊 OCR Service Status:")
        logger.info(f"Service: {status['service']}")
        logger.info(f"Status: {status['status']}")
        
        logger.info("⚙️ Configuration:")
        config = status['config']
        for key, value in config.items():
            logger.info(f"  {key}: {value}")
        
        logger.info("🔧 Engine Availability:")
        engines = status['engines']
        
        text_engines = engines['text_extraction']
        logger.info(f"  Text Extraction:")
        logger.info(f"    PDF Extractor: {'✅' if text_engines['pdf_extractor_available'] else '❌'}")
        logger.info(f"    OCR Processor: {'✅' if text_engines['ocr_processor_available'] else '❌'}")
        
        structured_engines = engines['structured_extraction']
        logger.info(f"  Structured Extraction:")
        logger.info(f"    AI Vision: {'✅' if structured_engines['ai_vision_available'] else '❌'}")
        
    except Exception as e:
        logger.error(f"❌ Status check failed: {e}")


async def example_backward_compatibility():
    """Example: Using backward compatibility functions."""
    
    logger.info("=== Backward Compatibility Example ===")
    
    try:
        from services.unified_ocr_service import extract_expense_data, extract_bank_statement_text
        
        ai_config = {
            "provider_name": "ollama",
            "model_name": "llama3.2-vision:11b",
            "provider_url": "http://localhost:11434"
        }
        
        # Extract expense data (backward compatible)
        logger.info("✓ Testing expense data extraction...")
        try:
            expense_data = await extract_expense_data("/path/to/receipt.jpg", ai_config)
            logger.info(f"✅ Expense extraction: {len(expense_data)} fields extracted")
        except Exception as e:
            logger.info(f"⚠️ Expense extraction failed (expected with dummy path): {e}")
        
        # Extract bank statement text (backward compatible)
        logger.info("✓ Testing bank statement text extraction...")
        try:
            statement_text = extract_bank_statement_text("/path/to/statement.pdf", ai_config)
            logger.info(f"✅ Statement extraction: {len(statement_text)} characters extracted")
        except Exception as e:
            logger.info(f"⚠️ Statement extraction failed (expected with dummy path): {e}")
            
    except Exception as e:
        logger.error(f"❌ Backward compatibility test failed: {e}")


async def main():
    """Run all examples."""
    
    logger.info("🚀 Unified OCR Service Integration Examples")
    logger.info("=" * 50)
    
    # Check service status first
    example_service_status()
    
    # Run processing examples
    await example_expense_processing()
    await example_bank_statement_processing()
    await example_invoice_processing()
    
    # Test backward compatibility
    await example_backward_compatibility()
    
    logger.info("=" * 50)
    logger.info("✅ All examples completed!")
    
    logger.info("\n💡 Integration Tips:")
    logger.info("1. Configure AI providers in your application settings")
    logger.info("2. Use appropriate document types for better accuracy")
    logger.info("3. Handle errors gracefully with fallback strategies")
    logger.info("4. Monitor processing times and adjust timeouts as needed")
    logger.info("5. Use cloud storage for file persistence and audit trails")


if __name__ == "__main__":
    asyncio.run(main())