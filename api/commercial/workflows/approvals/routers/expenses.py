"""
Expense approval workflow endpoints.

Covers: approvers list, submit, pending, approve, reject, history, unsubmit.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, text
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.schemas.approval import (
    ApprovalMetrics,
    ExpenseApproval,
    ExpenseApprovalCreate,
    ExpenseApprovalDecision,
    ExpenseApprovalHistory,
    PendingApprovalSummary,
)
from core.exceptions.approval_exceptions import (
    ApprovalConcurrencyError,
    ApprovalServiceError,
    ApprovalWorkflowError,
    ExpenseAlreadyApproved,
    ExpenseValidationError,
    InsufficientApprovalPermissions,
    InvalidApprovalState,
    NoApprovalRuleFound,
    ValidationError,
)
from core.utils.audit import log_audit_event
from core.utils.rbac import (
    require_approval_permission,
    require_approval_submission,
    require_non_viewer,
)
from commercial.workflows.approvals.routers._shared import get_approval_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["approvals"])


@router.get("/approvers", response_model=List[dict])
async def get_available_approvers(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get list of available approvers (non-viewer active users) for expense submissions."""
    try:
        require_non_viewer(current_user)

        from core.models.models_per_tenant import User

        approvers = (
            db.query(User)
            .filter(
                and_(
                    User.id != current_user.id,
                    User.role != "viewer",
                    User.is_active == True,
                )
            )
            .order_by(User.first_name, User.last_name)
            .all()
        )

        approver_list = [
            {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "email": user.email,
            }
            for user in approvers
        ]

        logger.info("Retrieved %d available approvers for user %s", len(approver_list), current_user.id)
        return approver_list

    except Exception as e:
        logger.error("Error retrieving available approvers for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/expenses/{expense_id}/submit-approval", response_model=List[ExpenseApproval])
async def submit_expense_for_approval(
    expense_id: int,
    submission_data: ExpenseApprovalCreate,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Submit an expense for approval."""
    try:
        require_approval_submission(current_user, "submit expenses for approval")

        if submission_data.expense_id != expense_id:
            raise HTTPException(
                status_code=400,
                detail="Expense ID in URL does not match expense ID in request body",
            )

        approvals = approval_service.submit_for_approval(
            expense_id=expense_id,
            submitter_id=current_user.id,
            notes=submission_data.notes,
            approver_id=submission_data.approver_id,
        )

        from core.models.models_per_tenant import (
            Expense,
            RecurrencePattern,
            Reminder,
            ReminderNotification,
            ReminderPriority,
            ReminderStatus,
        )

        now = datetime.now(timezone.utc)
        expense = db.query(Expense).filter(Expense.id == expense_id).first()

        for approval in approvals:
            if approval.approver_id:
                db.add(
                    ReminderNotification(
                        reminder_id=None,
                        user_id=approval.approver_id,
                        notification_type="expense_approval",
                        channel="in_app",
                        scheduled_for=now,
                        subject=f"Expense Approval Request #{expense_id}",
                        message=(
                            f"New expense approval request from {current_user.email}: "
                            f"${expense.amount if expense else 'N/A'} - "
                            f"{expense.vendor if expense and expense.vendor else 'Unknown Vendor'}"
                        ),
                        is_sent=True,
                        sent_at=now,
                    )
                )

                priority = ReminderPriority.MEDIUM
                if expense and expense.amount:
                    if expense.amount >= 5000:
                        priority = ReminderPriority.URGENT
                    elif expense.amount >= 1000:
                        priority = ReminderPriority.HIGH

                db.add(
                    Reminder(
                        title=f"Approve Expense: ${expense.amount if expense else 'N/A'} - {expense.vendor if expense and expense.vendor else 'Unknown Vendor'}",
                        description=(
                            f"Expense approval request from {current_user.email}\n\n"
                            f"Amount: ${expense.amount if expense else 'N/A'}\n"
                            f"Category: {expense.category if expense and expense.category else 'N/A'}\n"
                            f"Date: {expense.expense_date if expense and expense.expense_date else 'N/A'}\n\n"
                            f"Notes: {submission_data.notes or 'No notes provided'}"
                        ),
                        due_date=now + timedelta(days=3),
                        priority=priority,
                        status=ReminderStatus.PENDING,
                        recurrence_pattern=RecurrencePattern.NONE,
                        assigned_to_id=approval.approver_id,
                        created_by_id=current_user.id,
                        tags=["approval", "expense", f"expense-{expense_id}"],
                        extra_metadata={
                            "expense_id": expense_id,
                            "approval_id": approval.id,
                            "approval_level": approval.approval_level,
                            "submitter_id": current_user.id,
                            "submitter_email": current_user.email,
                        },
                    )
                )

        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="expense_submitted_for_approval",
            resource_type="expense",
            resource_id=str(expense_id),
            details={"expense_id": expense_id, "approval_count": len(approvals), "notes": submission_data.notes},
        )

        logger.info("User %s submitted expense %s for approval", current_user.id, expense_id)
        return approvals

    except ExpenseValidationError as e:
        logger.warning("Expense validation error submitting expense %s: %s", expense_id, e)
        raise HTTPException(
            status_code=400,
            detail={
                "error": e.to_dict(),
                "missing_fields": e.details.get("missing_fields", []),
                "validation_errors": e.details.get("validation_errors", []),
            },
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except ExpenseAlreadyApproved as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except InvalidApprovalState as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except NoApprovalRuleFound as e:
        raise HTTPException(status_code=422, detail=e.to_dict())
    except ApprovalConcurrencyError as e:
        raise HTTPException(status_code=409, detail=e.to_dict())
    except ApprovalWorkflowError as e:
        error_message = e.details.get("reason", e.user_message) if hasattr(e, "details") else str(e)
        raise HTTPException(status_code=422, detail=error_message)
    except ApprovalServiceError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error("Unexpected error submitting expense %s: %s", expense_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pending")
async def get_pending_approvals(
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0),
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Get pending expense approvals for the current user (paginated, cross-tenant)."""
    try:
        require_non_viewer(current_user)

        pending_approvals = approval_service.get_pending_approvals(
            approver_id=current_user.id,
            limit=limit,
            offset=offset,
        )

        from core.models.models_per_tenant import Expense, ExpenseApproval
        from core.models.models import user_tenant_association, Tenant
        from core.models.database import get_master_db
        from core.schemas.approval import ApprovalStatus
        from core.services.tenant_database_manager import tenant_db_manager
        from sqlalchemy import select

        master_db = next(get_master_db())
        stmt = select(user_tenant_association.c.tenant_id).where(
            and_(
                user_tenant_association.c.user_id == current_user.id,
                user_tenant_association.c.is_active == True,
            )
        )
        tenant_ids = [row[0] for row in master_db.execute(stmt)]
        tenant_names = {t.id: t.name for t in master_db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()}
        master_db.close()

        total = 0
        for tenant_id in tenant_ids:
            try:
                TenantSession = tenant_db_manager.get_tenant_session(tenant_id)
                tenant_db = TenantSession()
                try:
                    total += tenant_db.query(ExpenseApproval).filter(
                        and_(
                            ExpenseApproval.approver_id == current_user.id,
                            ExpenseApproval.status == ApprovalStatus.PENDING,
                            ExpenseApproval.is_current_level == True,
                        )
                    ).count()
                finally:
                    tenant_db.close()
            except Exception as e:
                logger.error("Error counting approvals from tenant %s: %s", tenant_id, e)

        enriched_approvals = []
        for approval in pending_approvals:
            approval_tenant_id = getattr(approval, "tenant_id", None)
            if not approval_tenant_id:
                logger.warning("Approval %s missing tenant_id", approval.id)
                continue
            TenantSession = tenant_db_manager.get_tenant_session(approval_tenant_id)
            tenant_db = TenantSession()
            try:
                expense = tenant_db.query(Expense).filter(Expense.id == approval.expense_id).first()
                enriched_approvals.append({
                    "id": approval.id,
                    "expense_id": approval.expense_id,
                    "approver_id": approval.approver_id,
                    "approval_rule_id": approval.approval_rule_id,
                    "status": approval.status,
                    "rejection_reason": approval.rejection_reason,
                    "notes": approval.notes,
                    "submitted_at": approval.submitted_at.isoformat(),
                    "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
                    "approval_level": approval.approval_level,
                    "is_current_level": approval.is_current_level,
                    "tenant_id": approval_tenant_id,
                    "tenant_name": tenant_names.get(approval_tenant_id, f"Org {approval_tenant_id}"),
                    "expense": {
                        "id": expense.id,
                        "amount": float(expense.amount),
                        "currency": expense.currency,
                        "expense_date": expense.expense_date,
                        "category": expense.category or "General",
                        "vendor": expense.vendor,
                        "status": expense.status,
                        "notes": expense.notes,
                    } if expense else None,
                })
            except Exception as e:
                logger.error("Error enriching approval %s: %s", approval.id, e)
            finally:
                tenant_db.close()

        logger.info(
            "Retrieved %d pending approvals (total: %d) for user %s across %d orgs",
            len(enriched_approvals), total, current_user.id, len(tenant_ids),
        )
        return {"approvals": enriched_approvals, "total": total}

    except Exception as e:
        logger.error("Error retrieving pending approvals for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pending/summary", response_model=PendingApprovalSummary)
async def get_pending_approvals_summary(
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
):
    """Get summary of pending approvals for dashboard display."""
    try:
        require_non_viewer(current_user)
        summary = approval_service.get_pending_approvals_summary(current_user.id)
        logger.info("Retrieved approval summary for user %s: %d pending", current_user.id, summary.total_pending)
        return summary
    except Exception as e:
        logger.error("Error retrieving approval summary for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{approval_id}/approve", response_model=ExpenseApproval)
async def approve_expense(
    approval_id: int,
    decision_data: ExpenseApprovalDecision,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Approve an expense."""
    try:
        require_approval_permission(current_user, "approve expenses")

        if decision_data.status.value != "approved":
            raise HTTPException(
                status_code=400,
                detail="Use the approve endpoint only for approvals. Use reject endpoint for rejections.",
            )

        approval = approval_service.approve_expense(
            approval_id=approval_id,
            approver_id=current_user.id,
            notes=decision_data.notes,
        )

        from sqlalchemy.orm import joinedload
        from core.models.models_per_tenant import ExpenseApproval as ExpenseApprovalModel, Expense, Reminder, ReminderNotification, ReminderStatus

        db.refresh(approval)
        approval = (
            db.query(ExpenseApprovalModel)
            .options(joinedload(ExpenseApprovalModel.approved_by), joinedload(ExpenseApprovalModel.rejected_by))
            .filter(ExpenseApprovalModel.id == approval_id)
            .first()
        )

        try:
            notif = db.query(ReminderNotification).filter(
                ReminderNotification.user_id == current_user.id,
                ReminderNotification.notification_type == "expense_approval",
                ReminderNotification.is_read == False,
                ReminderNotification.subject.contains(f"#{approval.expense_id}"),
            ).first()
            if notif:
                notif.is_read = True
                db.add(notif)
        except Exception as e:
            logger.warning("Failed to mark notification as read for expense %s: %s", approval.expense_id, e)

        now = datetime.now(timezone.utc)
        expense = db.query(Expense).filter(Expense.id == approval.expense_id).first()

        if expense and expense.user_id:
            db.add(ReminderNotification(
                reminder_id=None,
                user_id=expense.user_id,
                notification_type="expense_approved",
                channel="in_app",
                scheduled_for=now,
                subject=f"Expense Approved #{approval.expense_id}",
                message=f"Your expense of ${expense.amount} has been approved by {current_user.email}",
                is_sent=True,
                sent_at=now,
            ))

        reminder = db.query(Reminder).filter(
            Reminder.assigned_to_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata"),
        ).params(metadata=f'{{"approval_id": {approval_id}}}').first()
        if reminder:
            reminder.status = ReminderStatus.COMPLETED
            reminder.completed_at = now
            reminder.completed_by_id = current_user.id
            db.add(reminder)

        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="expense_approved",
            resource_type="expense_approval",
            resource_id=str(approval_id),
            details={
                "expense_id": approval.expense_id,
                "approval_level": approval.approval_level,
                "notes": decision_data.notes,
                "amount": expense.amount if expense else None,
                "currency": expense.currency if expense else None,
                "vendor": expense.vendor if expense else None,
                "category": expense.category if expense else None,
                "date": expense.expense_date.isoformat() if expense and expense.expense_date else None,
            },
        )

        logger.info("User %s approved expense approval %s", current_user.id, approval_id)

        from core.services.attribution_service import AttributionService
        return {
            "id": approval.id,
            "expense_id": approval.expense_id,
            "approver_id": approval.approver_id,
            "approval_rule_id": approval.approval_rule_id,
            "status": approval.status,
            "rejection_reason": approval.rejection_reason,
            "notes": approval.notes,
            "submitted_at": approval.submitted_at,
            "decided_at": approval.decided_at,
            "approval_level": approval.approval_level,
            "is_current_level": approval.is_current_level,
            "created_at": approval.created_at,
            "updated_at": approval.updated_at,
            "approved_by_user_id": approval.approved_by_user_id,
            "approved_by_username": AttributionService.get_display_name(approval.approved_by) if approval.approved_by else None,
            "rejected_by_user_id": approval.rejected_by_user_id,
            "rejected_by_username": AttributionService.get_display_name(approval.rejected_by) if approval.rejected_by else None,
        }

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientApprovalPermissions as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidApprovalState as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error approving %s: %s", approval_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{approval_id}/reject", response_model=ExpenseApproval)
async def reject_expense(
    approval_id: int,
    decision_data: ExpenseApprovalDecision,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Reject an expense."""
    try:
        require_non_viewer(current_user)

        if decision_data.status.value != "rejected":
            raise HTTPException(
                status_code=400,
                detail="Use the reject endpoint only for rejections. Use approve endpoint for approvals.",
            )

        if not decision_data.rejection_reason or not decision_data.rejection_reason.strip():
            raise HTTPException(status_code=400, detail="Rejection reason is required when rejecting an expense")

        approval = approval_service.reject_expense(
            approval_id=approval_id,
            approver_id=current_user.id,
            rejection_reason=decision_data.rejection_reason,
            notes=decision_data.notes,
        )

        from sqlalchemy.orm import joinedload
        from core.models.models_per_tenant import ExpenseApproval as ExpenseApprovalModel, Expense, Reminder, ReminderNotification, ReminderStatus

        db.refresh(approval)
        approval = (
            db.query(ExpenseApprovalModel)
            .options(joinedload(ExpenseApprovalModel.approved_by), joinedload(ExpenseApprovalModel.rejected_by))
            .filter(ExpenseApprovalModel.id == approval_id)
            .first()
        )

        try:
            notif = db.query(ReminderNotification).filter(
                ReminderNotification.user_id == current_user.id,
                ReminderNotification.notification_type == "expense_approval",
                ReminderNotification.is_read == False,
                ReminderNotification.subject.contains(f"#{approval.expense_id}"),
            ).first()
            if notif:
                notif.is_read = True
                db.add(notif)
        except Exception as e:
            logger.warning("Failed to mark notification as read for expense %s: %s", approval.expense_id, e)

        now = datetime.now(timezone.utc)
        expense = db.query(Expense).filter(Expense.id == approval.expense_id).first()

        if expense and expense.user_id:
            db.add(ReminderNotification(
                reminder_id=None,
                user_id=expense.user_id,
                notification_type="expense_rejected",
                channel="in_app",
                scheduled_for=now,
                subject=f"Expense Rejected #{approval.expense_id}",
                message=f"Your expense of ${expense.amount} was rejected by {current_user.email}. Reason: {decision_data.rejection_reason}",
                is_sent=True,
                sent_at=now,
            ))

        reminder = db.query(Reminder).filter(
            Reminder.assigned_to_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata"),
        ).params(metadata=f'{{"approval_id": {approval_id}}}').first()
        if reminder:
            reminder.status = ReminderStatus.CANCELLED
            db.add(reminder)

        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="expense_rejected",
            resource_type="expense_approval",
            resource_id=str(approval_id),
            details={
                "expense_id": approval.expense_id,
                "approval_level": approval.approval_level,
                "rejection_reason": decision_data.rejection_reason,
                "notes": decision_data.notes,
            },
        )

        logger.info("User %s rejected expense approval %s", current_user.id, approval_id)

        from core.services.attribution_service import AttributionService
        return {
            "id": approval.id,
            "expense_id": approval.expense_id,
            "approver_id": approval.approver_id,
            "approval_rule_id": approval.approval_rule_id,
            "status": approval.status,
            "rejection_reason": approval.rejection_reason,
            "notes": approval.notes,
            "submitted_at": approval.submitted_at,
            "decided_at": approval.decided_at,
            "approval_level": approval.approval_level,
            "is_current_level": approval.is_current_level,
            "created_at": approval.created_at,
            "updated_at": approval.updated_at,
            "approved_by_user_id": approval.approved_by_user_id,
            "approved_by_username": AttributionService.get_display_name(approval.approved_by) if approval.approved_by else None,
            "rejected_by_user_id": approval.rejected_by_user_id,
            "rejected_by_username": AttributionService.get_display_name(approval.rejected_by) if approval.rejected_by else None,
        }

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientApprovalPermissions as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidApprovalState as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error rejecting %s: %s", approval_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/{expense_id}", response_model=ExpenseApprovalHistory)
async def get_approval_history(
    expense_id: int,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
):
    """Get complete approval history for an expense."""
    try:
        require_non_viewer(current_user)
        history = approval_service.get_approval_history(expense_id)
        logger.info("Retrieved approval history for expense %s by user %s", expense_id, current_user.id)
        return history
    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving approval history for expense %s: %s", expense_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/expenses/{expense_id}/unsubmit", response_model=dict)
async def unsubmit_expense_approval(
    expense_id: int,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Unsubmit an expense approval request, reverting status and cancelling pending approvals."""
    try:
        require_non_viewer(current_user)

        success = approval_service.unsubmit_expense_approval(
            expense_id=expense_id,
            submitter_id=current_user.id,
        )

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="expense_approval_unsubmitted",
            resource_type="expense",
            resource_id=str(expense_id),
            details={"expense_id": expense_id},
        )

        logger.info("User %s unsubmitted expense %s", current_user.id, expense_id)
        return {"message": "Expense approval request unsubmitted successfully", "success": success}

    except InvalidApprovalState as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error unsubmitting expense %s: %s", expense_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")
