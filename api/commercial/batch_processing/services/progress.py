"""
Progress tracking and job status for batch processing.

Handles file completion callbacks, job progress updates, export triggering,
and status queries.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy import and_

from core.models.models_per_tenant import BatchProcessingJob, BatchFileProcessing

logger = logging.getLogger(__name__)


class BatchProgressMixin:
    """Mixin providing progress tracking, completion handling, and status queries."""

    async def process_file_completion(
        self,
        file_id: int,
        extracted_data: Optional[Dict[str, Any]] = None,
        status: str = "completed",
        error_message: Optional[str] = None,
        created_record_id: Optional[int] = None,
        record_type: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            batch_file = self.db.query(BatchFileProcessing).filter(
                BatchFileProcessing.id == file_id
            ).first()

            if not batch_file:
                raise ValueError(f"Batch file {file_id} not found")

            batch_job = self.db.query(BatchProcessingJob).filter(
                BatchProcessingJob.job_id == batch_file.job_id
            ).first()

            if not batch_job:
                raise ValueError(f"Batch job {batch_file.job_id} not found")

            if batch_job.status in ["cancelled", "failed"]:
                logger.info(
                    f"Skipping completion update for file {file_id} "
                    f"as job {batch_job.job_id} is already '{batch_job.status}'"
                )
                return {
                    "job_id": batch_job.job_id,
                    "status": batch_job.status,
                    "processed_files": batch_job.processed_files,
                    "completed": True
                }

            was_already_processed = batch_file.status in ["completed", "failed"]

            batch_file.status = status
            batch_file.completed_at = datetime.now(timezone.utc)

            if extracted_data:
                batch_file.extracted_data = extracted_data

            if error_message:
                batch_file.error_message = error_message

            if created_record_id and record_type:
                if record_type == 'invoice':
                    batch_file.created_invoice_id = created_record_id
                elif record_type == 'expense':
                    batch_file.created_expense_id = created_record_id
                elif record_type == 'statement':
                    batch_file.created_statement_id = created_record_id
                logger.info(
                    f"Linked batch file {file_id} to {record_type} record {created_record_id}"
                )

            if not was_already_processed:
                batch_job.processed_files += 1
                if status == "completed":
                    batch_job.successful_files += 1
                elif status == "failed":
                    batch_job.failed_files += 1
            else:
                logger.info(f"File {file_id} was retried - updating success/failure counts only")
                if status == "completed":
                    if batch_job.failed_files > 0:
                        batch_job.failed_files -= 1
                    batch_job.successful_files += 1
                elif status == "failed":
                    if batch_job.successful_files > 0:
                        batch_job.successful_files -= 1
                    batch_job.failed_files += 1

            if batch_job.total_files > 0:
                batch_job.progress_percentage = (
                    batch_job.processed_files / batch_job.total_files
                ) * 100.0

            batch_job.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(batch_job)

            logger.info(
                f"Processed file completion: file_id={file_id}, status={status}, "
                f"job_progress={batch_job.processed_files}/{batch_job.total_files} "
                f"({batch_job.progress_percentage:.1f}%)"
            )

            all_processed = batch_job.processed_files >= batch_job.total_files

            if all_processed:
                logger.info(
                    f"All files processed for job {batch_job.job_id}. "
                    f"Successful: {batch_job.successful_files}, "
                    f"Failed: {batch_job.failed_files}"
                )

                if batch_job.successful_files > 0:
                    await self._trigger_export(batch_job)
                else:
                    batch_job.status = "failed"
                    batch_job.completed_at = datetime.now(timezone.utc)
                    self.db.commit()

            return {
                "file_id": file_id,
                "job_id": batch_job.job_id,
                "file_status": status,
                "job_status": batch_job.status,
                "progress": {
                    "processed": batch_job.processed_files,
                    "total": batch_job.total_files,
                    "successful": batch_job.successful_files,
                    "failed": batch_job.failed_files,
                    "percentage": batch_job.progress_percentage
                },
                "all_processed": all_processed
            }

        except Exception as e:
            logger.error(f"Failed to process file completion for file {file_id}: {e}")
            self.db.rollback()
            raise

    async def _trigger_export(self, batch_job: BatchProcessingJob) -> None:
        try:
            logger.info(f"Triggering export for job {batch_job.job_id}")

            from core.services.export_service import ExportService
            export_service = ExportService(self.db)

            export_result = await export_service.generate_and_export_results(batch_job)

            batch_job.status = "completed"
            batch_job.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info(
                f"Export completed for job {batch_job.job_id}: "
                f"status={export_result['status']}, "
                f"url={export_result['export_url']}"
            )

        except Exception as e:
            logger.error(f"Failed to trigger export for job {batch_job.job_id}: {e}")
            raise

    def get_job_status(self, job_id: str, tenant_id: int) -> Optional[Dict[str, Any]]:
        try:
            batch_job = self.db.query(BatchProcessingJob).filter(
                and_(
                    BatchProcessingJob.job_id == job_id,
                    BatchProcessingJob.tenant_id == tenant_id
                )
            ).first()

            if not batch_job:
                return None

            batch_files = self.db.query(BatchFileProcessing).filter(
                BatchFileProcessing.job_id == job_id
            ).order_by(BatchFileProcessing.created_at).all()

            files_detail = []
            for batch_file in batch_files:
                file_info = {
                    "id": batch_file.id,
                    "filename": batch_file.original_filename,
                    "document_type": batch_file.document_type,
                    "status": batch_file.status,
                    "file_size": batch_file.file_size,
                    "retry_count": batch_file.retry_count,
                    "created_at": batch_file.created_at.isoformat() if batch_file.created_at else None,
                    "completed_at": batch_file.completed_at.isoformat() if batch_file.completed_at else None
                }
                if batch_file.extracted_data:
                    file_info["extracted_data"] = batch_file.extracted_data
                if batch_file.error_message:
                    file_info["error_message"] = batch_file.error_message
                files_detail.append(file_info)

            return {
                "job_id": batch_job.job_id,
                "status": batch_job.status,
                "progress": {
                    "total_files": batch_job.total_files,
                    "processed_files": batch_job.processed_files,
                    "successful_files": batch_job.successful_files,
                    "failed_files": batch_job.failed_files,
                    "progress_percentage": batch_job.progress_percentage
                },
                "export": {
                    "destination_type": batch_job.export_destination_type,
                    "export_file_url": batch_job.export_file_url,
                    "export_completed_at": batch_job.export_completed_at.isoformat()
                    if batch_job.export_completed_at else None
                },
                "timestamps": {
                    "created_at": batch_job.created_at.isoformat() if batch_job.created_at else None,
                    "updated_at": batch_job.updated_at.isoformat() if batch_job.updated_at else None,
                    "completed_at": batch_job.completed_at.isoformat() if batch_job.completed_at else None
                },
                "files": files_detail
            }

        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            raise
