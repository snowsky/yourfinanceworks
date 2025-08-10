import json
import logging
import os
import signal
import sys
from typing import Optional

from datetime import datetime, timezone

from services.ocr_service import process_attachment_inline
from models.database import set_tenant_context
from services.tenant_database_manager import tenant_db_manager

def _resolve_log_level(name: str) -> int:
    name = (name or "INFO").upper()
    return {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(name, logging.INFO)

log_level = _resolve_log_level(os.getenv("LOG_LEVEL", "INFO"))
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
logger.info(f"OCR worker log level set to {logging.getLevelName(log_level)}")


def _get_consumer():
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    topic = os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr")
    group = os.getenv("KAFKA_OCR_GROUP", "invoice-app-ocr")
    if not bootstrap:
        logger.error("KAFKA_BOOTSTRAP_SERVERS not set; cannot start OCR consumer")
        return None, topic
    try:
        from confluent_kafka import Consumer  # type: ignore

        conf = {
            "bootstrap.servers": bootstrap,
            "group.id": group,
            "auto.offset.reset": os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
            # We'll manually commit after a successful 'done' parse
            "enable.auto.commit": False,
        }
        consumer = Consumer(conf)
        return consumer, topic
    except Exception as e:
        logger.error(f"Failed to initialize Kafka consumer: {e}")
        return None, topic


def main() -> int:
    consumer, topic = _get_consumer()
    if not consumer:
        return 1
    consumer.subscribe([topic])

    running = True

    def handle_signal(signum, frame):
        nonlocal running
        logger.info("Stopping OCR consumer...")
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info(f"OCR consumer running on topic={topic}")
    while running:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            logger.error(f"Kafka error: {msg.error()}")
            continue
        try:
            payload = json.loads(msg.value().decode("utf-8"))
            expense_id = int(payload.get("expense_id"))
            attachment_id = int(payload.get("attachment_id"))
            file_path = str(payload.get("file_path"))
            tenant_id: Optional[int] = payload.get("tenant_id")

            if tenant_id is not None:
                try:
                    set_tenant_context(int(tenant_id))
                except Exception as e:
                    logger.warning(f"Failed to set tenant context {tenant_id}: {e}")

            # Open tenant-scoped DB session
            if tenant_id is None:
                logger.error("No tenant_id in OCR message; skipping")
                continue
            SessionLocalTenant = tenant_db_manager.get_tenant_session(int(tenant_id))
            db = SessionLocalTenant()
            try:
                # Skip if expense was manually overridden in the meantime
                from models.models_per_tenant import Expense
                exp = db.query(Expense).filter(Expense.id == expense_id).first()
                if not exp:
                    logger.warning(f"Expense {expense_id} not found; skipping")
                elif exp.manual_override:
                    logger.info(f"Expense {expense_id} manually overridden; skipping OCR application")
                else:
                    # Mark as processing and process
                    try:
                        exp.analysis_status = "processing"
                        exp.updated_at = datetime.now(timezone.utc)
                        db.commit()
                    except Exception:
                        db.rollback()
                    # Process with OCR
                    import asyncio
                    asyncio.get_event_loop().run_until_complete(
                        process_attachment_inline(db, expense_id, attachment_id, file_path)
                    )
                    # Refresh status and commit offset only if parsed as done
                    try:
                        db.refresh(exp)
                    except Exception:
                        pass
                    if getattr(exp, "analysis_status", None) == "done":
                        try:
                            consumer.commit(message=msg, asynchronous=False)
                            logger.info(f"Committed Kafka offset for expense_id={expense_id} (done)")
                        except Exception as e:
                            logger.error(f"Failed to commit Kafka offset: {e}
")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")

    try:
        consumer.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())


