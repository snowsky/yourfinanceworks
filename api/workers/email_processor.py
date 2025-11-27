import asyncio
import logging
import os
import time
import email
import imaplib
from email.header import decode_header
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

# Import models and services
from models.database import get_db, get_master_db, set_tenant_context
from models.models import Tenant, Settings as MasterSettings
from models.models_per_tenant import Settings, RawEmail, Expense, ExpenseAttachment
from services.tenant_database_manager import tenant_db_manager
from services.email_ingestion_service import EmailIngestionService
from constants.expense_status import ExpenseStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmailProcessorWorker:
    def __init__(self):
        self.poll_interval = int(os.getenv("EMAIL_POLL_INTERVAL", "60"))
        self.batch_size = int(os.getenv("EMAIL_BATCH_SIZE", "10"))
        self.running = True

    async def start(self):
        logger.info("Starting Email Processor Worker...")
        
        # Release all advisory locks on startup (cleanup from previous runs)
        self._cleanup_all_locks()
        
        # Start Kafka consumer in background
        import threading
        kafka_thread = threading.Thread(target=self._kafka_consumer_thread, daemon=True)
        kafka_thread.start()
        
        while self.running:
            try:
                any_enabled = await self.process_all_tenants()
                
                if any_enabled:
                    # Normal polling interval when at least one tenant has email integration enabled
                    logger.info(f"Email integration enabled for at least one tenant. Sleeping for {self.poll_interval} seconds...")
                    await asyncio.sleep(self.poll_interval)
                else:
                    # Sleep for 5 minutes when no tenants have email integration enabled
                    # Kafka consumer will wake us up if config changes
                    sleep_time = 300  # 5 minutes
                    logger.info(f"Email integration disabled for all tenants. Sleeping for {sleep_time} seconds (Kafka will wake on config change)...")
                    
                    # Use an event to allow Kafka consumer to wake us up
                    self.wake_event = asyncio.Event()
                    try:
                        await asyncio.wait_for(self.wake_event.wait(), timeout=sleep_time)
                        logger.info("Woken up by Kafka config change event!")
                    except asyncio.TimeoutError:
                        # Normal timeout, continue to next poll
                        pass
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                # Sleep normal interval on error
                await asyncio.sleep(self.poll_interval)
    
    def _kafka_consumer_thread(self):
        """Background thread to consume Kafka events for config changes."""
        try:
            import os
            import json
            from confluent_kafka import Consumer, KafkaError
            
            kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
            
            consumer = Consumer({
                'bootstrap.servers': kafka_servers,
                'group.id': 'email-worker-group',
                'auto.offset.reset': 'latest',
                'enable.auto.commit': True
            })
            
            consumer.subscribe(['email_integration_config_changed'])
            
            logger.info("Kafka consumer started, listening for email integration config changes...")
            
            while True:
                msg = consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                    
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka consumer error: {msg.error()}")
                        continue
                
                try:
                    event = json.loads(msg.value().decode('utf-8'))
                    tenant_id = event.get("tenant_id")
                    enabled = event.get("enabled")
                    
                    logger.info(f"Received config change event: tenant_id={tenant_id}, enabled={enabled}")
                    
                    # Wake up the main loop if it's sleeping
                    if hasattr(self, 'wake_event') and self.wake_event:
                        # Schedule wake_event.set() in the main event loop
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(self._wake_main_loop())
                        
                except Exception as e:
                    logger.error(f"Error processing Kafka message: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Kafka consumer error: {e}", exc_info=True)
            logger.warning("Kafka consumer failed, worker will rely on polling only")
    
    async def _wake_main_loop(self):
        """Wake up the main loop from Kafka consumer thread."""
        if hasattr(self, 'wake_event') and self.wake_event:
            self.wake_event.set()

    async def process_all_tenants(self):
        """Iterate through all active tenants and process their emails.
        Returns True if any tenant has email integration enabled, False otherwise.
        """
        # Get all active tenants from master DB
        # Use get_master_db() to avoid tenant context check
        db = next(get_master_db())
        any_enabled = False
        try:
            tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
            logger.info(f"Found {len(tenants)} active tenants to process.")
            
            for tenant in tenants:
                try:
                    # Try to acquire advisory lock for this tenant
                    # This prevents multiple workers from processing the same tenant
                    lock_acquired = self._try_acquire_tenant_lock(db, tenant.id)
                    
                    if not lock_acquired:
                        logger.debug(f"Tenant {tenant.id} is being processed by another worker, skipping...")
                        continue
                    
                    try:
                        tenant_has_email = await self.process_tenant(tenant.id)
                        if tenant_has_email:
                            any_enabled = True
                    finally:
                        # Always release the lock
                        self._release_tenant_lock(db, tenant.id)
                        
                except Exception as e:
                    logger.error(f"Error processing tenant {tenant.id}: {e}", exc_info=True)
        finally:
            db.close()
        
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

    async def process_tenant(self, tenant_id: int):
        """Process emails for a specific tenant.
        Returns True if email integration is enabled for this tenant, False otherwise.
        """
        logger.info(f"Processing tenant {tenant_id}...")
        
        # Set tenant context
        set_tenant_context(tenant_id)
        
        # Get tenant DB session
        SessionLocal = tenant_db_manager.get_tenant_session(tenant_id)
        if not SessionLocal:
            logger.warning(f"Could not get DB session for tenant {tenant_id}")
            return False

        db = SessionLocal()
        try:
            # Check if email integration is enabled
            # We can use the service to check config and run logic
            # We need a user_id for the service. 
            # We'll try to find an admin user.
            from models.models_per_tenant import User
            admin_user = db.query(User).filter(User.role == "admin").first()
            user_id = admin_user.id if admin_user else 1 # Fallback
            
            service = EmailIngestionService(db, user_id, tenant_id)
            
            # Check if enabled
            if not service.settings or not service.settings.get("enabled", False):
                logger.debug(f"Email integration disabled for tenant {tenant_id}")
                return False

            config = service.settings
            
            # 1. Poll IMAP and save to RawEmail
            # Run in executor to avoid blocking the async loop with blocking I/O
            loop = asyncio.get_event_loop()
            downloaded = await loop.run_in_executor(None, service.poll_and_save, config)
            if downloaded > 0:
                logger.info(f"Tenant {tenant_id}: Downloaded {downloaded} new emails.")
            
            # 2. Process pending RawEmails
            # Process in batches
            processed = await loop.run_in_executor(None, service.process_pending_emails, self.batch_size)
            if processed > 0:
                logger.info(f"Tenant {tenant_id}: Processed {processed} emails.")
            
            return True  # Email integration is enabled for this tenant
            
        except Exception as e:
            logger.error(f"Error processing tenant {tenant_id}: {e}", exc_info=True)
            return False  # Treat errors as disabled to avoid spam
        finally:
            db.close()

if __name__ == "__main__":
    worker = EmailProcessorWorker()
    asyncio.run(worker.start())
