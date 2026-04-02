import os
import asyncio
from typing import Optional, Dict, Any, List, Union

from ._shared import (
    OCRConfig,
    ProcessingResult,
    ProcessingStatus,
    calculate_backoff_delay,
    tenant_context,
    database_session,
    BankStatementTransaction,
    publish_fraud_audit_task,
    release_processing_lock,
    parse_number,
    get_tenant_timezone_aware_datetime,
)
from .base_handler import BaseMessageHandler


# ============================================================================
# Bank Statement Message Handler
# ============================================================================

class BankStatementMessageHandler(BaseMessageHandler):
    """Handler for bank statement messages"""

    def can_handle(self, topic: str, payload: Dict[str, Any]) -> bool:
        bank_topic = os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr")
        return topic == bank_topic

    def get_resource_type(self) -> str:
        return "bank_statement"

    async def process_single(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        return await self._process_single_statement(consumer, message, payload)

    async def process_batch(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        return await self._process_batch_statement(consumer, message, payload)

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
                    from core.services.statement_service import process_bank_pdf_with_llm, is_bank_llm_reachable, BankLLMUnavailableError
                    from commercial.ai.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
                    from datetime import datetime, timezone

                    # Get AI config
                    ai_conf = await self._get_ai_config(db)

                    # Get cloud file URL from batch file record
                    from core.models.models_per_tenant import BatchFileProcessing
                    batch_file = db.query(BatchFileProcessing).filter(
                        BatchFileProcessing.id == int(batch_file_id)
                    ).first()
                    cloud_file_url = batch_file.cloud_file_url if batch_file else None

                    # Create initial BankStatement record
                    statement = BankStatement(
                        tenant_id=tenant_id,
                        original_filename=payload.get("original_filename", "batch_file"),
                        stored_filename=payload.get("stored_filename", payload.get("original_filename", "batch_file")),
                        file_path=file_path,
                        cloud_file_url=cloud_file_url,
                        status='processing',
                        extracted_count=0,
                        notes=f"Batch processing started from job {batch_job_id}"
                    )
                    db.add(statement)
                    db.flush()  # Get the statement ID

                    # Ensure file is local using the real statement object
                    try:
                        # Pass payload to handle cloud key derivation and race conditions
                        file_path = await self._ensure_local_statement_file(db, statement, file_path, tenant_id, payload)
                    except Exception as e:
                        self.logger.error(f"Failed to ensure local file for batch statement: {e}")
                        statement.status = 'failed'
                        db.commit()
                        raise e

                    # Try unified OCR first, fallback to legacy
                    card_type = payload.get("card_type", "auto")
                    txns = []
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
                            txns = process_bank_pdf_with_llm(file_path, ai_conf, db, card_type=card_type)
                        else:
                            self.logger.warning(f"UnifiedOCR text extraction failed: {text_result.error_message}. Falling back to legacy.")
                            txns = process_bank_pdf_with_llm(file_path, ai_conf, db, card_type=card_type)

                    except Exception as e:
                        self.logger.warning(f"UnifiedOCR encountered error: {e}. Falling back to legacy.")
                        txns = process_bank_pdf_with_llm(file_path, ai_conf, db, card_type=card_type)

                    # Update statement with final results
                    created_statement_id = None

                    # Verify LLM reachability if no transactions found
                    if not txns:
                         if not is_bank_llm_reachable(ai_conf):
                             raise BankLLMUnavailableError("Bank LLM is unreachable and no transactions were extracted during batch processing.")

                    try:
                        statement.status = ProcessingStatus.PROCESSED.value
                        statement.extracted_count = len(txns) if txns else 0
                        statement.notes = f"Batch processed from job {batch_job_id}"
                        statement.file_path = file_path # Update to local path if changed
                        if txns:
                            detected = txns[0].get('card_type')
                            if detected in ('credit', 'debit'):
                                statement.card_type = detected

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
                        if txns:
                            for txn in txns:
                                # Validate required fields
                                if not txn.get('date'):
                                    self.logger.warning(f"Skipping transaction with missing date: {txn}")
                                    continue

                                try:
                                    transaction = BankStatementTransaction(
                                        statement_id=statement.id,
                                        date=txn.get('date'),
                                        description=txn.get('description', ''),
                                        amount=parse_number(txn.get('amount', 0.0)),
                                        transaction_type=txn.get('transaction_type', 'debit'),
                                        balance=parse_number(txn.get('balance')),
                                        category=txn.get('category')
                                    )
                                    db.add(transaction)
                                except Exception as txn_error:
                                    self.logger.error(f"Failed to create transaction record: {txn_error}, txn data: {txn}")
                                    continue

                            self.logger.info(f"Created transaction records for statement {statement.id}")

                        db.commit()

                        created_statement_id = statement.id
                        self.logger.info(f"✅ STEP: Updated bank statement record {created_statement_id}")
                    except Exception as e:
                        self.logger.error(f"❌ Failed to finalize bank statement record: {e}")
                        db.rollback()

                    # Update batch processing
                    self.logger.info(f"STEP: Updating batch service for statement {batch_file_id}")
                    from commercial.batch_processing.service import BatchProcessingService
                    batch_service = BatchProcessingService(db)
                    await batch_service.process_file_completion(
                        file_id=int(batch_file_id),
                        extracted_data={"transactions": txns, "transaction_count": len(txns)},
                        status="completed" if created_statement_id else "failed",
                        created_record_id=created_statement_id,
                        record_type='statement'
                    )

                    self.logger.info(f"✅ Batch bank statement OCR completed: batch_file_id={batch_file_id}")
                    return ProcessingResult(success=True, committed=False)

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
        original_file_path = str(payload.get("file_path"))
        tenant_id = self.extract_tenant_id(payload)
        attempt = int(payload.get("attempt", 0))

        self.logger.info(f"Processing bank statement: id={statement_id}, attempt={attempt}")

        try:
            with tenant_context(tenant_id):
                with database_session(tenant_id) as db:
                    from core.models.models_per_tenant import BankStatement, AIConfig as AIConfigModel
                    from core.services.statement_service import process_bank_pdf_with_llm, is_bank_llm_reachable, BankLLMUnavailableError

                    # Get AI config
                    ai_conf = await self._get_ai_config(db)

                    # Check if statement exists
                    stmt = db.query(BankStatement).filter(BankStatement.id == statement_id).first()
                    if stmt:
                         self.logger.info(f"Processing stmt {stmt.id}: initial created_by_user_id={stmt.created_by_user_id}")

                    if not stmt:
                        return ProcessingResult(success=True, committed=True)

                    # Check if already done - skip reprocessing
                    if stmt.status == ProcessingStatus.PROCESSED.value:
                        self.logger.info(f"Bank statement {statement_id} already processed. Skipping reprocessing.")
                        await self._commit_message(consumer, message)
                        return ProcessingResult(success=True, committed=True)

                    # Check if already failed - prevent infinite retry loop
                    if stmt.status == ProcessingStatus.FAILED.value:
                        self.logger.warning(f"Bank statement {statement_id} marked as FAILED. Skipping retry loop.")
                        await self._commit_message(consumer, message)
                        return ProcessingResult(success=False, committed=True, should_retry=False)

                    # Update status to processing
                    await self._handle_processing_status(db, stmt, ProcessingStatus.PROCESSING.value)

                    # Ensure file is local
                    try:
                        file_path = await self._ensure_local_statement_file(db, stmt, original_file_path, tenant_id, payload)
                    except Exception as e:
                        return await self._handle_statement_error(consumer, message, db, stmt, e, attempt, payload)

                    # Check LLM availability and process
                    try:
                        llm_ok = is_bank_llm_reachable(ai_conf)
                        txns = process_bank_pdf_with_llm(file_path, ai_conf, db, card_type=getattr(stmt, 'card_type', 'debit'))

                        self.logger.info(f"Extracted {len(txns)} transactions for statement_id={statement_id}")

                        # If auto-detected, save the result back to the statement
                        if getattr(stmt, 'card_type', 'debit') == 'auto' and txns:
                            detected = txns[0].get('card_type')
                            if detected in ['credit', 'debit']:
                                self.logger.info(f"Saving detected card_type '{detected}' for statement {statement_id}")
                                stmt.card_type = detected
                                try:
                                    db.add(stmt)
                                    db.commit()
                                    db.refresh(stmt)
                                except Exception as e:
                                    self.logger.warning(f"Failed to update detected card_type for statement {statement_id}: {e}")
                                    db.rollback()

                        # Handle processing results
                        if not txns:
                            if llm_ok:
                                # LLM worked but no transactions found - accept as processed
                                await self._handle_zero_transactions(db, stmt)
                                return ProcessingResult(success=True, committed=True)
                            else:
                                # LLM unreachable and no transactions - fail correctly
                                raise BankLLMUnavailableError("Bank LLM is unreachable and no transactions were extracted.")

                        # Detect extraction method
                        ext = file_path.lower().split('.')[-1]
                        method = "csv" if ext == "csv" else "llm"

                        # Save transactions
                        await self._save_transactions(db, stmt, txns, method)

                        # Trigger Anomaly Detection for each transaction
                        try:
                            # We get the fresh transactions from the DB to have their IDs
                            new_txns = db.query(BankStatementTransaction).filter(
                                BankStatementTransaction.statement_id == statement_id
                            ).all()

                            for txn in new_txns:
                                publish_fraud_audit_task(tenant_id, "bank_statement_transaction", txn.id)
                        except Exception as e:
                            self.logger.warning(f"Failed to run anomaly detection for statement transactions {statement_id}: {e}")

                        return ProcessingResult(success=True, committed=True)

                    except Exception as e:
                        return await self._handle_statement_error(consumer, message, db, stmt, e, attempt, payload)

        except Exception as e:
            self.logger.error(f"Failed to process bank statement {statement_id}: {e}")
            return ProcessingResult(success=False, error_message=str(e))

    async def _handle_statement_error(self, consumer, message, db, stmt, error: Exception, attempt: int, payload: Dict[str, Any]) -> ProcessingResult:
        """Handle bank statement processing errors"""
        from commercial.ai.services.ocr_service import publish_bank_statement_task

        statement_id = stmt.id
        retry_delay = calculate_backoff_delay(attempt)

        # Check for specific error types
        error_name = error.__class__.__name__
        if error_name == "BankLLMUnavailableError":
            # Fail fast for LLM unavailable - if service is down, retrying won't help
            # User can manually reprocess once they restart the LLM service
            if attempt >= 1:  # Fail after first attempt instead of max_attempts (5)
                self.logger.error(f"Bank LLM unavailable after {attempt+1} attempts for statement_id={statement_id}")
                stmt.status = "failed"
                stmt.analysis_error = str(error)
                stmt.extraction_method = "failed"
                stmt.analysis_updated_at = get_tenant_timezone_aware_datetime(db)
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                await self._commit_message(consumer, message)
                return ProcessingResult(success=False, committed=True)
            else:
                # Requeue with backoff
                self.logger.warning(f"LLM unavailable, retrying statement_id={statement_id} attempt={attempt+1} after {retry_delay}ms")
                await asyncio.sleep(retry_delay / 1000.0)
                payload.update({"attempt": attempt + 1})
                await publish_bank_statement_task(payload)
                await self._handle_processing_status(db, stmt, ProcessingStatus.PROCESSING.value)
                await self._commit_message(consumer, message)
                return ProcessingResult(success=False, should_retry=True, retry_count=attempt + 1)

        # Generic error handling
        self.logger.error(f"Failed processing bank statement: {error}")
        stmt.status = "failed"
        stmt.analysis_error = str(error)
        stmt.extraction_method = "failed"
        stmt.analysis_updated_at = get_tenant_timezone_aware_datetime(db)
        try:
            db.commit()
        except Exception:
            db.rollback()
        await self._commit_message(consumer, message)
        return ProcessingResult(success=False, committed=True)

    async def _ensure_local_statement_file(self, db, stmt, file_path: str, tenant_id: int, payload: Dict[str, Any] = None) -> str:
        """
        Ensure the statement file is available locally.
        Downloads from cloud storage if missing and caches the local path.
        Includes retry logic for race conditions with background cloud uploads.
        """
        if os.path.exists(file_path):
            self.logger.info(f"Using local file path: {file_path}")
            return file_path

        self.logger.info(f"File path '{file_path}' doesn't exist locally - checking for cloud storage...")

        # 1. Check for cached local file
        if stmt.local_cache_path and os.path.exists(stmt.local_cache_path) and os.path.getsize(stmt.local_cache_path) > 0:
            self.logger.info(f"Using cached local file from previous download: {stmt.local_cache_path}")
            return stmt.local_cache_path

        # 2. Download from cloud storage with retry for race conditions
        max_retries = 3
        retry_delay = 3.0  # Seconds
        
        for attempt in range(max_retries):
            try:
                from commercial.cloud_storage.service import CloudStorageService
                from commercial.cloud_storage.config import get_cloud_storage_config
                import tempfile
                from core.models.models_per_tenant import BatchFileProcessing

                cloud_config = get_cloud_storage_config()
                cloud_storage_service = CloudStorageService(db, cloud_config)

                # Find the correct cloud key
                # Priority 1: From current statement record
                cloud_key = stmt.cloud_file_url
                
                # Priority 2: From BatchFileProcessing record (might have been updated by background task)
                if not cloud_key and payload and payload.get("batch_file_id"):
                    db.refresh(stmt) # Ensure we have latest
                    batch_file = db.query(BatchFileProcessing).filter(
                        BatchFileProcessing.id == int(payload["batch_file_id"])
                    ).first()
                    if batch_file and batch_file.cloud_file_url:
                        cloud_key = batch_file.cloud_file_url
                        stmt.cloud_file_url = cloud_key
                        db.commit()

                # Priority 3: Derived from batch_job_id and filename (standard pattern)
                if not cloud_key and payload and payload.get("batch_job_id") and payload.get("original_filename"):
                    job_id = payload["batch_job_id"]
                    filename = payload["original_filename"]
                    cloud_key = f"{job_id}/{filename}"
                    self.logger.info(f"Derived cloud key: {cloud_key}")

                if not cloud_key:
                    # If this is not the last attempt, wait and retry
                    if attempt < max_retries - 1:
                        self.logger.warning(f"No cloud key found for statement {stmt.id} yet. Retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        db.expire_all() # Refresh all objects for next attempt
                        continue
                    else:
                        raise Exception("No cloud key available after retries")

                # Retrieve from cloud
                self.logger.info(f"Retrieving file from cloud using key: {cloud_key}")
                retrieve_result = await cloud_storage_service.retrieve_file(
                    file_key=cloud_key,
                    tenant_id=str(tenant_id),
                    user_id=1,  # System user
                    generate_url=False
                )

                if retrieve_result.success and retrieve_result.file_content:
                    # Save to temp file
                    suffix = f"_{stmt.id}_{os.path.basename(file_path)}"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                        temp_file.write(retrieve_result.file_content)
                        temp_path = temp_file.name

                    # Cache the local path
                    stmt.local_cache_path = temp_path
                    db.commit()
                    self.logger.info(f"Successfully downloaded and cached cloud file to {temp_path}")
                    return temp_path
                else:
                    error_msg = retrieve_result.error_message or "Unknown cloud storage error"
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Cloud retrieval failed: {error_msg}. Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        raise Exception(f"Failed to retrieve file from cloud after retries: {error_msg}")

            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Error during cloud download attempt {attempt + 1}: {e}. Retrying...")
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(f"Cloud download failed after {max_retries} attempts: {e}")
                    raise

        raise Exception(f"Failed to ensure local statement file for {stmt.id}")

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
                "ocr_enabled": ai_row.ocr_enabled,
            }
        else:
            self.logger.warning("⚠️ No AI config found in database, using environment variables")
            return None

    async def _handle_zero_transactions(self, db, stmt):
        """Handle statement with zero transactions"""

        db.query(BankStatementTransaction).filter(
            BankStatementTransaction.statement_id == stmt.id
        ).delete()
        stmt.status = ProcessingStatus.PROCESSED.value
        stmt.extracted_count = 0
        db.commit()
        self.logger.info(f"Bank statement processed with 0 transactions: id={stmt.id}")

        # Release processing lock (CRITICAL FIX for infinite processing state)
        await self._release_processing_lock("bank_statement", stmt.id)

    async def _save_transactions(self, db, stmt, transactions: List[Dict[str, Any]], method: str = "unknown"):
        """Save extracted transactions to database"""
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
                amount=parse_number(txn_data.get("amount", 0)),
                transaction_type=(
                    txn_data.get("transaction_type")
                    if txn_data.get("transaction_type") in ("debit", "credit")
                    else (
                        ("credit" if parse_number(txn_data.get("amount", 0)) < 0 else "debit")
                        if getattr(stmt, 'card_type', 'debit') == 'credit'
                        else ("debit" if parse_number(txn_data.get("amount", 0)) < 0 else "credit")
                    )
                ),
                balance=parse_number(txn_data.get("balance")),
                category=txn_data.get("category"),
            ))
            count += 1

        stmt.status = ProcessingStatus.PROCESSED.value
        stmt.extracted_count = count
        stmt.extraction_method = method
        stmt.analysis_error = None
        stmt.analysis_updated_at = get_tenant_timezone_aware_datetime(db)
        self.logger.info(f"Saving stmt {stmt.id}: checking created_by_user_id={stmt.created_by_user_id}")
        db.commit()
        self.logger.info(f"Bank statement processed: id={stmt.id}, transactions={count}")

        # Release processing lock
        await self._release_processing_lock("bank_statement", stmt.id)

    async def _handle_processing_status(self, db, stmt, status: str):
        """Update processing status"""
        try:
            stmt.status = status
            db.commit()
        except Exception:
            db.rollback()

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
