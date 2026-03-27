"""
Job cancellation for batch processing.

Handles cancellation of individual jobs and bulk cancellation of all
active jobs for an API client.
"""

import logging
from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import and_

from core.models.models_per_tenant import BatchProcessingJob, BatchFileProcessing
from core.utils.audit import log_audit_event

logger = logging.getLogger(__name__)


class BatchCancellationMixin:
    """Mixin providing job cancellation operations."""

    def cancel_job(self, job_id: str, tenant_id: int) -> Tuple[bool, str]:
        try:
            job = self.db.query(BatchProcessingJob).filter(
                and_(
                    BatchProcessingJob.job_id == job_id,
                    BatchProcessingJob.tenant_id == tenant_id
                )
            ).first()

            if not job:
                logger.warning(f"Cancel failed: Job {job_id} not found for tenant {tenant_id}")
                return False, "Job not found"

            if job.status == "cancelled":
                logger.info(f"Job {job_id} is already cancelled")
                return True, "Job is already cancelled"

            if job.status in ["completed", "failed", "partial_failure"]:
                logger.warning(
                    f"Cancel failed: Job {job_id} is already in final status '{job.status}'"
                )
                return False, f"Cannot cancel job in '{job.status}' status"

            old_status = job.status
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)

            pending_files = self.db.query(BatchFileProcessing).filter(
                and_(
                    BatchFileProcessing.job_id == job_id,
                    BatchFileProcessing.status.in_(["pending", "processing"])
                )
            ).all()

            for file in pending_files:
                file.status = "cancelled"
                file.error_message = f"Job cancelled by user (previous status: {old_status})"

            self.db.commit()

            logger.info(f"Successfully cancelled batch job {job_id} (tenant {tenant_id})")

            from core.models.models_per_tenant import User
            from core.models.database import set_tenant_context

            user = self.db.query(User).filter(User.id == job.user_id).first()
            user_email = user.email if user else "unknown@example.com"

            set_tenant_context(tenant_id)

            log_audit_event(
                db=self.db,
                user_id=job.user_id,
                user_email=user_email,
                action="UPDATE",
                resource_type="batch_processing_job",
                resource_id=job.job_id,
                resource_name=f"Batch Job {job.job_id}",
                details={
                    "previous_status": old_status,
                    "new_status": "cancelled",
                    "cancelled_file_count": len(pending_files)
                },
                status="success"
            )

            return True, "Batch job cancelled successfully"

        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            self.db.rollback()
            return False, f"Internal error during cancellation: {str(e)}"

    def cancel_all_jobs(self, tenant_id: int, api_client_id: str) -> Tuple[bool, str]:
        try:
            active_jobs = self.db.query(BatchProcessingJob).filter(
                BatchProcessingJob.tenant_id == tenant_id,
                BatchProcessingJob.api_client_id == api_client_id,
                BatchProcessingJob.status.in_(["pending", "processing"])
            ).all()

            if not active_jobs:
                return True, "No active batch jobs found to cancel"

            job_ids = [job.job_id for job in active_jobs]
            count = len(job_ids)

            for job in active_jobs:
                job.status = "cancelled"
                job.completed_at = datetime.now(timezone.utc)

                pending_files = self.db.query(BatchFileProcessing).filter(
                    BatchFileProcessing.job_id == job.job_id,
                    BatchFileProcessing.status.in_(["pending", "processing"])
                ).all()

                for file in pending_files:
                    file.status = "cancelled"
                    file.error_message = "Batch job cancelled by user (Cancel All)"

            self.db.commit()

            logger.info(f"Cancelled {count} jobs for client {api_client_id} (tenant {tenant_id})")

            from core.models.models_per_tenant import User
            from core.models.database import set_tenant_context

            user = self.db.query(User).filter(User.id == active_jobs[0].user_id).first()
            user_email = user.email if user else "unknown@example.com"

            set_tenant_context(tenant_id)

            log_audit_event(
                db=self.db,
                user_id=active_jobs[0].user_id,
                user_email=user_email,
                action="UPDATE",
                resource_type="batch_processing_job",
                resource_id="multiple",
                resource_name=f"Bulk Cancel {count} Jobs",
                details={"cancelled_job_ids": job_ids, "count": count},
                status="success"
            )

            return True, f"Successfully cancelled all {count} active batch jobs"

        except Exception as e:
            logger.error(f"Error in cancel_all_jobs for {api_client_id}: {e}")
            self.db.rollback()
            return False, f"Internal error during bulk cancellation: {str(e)}"
