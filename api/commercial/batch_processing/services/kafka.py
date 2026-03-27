"""
Kafka integration for batch processing.

Handles enqueueing batch files to document-type-specific Kafka topics
with retry logic.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy import and_

from core.models.models_per_tenant import BatchProcessingJob, BatchFileProcessing

logger = logging.getLogger(__name__)


class BatchKafkaMixin:
    """Mixin providing Kafka enqueueing for batch files."""

    async def enqueue_files_to_kafka(self, job_id: str) -> Dict[str, Any]:
        try:
            batch_job = self.db.query(BatchProcessingJob).filter(
                BatchProcessingJob.job_id == job_id
            ).first()

            if not batch_job:
                raise ValueError(f"Batch job {job_id} not found")

            batch_files = self.db.query(BatchFileProcessing).filter(
                and_(
                    BatchFileProcessing.job_id == job_id,
                    BatchFileProcessing.status == "pending"
                )
            ).all()

            if not batch_files:
                logger.warning(f"No pending files found for job {job_id}")
                return {"job_id": job_id, "enqueued": 0, "failed": 0, "files": []}

            batch_job.status = "processing"
            self.db.commit()

            enqueued_count = 0
            failed_count = 0
            results = []

            for batch_file in batch_files:
                try:
                    topic = self._get_kafka_topic_for_document_type(batch_file.document_type)

                    file_card_type = (
                        (batch_file.extracted_data or {}).get("card_type", "auto")
                        if batch_file.document_type == "statement"
                        else "auto"
                    )
                    message_id = await self._publish_to_kafka(
                        topic=topic,
                        job_id=job_id,
                        file_id=batch_file.id,
                        file_path=batch_file.file_path,
                        original_filename=batch_file.original_filename,
                        file_size=batch_file.file_size,
                        tenant_id=batch_job.tenant_id,
                        user_id=batch_job.user_id,
                        document_type=batch_file.document_type,
                        api_client_id=batch_job.api_client_id,
                        card_type=file_card_type
                    )

                    batch_file.kafka_topic = topic
                    batch_file.kafka_message_id = message_id
                    batch_file.status = "processing"
                    batch_file.processing_started_at = datetime.now(timezone.utc)

                    enqueued_count += 1
                    results.append({
                        "file_id": batch_file.id,
                        "filename": batch_file.original_filename,
                        "topic": topic,
                        "message_id": message_id,
                        "status": "enqueued"
                    })

                    logger.info(
                        f"Enqueued file {batch_file.id} ({batch_file.original_filename}) "
                        f"to topic {topic}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to enqueue file {batch_file.id} "
                        f"({batch_file.original_filename}): {e}"
                    )
                    batch_file.status = "failed"
                    batch_file.error_message = f"Failed to enqueue: {str(e)}"

                    failed_count += 1
                    results.append({
                        "file_id": batch_file.id,
                        "filename": batch_file.original_filename,
                        "status": "failed",
                        "error": str(e)
                    })

            self.db.commit()

            logger.info(
                f"Enqueued {enqueued_count} files, {failed_count} failed "
                f"for job {job_id}"
            )

            return {
                "job_id": job_id,
                "enqueued": enqueued_count,
                "failed": failed_count,
                "files": results
            }

        except Exception as e:
            logger.error(f"Failed to enqueue files for job {job_id}: {e}")
            self.db.rollback()
            raise

    def _get_kafka_topic_for_document_type(self, document_type: str) -> str:
        if document_type == 'invoice':
            topic = os.getenv('KAFKA_INVOICE_TOPIC', 'invoices_ocr')
        elif document_type == 'expense':
            topic = os.getenv('KAFKA_OCR_TOPIC', 'expense_ocr')
        elif document_type == 'statement':
            topic = os.getenv('KAFKA_BANK_TOPIC', 'bank_statements_ocr')
        else:
            raise ValueError(f"Unknown document type: {document_type}")

        logger.debug(f"Mapped document type '{document_type}' to topic '{topic}'")
        return topic

    async def _publish_to_kafka(
        self,
        topic: str,
        job_id: str,
        file_id: int,
        file_path: str,
        original_filename: str,
        file_size: int,
        tenant_id: int,
        user_id: int,
        document_type: str,
        api_client_id: Optional[str] = None,
        card_type: str = "auto"
    ) -> str:
        message_id = str(uuid.uuid4())

        message = {
            "batch_job_id": job_id,
            "batch_file_id": file_id,
            "file_path": file_path,
            "original_filename": original_filename,
            "file_size": file_size,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "document_type": document_type,
            "api_client_id": api_client_id,
            "card_type": card_type,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attempt": 0
        }

        try:
            from commercial.ai.services.ocr_service import _get_kafka_producer_for

            producer, _ = _get_kafka_producer_for(
                f"KAFKA_{document_type.upper()}_TOPIC",
                topic
            )

            if not producer:
                raise Exception("Kafka producer not available")

            max_retries = 3
            retry_delay = 1.0

            for attempt in range(max_retries):
                try:
                    payload = json.dumps(message).encode('utf-8')
                    key = f"{tenant_id}_{job_id}_{file_id}"

                    producer.produce(topic, value=payload, key=key)
                    remaining = producer.flush(timeout=10.0)

                    if remaining == 0:
                        logger.debug(
                            f"Published message {message_id} to topic {topic} "
                            f"(attempt {attempt + 1})"
                        )
                        return message_id
                    else:
                        raise Exception(
                            f"Failed to flush message, {remaining} messages remaining"
                        )

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Kafka publish attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {retry_delay}s..."
                        )
                        import asyncio
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        raise

            raise Exception(f"Failed to publish to Kafka after {max_retries} attempts")

        except Exception as e:
            logger.error(f"Failed to publish message to Kafka topic {topic}: {e}")
            raise
