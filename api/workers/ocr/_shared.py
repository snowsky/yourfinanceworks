"""
Improved OCR Consumer with better structure, performance, and maintainability

This module provides a more maintainable and performant version of the OCR consumer
that processes messages from Kafka topics for expenses, bank statements, and invoices.

Key improvements:
- Better separation of concerns with dedicated handler classes
- Improved error handling and retry logic
- Enhanced resource management
- Better code organization and readability
- Performance optimizations
- Comprehensive logging and monitoring
"""

import json
import logging
import os
import signal
import sys
import asyncio
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from contextlib import contextmanager
from enum import Enum
from datetime import datetime, timezone
from types import SimpleNamespace

# Service imports
from commercial.ai.services.ocr_service import (
    apply_ocr_extraction_to_expense,
    parse_number,
    first_key,
    process_attachment_inline,
    publish_ocr_result,
    publish_ocr_task,
    release_processing_lock,
    publish_fraud_audit_task
)
from core.utils.timezone import get_tenant_timezone_aware_datetime
from core.models.database import set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from sqlalchemy.orm import Session
from commercial.ai.exceptions.bank_ocr_exceptions import (
    OCRTimeoutError,
    OCRProcessingError,
    is_retryable_ocr_error,
    get_retry_delay
)

# Import models - these are used in multiple methods
try:
    from core.models.models_per_tenant import BankStatementTransaction
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import BankStatementTransaction: {e}")
    BankStatementTransaction = None

# Type imports for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.models.models_per_tenant import InvoiceProcessingTask


# ============================================================================
# Configuration and Data Structures
# ============================================================================

@dataclass
class OCRConfig:
    """Configuration for OCR processing"""
    max_attempts: int = 5
    backoff_base_ms: int = 1000
    max_backoff_ms: int = 60000
    timeout_seconds: int = 300
    dlq_enabled: bool = True


@dataclass
class ProcessingResult:
    """Result of processing a message"""
    success: bool
    committed: bool = False
    error_message: Optional[str] = None
    retry_count: int = 0
    should_retry: bool = False


class DocumentType(Enum):
    """Supported document types for processing"""
    EXPENSE = "expense"
    BANK_STATEMENT = "bank_statement"
    INVOICE = "invoice"


class ProcessingStatus(Enum):
    """Processing status for documents"""
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    PROCESSED = "processed"  # For bank statements after successful extraction
    COMPLETED = "completed"  # For invoice processing tasks
    FAILED = "failed"
    SKIPPED = "skipped"


# ============================================================================
# Logging Configuration
# ============================================================================

def _resolve_log_level(name: str) -> int:
    """Resolve log level from string name"""
    name = (name or "INFO").upper()
    return {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(name, logging.INFO)


# Setup logging
log_level = _resolve_log_level(os.getenv("LOG_LEVEL", "INFO"))
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info(f"OCR worker log level set to {logging.getLevelName(log_level)}")


# ============================================================================
# Resource Management
# ============================================================================

@contextmanager
def database_session(tenant_id: int):
    """Context manager for tenant database sessions"""
    SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
    db = SessionLocalTenant()
    try:
        yield db
    finally:
        db.close()
        logger.debug(f"Closed database session for tenant {tenant_id}")


@contextmanager
def tenant_context(tenant_id: int):
    """Context manager for tenant context"""
    try:
        set_tenant_context(tenant_id)
        logger.debug(f"Set tenant context to {tenant_id}")
        yield
    finally:
        # Tenant context cleanup if needed
        pass


# ============================================================================
# Error Handling and Retry Logic
# ============================================================================

class ProcessingError(Exception):
    """Base exception for processing errors"""
    def __init__(self, message: str, retryable: bool = False, retry_delay: int = 0):
        super().__init__(message)
        self.retryable = retryable
        self.retry_delay = retry_delay


class ConfigurationError(ProcessingError):
    """Configuration-related errors (not retryable)"""
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class DependencyError(ProcessingError):
    """Missing dependency errors"""
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


def calculate_backoff_delay(attempt: int, base_delay: int = 1000, max_delay: int = 60000) -> int:
    """Calculate exponential backoff delay with jitter"""
    import random
    exponential_delay = min(max_delay, base_delay * (2 ** attempt))
    # Add jitter (±25% of delay)
    jitter = int(exponential_delay * 0.25 * random.random())
    return max(0, exponential_delay + random.choice([-jitter, jitter]))
