import os
import json
import signal
import asyncio
from typing import Optional, List, Dict, Any

from ._shared import (
    OCRConfig,
    ProcessingResult,
    ProcessingStatus,
    logger,
    set_tenant_context,
    tenant_db_manager,
)
from .base_handler import BaseMessageHandler
from .expense_handler import ExpenseMessageHandler
from .bank_statement_handler import BankStatementMessageHandler
from .invoice_handler import InvoiceMessageHandler


# ============================================================================
# Message Router and Consumer
# ============================================================================

class MessageRouter:
    """Routes messages to appropriate handlers"""

    def __init__(self, config: OCRConfig):
        self.config = config
        self.handlers: List[BaseMessageHandler] = [
            ExpenseMessageHandler(config),
            BankStatementMessageHandler(config),
            InvoiceMessageHandler(config)
        ]
        self.logger = logger

    def get_handler(self, topic: str, payload: Dict[str, Any]) -> Optional[BaseMessageHandler]:
        """Get appropriate handler for message"""
        for handler in self.handlers:
            if handler.can_handle(topic, payload):
                return handler
        return None


class OCRConsumer:
    """Main OCR consumer with improved architecture"""

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()
        self.consumer: Optional[Any] = None
        self.router = MessageRouter(self.config)
        self.running = False
        self.logger = logger
        self._shutdown_event = asyncio.Event()

    async def start(self) -> int:
        """Start the OCR consumer"""
        try:
            # Initialize consumer
            self.consumer, topics = await self._initialize_consumer()
            if not self.consumer:
                return 1

            # Perform startup tasks
            await self._perform_startup_requeue()

            # Subscribe to topics
            expense_topic, bank_topic, invoice_topic = topics
            self.consumer.subscribe([expense_topic, bank_topic, invoice_topic])

            # Setup signal handlers
            self._setup_signal_handlers()

            self.logger.info(f"OCR consumer running on topics={[expense_topic, bank_topic, invoice_topic]}")

            # Main processing loop
            await self._processing_loop()

            return 0

        except Exception as e:
            self.logger.error(f"Consumer failed to start: {e}")
            return 1
        finally:
            await self._cleanup()

    async def _initialize_consumer(self):
        """Initialize Kafka consumer with topic management"""
        bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        if not bootstrap:
            self.logger.error("KAFKA_BOOTSTRAP_SERVERS not set; cannot start OCR consumer")
            return None, (None, None)

        try:
            from confluent_kafka import Consumer

            # Ensure topics exist
            await self._ensure_topics_exist(bootstrap)

            # Configure consumer
            conf = {
                "bootstrap.servers": bootstrap,
                "group.id": os.getenv("KAFKA_OCR_GROUP", "invoice-app-ocr"),
                "auto.offset.reset": os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
                "enable.auto.commit": False,
                "max.poll.interval.ms": int(os.getenv("KAFKA_MAX_POLL_INTERVAL_MS", "900000")),
                "session.timeout.ms": int(os.getenv("KAFKA_SESSION_TIMEOUT_MS", "45000")),
            }

            self.consumer = Consumer(conf)

            topics = (
                os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr"),
                os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr"),
                os.getenv("KAFKA_INVOICE_TOPIC", "invoices_ocr")
            )

            return self.consumer, topics

        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka consumer: {e}")
            return None, (None, None)

    async def _ensure_topics_exist(self, bootstrap: str):
        """Ensure required topics exist"""
        try:
            from confluent_kafka.admin import AdminClient, NewTopic

            admin = AdminClient({"bootstrap.servers": bootstrap})

            topics = [
                os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr"),
                os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr"),
                os.getenv("KAFKA_INVOICE_TOPIC", "invoices_ocr")
            ]

            for topic in topics:
                await self._ensure_single_topic_exists(admin, topic)

        except Exception as e:
            self.logger.debug(f"Kafka Admin client not available: {e}")

    async def _ensure_single_topic_exists(self, admin, topic_name: str):
        """Ensure a single topic exists"""
        try:
            from confluent_kafka.admin import NewTopic

            md = admin.list_topics(timeout=5)
            if topic_name in md.topics and not md.topics[topic_name].error:
                self.logger.debug(f"Kafka topic '{topic_name}' already exists")
                return

            # Create topic
            partitions = int(os.getenv("KAFKA_OCR_TOPIC_PARTITIONS", "1"))
            replication_factor = int(os.getenv("KAFKA_OCR_TOPIC_RF", "1"))
            new_topic = NewTopic(topic=topic_name, num_partitions=partitions, replication_factor=replication_factor)

            fs = admin.create_topics([new_topic])
            fut = fs.get(topic_name)

            try:
                fut.result(timeout=10)
                self.logger.info(f"Created Kafka topic '{topic_name}' (partitions={partitions}, rf={replication_factor})")
            except Exception as e:
                self.logger.warning(f"Topic creation for '{topic_name}' may have failed or already exists: {e}")

        except Exception as e:
            self.logger.warning(f"Unable to ensure Kafka topic '{topic_name}': {e}")

    async def _perform_startup_requeue(self):
        """Perform startup scan to requeue any queued expenses"""
        try:
            self.logger.info("Startup scan: requeue queued expenses if any")

            # Get tenant IDs
            tenant_ids: List[int] = tenant_db_manager.get_existing_tenant_ids()

            # Process each tenant
            for tid in tenant_ids:
                await self._requeue_tenant_expenses(tid)

        except Exception as e:
            self.logger.warning(f"Startup requeue scan failed: {e}")

    async def _requeue_tenant_expenses(self, tenant_id: int):
        """Requeue queued expenses for a specific tenant"""
        try:
            set_tenant_context(tenant_id)
            SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
        except Exception:
            return

        db = SessionLocalTenant()
        try:
            from core.models.models_per_tenant import Expense, ExpenseAttachment

            queued_expenses = db.query(Expense).filter(
                Expense.analysis_status == ProcessingStatus.QUEUED.value
            ).all()

            for expense in queued_expenses:
                attachment = (
                    db.query(ExpenseAttachment)
                    .filter(ExpenseAttachment.expense_id == expense.id)
                    .order_by(ExpenseAttachment.uploaded_at.desc())
                    .first()
                )

                if not attachment or not getattr(attachment, "file_path", None):
                    continue

                try:
                    from commercial.ai.services.ocr_service import queue_or_process_attachment
                    await queue_or_process_attachment(db, tenant_id, expense.id, attachment.id, str(attachment.file_path))
                    self.logger.info(f"Requeued queued expense_id={expense.id} tenant_id={tenant_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to requeue expense {expense.id} in tenant {tenant_id}: {e}")

        finally:
            db.close()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info("Stopping OCR consumer...")
            self.running = False
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _processing_loop(self):
        """Main message processing loop"""
        self.running = True

        while self.running and not self._shutdown_event.is_set():
            try:
                # Poll for message with timeout
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    self.logger.error(f"Kafka error: {msg.error()}")
                    continue

                # Process message
                await self._process_message(msg)

            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(1)  # Brief pause on unexpected errors

    async def _process_message(self, message):
        """Process a single Kafka message"""
        try:
            # Parse payload
            payload = json.loads(message.value().decode("utf-8"))
            topic_name = message.topic()

            self.logger.info(f"Processing message on topic={topic_name}: keys={list(payload.keys())}")

            # Get handler and process
            handler = self.router.get_handler(topic_name, payload)
            if not handler:
                self.logger.warning(f"No handler for topic {topic_name}, committing and skipping")
                await self._commit_message(message)
                return

            # Extract and validate tenant ID
            tenant_id = handler.extract_tenant_id(payload)
            if tenant_id is None:
                self.logger.error("No tenant_id in message; committing and skipping invalid message")
                await self._commit_message(message)
                return

            # Process with handler
            result = await handler.process(self.consumer, message, payload)

            # Handle processing result
            if result.success and not result.committed:
                await self._commit_message(message)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON message: {e}")
            await self._commit_message(message)
        except Exception as e:
            self.logger.error(f"Failed to handle message: {e}")
            # Don't commit on unexpected errors to allow retry

    async def _commit_message(self, message):
        """Safely commit a Kafka message"""
        try:
            self.consumer.commit(message=message, asynchronous=False)
        except Exception as e:
            self.logger.error(f"Failed to commit message: {e}")

    async def _cleanup(self):
        """Cleanup resources"""
        try:
            if self.consumer:
                self.consumer.close()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main_async() -> int:
    """Async main function"""
    try:
        # Load configuration
        config = OCRConfig(
            max_attempts=int(os.getenv("KAFKA_OCR_MAX_ATTEMPTS", "5")),
            backoff_base_ms=int(os.getenv("KAFKA_OCR_BACKOFF_BASE_MS", "1000")),
            max_backoff_ms=int(os.getenv("KAFKA_OCR_MAX_BACKOFF_MS", "60000")),
            timeout_seconds=int(os.getenv("KAFKA_OCR_TIMEOUT_SECONDS", "300")),
            dlq_enabled=os.getenv("KAFKA_OCR_DLQ_ENABLED", "true").lower() == "true"
        )

        # Create and start consumer
        consumer = OCRConsumer(config)
        return await consumer.start()

    except Exception as e:
        logger.error(f"Failed to start OCR consumer: {e}")
        return 1


def main() -> int:
    """Main entry point - runs async main in event loop"""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("OCR consumer interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"OCR consumer failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
