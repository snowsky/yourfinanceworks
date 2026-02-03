
import asyncio
from typing import Optional, Union, List, Dict, Any
import logging
import os
import signal
from datetime import datetime, timezone, timedelta
import json
import tempfile
from pathlib import Path

from sqlalchemy import text

from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select, func, or_, and_

from core.models.database import get_db, get_master_db, set_tenant_context, clear_tenant_context
from core.models.models import Tenant
from core.models.models_per_tenant import (
    Invoice, Expense, BankStatement, Settings,
    ExpenseAttachment, InvoiceAttachment, BankStatementAttachment
)
from commercial.ai.services.ai_config_service import AIConfigService
from core.services.review_service import ReviewService
from commercial.ai_invoice.services.invoice_ai_service import InvoiceAIService
from core.services.statement_service import StatementService
from commercial.ai.services.ocr_service import _run_ocr
from core.services.tenant_database_manager import tenant_db_manager
from commercial.prompt_management.services.prompt_service import get_prompt_service
from workers.ocr_consumer import ProcessingStatus

logger = logging.getLogger(__name__)

class ReviewProcessorWorker:
    def __init__(self):
        self.poll_interval = int(os.getenv("REVIEW_POLL_INTERVAL", "60"))
        self.batch_size = int(os.getenv("REVIEW_BATCH_SIZE", "10"))
        self.running = True
        self.review_topic = os.getenv("KAFKA_REVIEW_TOPIC", "review_trigger")
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self._kafka_consumer = None
        self._setup_signal_handlers()

    async def _get_statement_service(self, db: Session, config: dict, prompt_name: str = "raw_text_extraction"):
        """Get a configured StatementService instance."""
        try:
            return StatementService(
                ai_config=config,
                db_session=db,
                prompt_name=prompt_name
            )
        except Exception as e:
            logger.error(f"Failed to initialize StatementService: {e}")
            return None

    def _setup_signal_handlers(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_exit)

    async def _resolve_local_file(self, db: Session, tenant_id: int, file_path: str, record=None) -> tuple:
        """
        Ensures a file is available locally. Checks multiple paths and downloads from cloud if needed.
        Returns (local_path, is_temporary)
        """
        if not file_path:
            return None, False

        # 1. Check local_cache_path if record has it
        if record and hasattr(record, 'local_cache_path') and record.local_cache_path:
            if os.path.exists(record.local_cache_path) and os.path.getsize(record.local_cache_path) > 0:
                logger.debug(f"Using cached local file: {record.local_cache_path}")
                return record.local_cache_path, False

        # 2. Try various local paths
        search_paths = []
        if os.path.isabs(file_path):
            search_paths.append(file_path)
        else:
            # Paths relative to /app (project root in Docker)
            search_paths.append(os.path.join("/app", file_path))
            if not file_path.startswith("attachments/"):
                search_paths.append(os.path.join("/app/attachments", file_path))

            # Paths relative to current working directory (for local dev)
            search_paths.append(file_path)
            if not file_path.startswith("attachments/"):
                search_paths.append(os.path.join("attachments", file_path))

        for p in search_paths:
            if os.path.exists(p) and os.path.isfile(p):
                logger.debug(f"Found local file at: {p}")
                return p, False

        # 3. Fallback to Cloud Storage Download
        logger.info(f"File {file_path} not found locally, attempting cloud storage download for tenant {tenant_id}...")
        try:
            from commercial.cloud_storage.service import CloudStorageService
            from commercial.cloud_storage.config import get_cloud_storage_config

            cloud_config = get_cloud_storage_config()
            cloud_storage_service = CloudStorageService(db, cloud_config)

            # Try raw path first
            s3_key = file_path
            result = await cloud_storage_service.retrieve_file(
                file_key=s3_key,
                tenant_id=str(tenant_id),
                user_id=1, # System
                generate_url=False
            )

            # If not found, try with 'attachments/' prefix which is common for some types
            if (not result.success or not result.file_content) and not s3_key.startswith("attachments/"):
                logger.debug(f"Retrying cloud download with attachments/ prefix for {s3_key}")
                result = await cloud_storage_service.retrieve_file(
                    file_key=f"attachments/{s3_key}",
                    tenant_id=str(tenant_id),
                    user_id=1,
                    generate_url=False
                )

            if result.success and result.file_content:
                ext = Path(file_path).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(result.file_content)
                    temp_path = tmp.name

                logger.info(f"Successfully downloaded cloud file to temporary path: {temp_path}")

                # Update local cache path if model supports it (like BankStatement)
                if record and hasattr(record, 'local_cache_path'):
                    try:
                        record.local_cache_path = temp_path
                        db.commit()
                    except Exception as e:
                        logger.warning(f"Failed to update local_cache_path for record: {e}")

                return temp_path, True
            else:
                logger.warning(f"Cloud retrieval failed for {file_path}: {result.error_message}")

        except Exception as e:
            logger.error(f"Error during cloud retrieval for {file_path}: {e}")

        return None, False

    def _handle_exit(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down Review Processor...")
        self.running = False

    async def start(self):
        logger.info("Starting Review Processor Worker...")

        # Release all advisory locks on startup (cleanup from previous runs)
        self._cleanup_all_locks()

        # Ensure Kafka topics exist before starting listeners
        self._ensure_kafka_topic()

        # Initialize Kafka consumer for review events
        self._init_kafka_consumer()

        # Run both polling and event listening concurrently
        tasks = [
            asyncio.create_task(self._polling_loop()),
            asyncio.create_task(self._event_listener_loop())
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in worker tasks: {e}", exc_info=True)
        finally:
            if self._kafka_consumer:
                try:
                    self._kafka_consumer.close()
                except Exception:
                    pass

    def _init_kafka_consumer(self):
        """Initialize Kafka consumer for review trigger events"""
        try:
            from confluent_kafka import Consumer

            config = {
                'bootstrap.servers': self.bootstrap_servers,
                'group.id': 'review-processor-group',
                'auto.offset.reset': 'latest',
                'enable.auto.commit': True,
            }

            self._kafka_consumer = Consumer(config)
            self._kafka_consumer.subscribe([self.review_topic])
            logger.info(f"Kafka consumer initialized for review events (topic: {self.review_topic})")
        except Exception as e:
            logger.warning(f"Failed to initialize Kafka consumer: {e}. Will rely on polling only.")
            self._kafka_consumer = None

    async def _polling_loop(self):
        """Polling loop - runs every poll_interval seconds"""
        logger.info("Starting polling loop...")
        while self.running:
            try:
                await self.process_all_tenants()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}", exc_info=True)

            if self.running:
                await asyncio.sleep(self.poll_interval)

    async def _event_listener_loop(self):
        """Event listener loop - processes Kafka events immediately"""
        if not self._kafka_consumer:
            logger.info("Kafka consumer not available, event listening disabled")
            return

        logger.info("Starting event listener loop...")
        while self.running:
            try:
                # Poll for messages with short timeout to allow checking self.running
                msg = self._kafka_consumer.poll(timeout=1.0)

                if msg is None:
                    continue
                if msg.error():
                    logger.error(f"Kafka consumer error: {msg.error()}")
                    continue

                # Decode and process message
                try:
                    event = json.loads(msg.value().decode('utf-8'))
                    await self._process_review_event(event)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode Kafka message: {e}")

            except Exception as e:
                logger.error(f"Error in event listener loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    def _ensure_kafka_topic(self):
        """Ensure the review trigger Kafka topic exists, creating it if necessary."""
        try:
            from confluent_kafka.admin import AdminClient, NewTopic

            kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
            topic_name = os.getenv("KAFKA_REVIEW_TOPIC", "review_trigger")

            admin_client = AdminClient({'bootstrap.servers': kafka_servers})

            # Check if topic exists
            metadata = admin_client.list_topics(timeout=5)
            if topic_name in metadata.topics:
                logger.info(f"Kafka topic '{topic_name}' already exists")
                return

            # Create topic if it doesn't exist
            logger.info(f"Creating Kafka topic '{topic_name}'...")
            new_topic = NewTopic(topic_name, num_partitions=1, replication_factor=1)
            fs = admin_client.create_topics([new_topic], validate_only=False)

            # Wait for topic creation to complete
            for topic, f in fs.items():
                try:
                    f.result(timeout=10)
                    logger.info(f"Successfully created topic '{topic}'")
                except Exception as e:
                    logger.warning(f"Failed to create topic '{topic}': {e}")

        except Exception as e:
            logger.warning(f"Could not ensure Kafka topic: {e}")

    async def _process_review_event(self, event: dict):
        """Process a single review trigger event"""
        try:
            tenant_id = event.get("tenant_id")
            entity_type = event.get("entity_type")
            entity_id = event.get("entity_id")
            model_override = event.get("model_override")
            prompt_override = event.get("prompt_override")

            if not tenant_id or not entity_type or not entity_id:
                logger.warning(f"Received review event without tenant_id, entity_type, or entity_id: {event}")
                return

            # Set tenant context for encryption and standard DB logic
            set_tenant_context(tenant_id)

            # Check if review worker is enabled for this tenant
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            with SessionLocal_tenant() as session:
                if not AIConfigService.is_review_worker_enabled(session):
                    logger.info(f"Skipping review event for tenant {tenant_id} as review worker is disabled")
                    return

            logger.info(f"Processing event-driven review for {entity_type} {entity_id} for tenant {tenant_id}")

            # Re-fetch entity to check freshness and status
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            with SessionLocal_tenant() as session:
                if entity_type == "invoice":
                    entity = session.query(Invoice).filter(Invoice.id == entity_id).first()
                elif entity_type == "expense":
                    entity = session.query(Expense).filter(Expense.id == entity_id).first()
                elif entity_type in ["bank_statement", "statement"]:
                    entity = session.query(BankStatement).filter(BankStatement.id == entity_id).first()
                else:
                    entity = None

                if not entity:
                    logger.warning(f"Entity {entity_type} {entity_id} not found for review")
                    return

                # Skip if already reviewed
                if entity.review_status == "reviewed":
                    logger.info(f"Entity {entity_type} {entity_id} already reviewed, skipping event.")
                    return

                # Attempt to acquire tenant lock to avoid overlap with polling
                # Using a session-level lock that will be released when the block ends
                try:
                    lock_acquired = session.execute(text("SELECT pg_try_advisory_xact_lock(:lock_id)"), {"lock_id": tenant_id}).scalar()
                    if not lock_acquired:
                        logger.info(f"Tenant {tenant_id} lock held by poller, skipping event for {entity_type} {entity_id}")
                        return
                except Exception as e:
                    logger.warning(f"Failed to check advisory lock for tenant {tenant_id}: {e}")

            if entity_type == "invoice":
                await self.process_single_invoice(tenant_id, entity_id, model_override, prompt_override)
            elif entity_type == "expense":
                await self.process_single_expense(tenant_id, entity_id, model_override, prompt_override)
            elif entity_type in ["bank_statement", "statement"]:
                await self.process_single_bank_statement(tenant_id, entity_id, model_override, prompt_override)
            else:
                logger.warning(f"Unsupported entity_type for event-driven review: {entity_type}")

            logger.info(f"Completed event-driven review processing for {entity_type} {entity_id} for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"Error processing review event: {e}", exc_info=True)
        finally:
            clear_tenant_context()

    async def process_all_tenants(self):
        """Iterate through all active tenants and process their reviews.
        Returns True if any tenant has review integration enabled, False otherwise.
        """
        master_db = next(get_master_db())
        any_enabled = False
        try:
            tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
            logger.info(f"Found {len(tenants)} active tenants to process.")

            for tenant in tenants:
                if not self.running:
                    break

                # Try to acquire advisory lock for this tenant
                # This prevents multiple workers from processing the same tenant
                lock_acquired = self._try_acquire_tenant_lock(master_db, tenant.id)

                if not lock_acquired:
                    logger.debug(f"Tenant {tenant.id} is being processed by another worker, skipping...")
                    continue

                try:
                    tenant_has_review = await self.process_tenant(tenant)
                    if tenant_has_review:
                        any_enabled = True
                finally:
                    # Always release the lock
                    self._release_tenant_lock(master_db, tenant.id)
        finally:
            master_db.close()

        return any_enabled

    def _try_acquire_tenant_lock(self, db: Session, tenant_id: int) -> bool:
        """Try to acquire a PostgreSQL advisory lock for a tenant.
        Returns True if lock acquired, False if another worker has it.
        """
        try:
            # Use PostgreSQL advisory lock with a unique key based on tenant_id
            # pg_try_advisory_lock returns true if lock acquired, false if already held
            result = db.execute(text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": tenant_id})
            acquired = result.scalar()
            return acquired
        except Exception as e:
            logger.warning(f"Failed to acquire lock for tenant {tenant_id}: {e}")
            return False

    def _release_tenant_lock(self, db: Session, tenant_id: int):
        """Release the PostgreSQL advisory lock for a tenant."""
        try:
            db.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": tenant_id})
        except Exception as e:
            logger.warning(f"Failed to release lock for tenant {tenant_id}: {e}")

    def _cleanup_all_locks(self):
        """Release all advisory locks on startup to clean up from previous runs."""
        try:
            db = next(get_master_db())
            try:
                # pg_advisory_unlock_all() releases all advisory locks held by this session
                db.execute(text("SELECT pg_advisory_unlock_all()"))
                logger.info("Released all advisory locks from previous sessions")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to cleanup advisory locks on startup: {e}")

    async def process_tenant(self, tenant: Tenant):
        """Process reviews for a specific tenant.
        Returns True if review integration is enabled for this tenant, False otherwise.
        """
        logger.debug(f"Checking review tasks for tenant {tenant.name} ({tenant.id})")

        # Set tenant context for encryption and standard DB logic
        set_tenant_context(tenant.id)

        # Connect to tenant DB
        try:
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant.id)
            session = SessionLocal_tenant()
        except Exception as e:
            logger.error(f"Failed to connect to tenant {tenant.id} DB: {e}")
            clear_tenant_context()
            return False

        try:
            # Check if review worker is enabled
            if not AIConfigService.is_review_worker_enabled(session):
                logger.debug(f"Review integration disabled for tenant {tenant.id}")
                return False

            logger.info(f"Starting review processing for tenant {tenant.id} with batch_size={self.batch_size}")

            # Process Invoices with batch size
            await self.process_invoices_batch(session, tenant)

            # Process Expenses with batch size
            await self.process_expenses_batch(session, tenant)

            # Process Bank Statements with batch size
            await self.process_bank_statements_batch(session, tenant)

            return True  # Review integration is enabled for this tenant

        except Exception as e:
            logger.error(f"Error processing tenant {tenant.id}: {e}", exc_info=True)
            return False  # Treat errors as disabled to avoid spam
        finally:
            session.close()
            clear_tenant_context()

    async def process_single_invoice(self, tenant_id: int, invoice_id: int, model_override: Optional[str] = None, prompt_override: Optional[str] = None):
        """Processes a single invoice for review, typically triggered by an event."""
        # Double check if review worker is enabled
        SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
        with SessionLocal_tenant() as session:
            if not AIConfigService.is_review_worker_enabled(session):
                return

        logger.info(f"Processing single invoice {invoice_id} for tenant {tenant_id} (event-driven)")

        set_tenant_context(tenant_id)
        try:
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db = SessionLocal_tenant()
            try:
                invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
                if not invoice:
                    logger.error(f"Invoice {invoice_id} not found for tenant {tenant_id}")
                    return

                # Resolve effective path
                effective_path = invoice.attachment_path
                if not effective_path:
                    att = db.query(InvoiceAttachment).filter(InvoiceAttachment.invoice_id == invoice.id).first()
                    if att:
                        effective_path = att.file_path

                if not effective_path:
                    logger.error(f"No attachment found for Invoice {invoice_id}")
                    return

                invoice._effective_review_path = effective_path

                review_service = ReviewService(db)
                reviewer_config = AIConfigService.get_ai_config(db, component="reviewer", require_ocr=True)

                if not reviewer_config:
                    logger.warning(f"Review worker enabled but no reviewer config found for tenant {tenant_id}")
                    return

                if model_override:
                    reviewer_config["model_name"] = model_override
                    logger.info(f"Invoice {invoice_id}: Using model override: {model_override}")

                if prompt_override:
                    reviewer_config["prompt_override"] = prompt_override
                    logger.info(f"Invoice {invoice_id}: Using prompt override")

                await self._process_invoice_item(db, invoice, tenant_id, review_service, reviewer_config)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error processing single invoice {invoice_id} for tenant {tenant_id}: {e}", exc_info=True)
        finally:
            clear_tenant_context()

    async def process_single_expense(self, tenant_id: int, expense_id: int, model_override: Optional[str] = None, prompt_override: Optional[str] = None):
        """Processes a single expense for review, typically triggered by an event."""
        # Double check if review worker is enabled
        SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
        with SessionLocal_tenant() as session:
            if not AIConfigService.is_review_worker_enabled(session):
                return

        logger.info(f"Processing single expense {expense_id} for tenant {tenant_id} (event-driven)")

        set_tenant_context(tenant_id)
        try:
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db = SessionLocal_tenant()
            try:
                expense = db.query(Expense).filter(Expense.id == expense_id).first()
                if not expense:
                    logger.error(f"Expense {expense_id} not found for tenant {tenant_id}")
                    return

                # Resolve effective path
                effective_path = expense.receipt_path
                if not effective_path:
                    att = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense.id).first()
                    if att:
                        effective_path = att.file_path

                if not effective_path:
                    logger.error(f"No receipt/attachment found for Expense {expense_id}")
                    return

                expense._effective_review_path = effective_path

                review_service = ReviewService(db)
                reviewer_config = AIConfigService.get_ai_config(db, component="reviewer", require_ocr=True)

                if not reviewer_config:
                    logger.warning(f"Review worker enabled but no reviewer config found for tenant {tenant_id}")
                    return

                if model_override:
                    reviewer_config["model_name"] = model_override
                    logger.info(f"Expense {expense_id}: Using model override: {model_override}")

                if prompt_override:
                    reviewer_config["prompt_override"] = prompt_override
                    logger.info(f"Expense {expense_id}: Using prompt override")

                await self._process_expense_item(db, expense, tenant_id, review_service, reviewer_config)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error processing single expense {expense_id} for tenant {tenant_id}: {e}", exc_info=True)
        finally:
            clear_tenant_context()

    async def process_single_bank_statement(self, tenant_id: int, statement_id: int, model_override: Optional[str] = None, prompt_override: Optional[str] = None):
        """Processes a single bank statement for review, typically triggered by an event."""
        # Double check if review worker is enabled
        SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
        with SessionLocal_tenant() as session:
            if not AIConfigService.is_review_worker_enabled(session):
                return

        logger.info(f"Processing single bank statement {statement_id} for tenant {tenant_id} (event-driven)")

        set_tenant_context(tenant_id)
        try:
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db = SessionLocal_tenant()
            try:
                statement = db.query(BankStatement).filter(BankStatement.id == statement_id).first()
                if not statement:
                    logger.error(f"Bank Statement {statement_id} not found for tenant {tenant_id}")
                    return

                # Resolve effective path
                effective_path = statement.file_path
                if not effective_path:
                    att = db.query(BankStatementAttachment).filter(BankStatementAttachment.statement_id == statement.id).first()
                    if att:
                        effective_path = att.file_path

                if not effective_path:
                    logger.error(f"No file/attachment found for BankStatement {statement_id}")
                    return

                statement._effective_review_path = effective_path

                review_service = ReviewService(db)
                reviewer_config = AIConfigService.get_ai_config(db, component="reviewer", require_ocr=True)

                if not reviewer_config:
                    logger.warning(f"Review worker enabled but no reviewer config found for tenant {tenant_id}")
                    return

                if model_override:
                    reviewer_config["model_name"] = model_override
                    logger.info(f"Bank Statement {statement_id}: Using model override: {model_override}")

                if prompt_override:
                    reviewer_config["prompt_override"] = prompt_override
                    logger.info(f"Bank Statement {statement_id}: Using prompt override")

                await self._process_bank_statement_item(db, statement, tenant_id, review_service, reviewer_config)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error processing single bank statement {statement_id} for tenant {tenant_id}: {e}", exc_info=True)
        finally:
            clear_tenant_context()

    async def process_invoices_batch(self, db: Session, tenant: Tenant):
        """Processes a batch of invoices for review, typically for polling."""
        review_service = ReviewService(db)
        reviewer_config = AIConfigService.get_ai_config(db, component="reviewer", require_ocr=True)

        if not reviewer_config:
            logger.warning(f"Review worker enabled but no reviewer config found for tenant {tenant.id}")
            return

        # Fetch invoices needing review
        # Filter for items that are either:
        # 1. Not started
        # 2. Pending but stale (updated_at > 30 mins ago), which suggests a crashed worker
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=30)

        all_invoices = db.query(Invoice).filter(
            or_(
                Invoice.review_status == "not_started",
                and_(
                    Invoice.review_status == "pending",
                    Invoice.updated_at < stale_threshold
                )
            )
        ).limit(self.batch_size).all()

        if not all_invoices:
            return

        logger.info(f"Found {len(all_invoices)} invoices to review for tenant {tenant.id}")

        # Fetch related attachments for these invoices
        invoice_ids = [i.id for i in all_invoices]
        attachments = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id.in_(invoice_ids)
        ).all()
        attachment_map = {a.invoice_id: a.file_path for a in attachments}

        # Separate invoices with and without attachments
        invoices_with_attachment = []
        invoices_without_attachment = []

        for inv in all_invoices:
            effective_path = inv.attachment_path or attachment_map.get(inv.id)
            if effective_path:
                inv._effective_review_path = effective_path
                invoices_with_attachment.append(inv)
            else:
                invoices_without_attachment.append(inv)

        for invoice in invoices_with_attachment:
            if not self.running: break
            await self._process_invoice_item(db, invoice, tenant.id, review_service, reviewer_config)

        # Handle invoices without attachments
        if invoices_without_attachment:
            for invoice in invoices_without_attachment:
                if not self.running: break
                try:
                    invoice.review_status = "reviewed"
                    invoice.review_result = {"note": "No attachment available for review"}
                    invoice.reviewed_at = datetime.now(timezone.utc)
                    db.commit()
                except Exception as e:
                    logger.error(f"Exception marking Invoice {invoice.id} as reviewed: {e}")
                    invoice.review_status = "failed"
                    db.commit()

    async def _process_invoice_item(self, db: Session, invoice: Invoice, tenant_id: int, review_service: ReviewService, config: dict):
        """Helper to process a single invoice item."""
        local_path, is_temp = await self._resolve_local_file(db, tenant_id, invoice._effective_review_path, invoice)
        if not local_path:
            logger.error(f"Could not resolve file for Invoice {invoice.id}: {invoice._effective_review_path}")
            invoice.review_status = "failed"
            db.commit()
            return

        logger.info(f"Reviewing Invoice {invoice.id}...")
        invoice.review_status = "pending"
        db.commit()

        try:
            # Pass 1: Extract RAW data from document
            logger.info(f"Pass 1: Extracting raw context from invoice {invoice.id}...")
            raw_context = ""

            # Fetch OCR config for Pass 1 (vision support)
            # TODO: Future updates should allow users to explicitly configure both vision (OCR) and text-based (Reviewer) models in the AI Configuration tab.
            if config.get("use_for_extraction"):
                ocr_config = config
                logger.info(f"Using reviewer model for Pass 1 extraction (Invoice) as per configuration")
            else:
                ocr_config = AIConfigService.get_ai_config(db, component="ocr", require_ocr=True) or config

            if local_path.lower().endswith('.pdf'):
                try:
                    svc = await self._get_statement_service(db, ocr_config)
                    if svc:
                        docs = svc.load_pdf_with_langchain(local_path)
                        p_docs = svc.preprocess_documents(docs)
                        raw_context = "\n\n".join([doc.page_content for doc in p_docs])
                except Exception as e:
                    logger.warning(f"Pass 1: PDF extraction failed: {e}")

            if not raw_context:
                prompt_service = get_prompt_service(db)
                raw_text_prompt = prompt_service.get_prompt(
                    name="raw_text_extraction",
                    variables={},
                    provider_name=ocr_config.get("provider_name"),
                    fallback_prompt="Extract all text from this invoice exactly as it appears."
                )

                # Always use OCR config for vision-capable Pass 1
                first_pass_result = await _run_ocr(file_path=local_path, ai_config=ocr_config, custom_prompt=raw_text_prompt)
                if isinstance(first_pass_result, dict):
                    raw_context = first_pass_result.get("raw") or first_pass_result.get("text") or json.dumps(first_pass_result, indent=2)
                else:
                    raw_context = str(first_pass_result)

            if raw_context:
                # Pass 2: Apply reviewer prompt to raw text
                logger.info(f"Pass 2: Applying reviewer prompt to invoice {invoice.id}...")
                # Use LLM to re-process the data with reviewer prompt
                from commercial.ai.services.ocr_service import _convert_raw_ocr_to_json
                review_data = await _convert_raw_ocr_to_json(
                    raw_content=raw_context,
                    model_name=config.get("model_name", "gpt-4"),
                    provider_name=config.get("provider_name", "openai"),
                    kwargs={
                        "model": config.get("model_name", "gpt-4"),
                        "api_key": config.get("api_key"),
                        "base_url": config.get("provider_url")
                    },
                    db_session=db,
                    custom_prompt=config.get("prompt_override")
                )

                if review_data and "error" not in review_data:
                    review_service.compare_and_store_review(invoice, review_data)
                else:
                    logger.error(f"Pass 2 failed for Invoice {invoice.id}")
                    invoice.review_status = "failed"
                    db.commit()
            else:
                logger.error(f"Pass 1 extraction failed for Invoice {invoice.id}")
                invoice.review_status = "failed"
                db.commit()

        except Exception as e:
            logger.error(f"Exception reviewing Invoice {invoice.id}: {e}")
            invoice.review_status = "failed"
            db.commit()
        finally:
            if is_temp and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass

    async def process_expenses_batch(self, db: Session, tenant: Tenant):
        """Processes a batch of expenses for review, typically for polling."""
        review_service = ReviewService(db)
        reviewer_config = AIConfigService.get_ai_config(db, component="reviewer", require_ocr=True)

        if not reviewer_config:
            logger.warning(f"Review worker enabled but no reviewer config found for tenant {tenant.id}")
            return

        # Filter for items that are either:
        # 1. Not started
        # 2. Pending but stale (updated_at > 30 mins ago), which suggests a crashed worker
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=30)

        all_expenses = db.query(Expense).filter(
            or_(
                Expense.review_status == "not_started",
                and_(
                    Expense.review_status == "pending",
                    Expense.updated_at < stale_threshold
                )
            )
        ).limit(self.batch_size).all()

        if not all_expenses:
            return

        logger.info(f"Found {len(all_expenses)} expenses to review for tenant {tenant.id}")

        expense_ids = [e.id for e in all_expenses]
        expense_attachments = db.query(ExpenseAttachment).filter(
            ExpenseAttachment.expense_id.in_(expense_ids)
        ).all()
        attachment_map = {a.expense_id: a.file_path for a in expense_attachments}

        expenses_with_receipt = []
        expenses_without_receipt = []

        for exp in all_expenses:
            effective_path = exp.receipt_path or attachment_map.get(exp.id)
            if effective_path:
                exp._effective_review_path = effective_path
                expenses_with_receipt.append(exp)
            else:
                expenses_without_receipt.append(exp)

        for expense in expenses_with_receipt:
            if not self.running: break
            await self._process_expense_item(db, expense, tenant.id, review_service, reviewer_config)

        if expenses_without_receipt:
            for expense in expenses_without_receipt:
                if not self.running: break
                try:
                    expense.review_status = "reviewed"
                    expense.review_result = {"note": "No receipt available for review"}
                    expense.reviewed_at = datetime.now(timezone.utc)
                    db.commit()
                except Exception as e:
                    logger.error(f"Exception marking Expense {expense.id} as reviewed: {e}")
                    expense.review_status = "failed"
                    db.commit()

    async def _process_expense_item(self, db: Session, expense: Expense, tenant_id: int, review_service: ReviewService, config: dict):
        """Helper to process a single expense item."""
        local_path, is_temp = await self._resolve_local_file(db, tenant_id, expense._effective_review_path, expense)
        if not local_path:
            logger.error(f"Could not resolve file for Expense {expense.id}: {expense._effective_review_path}")
            expense.review_status = "failed"
            db.commit()
            return

        logger.info(f"Reviewing Expense {expense.id}...")
        expense.review_status = "pending"
        db.commit()

        try:
            logger.info(f"Pass 1: Extracting raw context from expense {expense.id}...")
            raw_context = ""

            # Fetch OCR config for Pass 1 (vision support)
            # If reviewer is configured to be used for extraction, prioritize it
            if config.get("use_for_extraction"):
                ocr_config = config
                logger.info(f"Using reviewer model for Pass 1 extraction as per configuration")
            else:
                ocr_config = AIConfigService.get_ai_config(db, component="ocr", require_ocr=True) or config

            if local_path.lower().endswith('.pdf'):
                try:
                    svc = await self._get_statement_service(db, ocr_config)
                    if svc:
                        docs = svc.load_pdf_with_langchain(local_path)
                        p_docs = svc.preprocess_documents(docs)
                        raw_context = "\n\n".join([doc.page_content for doc in p_docs])
                except Exception as e:
                    logger.warning(f"Pass 1: PDF extraction failed for expense {expense.id}: {e}")

            if not raw_context:
                prompt_service = get_prompt_service(db)
                raw_text_prompt = prompt_service.get_prompt(
                    name="raw_text_extraction",
                    variables={},
                    provider_name=ocr_config.get("provider_name"),
                    fallback_prompt="Transcribe all text from this receipt exactly."
                )

                # Always use OCR config for vision-capable Pass 1
                first_pass_result = await _run_ocr(file_path=local_path, ai_config=ocr_config, custom_prompt=raw_text_prompt)
                if isinstance(first_pass_result, dict):
                    raw_context = first_pass_result.get("raw") or first_pass_result.get("text") or json.dumps(first_pass_result, indent=2)
                else:
                    raw_context = str(first_pass_result)

            if raw_context:
                logger.info(f"Pass 2: Applying reviewer prompt to expense {expense.id}...")
                # Use LLM to re-process the data with reviewer prompt
                from commercial.ai.services.ocr_service import _convert_raw_ocr_to_json
                result = await _convert_raw_ocr_to_json(
                    raw_content=raw_context,
                    model_name=config.get("model_name", "gpt-4"),
                    provider_name=config.get("provider_name", "openai"),
                    kwargs={
                        "model": config.get("model_name", "gpt-4"),
                        "api_key": config.get("api_key"),
                        "base_url": config.get("provider_url")
                    },
                    db_session=db,
                    custom_prompt=config.get("prompt_override")
                )

                if result and "error" not in result:
                    review_service.compare_and_store_review(expense, result)
                else:
                    logger.error(f"Pass 2 failed for Expense {expense.id}")
                    expense.review_status = "failed"
                    db.commit()
            else:
                logger.error(f"Pass 1 failed for Expense {expense.id}")
                expense.review_status = "failed"
                db.commit()

        except Exception as e:
            logger.error(f"Exception reviewing Expense {expense.id}: {e}")
            expense.review_status = "failed"
            db.commit()
        finally:
            if is_temp and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass

    async def process_bank_statements_batch(self, db: Session, tenant: Tenant):
        """Processes a batch of bank statements for review, typically for polling."""
        review_service = ReviewService(db)
        reviewer_config = AIConfigService.get_ai_config(db, component="reviewer", require_ocr=True)

        if not reviewer_config:
            logger.warning(f"Review worker enabled but no reviewer config found for tenant {tenant.id}")
            return

        # Filter for items that are either:
        # 1. Not started
        # 2. Pending but stale (updated_at > 10 mins ago), which suggests a crashed worker
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=10)

        all_stmts = db.query(BankStatement).filter(
            or_(
                BankStatement.review_status == "not_started",
                and_(
                    BankStatement.review_status == "pending",
                    BankStatement.updated_at < stale_threshold
                )
            ),
            BankStatement.status == ProcessingStatus.PROCESSED.value
        ).limit(max(1, self.batch_size // 2)).all()

        if not all_stmts:
            return

        logger.info(f"Found {len(all_stmts)} statements to review for tenant {tenant.id}")

        stmt_ids = [s.id for s in all_stmts]
        stmt_attachments = db.query(BankStatementAttachment).filter(
            BankStatementAttachment.statement_id.in_(stmt_ids)
        ).all()
        attachment_map = {a.statement_id: a.file_path for a in stmt_attachments}

        stmts_with_file = []
        stmts_without_file = []

        for stmt in all_stmts:
            effective_path = stmt.file_path or attachment_map.get(stmt.id)
            if effective_path:
                stmt._effective_review_path = effective_path
                stmts_with_file.append(stmt)
            else:
                stmts_without_file.append(stmt)

        for stmt in stmts_with_file:
            if not self.running: break
            await self._process_bank_statement_item(db, stmt, tenant.id, review_service, reviewer_config)

        if stmts_without_file:
            for stmt in stmts_without_file:
                if not self.running: break
                try:
                    stmt.review_status = "reviewed"
                    stmt.review_result = {"note": "No file available for review"}
                    stmt.reviewed_at = datetime.now(timezone.utc)
                    db.commit()
                except Exception as e:
                    logger.error(f"Exception marking Bank Statement {stmt.id} as reviewed: {e}")
                    stmt.review_status = "failed"
                    db.commit()

    async def _process_bank_statement_item(self, db: Session, stmt: BankStatement, tenant_id: int, review_service: ReviewService, config: dict):
        """Helper to process a single bank statement item."""
        local_path, is_temp = await self._resolve_local_file(db, tenant_id, stmt._effective_review_path, stmt)
        if not local_path:
            logger.error(f"Could not resolve file for Bank Statement {stmt.id}: {stmt._effective_review_path}")
            stmt.review_status = "failed"
            db.commit()
            return

        logger.info(f"Reviewing Bank Statement {stmt.id}...")
        stmt.review_status = "pending"
        db.commit()

        try:
            statement_service = await self._get_statement_service(db, config, "bank_statement_review_extraction")
            if not statement_service:
                raise Exception("StatementService not available")

            docs = statement_service.load_pdf_with_langchain(local_path)
            p_docs = statement_service.preprocess_documents(docs)
            transactions = statement_service.extract_transactions_from_documents(p_docs)

            review_data = {"transactions": transactions}
            review_service.compare_and_store_review(stmt, review_data)

        except Exception as e:
            logger.error(f"Exception reviewing Statement {stmt.id}: {e}")
            stmt.review_status = "failed"
            db.commit()

if __name__ == "__main__":
    worker = ReviewProcessorWorker()
    asyncio.run(worker.start())
