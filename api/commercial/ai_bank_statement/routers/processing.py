"""Reprocessing and review endpoints for bank statements."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.rbac import require_non_viewer
from core.utils.feature_gate import require_feature
from core.models.models_per_tenant import BankStatement
from core.schemas.bank_statement import BankStatementResponse
from core.utils.audit import log_audit_event
from core.utils.timezone import get_tenant_timezone_aware_datetime
from core.services.review_service import ReviewService
from commercial.ai.services.ocr_service import publish_bank_statement_task
from ._shared import get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{statement_id}/reprocess", response_model=Dict[str, Any])
@require_feature("ai_bank_statement")
async def reprocess_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Reprocess a bank statement's analysis with proper status reset and duplicate prevention."""
    require_non_viewer(current_user, "reprocess statement")

    tenant_id = get_tenant_id()

    # Import ProcessingLock model
    from core.models.processing_lock import ProcessingLock

    # Check if statement is already being processed
    if ProcessingLock.is_locked(db, "bank_statement", statement_id):
        # Check if the lock is stale (statement is already in a terminal state)
        s_check = (
            db.query(BankStatement)
            .filter(
                BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id
            )
            .first()
        )

        if s_check and s_check.status in ["processed", "failed", "done"]:
            logger.info(
                f"Statement {statement_id} is in terminal state '{s_check.status}' but locked. Releasing stale lock."
            )
            ProcessingLock.release_lock(db, "bank_statement", statement_id)
        else:
            lock_info = ProcessingLock.get_active_lock_info(
                db, "bank_statement", statement_id
            )
            return {
                "success": True,
                "message": "Statement is already being processed",
                "status": "already_processing",
                "lock_info": lock_info,
            }

    s = (
        db.query(BankStatement)
        .filter(
            BankStatement.id == statement_id,
            BankStatement.tenant_id == tenant_id,
            BankStatement.is_deleted == False,
        )
        .first()
    )

    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    if s.status == "merged":
        raise HTTPException(
            status_code=400, detail="Merged statements cannot be reprocessed"
        )

    # Acquire processing lock
    request_id = (
        f"reprocess_statement_{statement_id}_{datetime.now(timezone.utc).timestamp()}"
    )
    if not ProcessingLock.acquire_lock(
        db,
        "bank_statement",
        statement_id,
        current_user.id,
        lock_duration_minutes=30,
        metadata={"request_id": request_id},
    ):
        lock_info = ProcessingLock.get_active_lock_info(
            db, "bank_statement", statement_id
        )
        return {
            "success": True,
            "message": "Statement is already being processed by another request",
            "status": "already_processing",
            "lock_info": lock_info,
        }

    try:
        # Update status to processing and clear error (KEY FIX)
        s.status = "processing"
        s.analysis_error = None  # This was missing in removed endpoint
        s.analysis_updated_at = get_tenant_timezone_aware_datetime(db)
        db.commit()

        # Enqueue processing task (sync call)
        try:
            publish_bank_statement_task(
                {
                    "statement_id": s.id,
                    "file_path": s.file_path,
                    "tenant_id": tenant_id,
                    "attempt": 0,
                }
            )
        except Exception as enqueue_err:
            s.status = "failed"
            s.analysis_error = "Failed to queue for processing"
            db.commit()
            ProcessingLock.release_lock(db, "bank_statement", statement_id)
            logger.error(f"Failed to enqueue reprocess task for statement {statement_id}: {enqueue_err}")
            raise HTTPException(status_code=500, detail="Failed to queue statement for reprocessing")

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="statement_reprocess",
            resource_type="bank_statement",
            resource_id=str(s.id),
            resource_name=s.original_filename,
            details={"statement_id": s.id},
        )

        logger.info(
            f"Reprocess started for bank statement {statement_id} (request_id={request_id})"
        )
        return {
            "success": True,
            "message": "Reprocessing started",
            "request_id": request_id,
        }

    except Exception as e:
        # Release lock on failure
        try:
            ProcessingLock.release_lock(db, "bank_statement", statement_id)
        except Exception as lock_err:
            logger.error(f"Lock release failed after error: {lock_err}")
        logger.error(f"Failed to reprocess bank statement {statement_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reprocess statement")


@router.post("/{statement_id}/accept-review", response_model=BankStatementResponse)
async def accept_review(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "review bank statements")

    # Set tenant context
    from core.models.database import get_tenant_context, set_tenant_context
    tenant_id = get_tenant_context()
    if not tenant_id:
        # Try to get from user
        tenant_id = current_user.tenant_id
        set_tenant_context(tenant_id)

    statement = db.query(BankStatement).filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == False).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")

    review_service = ReviewService(db)
    success = review_service.accept_review(statement)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to accept review or no review available")

    db.commit()
    db.refresh(statement)

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_ACCEPT_STATEMENT",
        resource_type="bank_statement",
        resource_id=str(statement.id),
        resource_name=statement.original_filename,
        details={"statement_id": statement.id, "review_status": statement.review_status}
    )

    return statement


@router.post("/{statement_id}/reject-review", response_model=BankStatementResponse)
async def reject_review(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    require_non_viewer(current_user, "review bank statements")

    statement = db.query(BankStatement).filter(BankStatement.id == statement_id).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")

    review_service = ReviewService(db)
    success = review_service.reject_review(statement)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject review")

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_REJECT_STATEMENT",
        resource_type="bank_statement",
        resource_id=str(statement.id),
        resource_name=statement.original_filename,
        details={"statement_id": statement.id, "review_status": statement.review_status}
    )

    return statement


@router.post("/{statement_id}/review", response_model=BankStatementResponse)
async def run_review(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Trigger a full re-review (reset status to not_started for the worker to pick up)"""
    require_non_viewer(current_user, "review bank statements")

    # Set tenant context
    from core.models.database import get_tenant_context, set_tenant_context
    tenant_id = get_tenant_context()
    if not tenant_id:
        tenant_id = current_user.tenant_id
        set_tenant_context(tenant_id)

    statement = db.query(BankStatement).filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == False).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")

    # Check if review worker is enabled
    from commercial.ai.services.ai_config_service import AIConfigService
    if not AIConfigService.is_review_worker_enabled(db):
        raise HTTPException(
            status_code=400,
            detail="Review worker is currently disabled. Please enable it in Settings > AI Configuration before triggering a review."
        )

    # Reset review status to pending so it shows immediately in UI
    # The worker will pick it up and process it
    statement.review_status = "pending"
    statement.review_result = None
    statement.reviewed_at = None

    db.commit()
    db.refresh(statement)

    # Publish Kafka event for immediate processing
    try:
        from core.services.review_event_service import get_review_event_service
        event_service = get_review_event_service()
        event_service.publish_single_review_trigger(tenant_id, "statement", statement_id)
    except Exception as e:
        logger.warning(f"Failed to publish review trigger event for statement {statement_id}: {e}")

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_TRIGGER_STATEMENT",
        resource_type="bank_statement",
        resource_id=str(statement.id),
        resource_name=statement.original_filename,
        details={"statement_id": statement.id, "review_status": statement.review_status}
    )

    return statement
