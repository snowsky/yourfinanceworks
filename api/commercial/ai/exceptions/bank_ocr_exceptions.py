"""
Bank Statement OCR Exception Classes

This module provides custom exception classes for bank statement OCR-related errors
with comprehensive error handling and retry logic capabilities.
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class OCRErrorCode(Enum):
    """Error codes for OCR operations."""
    GENERAL_ERROR = "OCR_001"
    UNAVAILABLE = "OCR_002"
    TIMEOUT = "OCR_003"
    PROCESSING_FAILED = "OCR_004"
    INVALID_FILE = "OCR_005"
    INSUFFICIENT_TEXT = "OCR_006"
    CONFIGURATION_ERROR = "OCR_007"
    DEPENDENCY_MISSING = "OCR_008"


class OCRError(Exception):
    """
    Base exception class for OCR-related errors.
    
    Provides structured error information and logging capabilities
    for bank statement OCR operations.
    """
    
    def __init__(
        self,
        message: str,
        error_code: OCRErrorCode = OCRErrorCode.GENERAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        is_transient: bool = False
    ):
        """
        Initialize OCR error.
        
        Args:
            message: Human-readable error message
            error_code: Specific error code for categorization
            details: Additional error details and context
            retry_after: Suggested retry delay in seconds
            is_transient: Whether this is a temporary error that might resolve
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.retry_after = retry_after
        self.is_transient = is_transient
        
        # Log the error for monitoring
        logger.error(
            f"OCR Error [{error_code.value}]: {message}",
            extra={
                "error_code": error_code.value,
                "details": details,
                "retry_after": retry_after,
                "is_transient": is_transient
            }
        )


class OCRUnavailableError(OCRError):
    """Exception raised when OCR functionality is not available."""
    
    def __init__(
        self,
        message: str = "OCR functionality is not available",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=OCRErrorCode.UNAVAILABLE,
            details=details,
            is_transient=False
        )


class OCRTimeoutError(OCRError):
    """Exception raised when OCR processing exceeds timeout."""
    
    def __init__(
        self,
        message: str = "OCR processing timed out",
        timeout_seconds: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
            
        super().__init__(
            message=message,
            error_code=OCRErrorCode.TIMEOUT,
            details=details,
            retry_after=60,  # Suggest retry after 1 minute
            is_transient=True
        )


class OCRProcessingError(OCRError):
    """Exception raised when OCR processing fails."""
    
    def __init__(
        self,
        message: str = "OCR processing failed",
        details: Optional[Dict[str, Any]] = None,
        is_transient: bool = False
    ):
        super().__init__(
            message=message,
            error_code=OCRErrorCode.PROCESSING_FAILED,
            details=details,
            retry_after=30 if is_transient else None,
            is_transient=is_transient
        )


class OCRInvalidFileError(OCRError):
    """Exception raised when the file is invalid for OCR processing."""
    
    def __init__(
        self,
        message: str = "Invalid file for OCR processing",
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if file_path:
            details["file_path"] = file_path
            
        super().__init__(
            message=message,
            error_code=OCRErrorCode.INVALID_FILE,
            details=details,
            is_transient=False
        )


class OCRInsufficientTextError(OCRError):
    """Exception raised when OCR extracts insufficient text."""
    
    def __init__(
        self,
        message: str = "OCR extracted insufficient text",
        text_length: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if text_length is not None:
            details["text_length"] = text_length
            
        super().__init__(
            message=message,
            error_code=OCRErrorCode.INSUFFICIENT_TEXT,
            details=details,
            is_transient=False
        )


class OCRConfigurationError(OCRError):
    """Exception raised when OCR configuration is invalid."""
    
    def __init__(
        self,
        message: str = "OCR configuration is invalid",
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if config_key:
            details["config_key"] = config_key
            
        super().__init__(
            message=message,
            error_code=OCRErrorCode.CONFIGURATION_ERROR,
            details=details,
            is_transient=False
        )


class OCRDependencyMissingError(OCRError):
    """Exception raised when required OCR dependencies are missing."""
    
    def __init__(
        self,
        message: str = "Required OCR dependencies are missing",
        missing_dependency: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if missing_dependency:
            details["missing_dependency"] = missing_dependency
            
        super().__init__(
            message=message,
            error_code=OCRErrorCode.DEPENDENCY_MISSING,
            details=details,
            is_transient=False
        )


def is_retryable_ocr_error(error: Exception) -> bool:
    """
    Check if an OCR error is retryable.
    
    Args:
        error: The exception to check
        
    Returns:
        True if the error is transient and retryable
    """
    if isinstance(error, OCRError):
        return error.is_transient
    
    # Check for common transient error patterns
    error_str = str(error).lower()
    transient_patterns = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "service unavailable",
        "rate limit"
    ]
    
    return any(pattern in error_str for pattern in transient_patterns)


def get_retry_delay(error: Exception) -> Optional[int]:
    """
    Get suggested retry delay for an OCR error.
    
    Args:
        error: The exception to check
        
    Returns:
        Suggested retry delay in seconds, or None if not retryable
    """
    if isinstance(error, OCRError):
        return error.retry_after
    
    # Default retry delays for common error types
    error_str = str(error).lower()
    if "timeout" in error_str:
        return 60
    elif "rate limit" in error_str:
        return 120
    elif "connection" in error_str or "network" in error_str:
        return 30
    
    return None