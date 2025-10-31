"""
Bank Statement Processing Models

This module defines data structures for bank statement processing results,
including extraction method tracking, timing information, and OCR metadata.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict, field
from enum import Enum

logger = logging.getLogger(__name__)


class ExtractionMethod(Enum):
    """Enumeration of extraction methods."""
    PDF_LOADER = "pdf_loader"
    OCR = "ocr"
    PDF_LOADER_INSUFFICIENT = "pdf_loader_insufficient"
    HYBRID = "hybrid"  # Future use for combined approaches


class ProcessingStatus(Enum):
    """Enumeration of processing statuses."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    INSUFFICIENT_TEXT = "insufficient_text"


@dataclass
class ExtractionMetadata:
    """Metadata about the extraction process."""
    method: ExtractionMethod
    processing_time: float
    text_length: int
    word_count: int
    confidence_score: Optional[float] = None
    quality_score: Optional[float] = None
    extraction_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # OCR-specific metadata
    ocr_engine: Optional[str] = None  # "tesseract", "unstructured_api", etc.
    ocr_strategy: Optional[str] = None  # "hi_res", "fast", etc.
    ocr_timeout_seconds: Optional[int] = None
    
    # PDF loader metadata
    pdf_loader_used: Optional[str] = None  # "pymupdf", "pdfplumber", etc.
    pdf_loader_fallback_count: Optional[int] = None
    
    # Text quality metrics
    text_sufficiency_reasons: Optional[List[str]] = None
    bank_keywords_found: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        # Convert enum values to strings
        result['method'] = self.method.value
        # Convert datetime to ISO string
        result['extraction_timestamp'] = self.extraction_timestamp.isoformat()
        return result


@dataclass
class DocumentCharacteristics:
    """Characteristics of the processed document."""
    file_path: str
    file_name: str
    file_size_bytes: int
    file_extension: str
    page_count: Optional[int] = None
    
    # Content analysis
    is_scanned: Optional[bool] = None
    has_tables: Optional[bool] = None
    text_density: Optional[float] = None  # Characters per page
    estimated_complexity: Optional[str] = None  # "low", "medium", "high"
    
    # Bank statement specific
    contains_bank_keywords: Optional[bool] = None
    statement_type: Optional[str] = None  # "checking", "savings", "credit_card", etc.
    date_range: Optional[Dict[str, str]] = None  # {"start": "2024-01-01", "end": "2024-01-31"}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class ProcessingError:
    """Information about processing errors."""
    error_type: str
    error_message: str
    error_code: Optional[str] = None
    is_transient: bool = False
    retry_count: int = 0
    error_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['error_timestamp'] = self.error_timestamp.isoformat()
        return result


@dataclass
class BankStatementProcessingResult:
    """
    Comprehensive result of bank statement processing operation.
    
    This data structure contains all information about the processing attempt,
    including extracted transactions, method used, timing, and metadata.
    """
    # Core results
    transactions: List[Dict[str, Any]]
    status: ProcessingStatus
    
    # Extraction metadata
    extraction_metadata: ExtractionMetadata
    
    # Document information
    document_characteristics: DocumentCharacteristics
    
    # Processing information
    processing_start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processing_end_time: Optional[datetime] = None
    total_processing_time: Optional[float] = None
    
    # AI/LLM information
    ai_config_used: Optional[Dict[str, Any]] = None
    llm_processing_time: Optional[float] = None
    llm_token_usage: Optional[Dict[str, Any]] = None
    
    # Error information (if any)
    errors: List[ProcessingError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.processing_end_time and self.total_processing_time is None:
            self.total_processing_time = (
                self.processing_end_time - self.processing_start_time
            ).total_seconds()
    
    def mark_completed(self, end_time: Optional[datetime] = None) -> None:
        """Mark processing as completed and calculate total time."""
        self.processing_end_time = end_time or datetime.now(timezone.utc)
        self.total_processing_time = (
            self.processing_end_time - self.processing_start_time
        ).total_seconds()
    
    def add_error(self, error: Union[ProcessingError, Exception, str]) -> None:
        """Add an error to the result."""
        if isinstance(error, ProcessingError):
            self.errors.append(error)
        elif isinstance(error, Exception):
            self.errors.append(ProcessingError(
                error_type=type(error).__name__,
                error_message=str(error),
                stack_trace=str(error) if len(str(error)) < 1000 else str(error)[:1000]
            ))
        else:
            self.errors.append(ProcessingError(
                error_type="GeneralError",
                error_message=str(error)
            ))
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)
    
    def is_successful(self) -> bool:
        """Check if processing was successful."""
        return self.status == ProcessingStatus.SUCCESS and len(self.transactions) > 0
    
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the processing result."""
        return {
            "transaction_count": len(self.transactions),
            "status": self.status.value,
            "extraction_method": self.extraction_metadata.method.value,
            "processing_time": self.total_processing_time,
            "text_length": self.extraction_metadata.text_length,
            "word_count": self.extraction_metadata.word_count,
            "file_name": self.document_characteristics.file_name,
            "file_size": self.document_characteristics.file_size_bytes,
            "success": self.is_successful(),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "transactions": self.transactions,
            "status": self.status.value,
            "extraction_metadata": self.extraction_metadata.to_dict(),
            "document_characteristics": self.document_characteristics.to_dict(),
            "processing_start_time": self.processing_start_time.isoformat(),
            "processing_end_time": self.processing_end_time.isoformat() if self.processing_end_time else None,
            "total_processing_time": self.total_processing_time,
            "ai_config_used": self.ai_config_used,
            "llm_processing_time": self.llm_processing_time,
            "llm_token_usage": self.llm_token_usage,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": self.warnings,
            "metadata": self.metadata
        }
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BankStatementProcessingResult':
        """Create instance from dictionary."""
        # Convert string values back to enums
        status = ProcessingStatus(data["status"])
        
        # Reconstruct extraction metadata
        extraction_data = data["extraction_metadata"]
        extraction_metadata = ExtractionMetadata(
            method=ExtractionMethod(extraction_data["method"]),
            processing_time=extraction_data["processing_time"],
            text_length=extraction_data["text_length"],
            word_count=extraction_data["word_count"],
            confidence_score=extraction_data.get("confidence_score"),
            quality_score=extraction_data.get("quality_score"),
            extraction_timestamp=datetime.fromisoformat(extraction_data["extraction_timestamp"]),
            ocr_engine=extraction_data.get("ocr_engine"),
            ocr_strategy=extraction_data.get("ocr_strategy"),
            ocr_timeout_seconds=extraction_data.get("ocr_timeout_seconds"),
            pdf_loader_used=extraction_data.get("pdf_loader_used"),
            pdf_loader_fallback_count=extraction_data.get("pdf_loader_fallback_count"),
            text_sufficiency_reasons=extraction_data.get("text_sufficiency_reasons"),
            bank_keywords_found=extraction_data.get("bank_keywords_found")
        )
        
        # Reconstruct document characteristics
        doc_data = data["document_characteristics"]
        document_characteristics = DocumentCharacteristics(**doc_data)
        
        # Reconstruct errors
        errors = [
            ProcessingError(
                error_type=error_data["error_type"],
                error_message=error_data["error_message"],
                error_code=error_data.get("error_code"),
                is_transient=error_data.get("is_transient", False),
                retry_count=error_data.get("retry_count", 0),
                error_timestamp=datetime.fromisoformat(error_data["error_timestamp"]),
                stack_trace=error_data.get("stack_trace")
            )
            for error_data in data.get("errors", [])
        ]
        
        # Create instance
        result = cls(
            transactions=data["transactions"],
            status=status,
            extraction_metadata=extraction_metadata,
            document_characteristics=document_characteristics,
            processing_start_time=datetime.fromisoformat(data["processing_start_time"]),
            processing_end_time=(
                datetime.fromisoformat(data["processing_end_time"]) 
                if data.get("processing_end_time") else None
            ),
            total_processing_time=data.get("total_processing_time"),
            ai_config_used=data.get("ai_config_used"),
            llm_processing_time=data.get("llm_processing_time"),
            llm_token_usage=data.get("llm_token_usage"),
            errors=errors,
            warnings=data.get("warnings", []),
            metadata=data.get("metadata", {})
        )
        
        return result


def create_processing_result(
    transactions: List[Dict[str, Any]],
    extraction_method: ExtractionMethod,
    processing_time: float,
    text_length: int,
    word_count: int,
    file_path: str,
    status: ProcessingStatus = ProcessingStatus.SUCCESS,
    **kwargs
) -> BankStatementProcessingResult:
    """
    Convenience function to create a BankStatementProcessingResult.
    
    Args:
        transactions: List of extracted transactions
        extraction_method: Method used for extraction
        processing_time: Time taken for extraction
        text_length: Length of extracted text
        word_count: Number of words in extracted text
        file_path: Path to the processed file
        status: Processing status
        **kwargs: Additional metadata
        
    Returns:
        BankStatementProcessingResult instance
    """
    from pathlib import Path
    
    file_path_obj = Path(file_path)
    
    # Create extraction metadata
    extraction_metadata = ExtractionMetadata(
        method=extraction_method,
        processing_time=processing_time,
        text_length=text_length,
        word_count=word_count,
        confidence_score=kwargs.get("confidence_score"),
        quality_score=kwargs.get("quality_score"),
        ocr_engine=kwargs.get("ocr_engine"),
        ocr_strategy=kwargs.get("ocr_strategy"),
        ocr_timeout_seconds=kwargs.get("ocr_timeout_seconds"),
        pdf_loader_used=kwargs.get("pdf_loader_used"),
        pdf_loader_fallback_count=kwargs.get("pdf_loader_fallback_count"),
        text_sufficiency_reasons=kwargs.get("text_sufficiency_reasons"),
        bank_keywords_found=kwargs.get("bank_keywords_found")
    )
    
    # Create document characteristics
    document_characteristics = DocumentCharacteristics(
        file_path=str(file_path_obj),
        file_name=file_path_obj.name,
        file_size_bytes=file_path_obj.stat().st_size if file_path_obj.exists() else 0,
        file_extension=file_path_obj.suffix.lower(),
        page_count=kwargs.get("page_count"),
        is_scanned=kwargs.get("is_scanned"),
        has_tables=kwargs.get("has_tables"),
        text_density=kwargs.get("text_density"),
        estimated_complexity=kwargs.get("estimated_complexity"),
        contains_bank_keywords=kwargs.get("contains_bank_keywords"),
        statement_type=kwargs.get("statement_type"),
        date_range=kwargs.get("date_range")
    )
    
    # Create processing result
    result = BankStatementProcessingResult(
        transactions=transactions,
        status=status,
        extraction_metadata=extraction_metadata,
        document_characteristics=document_characteristics,
        ai_config_used=kwargs.get("ai_config_used"),
        llm_processing_time=kwargs.get("llm_processing_time"),
        llm_token_usage=kwargs.get("llm_token_usage"),
        metadata=kwargs.get("metadata", {})
    )
    
    return result