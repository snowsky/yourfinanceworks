"""
Bank Statement OCR Processor

This module provides OCR processing capabilities for bank statements using
UnstructuredLoader with support for both local Tesseract and Unstructured API modes.
"""

import os
import signal
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from commercial.ai.settings.ocr_config import get_ocr_config, check_ocr_dependencies
from commercial.ai.exceptions.bank_ocr_exceptions import (
    OCRUnavailableError,
    OCRTimeoutError,
    OCRProcessingError,
    OCRDependencyMissingError,
    OCRConfigurationError
)
from core.utils.file_validation import validate_file_path

logger = logging.getLogger(__name__)

# Optional imports with fallbacks
try:
    from unstructured.partition.pdf import partition_pdf
    from unstructured.partition.auto import partition
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    logger.warning("unstructured not available - OCR functionality will be limited")
    UNSTRUCTURED_AVAILABLE = False
    
    # Fallback functions
    def partition_pdf(*args, **kwargs):
        raise ImportError("unstructured package not available")
    
    def partition(*args, **kwargs):
        raise ImportError("unstructured package not available")

class Document:
    """Simple document class for compatibility."""
    def __init__(self, page_content="", metadata=None):
        self.page_content = page_content
        self.metadata = metadata or {}


class TimeoutError(Exception):
    """Custom timeout exception for Python < 3.10 compatibility."""
    pass


@contextmanager
def timeout(seconds: int):
    """
    Context manager for implementing timeouts.

    Args:
        seconds: Timeout duration in seconds

    Raises:
        TimeoutError: If operation exceeds timeout
    """
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Restore the old signal handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class BankStatementOCRProcessor:
    """
    OCR processor for bank statements using UnstructuredLoader.

    Supports both local Tesseract and cloud-based Unstructured API processing
    with comprehensive timeout handling and error recovery.
    """

    def __init__(self, ai_config: Optional[Dict] = None, db_session: Optional[Any] = None):
        """
        Initialize the OCR processor.

        Args:
            ai_config: AI configuration dictionary (optional)
            db_session: Database session for AI config fallback (optional)
        """
        self.ai_config = ai_config
        self.db_session = db_session
        self.ocr_config = get_ocr_config()

        # Check dependencies
        self.dependencies = check_ocr_dependencies()
        self._validate_dependencies()

        # Initialize OCR loader
        self.ocr_loader_factory = self._initialize_ocr_loader()

        logger.info(f"BankStatementOCRProcessor initialized with {'API' if self.ocr_config.use_unstructured_api else 'local'} mode")

    def _validate_dependencies(self) -> None:
        """Validate that required dependencies are available."""
        if not UNSTRUCTURED_AVAILABLE:
            raise OCRDependencyMissingError(
                "unstructured package is required for OCR functionality",
                missing_dependency="unstructured"
            )

        if not self.dependencies["unstructured"]:
            raise OCRDependencyMissingError(
                "unstructured package is required for OCR functionality",
                missing_dependency="unstructured"
            )

        if self.ocr_config.use_unstructured_api:
            if not self.ocr_config.unstructured_api_key:
                raise OCRConfigurationError(
                    "Unstructured API key is required when using API mode",
                    config_key="unstructured_api_key"
                )
        else:
            # For local processing, we need tesseract
            if not self.dependencies["pytesseract"] or not self.dependencies["tesseract_binary"]:
                raise OCRDependencyMissingError(
                    "pytesseract and tesseract binary are required for local OCR processing",
                    missing_dependency="tesseract"
                )

    def _initialize_ocr_loader(self):
        """
        Initialize unstructured partition function factory.

        Returns:
            Function that processes files using unstructured
        """
        if not UNSTRUCTURED_AVAILABLE:
            raise OCRUnavailableError("unstructured package not available")

        def process_file(file_path: str) -> List[Document]:
            """Process file using unstructured and return Document objects."""

            if self.ocr_config.use_unstructured_api:
                logger.debug("Processing with Unstructured API")
                elements = partition(
                    filename=file_path,
                    strategy=self.ocr_config.strategy,
                    partition_via_api=True,
                    api_key=self.ocr_config.unstructured_api_key,
                    api_url=self.ocr_config.unstructured_api_url
                )
            else:
                logger.debug("Processing with local unstructured")

                # Set tesseract configuration if available
                if self.ocr_config.tesseract_cmd:
                    os.environ["TESSERACT_CMD"] = self.ocr_config.tesseract_cmd

                # Use partition_pdf for PDF files, partition for others
                if file_path.lower().endswith('.pdf'):
                    elements = partition_pdf(
                        filename=file_path,
                        strategy=self.ocr_config.strategy,
                        infer_table_structure=True,
                        extract_images_in_pdf=True
                    )
                else:
                    elements = partition(
                        filename=file_path,
                        strategy=self.ocr_config.strategy
                    )

            # Convert elements to Document objects
            documents = []
            for element in elements:
                doc = Document(
                    page_content=str(element),
                    metadata={
                        "element_type": element.category if hasattr(element, 'category') else 'unknown',
                        "source": file_path
                    }
                )
                documents.append(doc)

            return documents

        return process_file

    def get_effective_ai_config(self) -> Optional[Dict[str, Any]]:
        """
        Get effective AI configuration with fallback to environment variables.

        Returns:
            AI configuration dictionary or None
        """
        if self.ai_config:
            return self.ai_config

        if self.db_session:
            try:
                from commercial.ai.services.ai_config_service import AIConfigService
                return AIConfigService.get_ai_config(
                    self.db_session,
                    component="bank_statement",
                    require_ocr=True
                )
            except Exception as e:
                logger.warning(f"Failed to get AI config from service: {e}")

        return None

    def extract_with_ocr(self, pdf_path: str) -> str:
        """
        Extract text using OCR with timeout handling.
        
        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text

        Raises:
            OCRUnavailableError: If OCR is not available
            OCRTimeoutError: If processing exceeds timeout
            OCRProcessingError: If OCR processing fails
        """
        # Validate file path
        try:
            safe_path = validate_file_path(pdf_path)
            pdf_path = safe_path
        except ValueError as e:
            raise OCRProcessingError(f"Invalid PDF path: {e}", details={"pdf_path": pdf_path})

        if not Path(pdf_path).exists():
            raise OCRProcessingError(f"PDF file not found: {pdf_path}", details={"pdf_path": pdf_path})

        if not self.ocr_loader_factory:
            raise OCRUnavailableError("OCR loader not initialized")

        logger.info(f"Starting OCR extraction for: {pdf_path}")
        logger.info(f"OCR timeout: {self.ocr_config.timeout_seconds} seconds")

        try:
            with timeout(self.ocr_config.timeout_seconds):
                documents = self.ocr_loader_factory(pdf_path)

                # Combine all document content
                text_parts = []
                for doc in documents:
                    if doc.page_content and doc.page_content.strip():
                        text_parts.append(doc.page_content.strip())

                text = "\n\n".join(text_parts)

                if not text.strip():
                    raise OCRProcessingError(
                        "OCR extraction yielded no text",
                        details={"pdf_path": pdf_path, "document_count": len(documents)}
                    )

                logger.info(f"OCR extracted {len(text)} characters from {Path(pdf_path).name}")
                return text

        except TimeoutError:
            raise OCRTimeoutError(
                f"OCR processing timed out after {self.ocr_config.timeout_seconds} seconds",
                timeout_seconds=self.ocr_config.timeout_seconds,
                details={"pdf_path": pdf_path}
            )
        except Exception as e:
            if isinstance(e, (OCRTimeoutError, OCRProcessingError)):
                raise

            # Wrap other exceptions
            error_msg = f"OCR processing failed: {str(e)}"
            logger.error(error_msg)
            raise OCRProcessingError(
                error_msg,
                details={"pdf_path": pdf_path, "original_error": str(e)},
                is_transient=self._is_transient_error(e)
            )

    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and might resolve on retry.

        Args:
            error: The exception to check

        Returns:
            True if the error is likely transient
        """
        error_str = str(error).lower()
        transient_patterns = [
            "connection",
            "network",
            "timeout",
            "temporary",
            "service unavailable",
            "rate limit",
            "server error",
            "503",
            "502",
            "504"
        ]

        return any(pattern in error_str for pattern in transient_patterns)

    def test_ocr_availability(self) -> Dict[str, Any]:
        """
        Test OCR availability and return status information.

        Returns:
            Dictionary with availability status and details
        """
        status = {
            "available": False,
            "mode": "api" if self.ocr_config.use_unstructured_api else "local",
            "dependencies": self.dependencies,
            "config": self.ocr_config.to_dict(),
            "errors": []
        }

        try:
            # Test basic initialization
            if not self.ocr_loader_factory:
                status["errors"].append("OCR loader factory not initialized")
                return status

            # For API mode, we could test the API endpoint
            if self.ocr_config.use_unstructured_api:
                # Basic API key validation
                if not self.ocr_config.unstructured_api_key:
                    status["errors"].append("API key not configured")
                    return status

                # Could add actual API ping here if needed
                status["available"] = True

            else:
                # For local mode, test tesseract availability
                try:
                    import pytesseract
                    version = pytesseract.get_tesseract_version()
                    status["tesseract_version"] = str(version)
                    status["available"] = True
                except Exception as e:
                    status["errors"].append(f"Tesseract test failed: {e}")

        except Exception as e:
            status["errors"].append(f"OCR availability test failed: {e}")

        return status

    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get OCR processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        return {
            "mode": "api" if self.ocr_config.use_unstructured_api else "local",
            "timeout_seconds": self.ocr_config.timeout_seconds,
            "strategy": self.ocr_config.strategy,
            "dependencies_available": all(self.dependencies.values()),
            "config_valid": True  # If we got this far, config is valid
        }