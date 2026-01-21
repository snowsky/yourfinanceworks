"""
Unified OCR Service

This module provides a unified interface for OCR operations across different document types:
- Text extraction (bank statements, documents)
- Structured data extraction (expenses, invoices)

The service intelligently routes requests to the appropriate extraction engine
based on document type and extraction requirements.
"""

import logging
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

from core.utils.file_validation import validate_file_path

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Supported document types for OCR processing."""
    BANK_STATEMENT = "bank_statement"
    EXPENSE_RECEIPT = "expense_receipt"
    INVOICE = "invoice"
    GENERIC_DOCUMENT = "generic_document"


class ExtractionMethod(Enum):
    """Available extraction methods."""
    UNSTRUCTURED_OCR = "unstructured_ocr"  # For text extraction
    AI_VISION = "ai_vision"  # For structured data extraction
    PDF_LOADER = "pdf_loader"  # For simple PDF text extraction
    HYBRID = "hybrid"  # Combination of methods


@dataclass
class ExtractionResult:
    """Result of OCR extraction operation."""
    success: bool
    method: ExtractionMethod
    document_type: DocumentType
    processing_time: float
    
    # Text extraction results
    text: Optional[str] = None
    text_length: Optional[int] = None
    word_count: Optional[int] = None
    
    # Structured data extraction results
    structured_data: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class OCRConfig:
    """Configuration for OCR operations."""
    # AI configuration
    ai_config: Optional[Dict[str, Any]] = None
    
    # Text extraction settings
    enable_unstructured: bool = True
    enable_tesseract_fallback: bool = True
    
    # Structured extraction settings
    enable_ai_vision: bool = True
    enable_fallback_parsing: bool = True
    
    # Performance settings
    timeout_seconds: int = 300
    max_retries: int = 3
    
    # Quality settings
    min_text_threshold: int = 50
    min_confidence_threshold: float = 0.7


class TextExtractionEngine:
    """Engine for extracting plain text from documents."""
    
    def __init__(self, config: OCRConfig):
        self.config = config
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize text extraction components."""
        try:
            # Initialize enhanced PDF extractor with OCR fallback
            from commercial.ai.services.enhanced_pdf_extractor import EnhancedPDFTextExtractor
            self.pdf_extractor = EnhancedPDFTextExtractor(self.config.ai_config)
            logger.info("✅ Enhanced PDF text extractor initialized")
        except ImportError as e:
            logger.warning(f"Enhanced PDF extractor not available: {e}")
            self.pdf_extractor = None
        
        try:
            # Initialize bank statement OCR processor
            from commercial.ai_bank_statement.services.bank_statement_ocr_processor import BankStatementOCRProcessor
            self.ocr_processor = BankStatementOCRProcessor(self.config.ai_config)
            logger.info("✅ Bank statement OCR processor initialized")
        except ImportError as e:
            logger.warning(f"Bank statement OCR processor not available: {e}")
            self.ocr_processor = None
    
    def extract(self, file_path: str, document_type: DocumentType) -> ExtractionResult:
        """
        Extract text from document.
        
        Args:
            file_path: Path to the document file
            document_type: Type of document being processed
            
        Returns:
            ExtractionResult with extracted text and metadata
        """
        start_time = time.time()
        
        try:
            # Validate file path (don't require file to exist yet for batch files)
            safe_path = validate_file_path(file_path, must_exist=False)
            
            # Choose extraction method based on document type and available components
            if document_type == DocumentType.BANK_STATEMENT and self.pdf_extractor:
                result = self.pdf_extractor.extract_text(safe_path)
                
                return ExtractionResult(
                    success=True,
                    method=ExtractionMethod.UNSTRUCTURED_OCR if result.method == "ocr" else ExtractionMethod.PDF_LOADER,
                    document_type=document_type,
                    processing_time=result.processing_time,
                    text=result.text,
                    text_length=result.text_length,
                    word_count=result.word_count,
                    confidence_score=result.confidence_score,
                    metadata=result.metadata
                )
            
            elif self.ocr_processor:
                # Fallback to OCR processor
                text = self.ocr_processor.extract_with_ocr(safe_path)
                processing_time = time.time() - start_time
                
                return ExtractionResult(
                    success=True,
                    method=ExtractionMethod.UNSTRUCTURED_OCR,
                    document_type=document_type,
                    processing_time=processing_time,
                    text=text,
                    text_length=len(text),
                    word_count=len(text.split()),
                    metadata={"file_path": safe_path}
                )
            
            else:
                # No extraction methods available
                return ExtractionResult(
                    success=False,
                    method=ExtractionMethod.PDF_LOADER,
                    document_type=document_type,
                    processing_time=time.time() - start_time,
                    error_message="No text extraction methods available"
                )
                
        except Exception as e:
            logger.error(f"Text extraction failed for {file_path}: {e}")
            return ExtractionResult(
                success=False,
                method=ExtractionMethod.PDF_LOADER,
                document_type=document_type,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )


class StructuredDataEngine:
    """Engine for extracting structured data using AI vision models."""
    
    def __init__(self, config: OCRConfig):
        self.config = config
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize structured data extraction components."""
        try:
            # Import OCR service functions
            from commercial.ai.services.ocr_service import _run_ocr
            self.ai_ocr_function = _run_ocr
            logger.info("✅ AI vision OCR function initialized")
        except ImportError as e:
            logger.warning(f"AI vision OCR not available: {e}")
            self.ai_ocr_function = None
    
    async def extract(self, file_path: str, document_type: DocumentType, schema: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """
        Extract structured data from document using AI vision models.
        
        Args:
            file_path: Path to the document file
            document_type: Type of document being processed
            schema: Expected data schema (optional)
            
        Returns:
            ExtractionResult with structured data and metadata
        """
        start_time = time.time()
        
        try:
            # Validate file path (don't require file to exist yet for batch files)
            safe_path = validate_file_path(file_path, must_exist=False)
            
            if not self.ai_ocr_function:
                return ExtractionResult(
                    success=False,
                    method=ExtractionMethod.AI_VISION,
                    document_type=document_type,
                    processing_time=time.time() - start_time,
                    error_message="AI vision OCR not available"
                )
            
            # Create custom prompt based on document type
            custom_prompt = self._create_prompt_for_document_type(document_type, schema)
            
            # Run AI OCR extraction
            result = await self.ai_ocr_function(
                file_path=safe_path,
                custom_prompt=custom_prompt,
                ai_config=self.config.ai_config
            )
            
            processing_time = time.time() - start_time
            
            if isinstance(result, dict) and "error" not in result:
                return ExtractionResult(
                    success=True,
                    method=ExtractionMethod.AI_VISION,
                    document_type=document_type,
                    processing_time=processing_time,
                    structured_data=result,
                    metadata={"file_path": safe_path, "schema": schema}
                )
            else:
                error_msg = result.get("error", "Unknown AI vision error") if isinstance(result, dict) else "AI vision processing failed"
                return ExtractionResult(
                    success=False,
                    method=ExtractionMethod.AI_VISION,
                    document_type=document_type,
                    processing_time=processing_time,
                    error_message=error_msg
                )
                
        except Exception as e:
            logger.error(f"Structured data extraction failed for {file_path}: {e}")
            return ExtractionResult(
                success=False,
                method=ExtractionMethod.AI_VISION,
                document_type=document_type,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def _create_prompt_for_document_type(self, document_type: DocumentType, schema: Optional[Dict[str, Any]] = None) -> str:
        """Create appropriate prompt based on document type."""
        
        if document_type == DocumentType.EXPENSE_RECEIPT:
            return (
                "You are an OCR parser for expense receipts. Extract key expense fields and respond ONLY with compact JSON. "
                "Required keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, "
                "total_amount, payment_method, reference_number, notes, receipt_timestamp (YYYY-MM-DD HH:MM:SS if time is visible on receipt). "
                "IMPORTANT: For receipt_timestamp, look carefully for any time information on the receipt (like '14:32', '2:45 PM', '10:15 AM', etc.). "
                "If you find a time, combine it with the date to create a full timestamp. If only date is visible, set receipt_timestamp to null. "
                "If a field is unknown, set it to null. Do not include any prose."
            )
        
        elif document_type == DocumentType.INVOICE:
            return (
                "You are an OCR parser for invoices. Extract key invoice fields and respond ONLY with compact JSON. "
                "Required keys: invoice_number, amount, currency, invoice_date (YYYY-MM-DD), due_date (YYYY-MM-DD), "
                "vendor, customer, tax_rate, tax_amount, total_amount, payment_terms, notes. "
                "If a field is unknown, set it to null. Do not include any prose."
            )
        
        elif document_type == DocumentType.BANK_STATEMENT:
            return (
                "You are an OCR parser for bank statements. Extract transaction data and respond ONLY with compact JSON. "
                "Return an array of transactions with keys: date (YYYY-MM-DD), description, amount, transaction_type, balance. "
                "If a field is unknown, set it to null. Do not include any prose."
            )
        
        else:
            return (
                "You are an OCR parser. Extract key information from this document and respond ONLY with compact JSON. "
                "Include relevant fields based on the document content. If a field is unknown, set it to null. "
                "Do not include any prose."
            )


class UnifiedOCRService:
    """
    Unified OCR service supporting multiple extraction strategies.
    
    This service provides a single interface for all OCR operations while
    intelligently routing requests to the appropriate extraction engine.
    """
    
    def __init__(self, config: Optional[OCRConfig] = None):
        """
        Initialize the unified OCR service.
        
        Args:
            config: OCR configuration (optional, will use defaults if not provided)
        """
        self.config = config or OCRConfig()
        
        # Initialize extraction engines
        self.text_engine = TextExtractionEngine(self.config)
        self.structured_engine = StructuredDataEngine(self.config)
        
        logger.info("🚀 UnifiedOCRService initialized")
    
    def extract_text(self, file_path: str, document_type: Optional[DocumentType] = None) -> ExtractionResult:
        """
        Extract plain text from document.
        
        Args:
            file_path: Path to the document file
            document_type: Type of document (auto-detected if not provided)
            
        Returns:
            ExtractionResult with extracted text
        """
        if document_type is None:
            document_type = self._detect_document_type(file_path)
        
        logger.info(f"Extracting text from {document_type.value}: {Path(file_path).name}")
        return self.text_engine.extract(file_path, document_type)
    
    async def extract_structured_data(
        self, 
        file_path: str, 
        document_type: Optional[DocumentType] = None,
        schema: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract structured data from document using AI vision models.
        
        Args:
            file_path: Path to the document file
            document_type: Type of document (auto-detected if not provided)
            schema: Expected data schema (optional)
            
        Returns:
            ExtractionResult with structured data
        """
        if document_type is None:
            document_type = self._detect_document_type(file_path)
        
        logger.info(f"Extracting structured data from {document_type.value}: {Path(file_path).name}")
        return await self.structured_engine.extract(file_path, document_type, schema)
    
    def _detect_document_type(self, file_path: str) -> DocumentType:
        """
        Auto-detect document type based on file name and content patterns.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Detected document type
        """
        file_name = Path(file_path).name.lower()
        
        # Simple heuristics based on filename
        if any(keyword in file_name for keyword in ['statement', 'bank', 'account']):
            return DocumentType.BANK_STATEMENT
        elif any(keyword in file_name for keyword in ['receipt', 'expense', 'purchase']):
            return DocumentType.EXPENSE_RECEIPT
        elif any(keyword in file_name for keyword in ['invoice', 'bill', 'inv']):
            return DocumentType.INVOICE
        else:
            return DocumentType.GENERIC_DOCUMENT
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        Get status of OCR service components.
        
        Returns:
            Dictionary with service status information
        """
        return {
            "service": "UnifiedOCRService",
            "status": "active",
            "config": {
                "enable_unstructured": self.config.enable_unstructured,
                "enable_ai_vision": self.config.enable_ai_vision,
                "timeout_seconds": self.config.timeout_seconds,
                "max_retries": self.config.max_retries
            },
            "engines": {
                "text_extraction": {
                    "pdf_extractor_available": self.text_engine.pdf_extractor is not None,
                    "ocr_processor_available": self.text_engine.ocr_processor is not None
                },
                "structured_extraction": {
                    "ai_vision_available": self.structured_engine.ai_ocr_function is not None
                }
            }
        }


# Convenience functions for backward compatibility
def create_unified_ocr_service(ai_config: Optional[Dict[str, Any]] = None) -> UnifiedOCRService:
    """
    Create a unified OCR service instance with the given AI configuration.
    
    Args:
        ai_config: AI configuration dictionary
        
    Returns:
        UnifiedOCRService instance
    """
    config = OCRConfig(ai_config=ai_config)
    return UnifiedOCRService(config)


async def extract_expense_data(file_path: str, ai_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract structured data from expense receipt (backward compatibility).
    
    Args:
        file_path: Path to the expense receipt file
        ai_config: AI configuration dictionary
        
    Returns:
        Extracted expense data
    """
    service = create_unified_ocr_service(ai_config)
    result = await service.extract_structured_data(file_path, DocumentType.EXPENSE_RECEIPT)
    
    if result.success:
        return result.structured_data or {}
    else:
        raise Exception(result.error_message or "Failed to extract expense data")


def extract_bank_statement_text(file_path: str, ai_config: Optional[Dict[str, Any]] = None) -> str:
    """
    Extract text from bank statement (backward compatibility).
    
    Args:
        file_path: Path to the bank statement file
        ai_config: AI configuration dictionary
        
    Returns:
        Extracted text
    """
    service = create_unified_ocr_service(ai_config)
    result = service.extract_text(file_path, DocumentType.BANK_STATEMENT)
    
    if result.success:
        return result.text or ""
    else:
        raise Exception(result.error_message or "Failed to extract bank statement text")