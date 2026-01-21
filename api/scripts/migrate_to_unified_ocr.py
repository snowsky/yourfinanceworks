#!/usr/bin/env python3
"""
Migration script to transition from separate OCR implementations to UnifiedOCRService.

This script helps validate the migration and provides tools for testing the new service.
"""

import logging
import sys
import os
import asyncio
from typing import Dict, Any, List

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_unified_ocr_availability():
    """Check if UnifiedOCRService is available and properly configured."""
    
    logger.info("🔍 Checking UnifiedOCRService availability...")
    
    try:
        from commercial.ai.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
        
        # Test service initialization
        service = UnifiedOCRService()
        status = service.get_service_status()
        
        logger.info("✅ UnifiedOCRService is available")
        logger.info(f"Service Status: {status['status']}")
        
        # Check engine availability
        engines = status['engines']
        text_engines = engines['text_extraction']
        structured_engines = engines['structured_extraction']
        
        logger.info("🔧 Engine Availability:")
        logger.info(f"  Text Extraction:")
        logger.info(f"    PDF Extractor: {'✅' if text_engines['pdf_extractor_available'] else '❌'}")
        logger.info(f"    OCR Processor: {'✅' if text_engines['ocr_processor_available'] else '❌'}")
        
        logger.info(f"  Structured Extraction:")
        logger.info(f"    AI Vision: {'✅' if structured_engines['ai_vision_available'] else '❌'}")
        
        return True, status
        
    except ImportError as e:
        logger.error(f"❌ UnifiedOCRService not available: {e}")
        return False, None
    except Exception as e:
        logger.error(f"❌ UnifiedOCRService check failed: {e}")
        return False, None


def check_legacy_services():
    """Check availability of legacy OCR services."""
    
    logger.info("🔍 Checking legacy OCR services...")
    
    legacy_status = {
        "bank_statement_service": False,
        "enhanced_pdf_extractor": False,
        "ocr_service": False,
        "statement_service": False
    }
    
    # Check bank statement OCR processor
    try:
        from commercial.ai_bank_statement.services.bank_statement_ocr_processor import BankStatementOCRProcessor
        legacy_status["bank_statement_service"] = True
        logger.info("✅ BankStatementOCRProcessor available")
    except ImportError:
        logger.warning("❌ BankStatementOCRProcessor not available")
    
    # Check enhanced PDF extractor
    try:
        from commercial.ai.services.enhanced_pdf_extractor import EnhancedPDFTextExtractor
        legacy_status["enhanced_pdf_extractor"] = True
        logger.info("✅ EnhancedPDFTextExtractor available")
    except ImportError:
        logger.warning("❌ EnhancedPDFTextExtractor not available")
    
    # Check OCR service
    try:
        from commercial.ai.services.ocr_service import _run_ocr
        legacy_status["ocr_service"] = True
        logger.info("✅ OCR service (_run_ocr) available")
    except ImportError:
        logger.warning("❌ OCR service not available")
    
    # Check statement service
    try:
        from core.services.statement_service import process_bank_pdf_with_llm
        legacy_status["statement_service"] = True
        logger.info("✅ Statement service available")
    except ImportError:
        logger.warning("❌ Statement service not available")
    
    return legacy_status


async def test_unified_vs_legacy(test_file_path: str = None):
    """Compare UnifiedOCRService performance with legacy services."""
    
    if not test_file_path:
        logger.info("⚠️ No test file provided, skipping performance comparison")
        return
    
    logger.info(f"🔄 Testing UnifiedOCRService vs Legacy services with: {test_file_path}")
    
    # Test UnifiedOCRService
    try:
        from commercial.ai.services.unified_ocr_service import UnifiedOCRService, DocumentType
        
        service = UnifiedOCRService()
        
        # Test text extraction
        logger.info("Testing unified text extraction...")
        text_result = service.extract_text(test_file_path, DocumentType.BANK_STATEMENT)
        
        if text_result.success:
            logger.info(f"✅ Unified text extraction: {text_result.text_length} chars in {text_result.processing_time:.2f}s")
        else:
            logger.warning(f"❌ Unified text extraction failed: {text_result.error_message}")
        
        # Test structured extraction
        logger.info("Testing unified structured extraction...")
        structured_result = await service.extract_structured_data(test_file_path, DocumentType.EXPENSE_RECEIPT)
        
        if structured_result.success:
            logger.info(f"✅ Unified structured extraction: {len(structured_result.structured_data or {})} fields in {structured_result.processing_time:.2f}s")
        else:
            logger.warning(f"❌ Unified structured extraction failed: {structured_result.error_message}")
            
    except Exception as e:
        logger.error(f"❌ UnifiedOCRService test failed: {e}")
    
    # Test legacy services (if available)
    try:
        from commercial.ai.services.enhanced_pdf_extractor import EnhancedPDFTextExtractor
        
        logger.info("Testing legacy PDF extractor...")
        extractor = EnhancedPDFTextExtractor()
        legacy_result = extractor.extract_text(test_file_path)
        
        if legacy_result.text:
            logger.info(f"✅ Legacy text extraction: {len(legacy_result.text)} chars in {legacy_result.processing_time:.2f}s")
        else:
            logger.warning("❌ Legacy text extraction failed")
            
    except Exception as e:
        logger.warning(f"Legacy PDF extractor test failed: {e}")


def generate_migration_report():
    """Generate a comprehensive migration report."""
    
    logger.info("📊 Generating Migration Report...")
    
    # Check services
    unified_available, unified_status = check_unified_ocr_availability()
    legacy_status = check_legacy_services()
    
    report = {
        "unified_ocr_service": {
            "available": unified_available,
            "status": unified_status
        },
        "legacy_services": legacy_status,
        "migration_readiness": {
            "ready": unified_available,
            "blocking_issues": [],
            "recommendations": []
        }
    }
    
    # Analyze migration readiness
    if not unified_available:
        report["migration_readiness"]["blocking_issues"].append("UnifiedOCRService not available")
        report["migration_readiness"]["recommendations"].append("Install and configure UnifiedOCRService")
    
    if unified_available and unified_status:
        engines = unified_status['engines']
        
        if not engines['text_extraction']['pdf_extractor_available']:
            report["migration_readiness"]["recommendations"].append("Configure PDF extractor for text extraction")
        
        if not engines['structured_extraction']['ai_vision_available']:
            report["migration_readiness"]["recommendations"].append("Configure AI vision for structured extraction")
    
    # Print report
    logger.info("=" * 60)
    logger.info("MIGRATION READINESS REPORT")
    logger.info("=" * 60)
    
    logger.info(f"UnifiedOCRService Available: {'✅' if unified_available else '❌'}")
    
    logger.info("Legacy Services:")
    for service, available in legacy_status.items():
        logger.info(f"  {service}: {'✅' if available else '❌'}")
    
    logger.info(f"Migration Ready: {'✅' if report['migration_readiness']['ready'] else '❌'}")
    
    if report["migration_readiness"]["blocking_issues"]:
        logger.info("Blocking Issues:")
        for issue in report["migration_readiness"]["blocking_issues"]:
            logger.info(f"  ❌ {issue}")
    
    if report["migration_readiness"]["recommendations"]:
        logger.info("Recommendations:")
        for rec in report["migration_readiness"]["recommendations"]:
            logger.info(f"  💡 {rec}")
    
    return report


def validate_configuration():
    """Validate OCR configuration for the unified service."""
    
    logger.info("⚙️ Validating OCR Configuration...")
    
    try:
        from commercial.ai.services.unified_ocr_service import OCRConfig
        
        # Test default configuration
        default_config = OCRConfig()
        logger.info("✅ Default OCRConfig created successfully")
        
        # Test with AI configuration
        ai_config = {
            "provider_name": "test",
            "model_name": "test-model",
            "api_key": "test-key",
            "provider_url": "http://localhost:11434"
        }
        
        custom_config = OCRConfig(
            ai_config=ai_config,
            enable_unstructured=True,
            enable_ai_vision=True,
            timeout_seconds=120
        )
        logger.info("✅ Custom OCRConfig created successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        return False


async def main():
    """Run migration validation and testing."""
    
    logger.info("🚀 UnifiedOCRService Migration Validator")
    logger.info("=" * 50)
    
    # Step 1: Check service availability
    unified_available, _ = check_unified_ocr_availability()
    legacy_status = check_legacy_services()
    
    # Step 2: Validate configuration
    config_valid = validate_configuration()
    
    # Step 3: Generate migration report
    report = generate_migration_report()
    
    # Step 4: Test with sample file (if provided)
    test_file = os.getenv("TEST_FILE_PATH")
    if test_file and os.path.exists(test_file):
        await test_unified_vs_legacy(test_file)
    else:
        logger.info("💡 Set TEST_FILE_PATH environment variable to test with a sample file")
    
    # Step 5: Provide migration guidance
    logger.info("=" * 50)
    logger.info("MIGRATION GUIDANCE")
    logger.info("=" * 50)
    
    if report["migration_readiness"]["ready"]:
        logger.info("✅ System is ready for migration to UnifiedOCRService!")
        logger.info("Next steps:")
        logger.info("1. Update code to use UnifiedOCRService")
        logger.info("2. Test with your document types")
        logger.info("3. Monitor performance and accuracy")
        logger.info("4. Gradually phase out legacy services")
    else:
        logger.info("❌ System is not ready for migration")
        logger.info("Please address the blocking issues first")
    
    logger.info("=" * 50)
    logger.info("Migration validation completed!")
    
    return 0 if report["migration_readiness"]["ready"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))