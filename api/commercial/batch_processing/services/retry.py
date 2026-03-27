"""
Retry logic for failed batch files.

Provides exponential backoff retry for individual files and bulk
retry-all operations for a job.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import and_

from core.models.models_per_tenant import BatchProcessingJob, BatchFileProcessing

logger = logging.getLogger(__name__)


class BatchRetryMixin:
    """Mixin providing retry logic for failed batch files."""

    def should_retry_file(
        self,
        batch_file: BatchFileProcessing,
        max_retries: int = 3
    ) -> bool:
        if batch_file.status != "failed":
            return False
        if batch_file.retry_count >= max_retries:
            return False
        return True

    def get_retry_delay(self, retry_count: int) -> float:
        return float(2 ** (retry_count - 1))

    async def retry_failed_file(
        self,
        file_id: int,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        try:
            batch_file = self.db.query(BatchFileProcessing).filter(
                BatchFileProcessing.id == file_id
            ).first()

            if not batch_file:
                raise ValueError(f"Batch file {file_id} not found")

            if batch_file.status not in ["failed", "processing"]:
                raise ValueError(
                    f"File {file_id} is in status '{batch_file.status}' "
                    f"and cannot be retried"
                )

            if batch_file.retry_count >= max_retries:
                logger.warning(
                    f"File {file_id} has reached maximum retry attempts "
                    f"({batch_file.retry_count}/{max_retries}). "
                    f"Marking as permanently failed."
                )
                batch_file.status = "failed"
                batch_file.error_message = (
                    f"Permanently failed after {batch_file.retry_count} retry attempts. "
                    f"Last error: {batch_file.error_message}"
                )
                self.db.commit()
                return {
                    "file_id": file_id,
                    "status": "permanently_failed",
                    "retry_count": batch_file.retry_count,
                    "max_retries": max_retries,
                    "message": "Maximum retry attempts reached"
                }

            batch_file.retry_count += 1
            backoff_delay = self.get_retry_delay(batch_file.retry_count)

            logger.info(
                f"Retrying file {file_id} (attempt {batch_file.retry_count}/{max_retries}) "
                f"after {backoff_delay}s backoff"
            )

            import asyncio
            await asyncio.sleep(backoff_delay)

            previous_error = batch_file.error_message
            batch_file.status = "pending"
            batch_file.processing_started_at = None
            batch_file.completed_at = None
            batch_file.error_message = None

            self.db.commit()

            batch_job = self.db.query(BatchProcessingJob).filter(
                BatchProcessingJob.job_id == batch_file.job_id
            ).first()

            if not batch_job:
                raise ValueError(f"Batch job {batch_file.job_id} not found")

            try:
                topic = self._get_kafka_topic_for_document_type(batch_file.document_type)

                message_id = await self._publish_to_kafka(
                    topic=topic,
                    job_id=batch_file.job_id,
                    file_id=batch_file.id,
                    file_path=batch_file.file_path,
                    original_filename=batch_file.original_filename,
                    file_size=batch_file.file_size,
                    tenant_id=batch_job.tenant_id,
                    user_id=batch_job.user_id,
                    document_type=batch_file.document_type,
                    api_client_id=batch_job.api_client_id
                )

                batch_file.kafka_topic = topic
                batch_file.kafka_message_id = message_id
                batch_file.status = "processing"
                batch_file.processing_started_at = datetime.now(timezone.utc)

                self.db.commit()

                logger.info(
                    f"Successfully retried file {file_id} "
                    f"(attempt {batch_file.retry_count}/{max_retries})"
                )

                return {
                    "file_id": file_id,
                    "status": "retrying",
                    "retry_count": batch_file.retry_count,
                    "max_retries": max_retries,
                    "backoff_delay": backoff_delay,
                    "kafka_topic": topic,
                    "kafka_message_id": message_id,
                    "previous_error": previous_error
                }

            except Exception as e:
                logger.error(f"Failed to re-enqueue file {file_id}: {e}")
                batch_file.status = "failed"
                batch_file.error_message = (
                    f"Retry attempt {batch_file.retry_count} failed: {str(e)}. "
                    f"Previous error: {previous_error}"
                )
                self.db.commit()
                raise

        except Exception as e:
            logger.error(f"Failed to retry file {file_id}: {e}")
            self.db.rollback()
            raise

    async def retry_all_failed_files(
        self,
        job_id: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        try:
            failed_files = self.db.query(BatchFileProcessing).filter(
                and_(
                    BatchFileProcessing.job_id == job_id,
                    BatchFileProcessing.status == "failed",
                    BatchFileProcessing.retry_count < max_retries
                )
            ).all()

            if not failed_files:
                logger.info(f"No retryable failed files found for job {job_id}")
                return {"job_id": job_id, "retried": 0, "skipped": 0, "failed": 0, "files": []}

            logger.info(f"Retrying {len(failed_files)} failed files for job {job_id}")

            retried_count = 0
            skipped_count = 0
            failed_count = 0
            results = []

            for batch_file in failed_files:
                try:
                    result = await self.retry_failed_file(batch_file.id, max_retries=max_retries)

                    if result["status"] == "retrying":
                        retried_count += 1
                    elif result["status"] == "permanently_failed":
                        skipped_count += 1

                    results.append(result)

                except Exception as e:
                    logger.error(f"Failed to retry file {batch_file.id}: {e}")
                    failed_count += 1
                    results.append({
                        "file_id": batch_file.id,
                        "status": "retry_failed",
                        "error": str(e)
                    })

            logger.info(
                f"Retry results for job {job_id}: "
                f"retried={retried_count}, skipped={skipped_count}, "
                f"failed={failed_count}"
            )

            return {
                "job_id": job_id,
                "retried": retried_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "files": results
            }

        except Exception as e:
            logger.error(f"Failed to retry failed files for job {job_id}: {e}")
            raise
