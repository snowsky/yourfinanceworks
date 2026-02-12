"""
Holdings Import Worker for asynchronous portfolio holdings file processing.

This worker processes holdings files uploaded by users, extracts holdings data
using LLM services, and creates holding records in portfolios. It follows the
same pattern as the OCR worker for consistency and reliability.

Key features:
- Kafka-based message processing for scalability
- Multi-tenant support with advisory locks
- Comprehensive error handling and retry logic
- Status tracking (PENDING → PROCESSING → COMPLETED/FAILED/PARTIAL)
- Audit logging for all operations
"""

import json
import logging
import os
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum

from confluent_kafka import Consumer, KafkaError
from sqlalchemy.orm import Session
from sqlalchemy import text

from core.models.database import set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from core.models.models import TenantPluginSettings
from plugins.investments.services.portfolio_import_service import PortfolioImportService
from plugins.investments.repositories.file_attachment_repository import FileAttachmentRepository
from plugins.investments.models import FileAttachment, AttachmentStatus


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("portfolio_import_worker")



class HoldingsImportWorkerConfig:
    """Configuration for holdings import worker"""

    def __init__(self):
        self.kafka_bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.kafka_topic = os.getenv(
            "KAFKA_HOLDINGS_IMPORT_TOPIC", "holdings_import_tasks"
        )
        self.kafka_group = os.getenv(
            "KAFKA_HOLDINGS_IMPORT_GROUP", "holdings-import-worker"
        )
        self.poll_timeout_ms = 1000
        self.max_retries = 3
        self.retry_delay_seconds = 5


class HoldingsImportWorker:
    """Worker for processing holdings import tasks from Kafka"""

    def __init__(self):
        self.config = HoldingsImportWorkerConfig()
        self.consumer: Optional[Consumer] = None
        self.running = False

    def _initialize_consumer(self) -> Consumer:
        """Initialize Kafka consumer"""
        consumer_config = {
            'bootstrap.servers': self.config.kafka_bootstrap_servers,
            'group.id': self.config.kafka_group,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False,
            'session.timeout.ms': 30000,
            'heartbeat.interval.ms': 10000,
        }

        consumer = Consumer(consumer_config)
        consumer.subscribe([self.config.kafka_topic])
        return consumer

    async def start(self):
        """Start the holdings import worker"""
        try:
            self.consumer = self._initialize_consumer()
            self.running = True

            logger.info(
                f"Holdings Import Worker started. "
                f"Subscribed to {self.config.kafka_topic}"
            )

            await self._processing_loop()

        except Exception as e:
            logger.error(f"Holdings Import Worker failed: {e}", exc_info=True)
            return 1
        finally:
            if self.consumer:
                self.consumer.close()

        return 0

    async def _processing_loop(self):
        """Main processing loop"""
        while self.running:
            try:
                message = self.consumer.poll(timeout=self.config.poll_timeout_ms)

                if message is None:
                    continue

                if message.error():
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {message.error()}")
                        continue

                await self._process_message(message)

            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_message(self, message):
        """Process a single holdings import task message"""
        try:
            payload = json.loads(message.value().decode("utf-8"))

            attachment_id = payload.get("attachment_id")
            tenant_id = payload.get("tenant_id")

            if not attachment_id or not tenant_id:
                logger.error(
                    f"Invalid message payload: missing attachment_id or tenant_id"
                )
                self.consumer.commit(asynchronous=False)
                return

            logger.info(
                f"Processing holdings import task: "
                f"attachment_id={attachment_id}, tenant_id={tenant_id}"
            )

            # Set tenant context for multi-tenant operations
            set_tenant_context(tenant_id)

            # Get tenant-specific database session
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)

            with SessionLocal_tenant() as session:
                # Try to acquire advisory lock for this tenant
                # This prevents multiple workers from processing the same tenant simultaneously
                lock_acquired = self._try_acquire_tenant_lock(session, tenant_id)

                if not lock_acquired:
                    logger.debug(
                        f"Tenant {tenant_id} is being processed by another worker, "
                        f"requeuing message..."
                    )
                    # Don't commit - let the message be reprocessed
                    return

                try:
                    # Process the file
                    await self._process_portfolio_file(
                        session, attachment_id, tenant_id
                    )

                    # Commit the message after successful processing
                    self.consumer.commit(asynchronous=False)

                except Exception as e:
                    logger.error(
                        f"Error processing holdings file {attachment_id}: {e}",
                        exc_info=True
                    )
                    # Commit even on error to avoid infinite loops
                    self.consumer.commit(asynchronous=False)

                finally:
                    # Release the advisory lock
                    self._release_tenant_lock(session, tenant_id)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
            self.consumer.commit(asynchronous=False)
        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}", exc_info=True)
            self.consumer.commit(asynchronous=False)

    async def _process_portfolio_file(
        self, session: Session, attachment_id: int, tenant_id: int
    ):
        """Process a single holdings file"""
        try:
            # Get the file attachment
            attachment_repo = FileAttachmentRepository(session)
            attachment = attachment_repo.get_by_id(attachment_id, tenant_id)

            if not attachment:
                logger.error(f"Attachment {attachment_id} not found")
                return

            # Verify tenant ownership
            if attachment.tenant_id != tenant_id:
                logger.error(
                    f"Tenant {tenant_id} attempted to process attachment "
                    f"from tenant {attachment.tenant_id}"
                )
                return

            # Get user email from master database
            user_email = None
            try:
                from core.models.database import get_master_db
                from core.models.models import MasterUser

                master_db = next(get_master_db())
                user = master_db.query(MasterUser).filter(
                    MasterUser.id == attachment.created_by
                ).first()
                if user:
                    user_email = user.email
            except Exception as e:
                logger.warning(f"Failed to get user email: {e}")

            # Update status to PROCESSING
            attachment_repo.update(
                attachment_id,
                tenant_id,
                status=AttachmentStatus.PROCESSING
            )
            session.commit()

            logger.info(
                f"Updated attachment {attachment_id} status to PROCESSING"
            )

            # Process the file using PortfolioImportService
            import_service = PortfolioImportService(session)

            # Check plugin settings for transaction import
            use_ai_extraction = False
            try:
                from core.models.database import get_master_db
                master_db = next(get_master_db())
                plugin_settings = master_db.query(TenantPluginSettings).filter(
                    TenantPluginSettings.tenant_id == tenant_id
                ).first()

                if plugin_settings and plugin_settings.plugin_config:
                    investments_config = plugin_settings.plugin_config.get("investments", {})
                    # The setting controls AI-powered extraction of both holdings AND transactions
                    use_ai_extraction = investments_config.get("enable_ai_import", False)
                    logger.info(f"AI-powered holdings/transactions import enabled: {use_ai_extraction}")

            except Exception as e:
                logger.warning(f"Failed to check plugin settings, defaulting to holdings only: {e}")

            # If AI import is not enabled, skip processing
            # The system requires LLM for extraction, so we can't process without it
            if not use_ai_extraction:
                logger.info(
                    f"Skipping processing for attachment {attachment_id}: "
                    f"AI import is disabled. Enable 'Holdings/Transactions Import with AI' "
                    f"in plugin settings to process files."
                )
                # Update attachment status to indicate it's waiting for AI to be enabled
                attachment_repo.update(
                    attachment_id,
                    tenant_id,
                    status=AttachmentStatus.PENDING,
                    extraction_error="AI import is disabled. Enable 'Holdings/Transactions Import with AI' in plugin settings to process this file."
                )
                session.commit()
                return


            try:
                # Extract portfolio data from file
                portfolio_data = await import_service.extract_portfolio_data_from_file(
                    attachment.local_path,
                    attachment.file_type,
                    use_ai_extraction
                )
                extracted_holdings = portfolio_data["holdings"]
                extracted_transactions = portfolio_data.get("transactions", [])

                # Create holdings and transactions from extracted data
                result = await import_service.create_holdings_from_extracted_data(
                    attachment.portfolio_id,
                    extracted_holdings,
                    extracted_transactions,
                    attachment_id,
                    tenant_id,
                    user_email,
                    attachment.created_by
                )

                # Extract counts from result dictionary
                holdings_created = result["holdings_created"]
                holdings_failed = result["holdings_failed"]
                transactions_created = result["transactions_created"]
                transactions_failed = result["transactions_failed"]
                total_created = result["total_created"]
                total_failed = result["total_failed"]

                # Determine final status
                if total_failed == 0:
                    final_status = AttachmentStatus.COMPLETED
                elif total_created > 0:
                    final_status = AttachmentStatus.PARTIAL
                else:
                    final_status = AttachmentStatus.FAILED

                # Update attachment with results including transaction counts
                attachment_repo.update(
                    attachment_id,
                    tenant_id,
                    status=final_status,
                    extracted_holdings_count=holdings_created,
                    failed_holdings_count=holdings_failed,
                    extracted_transactions_count=transactions_created,
                    failed_transactions_count=transactions_failed,
                    processed_at=datetime.now(timezone.utc),
                    extraction_error=None
                )
                session.commit()

                logger.info(
                    f"Successfully processed attachment {attachment_id}: "
                    f"status={final_status}, holdings={holdings_created}/{holdings_failed}, "
                    f"transactions={transactions_created}/{transactions_failed}"
                )


            except Exception as e:
                # Update attachment with error
                attachment_repo.update(
                    attachment_id,
                    tenant_id,
                    status=AttachmentStatus.FAILED,
                    extraction_error=str(e),
                    processed_at=datetime.now(timezone.utc)
                )
                session.commit()

                logger.error(
                    f"Error processing holdings file {attachment_id}: {e}",
                    exc_info=True
                )
                raise

        except Exception as e:
            logger.error(
                f"Failed to process holdings file {attachment_id}: {e}",
                exc_info=True
            )
            raise

    def _try_acquire_tenant_lock(self, session: Session, tenant_id: int) -> bool:
        """
        Try to acquire a PostgreSQL advisory lock for a tenant.
        Returns True if lock acquired, False if another worker has it.
        """
        try:
            # Use tenant_id as the lock ID
            result = session.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": tenant_id}
            )
            lock_acquired = result.scalar()
            return lock_acquired
        except Exception as e:
            logger.error(f"Error acquiring advisory lock: {e}")
            return False

    def _release_tenant_lock(self, session: Session, tenant_id: int):
        """Release a PostgreSQL advisory lock for a tenant"""
        try:
            session.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": tenant_id})
        except Exception as e:
            logger.error(f"Error releasing advisory lock: {e}")


def main():
    """Entry point for the worker"""
    worker = HoldingsImportWorker()
    return asyncio.run(worker.start())


if __name__ == "__main__":
    exit(main())
