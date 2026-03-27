import os
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone
from types import SimpleNamespace

from ._shared import (
    OCRConfig,
    ProcessingResult,
    ProcessingStatus,
    tenant_context,
    database_session,
    release_processing_lock,
    parse_number,
    first_key,
)
from .base_handler import BaseMessageHandler


# ============================================================================
# Invoice Message Handler
# ============================================================================

class InvoiceMessageHandler(BaseMessageHandler):
    """Handler for invoice messages"""

    def can_handle(self, topic: str, payload: Dict[str, Any]) -> bool:
        invoice_topic = os.getenv("KAFKA_INVOICE_TOPIC", "invoices_ocr")
        return topic == invoice_topic

    def get_resource_type(self) -> str:
        return "invoice"

    async def process_single(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        return await self._process_single_invoice(consumer, message, payload)

    async def process_batch(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        return await self._process_batch_invoice(consumer, message, payload)

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

                    # Use default client if no client_id is specified
                    if client_id is None:
                        client_id = await self._get_or_create_default_client(db)
                        self.logger.info(f"Using default client ID {client_id} for batch invoice processing")

                    # Validate client_id exists before processing
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
                    extracted_data = await process_pdf_with_ai(file_path, ai_conf, db=db)

                    # Create Invoice record from extracted data
                    created_invoice_id = None
                    invoice_creation_error = None
                    try:
                        # Calculate subtotal and amount
                        total_amount = parse_number(first_key(extracted_data, ['total_amount', 'total', 'amount'])) or 0.0

                        invoice = Invoice(
                            client_id=client_id,
                            number=first_key(extracted_data, ['invoice_number', 'number']) or f'BATCH-{batch_file_id}',
                            due_date=first_key(extracted_data, ['due_date', 'date']) or datetime.now(timezone.utc),
                            amount=total_amount,
                            subtotal=total_amount,  # No discount for batch invoices
                            currency=first_key(extracted_data, ['currency', 'currency_code']) or 'USD',
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
                        return ProcessingResult(success=False, error_message=invoice_creation_error, committed=False)
                    else:
                        await batch_service.process_file_completion(
                            file_id=int(batch_file_id),
                            extracted_data=extracted_data,
                            status="completed",
                            created_record_id=created_invoice_id,
                            record_type='invoice'
                        )

                    self.logger.info(f"✅ Batch invoice OCR completed: batch_file_id={batch_file_id}")
                    return ProcessingResult(success=True, committed=False)

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

                    # Create or update processing task
                    task = await self._get_or_create_task(db, task_id, file_path, filename, user_id)

                    # Check if already completed - skip reprocessing
                    if task.status == ProcessingStatus.COMPLETED.value:
                        self.logger.info(f"Invoice task {task_id} already completed. Skipping reprocessing.")
                        await self._commit_message(consumer, message)
                        return ProcessingResult(success=True, committed=True)

                    # Get AI config
                    ai_conf = await self._get_ai_config(db)

                    # Process invoice
                    extracted_data = await process_pdf_with_ai(file_path, ai_conf, db=db)

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
                ocr_enabled=True,  # Default to True for environment config
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
            # Check if already completed - skip reprocessing
            if task.status == ProcessingStatus.COMPLETED.value:
                self.logger.info(f"Invoice task {task_id} already completed. Skipping reprocessing.")
                return task

            task.status = ProcessingStatus.PROCESSING.value
            task.updated_at = datetime.now(timezone.utc)

        db.commit()
        return task

    async def _get_or_create_default_client(self, db) -> int:
        """Get existing default client or create a new one"""
        from core.models.models_per_tenant import Client

        # Look for existing default client
        default_client = db.query(Client).filter(Client.name == "Default Client").first()

        if default_client:
            return default_client.id

        # Create new default client
        default_client = Client(
            name="Default Client",
            email="default@example.com",
            address="Default address for auto-created invoices",
            phone="",
            is_active=True
        )
        db.add(default_client)
        db.flush()  # Get the ID without committing
        return default_client.id

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
