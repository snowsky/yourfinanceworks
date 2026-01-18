
import asyncio
import logging
import os
import signal
import time
from datetime import datetime, timezone
import json

from sqlalchemy import text

from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select, func

from core.models.database import get_db, get_master_db, set_tenant_context, clear_tenant_context
from core.models.models import Tenant
from core.models.models_per_tenant import (
    Invoice, Expense, BankStatement, Settings
)
from core.services.ai_config_service import AIConfigService
from core.services.review_service import ReviewService
from core.services.invoice_ai_service import InvoiceAIService
from core.services.statement_service import StatementService
from core.services.ocr_service import _run_ocr
from core.services.tenant_database_manager import tenant_db_manager
from core.services.prompt_service import get_prompt_service

logger = logging.getLogger(__name__)

class ReviewProcessorWorker:
    def __init__(self):
        self.poll_interval = int(os.getenv("REVIEW_POLL_INTERVAL", "60"))
        self.running = True
        self.review_topic = os.getenv("KAFKA_REVIEW_TOPIC", "review_trigger")
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self._kafka_consumer = None
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_exit)

    def _handle_exit(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down Review Processor...")
        self.running = False

    async def start(self):
        logger.info("Starting Review Processor Worker...")
        
        # Release all advisory locks on startup (cleanup from previous runs)
        self._cleanup_all_locks()
        
        # Ensure Kafka topic exists before starting listener
        self._ensure_kafka_topic()
        
        # Initialize Kafka consumer
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
        """Ensure the review trigger topic exists, creating it if necessary."""
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

            # Create topic
            logger.info(f"Creating Kafka topic '{topic_name}'...")
            new_topic = NewTopic(topic_name, num_partitions=1, replication_factor=1)
            fs = admin_client.create_topics([new_topic])

            # Wait for creation
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
            trigger_type = event.get("trigger_type")
            
            if not tenant_id:
                logger.warning(f"Received review event without tenant_id: {event}")
                return
            
            logger.info(f"Processing review event: {trigger_type} for tenant {tenant_id}")
            
            # Get tenant from master DB
            master_db = next(get_master_db())
            try:
                tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active == True).first()
                if not tenant:
                    logger.warning(f"Tenant {tenant_id} not found or inactive")
                    return
                
                # Process the tenant immediately
                await self.process_tenant(tenant)
                logger.info(f"Completed event-driven review processing for tenant {tenant_id}")
                
            finally:
                master_db.close()
                
        except Exception as e:
            logger.error(f"Error processing review event: {e}", exc_info=True)

    async def process_all_tenants(self):
        master_db = next(get_master_db())
        try:
            tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
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
                    await self.process_tenant(tenant)
                finally:
                    # Always release the lock
                    self._release_tenant_lock(master_db, tenant.id)
        finally:
            master_db.close()

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
            return

        try:
            # Check if review worker is enabled
            setting = session.query(Settings).filter(Settings.key == "review_worker_enabled").first()
            if not setting or not setting.value:
                # disabled
                return

            review_service = ReviewService(session)
            reviewer_config = AIConfigService.get_ai_config(session, component="reviewer", require_ocr=True)
            
            if not reviewer_config:
                logger.warning(f"Review worker enabled but no reviewer config found for tenant {tenant.id}")
                return

            # Process Invoices
            await self.process_invoices(session, tenant, review_service, reviewer_config)
            
            # Process Expenses
            await self.process_expenses(session, tenant, review_service, reviewer_config)

            # Process Bank Statements
            await self.process_bank_statements(session, tenant, review_service, reviewer_config)

        except Exception as e:
            logger.error(f"Error processing tenant {tenant.id}: {e}", exc_info=True)
        finally:
            session.close()
            clear_tenant_context()

    async def process_invoices(self, db: Session, tenant: Tenant, review_service: ReviewService, config: dict):
        # Fetch invoices needing review
        # Condition: status not draft, review_status='not_started'
        invoices = db.query(Invoice).filter(
            Invoice.review_status == "not_started",
            Invoice.status != "draft", 
            Invoice.attachment_path.isnot(None)
        ).limit(10).all()

        if not invoices:
            return

        logger.info(f"Found {len(invoices)} invoices to review for tenant {tenant.id}")
        
        # Instantiate service with reviewer component
        invoice_service = InvoiceAIService(db, component="reviewer")
        
        for invoice in invoices:
            if not self.running: break
            
            logger.info(f"Reviewing Invoice {invoice.id}...")
            invoice.review_status = "pending"
            db.commit()

            try:
                # Re-extract data using reviewer config and specific prompt
                prompt_service = get_prompt_service(db)
                reviewer_prompt = prompt_service.get_prompt(
                    name="invoice_review_extraction",
                    variables={"text": "{{text}}"},
                    provider_name=config.get("provider_name"),
                    fallback_prompt="Extract invoice data with absolute precision for a forensic review."
                )
                
                extract_result = await invoice_service.extract_invoice_data(
                    invoice.attachment_path, 
                    custom_prompt=reviewer_prompt
                )
                
                if extract_result.get("success"):
                     review_data = extract_result.get("data", {})
                     review_service.compare_and_store_review(invoice, review_data)
                else:
                    logger.error(f"Review extraction failed for Invoice {invoice.id}: {extract_result.get('error')}")
                    invoice.review_status = "failed"
                    db.commit()

            except Exception as e:
                logger.error(f"Exception reviewing Invoice {invoice.id}: {e}")
                invoice.review_status = "failed"
                db.commit()

    async def process_expenses(self, db: Session, tenant: Tenant, review_service: ReviewService, config: dict):
        # Fetch expenses needing review
        # Condition: analysis_status='done', review_status='not_started'
        expenses = db.query(Expense).filter(
            Expense.review_status == "not_started",
            Expense.analysis_status == "done",
            Expense.receipt_path.isnot(None)
        ).limit(10).all()

        if not expenses:
            return

        logger.info(f"Found {len(expenses)} expenses to review for tenant {tenant.id}")

        for expense in expenses:
             if not self.running: break

             logger.info(f"Reviewing Expense {expense.id}...")
             expense.review_status = "pending"
             db.commit()

             try:
                 # Manually run OCR using helper, passing reviewer config explicitly
                 # Note: _run_ocr returns just the data dict or error dict
                 # We need to construct a prompt. Usually OCR service does this internally.
                 # Let's use _run_ocr directly but we need a prompt.
                 # Actually, `ocr_service.py` is lower level. `ExpenseAIService` doesn't exist?
                 # `apply_ocr_extraction_to_expense` logic...
                 
                 # Use dedicated reviewer prompt for expenses
                 prompt_service = get_prompt_service(db)
                 reviewer_prompt = prompt_service.get_prompt(
                     name="expense_review_extraction",
                     variables={"raw_content": "{{raw_content}}"},
                     provider_name=config.get("provider_name"),
                     fallback_prompt="Extract expense data with meticulous attention to subtotals and taxes."
                 )
                 
                 result = await _run_ocr(
                     file_path=expense.receipt_path,
                     ai_config=config,
                     custom_prompt=reviewer_prompt
                 )

                 if isinstance(result, dict) and "error" not in result:
                      review_service.compare_and_store_review(expense, result)
                 else:
                      logger.error(f"Review extraction failed for Expense {expense.id}")
                      expense.review_status = "failed"
                      db.commit()

             except Exception as e:
                 logger.error(f"Exception reviewing Expense {expense.id}: {e}")
                 expense.review_status = "failed"
                 db.commit()

    async def process_bank_statements(self, db: Session, tenant: Tenant, review_service: ReviewService, config: dict):
        # Fetch statements needing review
        stmts = db.query(BankStatement).filter(
            BankStatement.review_status == "not_started",
            BankStatement.status == "processed",
            BankStatement.file_path.isnot(None)
        ).limit(5).all()

        if not stmts:
            return
            
        logger.info(f"Found {len(stmts)} statements to review for tenant {tenant.id}")
        
        # Instantiate service with reviewer prompt name
        # Note: StatementService is an alias for UniversalBankTransactionExtractor
        statement_service = StatementService(
            ai_config=config, 
            db_session=db, 
            prompt_name="bank_statement_review_extraction"
        )
        
        for stmt in stmts:
             if not self.running: break
             
             logger.info(f"Reviewing Bank Statement {stmt.id}...")
             stmt.review_status = "pending"
             db.commit()
             
             try:
                  # Process PDF to get transactions
                  # 1. Load docs
                  docs = statement_service.load_pdf_with_langchain(stmt.file_path)
                  # 2. Preprocess (chunking etc)
                  p_docs = statement_service.preprocess_documents(docs)
                  # 3. Extract
                  transactions = statement_service.extract_transactions_from_documents(p_docs)
                  
                  # Store results
                  review_data = {"transactions": transactions}
                  review_service.compare_and_store_review(stmt, review_data)
                  
             except Exception as e:
                  logger.error(f"Exception reviewing Statement {stmt.id}: {e}")
                  stmt.review_status = "failed"
                  db.commit()

if __name__ == "__main__":
    worker = ReviewProcessorWorker()
    asyncio.run(worker.start())
