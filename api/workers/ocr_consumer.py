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
import time
import asyncio
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from contextlib import contextmanager
from enum import Enum
from datetime import datetime, timezone
from types import SimpleNamespace

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Service imports
from core.services.ocr_service import (
    process_attachment_inline,
    publish_ocr_result,
    publish_ocr_task,
    release_processing_lock
)
from core.models.database import set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from sqlalchemy.orm import Session
from core.exceptions.bank_ocr_exceptions import (
    OCRTimeoutError, 
    OCRProcessingError, 
    is_retryable_ocr_error,
    get_retry_delay
)

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


# ============================================================================
# Base Message Handler
# ============================================================================

class BaseMessageHandler:
    """Base class for message handlers"""

    def __init__(self, config: OCRConfig):
        self.config = config
        self.logger = logger

    def can_handle(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Check if handler can process this message type"""
        raise NotImplementedError

    async def process(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process the message"""
        raise NotImplementedError

    def extract_tenant_id(self, payload: Dict[str, Any]) -> Optional[int]:
        """Extract tenant ID from payload"""
        return payload.get("tenant_id")

    def is_batch_job(self, payload: Dict[str, Any]) -> bool:
        """Check if this is a batch job"""
        return payload.get("batch_job_id") is not None and payload.get("batch_file_id") is not None


# ============================================================================
# Expense Message Handler
# ============================================================================

class ExpenseMessageHandler(BaseMessageHandler):
    """Handler for expense-related messages"""

    def can_handle(self, topic: str, payload: Dict[str, Any]) -> bool:
        expense_topic = os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr")
        return topic == expense_topic

    async def process(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process expense OCR message"""
        try:
            # Handle batch job
            if self.is_batch_job(payload):
                return await self._process_batch_expense(consumer, message, payload)
            else:
                return await self._process_single_expense(consumer, message, payload)

        except Exception as e:
            self.logger.error(f"Unexpected error processing expense: {e}")
            return ProcessingResult(success=False, error_message=str(e))

    async def _process_batch_expense(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process batch expense job"""
        batch_job_id = payload.get("batch_job_id")
        batch_file_id = payload.get("batch_file_id")
        file_path = str(payload.get("file_path"))
        tenant_id = self.extract_tenant_id(payload)
        user_id = payload.get("user_id")

        if not user_id:
            self.logger.error(f"Missing user_id in batch expense payload for file {batch_file_id}")
            return ProcessingResult(success=False, error_message="Missing user_id in payload", committed=False)

        self.logger.info(f"Processing batch expense OCR: batch_job_id={batch_job_id}, batch_file_id={batch_file_id}, user_id={user_id}")

        try:
            with tenant_context(tenant_id):
                with database_session(tenant_id) as db:
                    from core.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
                    from commercial.batch_processing.service import BatchProcessingService
                    from core.models.models_per_tenant import Expense, ExpenseAttachment, AIConfig as AIConfigModel
                    from datetime import datetime, timezone

                    # Get AI config
                    ai_conf_model = db.query(AIConfigModel).first()
                    ai_conf = {}
                    if ai_conf_model:
                        ai_conf = {
                            "provider": ai_conf_model.provider,
                            "api_key": ai_conf_model.api_key,
                            "model_name": ai_conf_model.model_name,
                            "api_base": ai_conf_model.api_base,
                        }

                    # Process with unified OCR service
                    ocr_config = OCRConfig(ai_config=ai_conf, timeout_seconds=300)
                    ocr_service = UnifiedOCRService(ocr_config)

                    # Extract data from file using the service's extract_structured_data method
                    result = await ocr_service.extract_structured_data(file_path, DocumentType.EXPENSE_RECEIPT)

                    if not result.success:
                        raise Exception(result.error_message or "Failed to extract expense data")

                    extracted_data = result.structured_data or {}

                    # Create Expense record from extracted data
                    created_expense_id = None
                    try:
                        # Parse date if it's a string, otherwise use as-is
                        expense_date_value = extracted_data.get('date')
                        if isinstance(expense_date_value, str):
                            try:
                                from dateutil import parser
                                expense_date_value = parser.parse(expense_date_value)
                            except:
                                expense_date_value = datetime.now(timezone.utc)
                        elif expense_date_value is None:
                            expense_date_value = datetime.now(timezone.utc)

                        # Ensure category is never None (required field)
                        category = extracted_data.get('category') or 'Other'

                        expense = Expense(
                            user_id=user_id,
                            vendor=extracted_data.get('vendor') or 'Unknown Vendor',
                            amount=extracted_data.get('amount') or 0.0,
                            currency=extracted_data.get('currency') or 'USD',
                            expense_date=expense_date_value,
                            category=category,
                            tax_amount=extracted_data.get('tax_amount'),
                            notes=f"Batch processed from job {batch_job_id}",
                            status='recorded'
                        )
                        db.add(expense)
                        db.flush()  # Get the expense ID

                        # Create attachment record
                        # Detect content type from filename
                        import mimetypes
                        original_filename = payload.get("original_filename", "batch_file")
                        content_type, _ = mimetypes.guess_type(original_filename)
                        if not content_type:
                            content_type = 'application/octet-stream'
                        
                        attachment = ExpenseAttachment(
                            expense_id=expense.id,
                            filename=original_filename,
                            file_path=file_path,
                            size_bytes=payload.get("file_size", 0),
                            content_type=content_type
                        )
                        db.add(attachment)
                        db.commit()

                        created_expense_id = expense.id
                        self.logger.info(f"Created expense record {created_expense_id} from batch file {batch_file_id}")
                    except Exception as e:
                        self.logger.error(f"Failed to create expense record: {e}")
                        db.rollback()
                        # Continue anyway - we still have the extracted data

                    # Update batch processing service
                    batch_service = BatchProcessingService(db)
                    await batch_service.process_file_completion(
                        file_id=int(batch_file_id),
                        extracted_data=extracted_data,
                        status="completed",
                        created_record_id=created_expense_id,
                        record_type='expense'
                    )

                    self.logger.info(f"Batch expense OCR completed: batch_file_id={batch_file_id}")
                    return ProcessingResult(success=True, committed=True)

        except Exception as e:
            self.logger.error(f"Batch expense OCR failed: {e}")

            # Update batch processing service with failure
            try:
                with tenant_context(tenant_id):
                    with database_session(tenant_id) as db:
                        from commercial.batch_processing.service import BatchProcessingService
                        batch_service = BatchProcessingService(db)
                        await batch_service.process_file_completion(
                            file_id=int(batch_file_id),
                            status="failed",
                            error_message=str(e)
                        )
            except Exception as update_error:
                self.logger.error(f"Failed to update batch job on error: {update_error}")

            return ProcessingResult(success=False, error_message=str(e), committed=True)

    async def _process_single_expense(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process single expense OCR"""
        expense_id = int(payload.get("expense_id"))
        attachment_id = int(payload.get("attachment_id"))
        file_path = str(payload.get("file_path"))
        tenant_id = self.extract_tenant_id(payload)
        attempt = int(payload.get("attempt", 0))

        self.logger.info(f"Processing expense OCR: expense_id={expense_id}, attempt={attempt}")

        try:
            with tenant_context(tenant_id):
                with database_session(tenant_id) as db:
                    from core.models.models_per_tenant import Expense

                    # Check if expense exists and is not manually overridden
                    exp = db.query(Expense).filter(Expense.id == expense_id).first()
                    if not exp:
                        self.logger.warning(f"Expense {expense_id} not found; skipping")
                        return ProcessingResult(success=True, committed=True)

                    if exp.manual_override:
                        self.logger.info(f"Expense {expense_id} manually overridden; skipping OCR")
                        return ProcessingResult(success=True, committed=True)

                    # Update expense status
                    try:
                        exp.analysis_status = ProcessingStatus.PROCESSING.value
                        exp.updated_at = datetime.now(timezone.utc)
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise ProcessingError("Failed to update expense status")

                    # Process with OCR
                    await process_attachment_inline(db, expense_id, attachment_id, file_path, tenant_id)

                    # Refresh and check result
                    db.refresh(exp)

                    if getattr(exp, "analysis_status", None) == ProcessingStatus.DONE.value:
                        # Success - commit and publish result
                        await self._commit_message(consumer, message)
                        await self._publish_ocr_result(expense_id, tenant_id, "done")
                        return ProcessingResult(success=True, committed=True)
                    else:
                        # Handle failure with retry logic
                        return await self._handle_expense_failure(consumer, message, exp, attempt, payload)

        except Exception as e:
            self.logger.error(f"Failed to process expense {expense_id}: {e}")

            # Handle OCR-specific errors
            if isinstance(e, (OCRTimeoutError, OCRProcessingError)):
                if isinstance(e, OCRTimeoutError):
                    retry_delay = get_retry_delay(e)
                else:
                    retry_delay = calculate_backoff_delay(attempt)

                if attempt < self.config.max_attempts:
                    return ProcessingResult(
                        success=False, 
                        should_retry=True, 
                        retry_count=attempt + 1,
                        error_message=str(e)
                    )

            # Max retries exceeded or non-retryable error
            if attempt >= self.config.max_attempts and self.config.dlq_enabled:
                await self._send_to_dlq(expense_id, tenant_id, attachment_id, file_path, e, payload)

            return ProcessingResult(success=False, error_message=str(e), committed=True)

    async def _handle_expense_failure(self, consumer, message, expense, attempt: int, payload: Dict[str, Any]) -> ProcessingResult:
        """Handle expense processing failure with retry logic"""
        expense_id = expense.id
        tenant_id = self.extract_tenant_id(payload)

        error_message = getattr(expense, "analysis_error", "Unknown error")

        # Check if error is retryable
        if "timeout" in error_message.lower():
            retry_delay = min(300000, 60000 * (attempt + 1))  # 1-5 minutes for timeouts
        else:
            retry_delay = calculate_backoff_delay(attempt)

        if attempt < self.config.max_attempts:
            # Requeue with backoff
            self.logger.warning(f"Requeueing expense_id={expense_id} attempt={attempt+1} after {retry_delay}ms")
            await asyncio.sleep(retry_delay / 1000.0)

            payload.update({"attempt": attempt + 1})
            await publish_ocr_task(payload)
            await self._commit_message(consumer, message)

            return ProcessingResult(success=False, should_retry=True, retry_count=attempt + 1)
        else:
            # Max attempts reached - send to DLQ
            self.logger.warning(f"OCR failed for expense_id={expense_id}. Sending to DLQ after {attempt+1} attempts.")
            await self._send_to_dlq(expense_id, tenant_id, payload.get("attachment_id"), payload.get("file_path"), error_message, payload)
            return ProcessingResult(success=False, committed=True)

    async def _send_to_dlq(self, expense_id: int, tenant_id: int, attachment_id: int, file_path: str, error: Union[str, Exception], payload: Dict[str, Any]):
        """Send failed message to Dead Letter Queue"""
        try:
            from confluent_kafka import Producer
            from core.services.ocr_service import _get_kafka_producer

            producer, _ = _get_kafka_producer()
            if producer:
                dlq_topic = os.getenv("KAFKA_OCR_DLQ_TOPIC", "expenses_ocr_dlq")
                dlq_event = {
                    "tenant_id": tenant_id,
                    "expense_id": expense_id,
                    "attachment_id": attachment_id,
                    "file_path": file_path,
                    "attempt": payload.get("attempt", 0) + 1,
                    "error": str(error),
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                producer.produce(dlq_topic, key=str(expense_id), value=json.dumps(dlq_event).encode("utf-8"))
                producer.flush(1.0)

                # Publish failed result
                publish_ocr_result(expense_id, tenant_id, status="failed", details={"dlq": True})

        except Exception as e:
            self.logger.error(f"Failed to publish to DLQ: {e}")

    async def _commit_message(self, consumer, message):
        """Safely commit Kafka message"""
        try:
            consumer.commit(message=message, asynchronous=False)
        except Exception as e:
            self.logger.error(f"Failed to commit message: {e}")

    async def _publish_ocr_result(self, expense_id: int, tenant_id: int, status: str, details: Optional[Dict] = None):
        """Publish OCR result"""
        try:
            publish_ocr_result(expense_id, tenant_id, status, details)
        except Exception as e:
            self.logger.error(f"Failed to publish OCR result: {e}")


# ============================================================================
# Bank Statement Message Handler
# ============================================================================

class BankStatementMessageHandler(BaseMessageHandler):
    """Handler for bank statement messages"""

    def can_handle(self, topic: str, payload: Dict[str, Any]) -> bool:
        bank_topic = os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr")
        return topic == bank_topic

    async def process(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process bank statement OCR message"""
        try:
            # Handle batch job
            if self.is_batch_job(payload):
                return await self._process_batch_statement(consumer, message, payload)
            else:
                return await self._process_single_statement(consumer, message, payload)

        except Exception as e:
            self.logger.error(f"Unexpected error processing bank statement: {e}")
            return ProcessingResult(success=False, error_message=str(e))

    async def _process_batch_statement(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process batch bank statement"""
        batch_job_id = payload.get("batch_job_id")
        batch_file_id = payload.get("batch_file_id")
        file_path = str(payload.get("file_path"))
        tenant_id = self.extract_tenant_id(payload)
        user_id = payload.get("user_id")
        
        if not user_id:
            self.logger.error(f"Missing user_id in batch statement payload for file {batch_file_id}")
            return ProcessingResult(success=False, error_message="Missing user_id in payload", committed=False)
        
        self.logger.info(f"Processing batch bank statement OCR: batch_job_id={batch_job_id}, batch_file_id={batch_file_id}, user_id={user_id}")
        
        try:
            with tenant_context(tenant_id):
                with database_session(tenant_id) as db:
                    from core.models.models_per_tenant import AIConfig as AIConfigModel, BankStatement, BankStatementAttachment
                    from core.services.statement_service import process_bank_pdf_with_llm
                    from core.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
                    from datetime import datetime, timezone
                    
                    # Get AI config
                    ai_conf = await self._get_ai_config(db)
                    
                    # Try unified OCR first, fallback to legacy
                    try:
                        ocr_config = OCRConfig(
                            ai_config=ai_conf,
                            enable_unstructured=True,
                            enable_tesseract_fallback=True,
                            timeout_seconds=300
                        )
                        
                        ocr_service = UnifiedOCRService(ocr_config)
                        text_result = ocr_service.extract_text(file_path, DocumentType.BANK_STATEMENT)
                        
                        if text_result.success:
                            self.logger.info(f"✅ Text extraction successful: {text_result.text_length} chars")
                            # Use legacy transaction parsing for now
                            txns = process_bank_pdf_with_llm(file_path, ai_conf, db)
                        else:
                            raise Exception(f"UnifiedOCR text extraction failed: {text_result.error_message}")
                            
                    except ImportError:
                        # Fallback to legacy service
                        txns = process_bank_pdf_with_llm(file_path, ai_conf, db)
                    
                    # Get cloud file URL from batch file record
                    from core.models.models_per_tenant import BatchFileProcessing
                    batch_file = db.query(BatchFileProcessing).filter(
                        BatchFileProcessing.id == int(batch_file_id)
                    ).first()
                    cloud_file_url = batch_file.cloud_file_url if batch_file else None
                    
                    # Create BankStatement record from extracted data
                    created_statement_id = None
                    try:
                        # BankStatement model fields: tenant_id, original_filename, stored_filename, file_path, cloud_file_url, status, extracted_count, notes, labels
                        statement = BankStatement(
                            tenant_id=tenant_id,
                            original_filename=payload.get("original_filename", "batch_file"),
                            stored_filename=payload.get("stored_filename", payload.get("original_filename", "batch_file")),
                            file_path=file_path,
                            cloud_file_url=cloud_file_url,
                            status='processed',
                            extracted_count=len(txns) if txns else 0,
                            notes=f"Batch processed from job {batch_job_id}"
                        )
                        db.add(statement)
                        db.flush()  # Get the statement ID
                        
                        # Create attachment record
                        original_filename = payload.get("original_filename", "batch_file")
                        attachment = BankStatementAttachment(
                            statement_id=statement.id,
                            filename=original_filename,
                            stored_filename=payload.get("stored_filename", original_filename),
                            file_path=file_path,
                            cloud_file_url=cloud_file_url,
                            file_size=payload.get("file_size", 0),
                            content_type='application/pdf',
                            attachment_type='document',
                            document_type='statement',
                            uploaded_by=user_id
                        )
                        db.add(attachment)
                        
                        # Create transaction records
                        from core.models.models_per_tenant import BankStatementTransaction
                        if txns:
                            for txn in txns:
                                transaction = BankStatementTransaction(
                                    statement_id=statement.id,
                                    date=txn.get('date'),
                                    description=txn.get('description', ''),
                                    amount=txn.get('amount', 0.0),
                                    transaction_type=txn.get('type', 'debit'),
                                    balance=txn.get('balance'),
                                    category=txn.get('category')
                                )
                                db.add(transaction)
                            self.logger.info(f"Created {len(txns)} transaction records for statement {statement.id}")
                        
                        db.commit()
                        
                        created_statement_id = statement.id
                        self.logger.info(f"Created bank statement record {created_statement_id} with {len(txns) if txns else 0} transactions and attachment from batch file {batch_file_id}, cloud_url={cloud_file_url}")
                    except Exception as e:
                        self.logger.error(f"Failed to create bank statement record: {e}")
                        db.rollback()
                        # Continue anyway - we still have the extracted data
                    
                    # Update batch processing
                    from commercial.batch_processing.service import BatchProcessingService
                    batch_service = BatchProcessingService(db)
                    await batch_service.process_file_completion(
                        file_id=int(batch_file_id),
                        extracted_data={"transactions": txns, "transaction_count": len(txns)},
                        status="completed",
                        created_record_id=created_statement_id,
                        record_type='statement'
                    )
                    
                    self.logger.info(f"Batch bank statement OCR completed: batch_file_id={batch_file_id}")
                    return ProcessingResult(success=True, committed=True)
                    
        except Exception as e:
            self.logger.error(f"Batch bank statement OCR failed: {e}")
            
            # Update batch processing with failure
            try:
                with tenant_context(tenant_id):
                    with database_session(tenant_id) as db:
                        from commercial.batch_processing.service import BatchProcessingService
                        batch_service = BatchProcessingService(db)
                        await batch_service.process_file_completion(
                            file_id=int(batch_file_id),
                            status="failed",
                            error_message=str(e)
                        )
            except Exception as update_error:
                self.logger.error(f"Failed to update batch job: {update_error}")
            
            return ProcessingResult(success=False, error_message=str(e), committed=True)
    
    async def _process_single_statement(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process single bank statement"""
        statement_id = int(payload.get("statement_id"))
        file_path = str(payload.get("file_path"))
        tenant_id = self.extract_tenant_id(payload)
        attempt = int(payload.get("attempt", 0))
        
        self.logger.info(f"Processing bank statement: id={statement_id}, attempt={attempt}")
        
        try:
            with tenant_context(tenant_id):
                with database_session(tenant_id) as db:
                    from core.models.models_per_tenant import BankStatement, AIConfig as AIConfigModel
                    from core.services.statement_service import process_bank_pdf_with_llm, is_bank_llm_reachable
                    
                    # Get AI config
                    ai_conf = await self._get_ai_config(db)
                    
                    # Check if statement exists
                    stmt = db.query(BankStatement).filter(BankStatement.id == statement_id).first()
                    if not stmt:
                        return ProcessingResult(success=True, committed=True)
                    
                    # Check LLM availability and process
                    try:
                        llm_ok = is_bank_llm_reachable(ai_conf)
                        txns = process_bank_pdf_with_llm(file_path, ai_conf, db)
                        
                        self.logger.info(f"Extracted {len(txns)} transactions for statement_id={statement_id}")
                        
                        # Handle processing results
                        if not txns and llm_ok:
                            # LLM worked but no transactions found - accept as processed
                            await self._handle_zero_transactions(db, stmt)
                            return ProcessingResult(success=True, committed=True)
                        
                        # Save transactions
                        await self._save_transactions(db, stmt, txns)
                        return ProcessingResult(success=True, committed=True)
                        
                    except Exception as e:
                        return await self._handle_statement_error(consumer, message, stmt, e, attempt, payload)
                        
        except Exception as e:
            self.logger.error(f"Failed to process bank statement {statement_id}: {e}")
            return ProcessingResult(success=False, error_message=str(e))
    
    async def _handle_statement_error(self, consumer, message, stmt, error: Exception, attempt: int, payload: Dict[str, Any]) -> ProcessingResult:
        """Handle bank statement processing errors"""
        from core.services.ocr_service import publish_bank_statement_task
        
        statement_id = stmt.id
        retry_delay = calculate_backoff_delay(attempt)
        
        # Check for specific error types
        error_name = error.__class__.__name__
        if error_name == "BankLLMUnavailableError":
            if attempt >= self.config.max_attempts:
                self.logger.error(f"Bank LLM unavailable after {attempt+1} attempts for statement_id={statement_id}")
                stmt.status = ProcessingStatus.FAILED.value
                stmt.error_message = str(error)
                try:
                    stmt.db.commit()
                except Exception:
                    stmt.db.rollback()
                await self._commit_message(consumer, message)
                return ProcessingResult(success=False, committed=True)
            else:
                # Requeue with backoff
                self.logger.warning(f"LLM unavailable, retrying statement_id={statement_id} attempt={attempt+1} after {retry_delay}ms")
                await asyncio.sleep(retry_delay / 1000.0)
                payload.update({"attempt": attempt + 1})
                await publish_bank_statement_task(payload)
                await self._handle_processing_status(stmt, ProcessingStatus.PROCESSING.value)
                await self._commit_message(consumer, message)
                return ProcessingResult(success=False, should_retry=True, retry_count=attempt + 1)
        
        # Generic error handling
        self.logger.error(f"Failed processing bank statement: {error}")
        stmt.status = ProcessingStatus.FAILED.value
        stmt.error_message = str(error)
        try:
            stmt.db.commit()
        except Exception:
            stmt.db.rollback()
        await self._commit_message(consumer, message)
        return ProcessingResult(success=False, committed=True)
    
    async def _get_ai_config(self, db) -> Optional[Dict[str, Any]]:
        """Get AI configuration from database"""
        from core.models.models_per_tenant import AIConfig as AIConfigModel
        
        ai_row = db.query(AIConfigModel).filter(
            AIConfigModel.is_active == True,
            AIConfigModel.tested == True
        ).order_by(AIConfigModel.is_default.desc()).first()
        
        if ai_row:
            self.logger.info(f"🔧 Using AI config from database: {ai_row.provider_name} ({ai_row.model_name})")
            return {
                "provider_name": ai_row.provider_name,
                "provider_url": ai_row.provider_url,
                "api_key": ai_row.api_key,
                "model_name": ai_row.model_name,
            }
        else:
            self.logger.warning("⚠️ No AI config found in database, using environment variables")
            return None
    
    async def _handle_zero_transactions(self, db, stmt):
        """Handle statement with zero transactions"""
        db.query(BankStatementTransaction).filter(
            BankStatementTransaction.statement_id == stmt.id
        ).delete()
        stmt.status = ProcessingStatus.DONE.value
        stmt.extracted_count = 0
        db.commit()
        self.logger.info(f"Bank statement processed with 0 transactions: id={stmt.id}")
    
    async def _save_transactions(self, db, stmt, transactions: List[Dict[str, Any]]):
        """Save extracted transactions to database"""
        from core.models.models_per_tenant import BankStatementTransaction
        from datetime import datetime as dt
        
        # Delete existing transactions
        db.query(BankStatementTransaction).filter(
            BankStatementTransaction.statement_id == stmt.id
        ).delete()
        
        # Add new transactions
        count = 0
        for txn_data in transactions:
            try:
                transaction_date = dt.fromisoformat(txn_data.get("date", "")).date()
            except Exception:
                transaction_date = dt.utcnow().date()
            
            db.add(BankStatementTransaction(
                statement_id=stmt.id,
                date=transaction_date,
                description=txn_data.get("description", ""),
                amount=float(txn_data.get("amount", 0)),
                transaction_type=(
                    txn_data.get("transaction_type") 
                    if txn_data.get("transaction_type") in ("debit", "credit")
                    else ("debit" if float(txn_data.get("amount", 0)) < 0 else "credit")
                ),
                balance=float(txn_data["balance"]) if txn_data.get("balance") is not None else None,
                category=txn_data.get("category"),
            ))
            count += 1
        
        stmt.status = ProcessingStatus.DONE.value
        stmt.extracted_count = count
        db.commit()
        self.logger.info(f"Bank statement processed: id={stmt.id}, transactions={count}")
        
        # Release processing lock
        await self._release_processing_lock("bank_statement", stmt.id)
    
    async def _handle_processing_status(self, stmt, status: str):
        """Update processing status"""
        try:
            stmt.status = status
            stmt.db.commit()
        except Exception:
            stmt.db.rollback()
    
    async def _release_processing_lock(self, lock_type: str, item_id: Union[int, str]):
        """Release processing lock"""
        try:
            release_processing_lock(lock_type, item_id)
            self.logger.info(f"Released processing lock for {lock_type} {item_id}")
        except Exception as e:
            self.logger.warning(f"Failed to release processing lock: {e}")
    
    async def _commit_message(self, consumer, message):
        """Safely commit Kafka message"""
        try:
            consumer.commit(message=message, asynchronous=False)
        except Exception as e:
            self.logger.error(f"Failed to commit message: {e}")


# ============================================================================
# Invoice Message Handler
# ============================================================================

class InvoiceMessageHandler(BaseMessageHandler):
    """Handler for invoice messages"""
    
    def can_handle(self, topic: str, payload: Dict[str, Any]) -> bool:
        invoice_topic = os.getenv("KAFKA_INVOICE_TOPIC", "invoices_ocr")
        return topic == invoice_topic
    
    async def process(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process invoice OCR message"""
        try:
            # Handle batch job
            if self.is_batch_job(payload):
                return await self._process_batch_invoice(consumer, message, payload)
            else:
                return await self._process_single_invoice(consumer, message, payload)
                
        except Exception as e:
            self.logger.error(f"Unexpected error processing invoice: {e}")
            return ProcessingResult(success=False, error_message=str(e))
    
    async def _process_batch_invoice(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process batch invoice job"""
        batch_job_id = payload.get("batch_job_id")
        batch_file_id = payload.get("batch_file_id")
        file_path = str(payload.get("file_path"))
        tenant_id = self.extract_tenant_id(payload)
        user_id = payload.get("user_id")
        
        if not user_id:
            self.logger.error(f"Missing user_id in batch invoice payload for file {batch_file_id}")
            return ProcessingResult(success=False, error_message="Missing user_id in payload", committed=False)
        
        self.logger.info(f"Processing batch invoice OCR: batch_job_id={batch_job_id}, batch_file_id={batch_file_id}, user_id={user_id}")
        
        try:
            with tenant_context(tenant_id):
                with database_session(tenant_id) as db:
                    from core.models.models_per_tenant import AIConfig as AIConfigModel, Invoice, InvoiceItem, InvoiceAttachment
                    from commercial.ai.pdf_processor import process_pdf_with_ai
                    from types import SimpleNamespace
                    from datetime import datetime, timezone
                    
                    # Get batch job to retrieve client_id
                    from core.models.models_per_tenant import BatchProcessingJob, Client
                    batch_job = db.query(BatchProcessingJob).filter(
                        BatchProcessingJob.job_id == batch_job_id
                    ).first()
                    
                    client_id = batch_job.client_id if batch_job else None
                    
                    # Validate client_id exists before processing
                    if client_id is not None:
                        client = db.query(Client).filter(Client.id == client_id).first()
                        if not client:
                            error_msg = f"Client ID {client_id} does not exist. Cannot create invoice."
                            self.logger.error(f"Batch invoice processing aborted: {error_msg}")
                            
                            # Mark file as failed without processing
                            from commercial.batch_processing.service import BatchProcessingService
                            batch_service = BatchProcessingService(db)
                            await batch_service.process_file_completion(
                                file_id=int(batch_file_id),
                                extracted_data={},
                                status="failed",
                                error_message=error_msg
                            )
                            return ProcessingResult(success=False, error_message=error_msg, committed=True)
                    
                    # Get AI config
                    ai_conf = await self._get_ai_config(db)
                    
                    # Process invoice
                    extracted_data = await process_pdf_with_ai(file_path, ai_conf)
                    
                    # Create Invoice record from extracted data
                    created_invoice_id = None
                    invoice_creation_error = None
                    try:
                        # Calculate subtotal and amount
                        total_amount = extracted_data.get('total_amount', 0.0)
                        
                        invoice = Invoice(
                            client_id=client_id,
                            number=extracted_data.get('invoice_number', f'BATCH-{batch_file_id}'),
                            due_date=extracted_data.get('due_date') or datetime.now(timezone.utc),
                            amount=total_amount,
                            subtotal=total_amount,  # No discount for batch invoices
                            currency=extracted_data.get('currency', 'USD'),
                            status='draft',
                            notes=f"Batch processed from job {batch_job_id}"
                        )
                        db.add(invoice)
                        db.flush()  # Get the invoice ID
                        
                        # Create invoice items if available
                        items = extracted_data.get('items', extracted_data.get('line_items', []))
                        for item_data in items:
                            item = InvoiceItem(
                                invoice_id=invoice.id,
                                description=item_data.get('description', 'Item'),
                                quantity=item_data.get('quantity', 1.0),
                                price=item_data.get('price', 0.0),
                                amount=item_data.get('amount', 0.0)
                            )
                            db.add(item)
                        
                        # Create attachment record
                        original_filename = payload.get("original_filename", "batch_file")
                        attachment = InvoiceAttachment(
                            invoice_id=invoice.id,
                            filename=original_filename,
                            stored_filename=payload.get("stored_filename", original_filename),
                            file_path=file_path,
                            file_size=payload.get("file_size", 0),
                            content_type='application/pdf',
                            attachment_type='document',
                            uploaded_by=user_id
                        )
                        db.add(attachment)
                        db.commit()
                        
                        created_invoice_id = invoice.id
                        self.logger.info(f"Created invoice record {created_invoice_id} from batch file {batch_file_id}")
                    except Exception as e:
                        self.logger.error(f"Failed to create invoice record: {e}", exc_info=True)
                        db.rollback()
                        invoice_creation_error = str(e)
                    
                    # Update batch processing
                    from commercial.batch_processing.service import BatchProcessingService
                    batch_service = BatchProcessingService(db)
                    
                    # If invoice creation failed, mark as failed
                    if created_invoice_id is None:
                        await batch_service.process_file_completion(
                            file_id=int(batch_file_id),
                            extracted_data=extracted_data,
                            status="failed",
                            error_message=f"Failed to create invoice record: {invoice_creation_error}"
                        )
                        self.logger.warning(f"Batch invoice OCR completed but invoice creation failed: batch_file_id={batch_file_id}")
                        return ProcessingResult(success=False, error_message=invoice_creation_error, committed=True)
                    else:
                        await batch_service.process_file_completion(
                            file_id=int(batch_file_id),
                            extracted_data=extracted_data,
                            status="completed",
                            created_record_id=created_invoice_id,
                            record_type='invoice'
                        )
                    
                    self.logger.info(f"Batch invoice OCR completed: batch_file_id={batch_file_id}")
                    return ProcessingResult(success=True, committed=True)
                    
        except Exception as e:
            self.logger.error(f"Batch invoice OCR failed: {e}")
            
            # Update batch processing with failure
            try:
                with tenant_context(tenant_id):
                    with database_session(tenant_id) as db:
                        from commercial.batch_processing.service import BatchProcessingService
                        batch_service = BatchProcessingService(db)
                        await batch_service.process_file_completion(
                            file_id=int(batch_file_id),
                            status="failed",
                            error_message=str(e)
                        )
            except Exception as update_error:
                self.logger.error(f"Failed to update batch job: {update_error}")
            
            return ProcessingResult(success=False, error_message=str(e), committed=True)
    
    async def _process_single_invoice(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process single invoice"""
        task_id = str(payload.get("task_id"))
        file_path = str(payload.get("file_path"))
        filename = str(payload.get("filename", "invoice.pdf"))
        user_id = int(payload.get("user_id"))
        tenant_id = self.extract_tenant_id(payload)
        
        self.logger.info(f"Processing invoice OCR: task_id={task_id}, file={file_path}")
        
        try:
            with tenant_context(tenant_id):
                with database_session(tenant_id) as db:
                    from core.models.models_per_tenant import AIConfig as AIConfigModel, InvoiceProcessingTask, Client
                    from commercial.ai.pdf_processor import process_pdf_with_ai
                    from types import SimpleNamespace
                    import re
                    
                    # Create or update processing task
                    task = await self._get_or_create_task(db, task_id, file_path, filename, user_id)
                    
                    # Get AI config
                    ai_conf = await self._get_ai_config(db)
                    
                    # Process invoice
                    extracted_data = await process_pdf_with_ai(file_path, ai_conf)
                    
                    # Process client information
                    client_info = await self._process_client_info(db, extracted_data)
                    
                    # Format result
                    result_data = {
                        'invoice_data': extracted_data,
                        'client_exists': client_info['existing_client'] is not None,
                        'existing_client': client_info['existing_client'],
                        'suggested_client': client_info['suggested_client']
                    }
                    
                    # Update task with results
                    task.status = ProcessingStatus.COMPLETED.value
                    task.result_data = result_data
                    task.completed_at = datetime.now(timezone.utc)
                    task.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    
                    self.logger.info(f"Invoice OCR completed successfully: task_id={task_id}")
                    
                    # Send notification
                    await self._send_invoice_notification(db, task_id, user_id, tenant_id)
                    
                    # Release processing lock
                    await self._release_processing_lock("invoice", task_id)
                    
                    return ProcessingResult(success=True, committed=True)
                    
        except Exception as e:
            self.logger.error(f"Failed to process invoice: {e}")
            return await self._handle_invoice_error(consumer, message, payload, e)
    
    async def _handle_invoice_error(self, consumer, message, payload: Dict[str, Any], error: Exception) -> ProcessingResult:
        """Handle invoice processing errors"""
        # Check if this is a batch job
        if self.is_batch_job(payload):
            try:
                tenant_id = self.extract_tenant_id(payload)
                with tenant_context(tenant_id):
                    with database_session(tenant_id) as db:
                        from commercial.batch_processing.service import BatchProcessingService
                        batch_service = BatchProcessingService(db)
                        await batch_service.process_file_completion(
                            file_id=int(payload.get("batch_file_id")),
                            status="failed",
                            error_message=str(error)
                        )
            except Exception as update_error:
                self.logger.error(f"Failed to update batch job: {update_error}")
        else:
            # Update regular task with error
            try:
                tenant_id = self.extract_tenant_id(payload)
                with tenant_context(tenant_id):
                    with database_session(tenant_id) as db:
                        from core.models.models_per_tenant import InvoiceProcessingTask
                        task_id = str(payload.get("task_id"))
                        task = db.query(InvoiceProcessingTask).filter(
                            InvoiceProcessingTask.task_id == task_id
                        ).first()
                        if task:
                            task.status = ProcessingStatus.FAILED.value
                            task.error_message = str(error)
                            task.updated_at = datetime.now(timezone.utc)
                            db.commit()
            except Exception as update_error:
                self.logger.error(f"Failed to update task error: {update_error}")
                db.rollback()
        
        # Commit message to avoid reprocessing
        await self._commit_message(consumer, message)
        return ProcessingResult(success=False, error_message=str(error), committed=True)
    
    async def _get_ai_config(self, db) -> Union[SimpleNamespace, Any]:
        """Get AI configuration"""
        from core.models.models_per_tenant import AIConfig as AIConfigModel
        
        ai_row = db.query(AIConfigModel).filter(
            AIConfigModel.is_active == True,
            AIConfigModel.tested == True
        ).order_by(AIConfigModel.is_default.desc()).first()
        
        if not ai_row:
            # Fallback to environment configuration
            model_name = os.getenv("LLM_MODEL_INVOICES") or os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
            provider_url = os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE")
            api_key = os.getenv("LLM_API_KEY")
            provider_name = "ollama" if os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE") or os.getenv("OLLAMA_MODEL") else "openai"
            
            return SimpleNamespace(
                provider_name=provider_name,
                provider_url=provider_url,
                api_key=api_key,
                model_name=model_name,
                is_active=True,
                tested=True,
            )
        else:
            return ai_row
    
    async def _get_or_create_task(self, db, task_id: str, file_path: str, filename: str, user_id: int) -> "InvoiceProcessingTask":
        """Get existing task or create new one"""
        from core.models.models_per_tenant import InvoiceProcessingTask
        
        task = db.query(InvoiceProcessingTask).filter(
            InvoiceProcessingTask.task_id == task_id
        ).first()
        
        if not task:
            task = InvoiceProcessingTask(
                task_id=task_id,
                file_path=file_path,
                filename=filename,
                user_id=user_id,
                status=ProcessingStatus.PROCESSING.value
            )
            db.add(task)
        else:
            task.status = ProcessingStatus.PROCESSING.value
            task.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        return task
    
    async def _process_client_info(self, db, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process client information from extracted data"""
        from core.models.models_per_tenant import Client
        import re
        
        client_info = extracted_data.get('bills_to', '')
        existing_client = None
        suggested_client = None
        
        if client_info:
            # Check for existing client
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', client_info)
            if email_match:
                client_email = email_match.group()
                existing_client = db.query(Client).filter(
                    Client.email.ilike(client_email)
                ).first()
            
            # Create suggested client
            client_email = email_match.group() if email_match else None
            suggested_client = {
                'name': client_info.split('\n')[0].strip() if client_info else '',
                'email': client_email or '',
                'address': client_info
            }
        
        return {
            'existing_client': {
                'id': existing_client.id,
                'name': existing_client.name,
                'email': existing_client.email
            } if existing_client else None,
            'suggested_client': suggested_client
        }
    
    async def _send_invoice_notification(self, db, task_id: str, user_id: int, tenant_id: int):
        """Send invoice processing completion notification"""
        try:
            from core.utils.ocr_notifications import notify_invoice_ocr_complete
            await notify_invoice_ocr_complete(db, task_id, user_id, tenant_id)
        except Exception as e:
            self.logger.warning(f"Failed to send invoice OCR notification: {e}")
    
    async def _release_processing_lock(self, lock_type: str, item_id: Union[int, str]):
        """Release processing lock"""
        try:
            release_processing_lock(lock_type, item_id)
            self.logger.info(f"Released processing lock for {lock_type} {item_id}")
        except Exception as e:
            self.logger.warning(f"Failed to release processing lock: {e}")
    
    async def _commit_message(self, consumer, message):
        """Safely commit Kafka message"""
        try:
            consumer.commit(message=message, asynchronous=False)
        except Exception as e:
            self.logger.error(f"Failed to commit message: {e}")


# ============================================================================
# Message Router and Consumer
# ============================================================================

class MessageRouter:
    """Routes messages to appropriate handlers"""
    
    def __init__(self, config: OCRConfig):
        self.config = config
        self.handlers: List[BaseMessageHandler] = [
            ExpenseMessageHandler(config),
            BankStatementMessageHandler(config), 
            InvoiceMessageHandler(config)
        ]
        self.logger = logger
    
    def get_handler(self, topic: str, payload: Dict[str, Any]) -> Optional[BaseMessageHandler]:
        """Get appropriate handler for message"""
        for handler in self.handlers:
            if handler.can_handle(topic, payload):
                return handler
        return None


class OCRConsumer:
    """Main OCR consumer with improved architecture"""

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()
        self.consumer: Optional[Any] = None
        self.router = MessageRouter(self.config)
        self.running = False
        self.logger = logger
        self._shutdown_event = asyncio.Event()

    async def start(self) -> int:
        """Start the OCR consumer"""
        try:
            # Initialize consumer
            self.consumer, topics = await self._initialize_consumer()
            if not self.consumer:
                return 1

            # Perform startup tasks
            await self._perform_startup_requeue()

            # Subscribe to topics
            expense_topic, bank_topic, invoice_topic = topics
            self.consumer.subscribe([expense_topic, bank_topic, invoice_topic])

            # Setup signal handlers
            self._setup_signal_handlers()

            self.logger.info(f"OCR consumer running on topics={[expense_topic, bank_topic, invoice_topic]}")

            # Main processing loop
            await self._processing_loop()

            return 0

        except Exception as e:
            self.logger.error(f"Consumer failed to start: {e}")
            return 1
        finally:
            await self._cleanup()

    async def _initialize_consumer(self):
        """Initialize Kafka consumer with topic management"""
        bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        if not bootstrap:
            self.logger.error("KAFKA_BOOTSTRAP_SERVERS not set; cannot start OCR consumer")
            return None, (None, None)

        try:
            from confluent_kafka import Consumer

            # Ensure topics exist
            await self._ensure_topics_exist(bootstrap)

            # Configure consumer
            conf = {
                "bootstrap.servers": bootstrap,
                "group.id": os.getenv("KAFKA_OCR_GROUP", "invoice-app-ocr"),
                "auto.offset.reset": os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
                "enable.auto.commit": False,
                "max.poll.interval.ms": int(os.getenv("KAFKA_MAX_POLL_INTERVAL_MS", "900000")),
                "session.timeout.ms": int(os.getenv("KAFKA_SESSION_TIMEOUT_MS", "45000")),
            }

            self.consumer = Consumer(conf)

            topics = (
                os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr"),
                os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr"),
                os.getenv("KAFKA_INVOICE_TOPIC", "invoices_ocr")
            )

            return self.consumer, topics

        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka consumer: {e}")
            return None, (None, None)

    async def _ensure_topics_exist(self, bootstrap: str):
        """Ensure required topics exist"""
        try:
            from confluent_kafka.admin import AdminClient, NewTopic

            admin = AdminClient({"bootstrap.servers": bootstrap})

            topics = [
                os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr"),
                os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr"),
                os.getenv("KAFKA_INVOICE_TOPIC", "invoices_ocr")
            ]

            for topic in topics:
                await self._ensure_single_topic_exists(admin, topic)

        except Exception as e:
            self.logger.debug(f"Kafka Admin client not available: {e}")

    async def _ensure_single_topic_exists(self, admin, topic_name: str):
        """Ensure a single topic exists"""
        try:
            from confluent_kafka.admin import NewTopic

            md = admin.list_topics(timeout=5)
            if topic_name in md.topics and not md.topics[topic_name].error:
                self.logger.debug(f"Kafka topic '{topic_name}' already exists")
                return

            # Create topic
            partitions = int(os.getenv("KAFKA_OCR_TOPIC_PARTITIONS", "1"))
            replication_factor = int(os.getenv("KAFKA_OCR_TOPIC_RF", "1"))
            new_topic = NewTopic(topic=topic_name, num_partitions=partitions, replication_factor=replication_factor)

            fs = admin.create_topics([new_topic])
            fut = fs.get(topic_name)

            try:
                fut.result(timeout=10)
                self.logger.info(f"Created Kafka topic '{topic_name}' (partitions={partitions}, rf={replication_factor})")
            except Exception as e:
                self.logger.warning(f"Topic creation for '{topic_name}' may have failed or already exists: {e}")

        except Exception as e:
            self.logger.warning(f"Unable to ensure Kafka topic '{topic_name}': {e}")

    async def _perform_startup_requeue(self):
        """Perform startup scan to requeue any queued expenses"""
        try:
            self.logger.info("Startup scan: requeue queued expenses if any")

            # Get tenant IDs
            tenant_ids: List[int] = tenant_db_manager.get_existing_tenant_ids()

            # Process each tenant
            for tid in tenant_ids:
                await self._requeue_tenant_expenses(tid)

        except Exception as e:
            self.logger.warning(f"Startup requeue scan failed: {e}")

    async def _requeue_tenant_expenses(self, tenant_id: int):
        """Requeue queued expenses for a specific tenant"""
        try:
            set_tenant_context(tenant_id)
            SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
        except Exception:
            return

        db = SessionLocalTenant()
        try:
            from core.models.models_per_tenant import Expense, ExpenseAttachment

            queued_expenses = db.query(Expense).filter(
                Expense.analysis_status == ProcessingStatus.QUEUED.value
            ).all()

            for expense in queued_expenses:
                attachment = (
                    db.query(ExpenseAttachment)
                    .filter(ExpenseAttachment.expense_id == expense.id)
                    .order_by(ExpenseAttachment.uploaded_at.desc())
                    .first()
                )

                if not attachment or not getattr(attachment, "file_path", None):
                    continue

                try:
                    from core.services.ocr_service import queue_or_process_attachment
                    await queue_or_process_attachment(db, tenant_id, expense.id, attachment.id, str(attachment.file_path))
                    self.logger.info(f"Requeued queued expense_id={expense.id} tenant_id={tenant_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to requeue expense {expense.id} in tenant {tenant_id}: {e}")

        finally:
            db.close()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info("Stopping OCR consumer...")
            self.running = False
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _processing_loop(self):
        """Main message processing loop"""
        self.running = True

        while self.running and not self._shutdown_event.is_set():
            try:
                # Poll for message with timeout
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    self.logger.error(f"Kafka error: {msg.error()}")
                    continue

                # Process message
                await self._process_message(msg)
                
            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(1)  # Brief pause on unexpected errors

    async def _process_message(self, message):
        """Process a single Kafka message"""
        try:
            # Parse payload
            payload = json.loads(message.value().decode("utf-8"))
            topic_name = message.topic()

            self.logger.info(f"Processing message on topic={topic_name}: keys={list(payload.keys())}")

            # Get handler and process
            handler = self.router.get_handler(topic_name, payload)
            if not handler:
                self.logger.warning(f"No handler for topic {topic_name}, committing and skipping")
                await self._commit_message(message)
                return

            # Extract and validate tenant ID
            tenant_id = handler.extract_tenant_id(payload)
            if tenant_id is None:
                self.logger.error("No tenant_id in message; committing and skipping invalid message")
                await self._commit_message(message)
                return

            # Process with handler
            result = await handler.process(self.consumer, message, payload)

            # Handle processing result
            if result.success and not result.committed:
                await self._commit_message(message)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON message: {e}")
            await self._commit_message(message)
        except Exception as e:
            self.logger.error(f"Failed to handle message: {e}")
            # Don't commit on unexpected errors to allow retry

    async def _commit_message(self, message):
        """Safely commit a Kafka message"""
        try:
            self.consumer.commit(message=message, asynchronous=False)
        except Exception as e:
            self.logger.error(f"Failed to commit message: {e}")

    async def _cleanup(self):
        """Cleanup resources"""
        try:
            if self.consumer:
                self.consumer.close()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main_async() -> int:
    """Async main function"""
    try:
        # Load configuration
        config = OCRConfig(
            max_attempts=int(os.getenv("KAFKA_OCR_MAX_ATTEMPTS", "5")),
            backoff_base_ms=int(os.getenv("KAFKA_OCR_BACKOFF_BASE_MS", "1000")),
            max_backoff_ms=int(os.getenv("KAFKA_OCR_MAX_BACKOFF_MS", "60000")),
            timeout_seconds=int(os.getenv("KAFKA_OCR_TIMEOUT_SECONDS", "300")),
            dlq_enabled=os.getenv("KAFKA_OCR_DLQ_ENABLED", "true").lower() == "true"
        )

        # Create and start consumer
        consumer = OCRConsumer(config)
        return await consumer.start()

    except Exception as e:
        logger.error(f"Failed to start OCR consumer: {e}")
        return 1


def main() -> int:
    """Main entry point - runs async main in event loop"""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("OCR consumer interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"OCR consumer failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())