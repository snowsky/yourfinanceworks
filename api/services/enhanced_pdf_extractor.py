"""
Enhanced PDF Text Extraction with OCR Fallback

This module provides enhanced PDF text extraction capabilities with automatic
OCR fallback when standard PDF text extraction yields insufficient results.
"""

import os
import re
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from dataclasses import dataclass

from settings.ocr_config import get_ocr_config, is_ocr_available
from exceptions.bank_ocr_exceptions import (
    OCRProcessingError,
    OCRInvalidFileError
)
from utils.file_validation import validate_file_path
from utils.text_sufficiency_validator import TextSufficiencyValidator

logger = logging.getLogger(__name__)

# Optional imports with fallbacks
try:
    from langchain_community.document_loaders import (
        PyPDFLoader,
        PyMuPDFLoader,
        PDFMinerLoader,
        PyPDFium2Loader,
        PDFPlumberLoader,
        UnstructuredPDFLoader,
    )
    from langchain_core.documents import Document
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not available - PDF loading will be limited")
    
    class Document:
        def __init__(self, page_content="", metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}
    
    LANGCHAIN_AVAILABLE = False


@dataclass
class TextExtractionResult:
    """Result of text extraction operation."""
    text: str
    method: str  # "pdf_loader" or "ocr"
    processing_time: float
    text_length: int
    word_count: int
    confidence_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class EnhancedPDFTextExtractor:
    """
    Enhanced PDF text extractor with OCR fallback capability.

    This class handles both PDF loader and OCR extraction methods,
    implementing text quality validation logic to determine when OCR is needed.
    """

    def __init__(self, ai_config: Optional[Dict] = None):
        """
        Initialize the enhanced PDF text extractor.

        Args:
            ai_config: AI configuration dictionary (optional)
        """
        self.ai_config = ai_config
        self.ocr_config = get_ocr_config()

        # Initialize PDF loaders
        self.pdf_loaders = self._initialize_pdf_loaders()

        # Initialize text sufficiency validator
        self.text_validator = TextSufficiencyValidator()

        # Initialize OCR processor (lazy loading)
        self._ocr_processor = None

        logger.info(f"EnhancedPDFTextExtractor initialized with OCR {'enabled' if self.ocr_config.enabled else 'disabled'}")

    def _initialize_pdf_loaders(self) -> Dict[str, Dict[str, Any]]:
        """Initialize available PDF loaders."""
        loaders = {}

        if not LANGCHAIN_AVAILABLE:
            logger.warning("LangChain not available - PDF loading will be limited")
            return loaders

        # Try to initialize each loader
        loader_configs = [
            ('pymupdf', PyMuPDFLoader, 'High-quality text extraction with metadata', 'Most PDF types, good balance of speed and quality'),
            ('pdfplumber', PDFPlumberLoader, 'Excellent for tables and structured data', 'Bank statements with tables'),
            ('pdfium2', PyPDFium2Loader, 'Google\'s PDF library, fast and reliable', 'Modern PDFs, good performance'),
            ('pypdf', PyPDFLoader, 'Fast, basic PDF text extraction', 'Simple text-based PDFs'),
            ('pdfminer', PDFMinerLoader, 'Detailed text extraction with layout info', 'Complex layouts, precise text positioning'),
            ('unstructured', UnstructuredPDFLoader, 'Advanced preprocessing and cleaning', 'Messy or poorly formatted PDFs')
        ]

        for name, loader_class, description, best_for in loader_configs:
            try:
                # Test if the loader can be imported and instantiated
                test_loader = loader_class
                loaders[name] = {
                    'class': loader_class,
                    'description': description,
                    'best_for': best_for
                }
                logger.debug(f"PDF loader '{name}' available")
            except Exception as e:
                logger.debug(f"PDF loader '{name}' not available: {e}")

        logger.info(f"Initialized {len(loaders)} PDF loaders: {list(loaders.keys())}")
        return loaders

    @property
    def ocr_processor(self):
        """Lazy-loaded OCR processor."""
        if self._ocr_processor is None:
            from .bank_statement_ocr_processor import BankStatementOCRProcessor
            self._ocr_processor = BankStatementOCRProcessor(self.ai_config)
        return self._ocr_processor

    def extract_text(self, pdf_path: str) -> TextExtractionResult:
        """
        Extract text from PDF with OCR fallback.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            TextExtractionResult with extracted text and metadata

        Raises:
            OCRInvalidFileError: If the file is invalid
            OCRProcessingError: If both PDF and OCR extraction fail
        """
        import time

        # Validate file path
        try:
            safe_path = validate_file_path(pdf_path)
            pdf_path = safe_path
        except ValueError as e:
            raise OCRInvalidFileError(f"Invalid PDF path: {e}", file_path=pdf_path)

        if not Path(pdf_path).exists():
            raise OCRInvalidFileError(f"PDF file not found: {pdf_path}", file_path=pdf_path)

        logger.info(f"Starting text extraction for: {pdf_path}")

        # Try PDF loaders first
        start_time = time.time()
        try:
            text = self._extract_with_pdf_loaders(pdf_path)
            processing_time = time.time() - start_time
            
            text_metrics = self.text_validator.validate_text_sufficiency(text)
            if text_metrics.is_sufficient:
                result = TextExtractionResult(
                    text=text,
                    method="pdf_loader",
                    processing_time=processing_time,
                    text_length=text_metrics.text_length,
                    word_count=text_metrics.word_count,
                    metadata={
                        "pdf_path": pdf_path,
                        "quality_score": text_metrics.quality_score,
                        "validation_reasons": text_metrics.reasons
                    }
                )
                logger.info(f"PDF extraction successful: {result.text_length} chars, {result.word_count} words, quality={text_metrics.quality_score:.1f}")
                self._track_extraction_method("pdf_loader", pdf_path, processing_time)
                return result
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")

        # Fallback to OCR if enabled
        if not self.ocr_config.enabled:
            logger.warning(f"OCR is disabled, cannot process scanned document: {pdf_path}")
            # Return the insufficient text with a warning rather than failing completely
            result = TextExtractionResult(
                text=text if 'text' in locals() else "",
                method="pdf_loader_insufficient",
                processing_time=processing_time,
                text_length=len(text) if 'text' in locals() else 0,
                word_count=len(text.split()) if 'text' in locals() else 0,
                metadata={
                    "pdf_path": pdf_path,
                    "warning": "OCR disabled, text may be insufficient for processing"
                }
            )
            return result

        if not is_ocr_available():
            logger.warning(f"OCR dependencies not available, cannot process scanned document: {pdf_path}")
            # Return the insufficient text with a warning rather than failing completely
            result = TextExtractionResult(
                text=text if 'text' in locals() else "",
                method="pdf_loader_insufficient",
                processing_time=processing_time,
                text_length=len(text) if 'text' in locals() else 0,
                word_count=len(text.split()) if 'text' in locals() else 0,
                metadata={
                    "pdf_path": pdf_path,
                    "warning": "OCR dependencies not available, text may be insufficient for processing"
                }
            )
            return result

        logger.info(f"PDF extraction yielded insufficient text, falling back to OCR for {pdf_path}")

        # Notify user about OCR fallback
        try:
            from utils.ocr_notifications import notify_ocr_fallback_triggered
            notify_ocr_fallback_triggered(
                pdf_path, 
                "PDF text extraction yielded insufficient text for processing"
            )
        except ImportError:
            pass

        # Try OCR extraction
        start_time = time.time()
        try:
            ocr_text = self.ocr_processor.extract_with_ocr(pdf_path)
            processing_time = time.time() - start_time

            result = TextExtractionResult(
                text=ocr_text,
                method="ocr",
                processing_time=processing_time,
                text_length=len(ocr_text),
                word_count=len(ocr_text.split()),
                metadata={"pdf_path": pdf_path}
            )
            logger.info(f"OCR extraction successful: {result.text_length} chars, {result.word_count} words")
            self._track_extraction_method("ocr", pdf_path, processing_time)
            return result

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise OCRProcessingError(
                f"Both PDF and OCR extraction failed: {e}",
                details={"pdf_path": pdf_path, "ocr_error": str(e)}
            )

    def _extract_with_pdf_loaders(self, pdf_path: str) -> str:
        """
        Extract text using PDF loaders with automatic fallback.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text

        Raises:
            Exception: If all PDF loaders fail
        """
        if not LANGCHAIN_AVAILABLE:
            raise Exception("LangChain not available for PDF loading")
        
        # Try loaders in order of preference
        loader_order = ['pymupdf', 'pdfplumber', 'pdfium2', 'pypdf', 'pdfminer', 'unstructured']
        last_error = None

        for loader_name in loader_order:
            if loader_name not in self.pdf_loaders:
                continue

            try:
                logger.debug(f"Trying {loader_name} loader...")
                loader_class = self.pdf_loaders[loader_name]['class']
                loader = loader_class(pdf_path)

                documents = loader.load()

                if documents and any(doc.page_content.strip() for doc in documents):
                    # Combine all document content
                    text = "\n\n".join(doc.page_content for doc in documents if doc.page_content.strip())
                    logger.debug(f"Successfully loaded with {loader_name}: {len(text)} characters")
                    return text

            except Exception as e:
                last_error = e
                logger.debug(f"{loader_name} failed: {str(e)[:100]}...")
                continue

        raise Exception(f"All PDF loaders failed. Last error: {last_error}")

    def _track_extraction_method(self, method: str, pdf_path: str, processing_time: float) -> None:
        """
        Track extraction method usage for analytics.
        
        Args:
            method: Extraction method used ("pdf_loader" or "ocr")
            pdf_path: Path to the processed file
            processing_time: Time taken for extraction
        """
        logger.info(
            f"Extraction method tracking: method={method} "
            f"file={Path(pdf_path).name} time={processing_time:.2f}s"
        )

        # Track using the analytics service
        try:
            from services.bank_statement_analytics_service import track_bank_statement_extraction
            from models.database import get_db
            
            # Get database session for tracking
            db = next(get_db())
            
            # Track the extraction attempt
            track_bank_statement_extraction(
                db=db,
                method=method,
                pdf_path=pdf_path,
                processing_time=processing_time,
                text_length=0,  # Will be updated by caller if available
                word_count=0,   # Will be updated by caller if available
                success=True,   # Assume success if we're tracking
                ai_config=self.ai_config
            )
            
        except Exception as e:
            logger.warning(f"Failed to track extraction method with analytics service: {e}")
            # Don't fail the main operation if tracking fails
    
    def get_available_loaders(self) -> List[str]:
        """Get list of available PDF loaders."""
        return list(self.pdf_loaders.keys())
    
    def get_loader_info(self, loader_name: str) -> Optional[Dict[str, str]]:
        """Get information about a specific PDF loader."""
        return self.pdf_loaders.get(loader_name)