"""
Background Task Service for Report Scheduling

This service handles the background execution of scheduled reports,
including periodic checking for due schedules and executing them.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from ..services.report_scheduler import ReportScheduler
from ..models.database import get_db
from ..services.report_service import ReportService
from ..services.email_service import EmailService, EmailProviderConfig, EmailProvider
from ..services.report_exporter import ReportExportService

logger = logging.getLogger(__name__)


class ReportSchedulerBackgroundService:
    """
    Background service for executing scheduled reports.
    
    This service runs as a background task and periodically checks for
    due scheduled reports and executes them automatically.
    """
    
    def __init__(
        self,
        check_interval: int = 60,  # Check every 60 seconds by default
        max_concurrent_executions: int = 5
    ):
        self.check_interval = check_interval
        self.max_concurrent_executions = max_concurrent_executions
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.execution_semaphore = asyncio.Semaphore(max_concurrent_executions)
        
    async def start(self) -> None:
        """Start the background scheduler service."""
        if self.is_running:
            logger.warning("Background scheduler is already running")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._run_scheduler_loop())
        logger.info(f"Started background scheduler with {self.check_interval}s check interval")
    
    async def stop(self) -> None:
        """Stop the background scheduler service."""
        if not self.is_running:
            logger.warning("Background scheduler is not running")
            return
        
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped background scheduler")
    
    async def _run_scheduler_loop(self) -> None:
        """Main scheduler loop that runs in the background."""
        logger.info("Starting scheduler loop")
        
        while self.is_running:
            try:
                await self._check_and_execute_due_schedules()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                # Continue running even if there's an error
                await asyncio.sleep(self.check_interval)
    
    async def _check_and_execute_due_schedules(self) -> None:
        """Check for due schedules and execute them."""
        try:
            # Get database session
            db = next(get_db())
            
            try:
                # Create services
                email_config = self._get_email_config()
                email_service = EmailService(email_config) if email_config else None
                report_exporter = ReportExportService()
                report_service = ReportService(db)
                
                # Create scheduler
                scheduler = ReportScheduler(
                    db=db,
                    report_service=report_service,
                    email_service=email_service,
                    report_exporter=report_exporter
                )
                
                # Get due schedules
                due_schedules = scheduler.get_due_schedules()
                
                if due_schedules:
                    logger.info(f"Found {len(due_schedules)} due schedules")
                    
                    # Execute schedules concurrently with semaphore limit
                    tasks = []
                    for schedule in due_schedules:
                        task = asyncio.create_task(
                            self._execute_schedule_with_semaphore(scheduler, schedule.id)
                        )
                        tasks.append(task)
                    
                    # Wait for all executions to complete
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Log results
                        successful = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
                        failed = len(results) - successful
                        
                        logger.info(f"Executed {len(results)} schedules: {successful} successful, {failed} failed")
                        
                        # Log any exceptions
                        for i, result in enumerate(results):
                            if isinstance(result, Exception):
                                logger.error(f"Schedule execution {i} failed with exception: {str(result)}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error checking and executing due schedules: {str(e)}")
    
    async def _execute_schedule_with_semaphore(
        self, 
        scheduler: ReportScheduler, 
        schedule_id: int
    ) -> Dict[str, Any]:
        """Execute a single schedule with semaphore protection."""
        async with self.execution_semaphore:
            try:
                # Execute in thread pool since scheduler methods are synchronous
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    scheduler.execute_scheduled_report, 
                    schedule_id
                )
                
                return {
                    "schedule_id": schedule_id,
                    "success": result.success,
                    "error": result.error_message if not result.success else None
                }
                
            except Exception as e:
                logger.error(f"Failed to execute schedule {schedule_id}: {str(e)}")
                return {
                    "schedule_id": schedule_id,
                    "success": False,
                    "error": str(e)
                }
    
    def _get_email_config(self) -> Optional[EmailProviderConfig]:
        """Get email configuration from environment or settings."""
        import os
        
        # Try to get email configuration from environment
        provider = os.getenv("EMAIL_PROVIDER", "").lower()
        
        if provider == "aws_ses":
            return EmailProviderConfig(
                provider=EmailProvider.AWS_SES,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                aws_region=os.getenv("AWS_REGION", "us-east-1")
            )
        elif provider == "azure_email":
            return EmailProviderConfig(
                provider=EmailProvider.AZURE_EMAIL,
                azure_connection_string=os.getenv("AZURE_EMAIL_CONNECTION_STRING")
            )
        elif provider == "mailgun":
            return EmailProviderConfig(
                provider=EmailProvider.MAILGUN,
                mailgun_api_key=os.getenv("MAILGUN_API_KEY"),
                mailgun_domain=os.getenv("MAILGUN_DOMAIN")
            )
        
        logger.warning("No email provider configured for scheduled reports")
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the background service."""
        return {
            "is_running": self.is_running,
            "check_interval": self.check_interval,
            "max_concurrent_executions": self.max_concurrent_executions,
            "current_executions": self.max_concurrent_executions - self.execution_semaphore._value,
            "task_status": "running" if self.task and not self.task.done() else "stopped"
        }


# Global instance of the background service
_background_service: Optional[ReportSchedulerBackgroundService] = None


def get_background_service() -> ReportSchedulerBackgroundService:
    """Get the global background service instance."""
    global _background_service
    if _background_service is None:
        _background_service = ReportSchedulerBackgroundService()
    return _background_service


@asynccontextmanager
async def report_scheduler_lifespan():
    """Context manager for managing the report scheduler lifecycle."""
    service = get_background_service()
    
    try:
        await service.start()
        yield service
    finally:
        await service.stop()


async def start_background_scheduler() -> None:
    """Start the background scheduler service."""
    service = get_background_service()
    await service.start()


async def stop_background_scheduler() -> None:
    """Stop the background scheduler service."""
    service = get_background_service()
    await service.stop()


def get_scheduler_status() -> Dict[str, Any]:
    """Get the current status of the background scheduler."""
    service = get_background_service()
    return service.get_status()