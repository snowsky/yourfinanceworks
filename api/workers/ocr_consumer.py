import json
import logging
import os
import signal
import sys
from typing import Optional
from types import SimpleNamespace

from datetime import datetime, timezone

from services.ocr_service import process_attachment_inline
from models.database import set_tenant_context
from services.tenant_database_manager import tenant_db_manager
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List

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
    expense_topic = os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr")
    bank_topic = os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr")
    invoice_topic = os.getenv("KAFKA_INVOICE_TOPIC", "invoices_ocr")
    group = os.getenv("KAFKA_OCR_GROUP", "invoice-app-ocr")
    if not bootstrap:
        logger.error("KAFKA_BOOTSTRAP_SERVERS not set; cannot start OCR consumer")
        return None, (expense_topic, bank_topic)
    try:
        from confluent_kafka import Consumer  # type: ignore
        # Try to ensure topic exists before subscribing (consumer subscription won't auto-create)
        try:
            from confluent_kafka.admin import AdminClient, NewTopic  # type: ignore

            def ensure_topic_exists(topic_name: str) -> None:
                try:
                    admin = AdminClient({"bootstrap.servers": bootstrap})
                    md = admin.list_topics(timeout=5)
                    if topic_name in md.topics and not md.topics[topic_name].error:
                        logger.debug(f"Kafka topic '{topic_name}' already exists")
                        return
                    partitions = int(os.getenv("KAFKA_OCR_TOPIC_PARTITIONS", "1"))
                    replication_factor = int(os.getenv("KAFKA_OCR_TOPIC_RF", "1"))
                    new_topic = NewTopic(topic=topic_name, num_partitions=partitions, replication_factor=replication_factor)
                    fs = admin.create_topics([new_topic])
                    fut = fs.get(topic_name)
                    try:
                        fut.result(timeout=10)
                        logger.info(f"Created Kafka topic '{topic_name}' (partitions={partitions}, rf={replication_factor})")
                    except Exception as e:
                        # If topic exists due to race, ignore; otherwise log warning
                        logger.warning(f"Topic creation for '{topic_name}' may have failed or already exists: {e}")
                except Exception as e:
                    logger.warning(f"Unable to ensure Kafka topic '{topic_name}': {e}")

            ensure_topic_exists(expense_topic)
            ensure_topic_exists(bank_topic)
            ensure_topic_exists(invoice_topic)
        except Exception as e:
            logger.debug(f"Kafka Admin client not available or failed: {e}")

        conf = {
            "bootstrap.servers": bootstrap,
            "group.id": group,
            "auto.offset.reset": os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
            # We'll manually commit after a successful 'done' parse
            "enable.auto.commit": False,
            # Be generous to allow long OCR jobs without rebalance kicking us out
            "max.poll.interval.ms": int(os.getenv("KAFKA_MAX_POLL_INTERVAL_MS", "900000")),  # 15 minutes
            "session.timeout.ms": int(os.getenv("KAFKA_SESSION_TIMEOUT_MS", "45000")),
        }
        consumer = Consumer(conf)
        return consumer, (expense_topic, bank_topic, invoice_topic)
    except Exception as e:
        logger.error(f"Failed to initialize Kafka consumer: {e}")
        return None, (expense_topic, bank_topic)


def main() -> int:
    consumer, topics = _get_consumer()
    if not consumer:
        return 1
    expense_topic, bank_topic, invoice_topic = topics
    try:
        # On startup, scan all tenants for queued expenses and requeue them
        logger.info("Startup scan: requeue queued expenses if any")
        # Fetch tenant IDs from master
        tenant_ids: List[int] = tenant_db_manager.get_existing_tenant_ids()
        # For each tenant, look for queued expenses and requeue using latest attachment
        for tid in tenant_ids:
            try:
                set_tenant_context(tid)
            except Exception:
                continue
            try:
                SessionLocalTenant = tenant_db_manager.get_tenant_session(tid)
            except ValueError as e:
                logger.warning(f"Skipping tenant {tid}: {e}")
                continue
            db = SessionLocalTenant()
            try:
                from models.models_per_tenant import Expense, ExpenseAttachment
                queued: List[Expense] = db.query(Expense).filter(Expense.analysis_status == "queued").all()
                for exp in queued:
                    att = (
                        db.query(ExpenseAttachment)
                        .filter(ExpenseAttachment.expense_id == exp.id)
                        .order_by(ExpenseAttachment.uploaded_at.desc())
                        .first()
                    )
                    if not att or not getattr(att, "file_path", None):
                        continue
                    # Reuse queue_or_process_attachment via lightweight import to avoid cycles
                    try:
                        from services.ocr_service import queue_or_process_attachment
                        queue_or_process_attachment(db, tid, exp.id, att.id, str(att.file_path))
                        logger.info(f"Requeued queued expense_id={exp.id} tenant_id={tid}")
                    except Exception as e:
                        logger.warning(f"Failed to requeue expense {exp.id} in tenant {tid}: {e}")
            finally:
                db.close()
    except Exception as e:
        logger.warning(f"Startup requeue scan failed: {e}")
    consumer.subscribe([expense_topic, bank_topic, invoice_topic])

    running = True

    def handle_signal(signum, frame):
        nonlocal running
        logger.info("Stopping OCR consumer...")
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info(f"OCR consumer running on topics={[expense_topic, bank_topic, invoice_topic]}")
    while running:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            # Don't commit on poll errors; just log and continue so we can retry.
            logger.error(f"Kafka error: {msg.error()}")
            continue
        try:
            payload = json.loads(msg.value().decode("utf-8"))
            tenant_id: Optional[int] = payload.get("tenant_id")
            attempt = int(payload.get("attempt", 0))

            if tenant_id is not None:
                try:
                    set_tenant_context(int(tenant_id))
                except Exception as e:
                    # Don't commit; without tenant context we cannot process. Let retry handle it.
                    logger.warning(f"Failed to set tenant context {tenant_id}: {e}")

            # Open tenant-scoped DB session
            if tenant_id is None:
                # Invalid message; commit to avoid poison-pill redelivery.
                logger.error("No tenant_id in OCR message; committing and skipping invalid message")
                try:
                    consumer.commit(message=msg, asynchronous=False)
                except Exception:
                    pass
                continue
            try:
                SessionLocalTenant = tenant_db_manager.get_tenant_session(int(tenant_id))
            except ValueError as e:
                logger.warning(f"Skipping message for tenant {tenant_id}: {e}")
                try:
                    consumer.commit(message=msg, asynchronous=False)
                except Exception:
                    pass
                continue
            db = SessionLocalTenant()
            try:
                topic_name = msg.topic()
                logger.info(f"Kafka message received on topic={topic_name}: keys={list(payload.keys())}")
                # Handle expenses (existing path)
                if topic_name == expense_topic:
                    from models.models_per_tenant import Expense
                    expense_id = int(payload.get("expense_id"))
                    attachment_id = int(payload.get("attachment_id"))
                    file_path = str(payload.get("file_path"))
                    exp = db.query(Expense).filter(Expense.id == expense_id).first()
                    if not exp:
                        # Commit because the referenced expense no longer exists
                        logger.warning(f"Expense {expense_id} not found; committing and skipping")
                        try:
                            consumer.commit(message=msg, asynchronous=False)
                        except Exception:
                            pass
                    elif exp.manual_override:
                        # Commit because we should not retry if user manually overrided it
                        logger.info(f"Expense {expense_id} manually overridden; committing and skipping OCR application")
                        try:
                            consumer.commit(message=msg, asynchronous=False)
                        except Exception:
                            pass
                    else:
                        # Mark as processing and process
                        try:
                            exp.analysis_status = "processing"
                            exp.updated_at = datetime.now(timezone.utc)
                            db.commit()
                        except Exception:
                            db.rollback()
                        # Process with OCR (uses updated process_attachment_inline that fetches AI config)
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
                                logger.error(f"Failed to commit Kafka offset: {e}")
                            try:
                                from services.ocr_service import publish_ocr_result
                                publish_ocr_result(expense_id, tenant_id, status="done")
                            except Exception:
                                logger.error(f"Failed to publish OCR result for expense_id={expense_id}")
                                pass
                        elif getattr(exp, "analysis_status", None) == "failed":
                            # Retry with backoff and DLQ after max attempts
                            MAX_ATTEMPTS = int(os.getenv("KAFKA_OCR_MAX_ATTEMPTS", "5"))
                            if attempt + 1 >= MAX_ATTEMPTS:
                                logger.warning(f"OCR failed for expense_id={expense_id}. Sending to DLQ after {attempt+1} attempts.")
                                try:
                                    from confluent_kafka import Producer  # type: ignore
                                    from services.ocr_service import _get_kafka_producer
                                    producer, _ = _get_kafka_producer()
                                    if producer:
                                        dlq_topic = os.getenv("KAFKA_OCR_DLQ_TOPIC", "expenses_ocr_dlq")
                                        dlq_event = {
                                            "tenant_id": tenant_id,
                                            "expense_id": expense_id,
                                            "attachment_id": attachment_id,
                                            "file_path": file_path,
                                            "attempt": attempt + 1,
                                            "ts": datetime.now(timezone.utc).isoformat(),
                                        }
                                        producer.produce(dlq_topic, key=str(expense_id), value=json.dumps(dlq_event).encode("utf-8"))
                                        producer.flush(1.0)
                                    # Commit the failed message since we moved it to DLQ
                                    try:
                                        consumer.commit(message=msg, asynchronous=False)
                                    except Exception:
                                        pass
                                    try:
                                        from services.ocr_service import publish_ocr_result
                                        publish_ocr_result(expense_id, tenant_id, status="failed", details={"dlq": True})
                                    except Exception:
                                        pass
                                except Exception as e:
                                    logger.error(f"Failed to publish to DLQ: {e}")
                            else:
                                # Requeue with incremented attempt and simple time-based backoff (client-side)
                                try:
                                    backoff_ms = min(60000, 1000 * (2 ** attempt))
                                    logger.warning(f"Requeueing expense_id={expense_id} attempt={attempt+1} after backoff_ms={backoff_ms}")
                                    from time import sleep
                                    sleep(backoff_ms / 1000.0)
                                    from services.ocr_service import publish_ocr_task
                                    payload.update({"attempt": attempt + 1})
                                    publish_ocr_task(payload)
                                    # Commit the current message so we don't tight-loop
                                    try:
                                        consumer.commit(message=msg, asynchronous=False)
                                    except Exception:
                                        pass
                                except Exception as e:
                                    logger.error(f"Failed to requeue message: {e}")
                # Handle bank statements via LLM+regex extractor
                elif topic_name == bank_topic:
                    try:
                        from models.models_per_tenant import BankStatement, BankStatementTransaction, AIConfig as AIConfigModel
                        from services.bank_statement_service import process_bank_pdf_with_llm, BankLLMUnavailableError, is_bank_llm_reachable
                        statement_id = int(payload.get("statement_id"))
                        file_path = str(payload.get("file_path"))
                        logger.info(f"Processing bank statement: id={statement_id} tenant_id={tenant_id} file={file_path}")
                        stmt = db.query(BankStatement).filter(BankStatement.id == statement_id).first()
                        if not stmt:
                            try:
                                consumer.commit(message=msg, asynchronous=False)
                            except Exception:
                                pass
                        else:
                            # Fetch active AI config for tenant, if any
                            ai_row = db.query(AIConfigModel).filter(
                                AIConfigModel.is_active == True,
                                AIConfigModel.tested == True
                            ).first()
                            ai_conf = None
                            if ai_row:
                                ai_conf = {
                                    "provider_name": ai_row.provider_name,
                                    "provider_url": ai_row.provider_url,
                                    "api_key": ai_row.api_key,
                                    "model_name": ai_row.model_name,
                                }
                            # Retry up to 5 times on LLM errors with incremental backoff
                            attempts = int(payload.get("attempt", 0))
                            max_attempts = int(os.getenv("BANK_LLM_MAX_ATTEMPTS", "5"))
                            backoff_base_ms = int(os.getenv("BANK_LLM_BACKOFF_BASE_MS", "2000"))
                            # Pre-check LLM availability to distinguish outages from valid zero-transaction statements
                            llm_ok = is_bank_llm_reachable(ai_conf)
                            try:
                                txns = process_bank_pdf_with_llm(file_path, ai_conf)
                                logger.info(f"Extracted {len(txns)} transactions for statement_id={statement_id}")
                            except BankLLMUnavailableError as llm_err:
                                if attempts + 1 >= max_attempts:
                                    logger.error(f"Bank LLM unavailable after {attempts+1} attempts for statement_id={statement_id}: {llm_err}")
                                    # Mark statement as failed and commit offset
                                    try:
                                        stmt.status = "failed"
                                        db.commit()
                                    except Exception:
                                        db.rollback()
                                    try:
                                        consumer.commit(message=msg, asynchronous=False)
                                    except Exception:
                                        pass
                                    continue
                                # Requeue with backoff
                                from time import sleep
                                delay_ms = min(60000, backoff_base_ms * (attempts + 1))
                                logger.warning(f"LLM unavailable, retrying statement_id={statement_id} attempt={attempts+1} after {delay_ms}ms")
                                sleep(delay_ms / 1000.0)
                                from services.ocr_service import publish_bank_statement_task
                                payload.update({"attempt": attempts + 1})
                                publish_bank_statement_task(payload)
                                # Mark current as failed processing attempt and commit so we don't tight-loop
                                try:
                                    stmt.status = "processing"
                                    db.commit()
                                except Exception:
                                    db.rollback()
                                try:
                                    consumer.commit(message=msg, asynchronous=False)
                                except Exception:
                                    pass
                                continue

                            # If extraction returned zero transactions and LLM was reachable, accept as processed with 0
                            # Otherwise, treat as failure/retry
                            if not txns and not llm_ok:
                                if attempts + 1 >= max_attempts:
                                    logger.error(f"No transactions extracted after {attempts+1} attempts for statement_id={statement_id}; marking failed")
                                    try:
                                        stmt.status = "failed"
                                        db.commit()
                                    except Exception:
                                        db.rollback()
                                    try:
                                        consumer.commit(message=msg, asynchronous=False)
                                    except Exception:
                                        pass
                                    continue
                                from time import sleep
                                delay_ms = min(60000, backoff_base_ms * (attempts + 1))
                                logger.warning(f"Zero transactions extracted, retrying statement_id={statement_id} attempt={attempts+1} after {delay_ms}ms")
                                sleep(delay_ms / 1000.0)
                                from services.ocr_service import publish_bank_statement_task
                                payload.update({"attempt": attempts + 1})
                                publish_bank_statement_task(payload)
                                try:
                                    stmt.status = "processing"
                                    db.commit()
                                except Exception:
                                    db.rollback()
                                try:
                                    consumer.commit(message=msg, asynchronous=False)
                                except Exception:
                                    pass
                                continue
                            if not txns and llm_ok:
                                logger.info(f"LLM reachable but no transactions found for statement_id={statement_id}; marking processed with 0")
                                db.query(BankStatementTransaction).filter(BankStatementTransaction.statement_id == statement_id).delete()
                                stmt.status = "processed"
                                stmt.extracted_count = 0
                                db.commit()
                                try:
                                    consumer.commit(message=msg, asynchronous=False)
                                except Exception:
                                    pass
                                continue

                            # Replace
                            db.query(BankStatementTransaction).filter(BankStatementTransaction.statement_id == statement_id).delete()
                            count = 0
                            from datetime import datetime as _dt
                            for t in txns:
                                try:
                                    dt = _dt.fromisoformat(t.get("date", "")).date()
                                except Exception:
                                    dt = _dt.utcnow().date()
                                db.add(BankStatementTransaction(
                                    statement_id=statement_id,
                                    date=dt,
                                    description=t.get("description", ""),
                                    amount=float(t.get("amount", 0)),
                                    transaction_type=(t.get("transaction_type") if t.get("transaction_type") in ("debit", "credit") else ("debit" if float(t.get("amount", 0)) < 0 else "credit")),
                                    balance=(float(t["balance"]) if t.get("balance") is not None else None),
                                    category=t.get("category"),
                                ))
                                count += 1
                            stmt.status = "processed"
                            stmt.extracted_count = count
                            db.commit()
                            logger.info(f"Bank statement processed: id={statement_id} count={count}")
                            try:
                                consumer.commit(message=msg, asynchronous=False)
                            except Exception:
                                pass
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Failed processing bank statement: {e}")
                # Handle invoice OCR
                elif topic_name == invoice_topic:
                    try:
                        # Pull AI config and process invoice using existing PDF processor route logic
                        from models.models_per_tenant import AIConfig as AIConfigModel
                        from routers.pdf_processor import process_pdf_with_ai  # uses LiteLLM and active config
                        # Expect payload to include a temp file path and a generated task_id
                        task_id = str(payload.get("task_id"))
                        file_path = str(payload.get("file_path"))
                        # Load AI config
                        ai_row = db.query(AIConfigModel).filter(
                            AIConfigModel.is_active == True,
                            AIConfigModel.tested == True
                        ).first()
                        if not ai_row:
                            # Fallback to environment configuration
                            model_name = os.getenv("LLM_MODEL_INVOICES") or os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
                            provider_url = os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE")
                            api_key = os.getenv("LLM_API_KEY")
                            provider_name = "ollama" if os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE") or os.getenv("OLLAMA_MODEL") else "openai"
                            ai_conf = SimpleNamespace(
                                provider_name=provider_name,
                                provider_url=provider_url,
                                api_key=api_key,
                                model_name=model_name,
                                is_active=True,
                                tested=True,
                            )
                        else:
                            ai_conf = ai_row  # reuse model instance
                        # Run extraction
                        import asyncio
                        data = asyncio.get_event_loop().run_until_complete(process_pdf_with_ai(file_path, ai_conf))
                        # Publish result
                        from services.ocr_service import publish_invoice_result
                        publish_invoice_result(task_id, tenant_id, {"invoice_data": data})
                        try:
                            consumer.commit(message=msg, asynchronous=False)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.error(f"Failed processing invoice OCR: {e}")
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
