from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import time
import logging

from core.models.database import get_db
from core.models.models_per_tenant import Settings
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from commercial.integrations.email.service import EmailIngestionService
from commercial.integrations.email.references_router import router as references_router
from core.utils.rbac import require_admin
from core.utils.feature_gate import require_feature

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/email-integration",
    tags=["email-integration"],
    dependencies=[Depends(lambda db=Depends(get_db): require_feature("email_integration")(lambda: None)())]
)
router.include_router(references_router)

class EmailConfig(BaseModel):
    imap_host: str
    imap_port: int = 993
    username: str
    password: str
    enabled: bool = False
    folders: list[str] = ["INBOX"]
    allowed_senders: str = "" # Comma separated
    lookback_days: int = 7  # Default to 7 days for recent emails
    max_emails_to_fetch: int = 100 # Max emails to fetch in one sync
    enable_ai_classification: bool = True  # Enable AI classification
    min_confidence_threshold: float = 0.7  # Minimum confidence for expense classification
    verify_ssl: bool = True  # Verify SSL certificates (disable for testing only)

class EmailConfigResponse(BaseModel):
    imap_host: Optional[str] = None
    imap_port: int = 993
    username: Optional[str] = None
    enabled: bool = False
    folders: list[str] = ["INBOX"]
    allowed_senders: str = ""
    lookback_days: int = 7
    max_emails_to_fetch: int = 100
    enable_ai_classification: bool = True
    min_confidence_threshold: float = 0.7
    verify_ssl: bool = True
    # Do not return password

@router.get("/config", response_model=EmailConfigResponse)
async def get_config(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    setting = db.query(Settings).filter(Settings.key == "email_integration_config").first()
    if not setting:
        return EmailConfigResponse()
    
    config = setting.value
    return EmailConfigResponse(
        imap_host=config.get("imap_host"),
        imap_port=config.get("imap_port", 993),
        username=config.get("username"),
        enabled=config.get("enabled", False),
        folders=config.get("folders", ["INBOX"]),
        allowed_senders=config.get("allowed_senders", ""),
        lookback_days=config.get("lookback_days", 7),
        max_emails_to_fetch=config.get("max_emails_to_fetch", 100),
        enable_ai_classification=config.get("enable_ai_classification", True),
        min_confidence_threshold=config.get("min_confidence_threshold", 0.7),
        verify_ssl=config.get("verify_ssl", True)
    )

import asyncio

@router.post("/config")
async def update_config(
    config: EmailConfig,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    service = EmailIngestionService(db, current_user.id, current_user.tenant_id)
    
    # Validate connection before saving (Blocking I/O)
    config_dict = config.model_dump()
    
    # Get existing config to preserve password if not provided
    setting = db.query(Settings).filter(Settings.key == "email_integration_config").first()
    if setting and not config_dict.get("password"):
        # Preserve existing password if new password is empty
        existing_password = setting.value.get("password")
        if existing_password:
            config_dict["password"] = existing_password
    
    loop = asyncio.get_event_loop()
    is_valid, error = await loop.run_in_executor(None, service.validate_config, config_dict)
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Connection failed: {error}")

    if not setting:
        setting = Settings(
            key="email_integration_config",
            value=config_dict,
            category="integration",
            description="Email integration configuration for expense ingestion"
        )
        db.add(setting)
    else:
        setting.value = config_dict
    
    db.commit()
    
    # Publish config change event to Kafka if enabled
    if config_dict.get("enabled", False):
        try:
            import os
            import json
            from confluent_kafka import Producer
            
            kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
            
            producer = Producer({
                'bootstrap.servers': kafka_servers,
                'client.id': 'email-integration-api'
            })
            
            event = {
                "tenant_id": current_user.tenant_id,
                "enabled": True,
                "timestamp": time.time()
            }
            
            # Produce message
            producer.produce(
                'email_integration_config_changed',
                key=str(current_user.tenant_id).encode('utf-8'),
                value=json.dumps(event).encode('utf-8')
            )
            producer.flush()
            
            logger.info(f"Published email integration config change event for tenant {current_user.tenant_id}")
        except Exception as e:
            # Don't fail the request if Kafka is unavailable
            logger.warning(f"Failed to publish config change event to Kafka: {e}")
    
    return {"status": "success", "message": "Configuration saved"}

@router.post("/test")
async def test_connection(
    config: EmailConfig,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    
    service = EmailIngestionService(db, current_user.id, current_user.tenant_id)
    
    # Get config dict
    config_dict = config.model_dump()
    
    # Preserve existing password if not provided (same as save logic)
    if not config_dict.get("password"):
        setting = db.query(Settings).filter(Settings.key == "email_integration_config").first()
        if setting:
            existing_password = setting.value.get("password")
            if existing_password:
                config_dict["password"] = existing_password
    
    # Blocking I/O
    loop = asyncio.get_event_loop()
    is_valid, error = await loop.run_in_executor(None, service.validate_config, config_dict)
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Connection failed: {error}")
    
    return {"status": "success", "message": "Connection successful"}

@router.get("/sync/status")
async def get_sync_status(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    setting = db.query(Settings).filter(Settings.key == "email_sync_status").first()
    if not setting:
        return {"status": "idle", "message": "No sync in progress"}
    
    return setting.value

@router.post("/sync")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Sync triggered by user {current_user.id} for tenant {current_user.tenant_id}")
    
    require_admin(current_user)
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    # Initialize status
    status_setting = db.query(Settings).filter(Settings.key == "email_sync_status").first()
    initial_status = {
        "status": "starting", 
        "message": "Initializing sync...", 
        "downloaded": 0, 
        "processed": 0,
        "timestamp": datetime.now().isoformat()
    }
    
    if not status_setting:
        status_setting = Settings(
            key="email_sync_status",
            value=initial_status,
            category="system",
            description="Status of email synchronization"
        )
        db.add(status_setting)
    else:
        status_setting.value = initial_status
    
    db.commit()

    logger.info("Creating EmailIngestionService...")
    # We need to create a new session for the background task since the current one will be closed
    from core.services.tenant_database_manager import tenant_db_manager
    
    def run_sync_in_background(user_id, tenant_id):
        # Set tenant context for background thread
        set_tenant_context(tenant_id)
        
        # Get tenant-specific session
        TenantSessionLocal = tenant_db_manager.get_tenant_session(tenant_id)
        if not TenantSessionLocal:
            logger.error(f"Could not get tenant database session for tenant {tenant_id}")
            return
        
        db_bg = TenantSessionLocal()
        try:
            service = EmailIngestionService(db_bg, user_id, tenant_id)
            logger.info("Starting email sync in background...")
            service.sync_emails()
        except Exception as e:
            logger.error(f"Background sync failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Update status to failed
            try:
                s = db_bg.query(Settings).filter(Settings.key == "email_sync_status").first()
                if s:
                    s.value = {
                        "status": "failed", 
                        "message": f"Sync failed: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }
                    db_bg.commit()
            except:
                pass
        finally:
            db_bg.close()

    background_tasks.add_task(run_sync_in_background, current_user.id, current_user.tenant_id)
    
    return {"status": "success", "message": "Sync started in background"}
