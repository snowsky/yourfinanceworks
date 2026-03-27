import os
import json
import asyncio
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone

from ._shared import (
    OCRConfig,
    ProcessingResult,
    ProcessingStatus,
    ProcessingError,
    calculate_backoff_delay,
    tenant_context,
    database_session,
    publish_ocr_result,
    publish_ocr_task,
    publish_fraud_audit_task,
    process_attachment_inline,
    apply_ocr_extraction_to_expense,
    OCRTimeoutError,
    OCRProcessingError,
    get_retry_delay,
)
from .base_handler import BaseMessageHandler


# ============================================================================
# Expense Message Handler
# ============================================================================

class ExpenseMessageHandler(BaseMessageHandler):
    """Handler for expense-related messages"""

    def can_handle(self, topic: str, payload: Dict[str, Any]) -> bool:
        expense_topic = os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr")
        return topic == expense_topic

    def get_resource_type(self) -> str:
        return "expense"

    async def process_single(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        return await self._process_single_expense(consumer, message, payload)

    async def process_batch(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        return await self._process_batch_expense(consumer, message, payload)

    async def _process_batch_expense(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Process batch expense job"""
        batch_job_id = payload.get("batch_job_id")
        batch_file_id = payload.get("batch_file_id")
        file_path = str(payload.get("file_path"))
        tenant_id = self.extract_tenant_id(payload)
        user_id = payload.get("user_id")
        api_client_id = payload.get("api_client_id")  # Extract API client ID for attribution

        if not user_id:
            self.logger.error(f"Missing user_id in batch expense payload for file {batch_file_id}")
            return ProcessingResult(success=False, error_message="Missing user_id in payload", committed=False)

        self.logger.info(f"Processing batch expense OCR: batch_job_id={batch_job_id}, batch_file_id={batch_file_id}, user_id={user_id}")

        try:
            with tenant_context(tenant_id):
                with database_session(tenant_id) as db:
                    from commercial.ai.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
                    from commercial.batch_processing.service import BatchProcessingService
                    from core.models.models_per_tenant import Expense, ExpenseAttachment, AIConfig as AIConfigModel, User
                    from datetime import datetime, timezone

                    # Get API client user for attribution if api_client_id is provided
                    created_by_user_id = user_id  # Default to user_id from payload
                    if api_client_id:
                        try:
                            # Query the master database to get API client info
                            from core.models.database import get_master_db
                            from core.models.api_models import APIClient

                            master_db = next(get_master_db())
                            api_client = master_db.query(APIClient).filter(
                                APIClient.client_id == api_client_id
                            ).first()

                            if api_client:
                                # Use the API client's owner user ID for both attribution and gamification
                                created_by_user_id = api_client.user_id
                                self.logger.info(f"Using API client owner for attribution and gamification: client_id={api_client_id}, owner_user_id={created_by_user_id}")
                            else:
                                self.logger.warning(f"API client not found: {api_client_id}, using default user attribution")
                        except Exception as e:
                            self.logger.error(f"Failed to look up API client {api_client_id}: {e}, using default user attribution")

                    # Get AI config
                    ai_conf_model = db.query(AIConfigModel).first()
                    ai_conf = {}
                    if ai_conf_model:
                        ai_conf = {
                            "provider": ai_conf_model.provider_name,
                            "api_key": ai_conf_model.api_key,
                            "model_name": ai_conf_model.model_name,
                            "api_base": ai_conf_model.provider_url,
                            "ocr_enabled": ai_conf_model.ocr_enabled,
                        }

                    # Process with unified OCR service
                    ocr_config = OCRConfig(ai_config=ai_conf, timeout_seconds=300)
                    ocr_service = UnifiedOCRService(ocr_config)

                    # Extract data from file using the service's extract_structured_data method
                    result = await ocr_service.extract_structured_data(file_path, DocumentType.EXPENSE_RECEIPT, db_session=db)

                    if not result.success:
                        raise Exception(result.error_message or "Failed to extract expense data")

                    extracted_data = result.structured_data or {}

                    # Create Expense record with unified mapping
                    created_expense_id = None
                    try:
                        expense = Expense(
                            user_id=user_id,
                            vendor='Unknown Vendor',
                            amount=0.0,
                            currency='USD',
                            expense_date=datetime.now(timezone.utc),
                            category='General',
                            notes=f"Batch processed from job {batch_job_id}",
                            status='recorded',
                            created_by_user_id=created_by_user_id,  # API client attribution
                            analysis_status='processing',
                            imported_from_attachment=True  # Mark as imported from attachment
                        )
                        db.add(expense)
                        db.flush()  # Get the expense ID

                        # Create attachment record
                        import mimetypes
                        original_filename = payload.get("original_filename", "batch_file")
                        content_type, _ = mimetypes.guess_type(original_filename)
                        if not content_type:
                            content_type = 'application/octet-stream'

                        attachment = ExpenseAttachment(
                            expense_id=expense.id,
                            filename=original_filename,
                            file_path=file_path,
                            file_size=payload.get("file_size", 0),
                            content_type=content_type
                        )
                        db.add(attachment)
                        db.flush()

                        # Apply unified robust mapping
                        await apply_ocr_extraction_to_expense(
                            db=db,
                            expense=expense,
                            extracted=extracted_data,
                            attachment_id=attachment.id,
                            ai_extraction_attempted=True,
                            file_path=file_path,
                            ai_config=ai_conf
                        )

                        created_expense_id = expense.id
                        self.logger.info(f"✅ STEP: Created expense record {created_expense_id} from batch file {batch_file_id}")

                        # Trigger Anomaly Detection (AI Auditor)
                        try:
                            # Trigger Fraud Audit asynchronously via Kafka
                            publish_fraud_audit_task(tenant_id, "expense", expense.id)
                        except Exception as e:
                            self.logger.warning(f"Failed to run anomaly detection for batch expense {expense.id}: {e}")

                        # Process gamification event for API-created expense
                        try:
                            from core.services.tenant_database_manager import tenant_db_manager
                            from core.services.financial_event_processor import create_financial_event_processor

                            self.logger.info(f"STEP: Processing gamification for expense {expense.id}")

                            # Get tenant database session for gamification
                            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
                            if tenant_session:
                                gamification_db = tenant_session()
                                try:
                                    event_processor = create_financial_event_processor(gamification_db)

                                    expense_data = {
                                        "vendor": expense.vendor,
                                        "category": expense.category,
                                        "amount": float(expense.amount) if expense.amount else 0
                                    }

                                    # For API keys, use the master user ID directly
                                    await event_processor.process_expense_added(
                                        user_id=created_by_user_id,
                                        expense_id=expense.id,
                                        expense_data=expense_data
                                    )
                                    self.logger.info(f"✅ STEP: Gamification processed for expense {expense.id}")
                                finally:
                                    gamification_db.close()
                        except Exception as e:
                            self.logger.warning(f"Failed to process gamification: {e}")

                    except Exception as e:
                        self.logger.error(f"❌ Error during expense record creation: {e}", exc_info=True)
                        db.rollback()

                    # Update batch processing service
                    self.logger.info(f"STEP: Updating batch service for expense {batch_file_id}")
                    batch_service = BatchProcessingService(db)
                    await batch_service.process_file_completion(
                        file_id=int(batch_file_id),
                        extracted_data=extracted_data,
                        status="completed" if created_expense_id else "failed",
                        created_record_id=created_expense_id,
                        record_type='expense'
                    )

                    self.logger.info(f"✅ Batch expense OCR completed: batch_file_id={batch_file_id}")
                    return ProcessingResult(success=True, committed=False)

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

                    # Check if expense exists, is not deleted, and is not manually overridden
                    exp = db.query(Expense).filter(Expense.id == expense_id).first()
                    if not exp:
                        self.logger.warning(f"Expense {expense_id} not found; skipping")
                        return ProcessingResult(success=True, committed=True)
                    if getattr(exp, 'is_deleted', False):
                        self.logger.warning(f"Expense {expense_id} is deleted; skipping OCR")
                        return ProcessingResult(success=True, committed=True)

                    if exp.manual_override:
                        self.logger.info(f"Expense {expense_id} manually overridden; skipping OCR")
                        return ProcessingResult(success=True, committed=True)

                    # Skip already done check to allow reprocessing
                    # if getattr(exp, "analysis_status", None) == ProcessingStatus.DONE.value:
                    #     self.logger.info(f"Expense {expense_id} already done. Skipping reprocessing.")
                    #     await self._commit_message(consumer, message)
                    #     return ProcessingResult(success=True, committed=True)

                    # Skip already failed check to allow manual reprocessing
                    # if getattr(exp, "analysis_status", None) == ProcessingStatus.FAILED.value:
                    #     self.logger.warning(f"Expense {expense_id} marked as FAILED. Skipping retry loop.")
                    #     await self._commit_message(consumer, message)
                    #     await self._publish_ocr_result(expense_id, tenant_id, "failed")
                    #     return ProcessingResult(success=False, committed=True, should_retry=False)

                    # Update expense status
                    try:
                        exp.analysis_status = ProcessingStatus.PROCESSING.value
                        exp.updated_at = datetime.now(timezone.utc)
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise ProcessingError("Failed to update expense status")

                    # Fetch AI config from database to ensure consistency with what user configured
                    ai_config = None
                    try:
                        from core.models.models_per_tenant import AIConfig as AIConfigModel
                        from commercial.ai.services.ai_config_service import AIConfigService

                        # Use new service if possible or query directly
                        # We want ANY valid OCR config, even if not explicitly "tested" via the UI button
                        # This fixes the issue where valid configs are ignored because they weren't "tested"
                        ai_row = db.query(AIConfigModel).filter(
                            AIConfigModel.is_active == True,
                            AIConfigModel.ocr_enabled == True
                        ).order_by(AIConfigModel.is_default.desc()).first()

                        if ai_row:
                            ai_config = {
                                "provider_name": ai_row.provider_name,
                                "provider_url": ai_row.provider_url,
                                "api_key": ai_row.api_key,
                                "model_name": ai_row.model_name,
                                "ocr_enabled": ai_row.ocr_enabled,
                            }
                            self.logger.info(f"Using OCR config from DB: {ai_row.provider_name}/{ai_row.model_name}")
                    except Exception as config_error:
                         self.logger.warning(f"Failed to fetch AI config in consumer: {config_error}")

                    # Process with OCR
                    await process_attachment_inline(db, expense_id, attachment_id, file_path, tenant_id, ai_config=ai_config)

                    # Refresh and check result
                    db.refresh(exp)

                    if getattr(exp, "analysis_status", None) == ProcessingStatus.DONE.value:
                        # Success - commit and publish result

                        # Trigger Anomaly Detection (AI Auditor)
                        try:
                            # Trigger Fraud Audit asynchronously via Kafka
                            publish_fraud_audit_task(tenant_id, "expense", exp.id) # Corrected entity type and ID
                        except Exception as e:
                            self.logger.warning(f"Failed to run anomaly detection for expense {expense_id}: {e}")

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
        # Non-retryable errors: invalid request, bad image, model limitations, auth failures
        non_retryable_patterns = [
            "invalid_request_error", "could not process image", "bad request",
            "invalidaccesskeyid", "authentication", "authorization",
            "does not support image", "does not support vision",
        ]
        if any(p in error_message.lower() for p in non_retryable_patterns):
            self.logger.warning(f"Non-retryable OCR error for expense_id={expense_id}: {error_message}")
            await self._send_to_dlq(expense_id, tenant_id, payload.get("attachment_id"), payload.get("file_path"), error_message, payload)
            return ProcessingResult(success=False, committed=True)

        if "timeout" in error_message.lower():
            retry_delay = min(300000, 60000 * (attempt + 1))  # 1-5 minutes for timeouts
        else:
            retry_delay = calculate_backoff_delay(attempt)

        if attempt < self.config.max_attempts:
            # Requeue with backoff
            self.logger.warning(f"Requeueing expense_id={expense_id} attempt={attempt+1} after {retry_delay}ms")
            await asyncio.sleep(retry_delay / 1000.0)

            payload.update({"attempt": attempt + 1})
            publish_ocr_task(payload)
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
            from commercial.ai.services.ocr_service import _get_kafka_producer

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
