"""
Batch Completion Monitor Service

Background service that polls for completed batch processing jobs and triggers
export operations. Runs periodically to detect when all files in a job have
been processed.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models.models_per_tenant import BatchProcessingJob
from core.services.export_service import ExportService

logger = logging.getLogger(__name__)


class BatchCompletionMonitor:
    """
    Background service that monitors batch processing jobs for completion.
    
    Polls the database every 30 seconds to find jobs where all files have been
    processed, then triggers the export process for those jobs.
    """

    def __init__(self, db_session_factory):
        """
        Initialize the batch completion monitor.
        
        Args:
            db_session_factory: Factory function that returns a database session
        """
        self.db_session_factory = db_session_factory
        self.poll_interval = 30  # seconds
        self.is_running = False
        logger.info("BatchCompletionMonitor initialized")

    async def start(self):
        """
        Start the monitoring loop.
        
        Runs continuously until stopped, polling for completed jobs every
        30 seconds.
        """
        self.is_running = True
        logger.info(
            f"Starting BatchCompletionMonitor with {self.poll_interval}s poll interval"
        )
        
        while self.is_running:
            try:
                await self.check_for_completed_jobs()
            except Exception as e:
                logger.error(f"Error in batch completion monitor loop: {e}", exc_info=True)
            
            # Wait before next poll
            await asyncio.sleep(self.poll_interval)
        
        logger.info("BatchCompletionMonitor stopped")

    async def stop(self):
        """Stop the monitoring loop."""
        logger.info("Stopping BatchCompletionMonitor...")
        self.is_running = False

    async def check_for_completed_jobs(self):
        """
        Check for completed batch jobs and trigger exports.
        
        Queries for BatchProcessingJob records where:
        - processed_files == total_files (all files processed)
        - status == "processing" (not yet marked as completed)
        
        For each completed job found, triggers the export process.
        """
        db = None
        try:
            # Create a new database session for this check
            db = self.db_session_factory()
            
            # Query for completed jobs that haven't been exported yet
            completed_jobs = db.query(BatchProcessingJob).filter(
                and_(
                    BatchProcessingJob.processed_files >= BatchProcessingJob.total_files,
                    BatchProcessingJob.status == "processing"
                )
            ).all()
            
            if not completed_jobs:
                logger.debug("No completed jobs found")
                return
            
            logger.info(f"Found {len(completed_jobs)} completed jobs to export")
            
            # Process each completed job
            for job in completed_jobs:
                try:
                    await self.trigger_export_for_job(job, db)
                except Exception as e:
                    logger.error(
                        f"Failed to trigger export for job {job.job_id}: {e}",
                        exc_info=True
                    )
                    # Continue with other jobs even if one fails
                    continue
            
        except Exception as e:
            logger.error(f"Error checking for completed jobs: {e}", exc_info=True)
        finally:
            if db:
                db.close()

    async def trigger_export_for_job(self, job: BatchProcessingJob, db: Session):
        """
        Trigger export process for a completed batch job.
        
        Args:
            job: BatchProcessingJob instance
            db: Database session
        """
        job_id = job.job_id
        tenant_id = job.tenant_id
        
        logger.info(
            f"Triggering export for job {job_id}: "
            f"total={job.total_files}, processed={job.processed_files}, "
            f"successful={job.successful_files}, failed={job.failed_files}"
        )
        
        try:
            # Check if there are any successful files to export
            if job.successful_files == 0:
                logger.warning(
                    f"Job {job_id} has no successful files. "
                    f"Marking as failed without export."
                )
                
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                job.updated_at = datetime.now(timezone.utc)
                db.commit()
                
                # Send webhook notification for failed job
                await self.send_webhook_notification(job, db)
                return
            
            # Create export service and trigger export
            export_service = ExportService(db)
            
            export_result = await export_service.generate_and_export_results(job)
            
            logger.info(
                f"Export completed for job {job_id}: "
                f"status={export_result['status']}, "
                f"url={export_result['export_url']}"
            )
            
            # Refresh job to get updated status
            db.refresh(job)
            
            # Send webhook notification for completed job
            await self.send_webhook_notification(job, db)
            
        except Exception as e:
            logger.error(
                f"Failed to export results for job {job_id}: {e}",
                exc_info=True
            )
            
            # Mark job as failed
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            # Send webhook notification for failed job
            await self.send_webhook_notification(job, db)
            
            # Re-raise to allow caller to handle
            raise

    async def send_webhook_notification(self, job: BatchProcessingJob, db: Session):
        """
        Send webhook notification for job completion.
        
        This is a placeholder that will be implemented in subtask 8.2.
        
        Args:
            job: BatchProcessingJob instance
            db: Database session
        """
        # Import here to avoid circular dependency
        from core.services.webhook_notification_service import WebhookNotificationService
        
        if not job.webhook_url:
            logger.debug(f"No webhook URL configured for job {job.job_id}")
            return
        
        try:
            webhook_service = WebhookNotificationService()
            await webhook_service.send_job_completion_notification(job)
        except Exception as e:
            logger.error(
                f"Failed to send webhook notification for job {job.job_id}: {e}",
                exc_info=True
            )
            # Don't fail the job if webhook fails

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the monitor.
        
        Returns:
            Dictionary with monitor status information
        """
        return {
            "is_running": self.is_running,
            "poll_interval": self.poll_interval,
            "service": "BatchCompletionMonitor"
        }


# Singleton instance for the monitor
_monitor_instance = None


def get_batch_completion_monitor(db_session_factory) -> BatchCompletionMonitor:
    """
    Get or create the singleton batch completion monitor instance.
    
    Args:
        db_session_factory: Factory function that returns a database session
        
    Returns:
        BatchCompletionMonitor instance
    """
    global _monitor_instance
    
    if _monitor_instance is None:
        _monitor_instance = BatchCompletionMonitor(db_session_factory)
    
    return _monitor_instance
