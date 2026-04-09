"""Review workflow endpoints: accept, reject, trigger, and cancel expense reviews."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import Expense, User
from core.routers.auth import get_current_user
from core.schemas.expense import Expense as ExpenseSchema
from core.services.review_service import ReviewService
from core.utils.audit import log_audit_event
from core.utils.rbac import require_non_viewer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{expense_id:int}/accept-review", response_model=ExpenseSchema)
async def accept_review(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "review expenses")

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.is_deleted == False).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    review_service = ReviewService(db)
    success = review_service.accept_review(expense)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to accept review or no review available")

    db.commit()
    db.refresh(expense)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_ACCEPT_EXPENSE",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=getattr(expense, "vendor", None),
        details={"expense_id": expense.id, "review_status": expense.review_status}
    )

    return expense


@router.post("/{expense_id:int}/reject-review", response_model=ExpenseSchema)
async def reject_review(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_non_viewer(current_user, "review expenses")

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    review_service = ReviewService(db)
    success = review_service.reject_review(expense)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject review")

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_REJECT_EXPENSE",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=getattr(expense, "vendor", None),
        details={"expense_id": expense.id, "review_status": expense.review_status}
    )

    return expense


@router.post("/{expense_id:int}/review", response_model=ExpenseSchema)
async def run_review(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Trigger a full re-review (reset status to not_started for the worker to pick up)"""
    require_non_viewer(current_user, "review expenses")

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.is_deleted == False).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    from commercial.ai.services.ai_config_service import AIConfigService
    if not AIConfigService.is_review_worker_enabled(db):
        raise HTTPException(
            status_code=400,
            detail="Review worker is currently disabled. Please enable it in Settings > AI Configuration before triggering a review."
        )

    expense.review_status = "pending"
    expense.review_result = None
    expense.reviewed_at = None

    db.commit()
    db.refresh(expense)

    try:
        from core.services.review_event_service import get_review_event_service
        from core.models.database import get_tenant_context

        tenant_id = get_tenant_context()
        if tenant_id:
            event_service = get_review_event_service()
            event_service.publish_single_review_trigger(
                tenant_id=tenant_id,
                entity_type="expense",
                entity_id=expense_id
            )
            logger.info(f"Published Kafka event to trigger review for expense {expense_id}")
    except Exception as e:
        logger.warning(f"Failed to publish Kafka event for expense review trigger: {e}")

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_TRIGGER_EXPENSE",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=getattr(expense, "vendor", None),
        details={"expense_id": expense.id, "review_status": expense.review_status}
    )

    return expense


@router.post("/{expense_id:int}/cancel-review", response_model=ExpenseSchema)
async def cancel_expense_review(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Cancel an in-progress review for an expense"""
    require_non_viewer(current_user, "review expenses")

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.is_deleted == False).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    if expense.review_status not in ["pending", "not_started", "rejected", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel review with status '{expense.review_status}'. Only pending, rejected, failed, or not_started reviews can be cancelled."
        )

    expense.review_status = "not_started"
    expense.review_result = None
    expense.reviewed_at = None

    db.commit()
    db.refresh(expense)

    logger.info(f"Cancelled review for expense {expense_id}")

    return expense
