"""
Background Service for Reminder Processing

This service handles the background execution of reminder checking and notifications,
including periodic scanning for due reminders and sending notifications.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from core.services.reminder_scheduler import ReminderScheduler
from core.models.database import get_db
from config import get_settings

logger = logging.getLogger(__name__)


class ReminderBackgroundService:
    """
    Background service for processing reminders.
    
    This service runs as a background task and periodically checks for
    due reminders and sends notifications automatically.
    """
    
    def __init__(
        self,
        check_interval: int = 60,  # Check every 1 minute by default
        max_concurrent_executions: int = 3
    ):
        self.check_interval = check_interval
        self.max_concurrent_executions = max_concurrent_executions
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.execution_semaphore = asyncio.Semaphore(max_concurrent_executions)
        self.settings = get_settings()
        
    async def start(self) -> None:
        """Start the background reminder service."""
        if self.is_running:
            logger.warning("Background reminder service is already running")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._run_reminder_loop())
        logger.info(f"Started background reminder service with {self.check_interval}s check interval")
    
    async def stop(self) -> None:
        """Stop the background reminder service."""
        if not self.is_running:
            logger.warning("Background reminder service is not running")
            return
        
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped background reminder service")
    
    async def _run_reminder_loop(self) -> None:
        """Main reminder processing loop that runs in the background."""
        logger.info("Starting reminder processing loop")
        
        while self.is_running:
            try:
                await self._process_all_tenant_reminders()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Reminder processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in reminder processing loop: {str(e)}")
                # Continue running even if there's an error
                await asyncio.sleep(self.check_interval)
    
    async def _process_all_tenant_reminders(self) -> None:
        """Process reminders for all tenants."""
        try:
            # Get all existing tenant IDs
            from core.services.tenant_database_manager import tenant_db_manager
            tenant_ids = tenant_db_manager.get_existing_tenant_ids()

            logger.info(f"Processing reminders for {len(tenant_ids)} tenants")

            # Process reminders for each tenant
            for tenant_id in tenant_ids:
                async with self.execution_semaphore:
                    await self._process_tenant_reminders(tenant_id)

        except Exception as e:
            logger.error(f"Error processing tenant reminders: {str(e)}")
    
    async def _process_tenant_reminders(self, tenant_id: int) -> Dict[str, Any]:
        """Process reminders for a single tenant."""
        try:
            # Set tenant context for this background operation
            from core.models.database import set_tenant_context
            set_tenant_context(tenant_id)

            # Get tenant-specific database session
            from core.services.tenant_database_manager import tenant_db_manager
            SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
            db = SessionLocalTenant()

            try:
                scheduler = ReminderScheduler(db)
                from core.services.workflow_service import WorkflowService
                workflow_service = WorkflowService(db)

                # Process due reminders
                due_stats = scheduler.process_due_reminders()
                logger.info(f"Processed due reminders for tenant {tenant_id}: {due_stats}")

                # Send upcoming reminder notifications (24 hours in advance)
                upcoming_stats = scheduler.send_upcoming_reminders(advance_days=1)
                logger.info(f"Processed upcoming reminders for tenant {tenant_id}: {upcoming_stats}")

                workflow_stats = workflow_service.process_due_invoice_workflows()
                logger.info(f"Processed workflows for tenant {tenant_id}: {workflow_stats}")

                # Process expense digest schedule
                expense_digest_stats = self._process_expense_digest(db, tenant_id)
                if expense_digest_stats.get("status") not in {"skipped", "failed"}:
                    logger.info(f"Processed expense digest for tenant {tenant_id}: {expense_digest_stats}")

                # Cleanup old notifications once per day (roughly)
                if self._should_cleanup():
                    cleanup_count = scheduler.cleanup_old_notifications()
                    logger.info(f"Cleaned up {cleanup_count} old notifications for tenant {tenant_id}")

                return {
                    "tenant_id": tenant_id,
                    "due_reminders": due_stats,
                    "upcoming_reminders": upcoming_stats,
                    "workflow_runs": workflow_stats,
                    "expense_digest": expense_digest_stats,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error processing tenant reminders for tenant {tenant_id}: {str(e)}")
            return {
                "tenant_id": tenant_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _process_expense_digest(self, db, tenant_id: int) -> Dict[str, Any]:
        """Process due expense digest for a tenant if configured."""
        try:
            from core.models.models_per_tenant import Settings
            from core.services.email_service import EmailProvider, EmailProviderConfig, EmailService
            from core.services.expense_digest_service import ExpenseDigestService

            email_settings = db.query(Settings).filter(Settings.key == "email_config").first()
            if not email_settings or not email_settings.value:
                return {"status": "skipped", "reason": "email_config_missing"}

            email_config_data = email_settings.value
            if not email_config_data.get("enabled", False):
                return {"status": "skipped", "reason": "email_disabled"}

            config = EmailProviderConfig(
                provider=EmailProvider(email_config_data["provider"]),
                from_email=email_config_data.get("from_email"),
                from_name=email_config_data.get("from_name"),
                aws_access_key_id=email_config_data.get("aws_access_key_id"),
                aws_secret_access_key=email_config_data.get("aws_secret_access_key"),
                aws_region=email_config_data.get("aws_region"),
                azure_connection_string=email_config_data.get("azure_connection_string"),
                mailgun_api_key=email_config_data.get("mailgun_api_key"),
                mailgun_domain=email_config_data.get("mailgun_domain"),
            )
            email_service = EmailService(config)
            digest_service = ExpenseDigestService(db, email_service)
            return digest_service.process_due_digest(force=False)
        except Exception as e:
            logger.error(f"Error processing expense digest for tenant {tenant_id}: {str(e)}")
            return {"status": "failed", "reason": str(e)}
    
    def _should_cleanup(self) -> bool:
        """Determine if we should run cleanup (approximately once per day)."""
        # Run cleanup roughly once per day based on check interval
        # If check_interval is 300s (5 min), this gives us about 1/288 chance per check
        cleanup_probability = self.check_interval / 86400  # 86400 seconds in a day
        
        import random
        return random.random() < cleanup_probability
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get the current status of the background service."""
        return {
            "is_running": self.is_running,
            "check_interval": self.check_interval,
            "max_concurrent_executions": self.max_concurrent_executions,
            "task_status": "running" if self.task and not self.task.done() else "stopped",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def process_reminders_now(self) -> Dict[str, Any]:
        """Manually trigger reminder processing (for testing/admin use)."""
        logger.info("Manually triggered reminder processing")

        # Get all existing tenant IDs
        from core.services.tenant_database_manager import tenant_db_manager
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()

        logger.info(f"Manually processing reminders for {len(tenant_ids)} tenants")

        results = []
        for tenant_id in tenant_ids:
            result = await self._process_tenant_reminders(tenant_id)
            results.append(result)

        return {
            "total_tenants": len(tenant_ids),
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global service instance
_reminder_background_service: Optional[ReminderBackgroundService] = None


def get_reminder_background_service() -> ReminderBackgroundService:
    """Get the global reminder background service instance."""
    global _reminder_background_service
    if _reminder_background_service is None:
        settings = get_settings()
        # Get check interval from core.settings or use default
        check_interval = getattr(settings, 'REMINDER_CHECK_INTERVAL', 300)
        _reminder_background_service = ReminderBackgroundService(check_interval=check_interval)
    return _reminder_background_service


async def start_reminder_background_service() -> None:
    """Start the reminder background service."""
    service = get_reminder_background_service()
    await service.start()


async def stop_reminder_background_service() -> None:
    """Stop the reminder background service."""
    service = get_reminder_background_service()
    await service.stop()


@asynccontextmanager
async def reminder_background_service_lifespan():
    """Context manager for reminder background service lifecycle."""
    try:
        await start_reminder_background_service()
        yield
    finally:
        await stop_reminder_background_service()
