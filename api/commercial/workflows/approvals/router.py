"""
Approval Router

This router provides REST API endpoints for the expense approval workflow.
It handles expense submission for approval, approval decisions, and approval history.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, text
from typing import List, Optional
from datetime import datetime, timezone
import logging

from core.models.database import get_db, get_tenant_context
from core.routers.auth import get_current_user, get_email_service_for_tenant
from core.models.models import MasterUser
from core.schemas.approval import (
    ExpenseApprovalCreate, ExpenseApprovalDecision, ExpenseApproval,
    PendingApprovalSummary, ExpenseApprovalHistory, ApprovalMetrics,
    ApprovalDelegateCreate, ApprovalDelegateUpdate, ApprovalDelegate,
    ApprovalStatus
)
from commercial.workflows.approvals.services.approval_service import ApprovalService
from core.exceptions.approval_exceptions import (
    ApprovalException, ValidationError, ExpenseValidationError,
    InsufficientApprovalPermissions, ExpenseAlreadyApproved, 
    InvalidApprovalState, ApprovalServiceError, NoApprovalRuleFound,
    ApprovalNotFoundException, ExpenseNotFoundException,
    ApprovalWorkflowError, ApprovalConcurrencyError
)
from core.services.notification_service import NotificationService
from commercial.workflows.approvals.services.approval_permission_service import ApprovalPermissionService
from core.utils.rbac import (
    require_non_viewer, require_admin, require_approval_submission,
    require_approval_permission
)
from core.utils.feature_gate import require_feature
from core.utils.audit import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/approvals",
    tags=["approvals"]
)


def get_approval_service(db: Session = Depends(get_db)) -> ApprovalService:
    """Get approval service instance with notification service."""
    # Create notification service without email service for now
    # Email service will be resolved later if needed
    notification_service = NotificationService(db, None)
    return ApprovalService(db, notification_service)


def get_approval_permission_service(db: Session = Depends(get_db)) -> ApprovalPermissionService:
    """Get approval permission service instance."""
    return ApprovalPermissionService(db)


@router.get("/approvers", response_model=List[dict])
async def get_available_approvers(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of available approvers for expense submissions.

    This endpoint returns users who can serve as approvers, excluding the current user.
    Useful for allowing users to select specific approvers when submitting expenses.

    Args:
        current_user: Currently authenticated user
        db: Database session

    Returns:
        List of approver dictionaries with id, name, and email
    """
    try:
        require_non_viewer(current_user)

        # Import here to avoid circular imports
        from core.models.models_per_tenant import User

        # Get all users except the current user who are not viewers
        approvers = db.query(User).filter(
            and_(
                User.id != current_user.id,
                User.role != "viewer"  # Exclude viewers from approver list
            )
        ).order_by(User.first_name, User.last_name).all()

        # Format as simple dictionaries for the frontend
        approver_list = [
            {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "email": user.email
            }
            for user in approvers
        ]

        logger.info(f"Retrieved {len(approver_list)} available approvers for user {current_user.id}")

        return approver_list

    except Exception as e:
        logger.error(f"Error retrieving available approvers for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/expenses/{expense_id}/submit-approval", response_model=List[ExpenseApproval])
async def submit_expense_for_approval(
    expense_id: int,
    submission_data: ExpenseApprovalCreate,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Submit an expense for approval.
    
    This endpoint allows users to submit their expenses for approval according to
    configured approval rules. The system will automatically assign appropriate
    approvers based on expense amount, category, and organizational rules.
    
    Args:
        expense_id: ID of the expense to submit for approval
        submission_data: Submission details including optional notes
        current_user: Currently authenticated user
        approval_service: Approval service instance
        db: Database session
        
    Returns:
        List of created ExpenseApproval records
        
    Raises:
        HTTPException: 400 if expense is invalid or already in approval workflow
        HTTPException: 403 if user lacks permission to submit this expense
        HTTPException: 404 if expense not found
        HTTPException: 422 if no approval rules match the expense
    """
    try:
        # Verify user has permission to submit expenses for approval
        require_approval_submission(current_user, "submit expenses for approval")
        
        # Validate expense_id matches the one in submission_data
        if submission_data.expense_id != expense_id:
            raise HTTPException(
                status_code=400,
                detail="Expense ID in URL does not match expense ID in request body"
            )
        
        # Submit expense for approval
        approvals = approval_service.submit_for_approval(
            expense_id=expense_id,
            submitter_id=current_user.id,
            notes=submission_data.notes,
            approver_id=submission_data.approver_id
        )
        
        # Create notification and reminder for approvers
        from core.models.models_per_tenant import ReminderNotification, Expense, Reminder, ReminderStatus, ReminderPriority, RecurrencePattern
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        
        for approval in approvals:
            if approval.approver_id:
                # Create in-app notification with expense_id in subject for navigation
                notification = ReminderNotification(
                    reminder_id=None,
                    user_id=approval.approver_id,
                    notification_type="expense_approval",
                    channel="in_app",
                    scheduled_for=now,
                    subject=f"Expense Approval Request #{expense_id}",  # Include expense_id for navigation
                    message=f"New expense approval request from {current_user.email}: ${expense.amount if expense else 'N/A'} - {expense.vendor if expense and expense.vendor else 'Unknown Vendor'}",
                    is_sent=True,
                    sent_at=now
                )
                db.add(notification)

                # Create a reminder task for the approver
                # Determine priority based on expense amount
                priority = ReminderPriority.MEDIUM
                if expense and expense.amount:
                    if expense.amount >= 1000:
                        priority = ReminderPriority.HIGH
                    elif expense.amount >= 5000:
                        priority = ReminderPriority.URGENT

                # Set due date to 3 business days from now
                due_date = now + timedelta(days=3)

                reminder = Reminder(
                    title=f"Approve Expense: ${expense.amount if expense else 'N/A'} - {expense.vendor if expense and expense.vendor else 'Unknown Vendor'}",
                    description=f"Expense approval request from {current_user.email}\n\nAmount: ${expense.amount if expense else 'N/A'}\nCategory: {expense.category if expense and expense.category else 'N/A'}\nDate: {expense.expense_date if expense and expense.expense_date else 'N/A'}\n\nNotes: {submission_data.notes if submission_data.notes else 'No notes provided'}",
                    due_date=due_date,
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
                        "submitter_email": current_user.email
                    }
                )
                db.add(reminder)

        db.commit()

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="expense_submitted_for_approval",
            resource_type="expense",
            resource_id=str(expense_id),
            details={
                "expense_id": expense_id,
                "approval_count": len(approvals),
                "notes": submission_data.notes
            }
        )

        logger.info(f"User {current_user.id} submitted expense {expense_id} for approval")

        return approvals

    except ExpenseValidationError as e:
        logger.warning(f"Expense validation error submitting expense {expense_id}: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail={
                "error": e.to_dict(),
                "missing_fields": e.details.get("missing_fields", []),
                "validation_errors": e.details.get("validation_errors", [])
            }
        )
    except ValidationError as e:
        logger.warning(f"Validation error submitting expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except ExpenseAlreadyApproved as e:
        logger.warning(f"Expense {expense_id} already approved: {str(e)}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except InvalidApprovalState as e:
        logger.warning(f"Invalid approval state for expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except NoApprovalRuleFound as e:
        logger.warning(f"No approval rule found for expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=422, detail=e.to_dict())
    except ApprovalConcurrencyError as e:
        logger.warning(f"Concurrency error for expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=409, detail=e.to_dict())
    except ApprovalWorkflowError as e:
        logger.error(f"Workflow error for expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=422, detail=e.to_dict())
    except ApprovalServiceError as e:
        logger.error(f"Approval service error for expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error submitting expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pending")
async def get_pending_approvals(
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Number of results to skip"),
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Get pending approvals for the current user.

    This endpoint returns all expenses that are currently pending approval
    by the authenticated user. Results can be paginated using limit and offset.

    Args:
        limit: Maximum number of results to return (default: no limit)
        offset: Number of results to skip for pagination (default: 0)
        current_user: Currently authenticated user
        approval_service: Approval service instance

    Returns:
        Object containing approvals list and total count
    """
    try:
        require_non_viewer(current_user)

        pending_approvals = approval_service.get_pending_approvals(
            approver_id=current_user.id,
            limit=limit,
            offset=offset
        )

        # Get total count for pagination
        from core.models.models_per_tenant import ExpenseApproval, Expense
        from core.schemas.approval import ApprovalStatus
        total = db.query(ExpenseApproval).filter(
            and_(
                ExpenseApproval.approver_id == current_user.id,
                ExpenseApproval.status == ApprovalStatus.PENDING,
                ExpenseApproval.is_current_level == True
            )
        ).count()

        # Enrich approvals with expense data
        enriched_approvals = []
        for approval in pending_approvals:
            expense = db.query(Expense).filter(Expense.id == approval.expense_id).first()
            approval_dict = {
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
                "expense": {
                    "id": expense.id,
                    "amount": float(expense.amount),
                    "currency": expense.currency,
                    "expense_date": expense.expense_date,
                    "category": expense.category or "General",
                    "vendor": expense.vendor,
                    "status": expense.status,
                    "notes": expense.notes
                } if expense else None
            }
            enriched_approvals.append(approval_dict)

        logger.info(f"Retrieved {len(pending_approvals)} pending approvals (total: {total}) for user {current_user.id}")

        return {
            "approvals": enriched_approvals,
            "total": total
        }

    except Exception as e:
        logger.error(f"Error retrieving pending approvals for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pending/summary", response_model=PendingApprovalSummary)
async def get_pending_approvals_summary(
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service)
):
    """
    Get summary of pending approvals for dashboard display.

    This endpoint provides aggregated information about pending approvals
    including total count, total amount, and breakdown by category.

    Args:
        current_user: Currently authenticated user
        approval_service: Approval service instance

    Returns:
        PendingApprovalSummary with aggregated approval information
    """
    try:
        require_non_viewer(current_user)

        summary = approval_service.get_pending_approvals_summary(current_user.id)

        logger.info(f"Retrieved approval summary for user {current_user.id}: {summary.total_pending} pending")

        return summary
        
    except Exception as e:
        logger.error(f"Error retrieving approval summary for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{approval_id}/approve", response_model=ExpenseApproval)
async def approve_expense(
    approval_id: int,
    decision_data: ExpenseApprovalDecision,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Approve an expense.

    This endpoint allows authorized approvers to approve expenses assigned to them.
    The approval will advance the expense through the approval workflow according
    to configured rules.

    Args:
        approval_id: ID of the approval record to approve
        decision_data: Approval decision details including optional notes
        current_user: Currently authenticated user
        approval_service: Approval service instance
        db: Database session

    Returns:
        Updated ExpenseApproval record

    Raises:
        HTTPException: 400 if approval is not in pending state
        HTTPException: 403 if user lacks permission to approve this expense
        HTTPException: 404 if approval not found
    """
    try:
        # Verify user has approval permissions
        require_approval_permission(current_user, "approve expenses")

        # Validate decision status
        if decision_data.status.value != "approved":
            raise HTTPException(
                status_code=400,
                detail="Use the approve endpoint only for approvals. Use reject endpoint for rejections."
            )

        # Approve the expense
        approval = approval_service.approve_expense(
            approval_id=approval_id,
            approver_id=current_user.id,
            notes=decision_data.notes
        )

        # Refresh approval to load relationships
        from sqlalchemy.orm import joinedload
        from core.models.models_per_tenant import ExpenseApproval as ExpenseApprovalModel
        db.refresh(approval)
        approval = db.query(ExpenseApprovalModel).options(
            joinedload(ExpenseApprovalModel.approved_by),
            joinedload(ExpenseApprovalModel.rejected_by)
        ).filter(ExpenseApprovalModel.id == approval_id).first()

        # Create notification for expense submitter and complete the reminder
        from core.models.models_per_tenant import ReminderNotification, Expense, Reminder, ReminderStatus

        # Mark the original approval notification as read
        try:
            # Find the notification for this user about this expense
            # Since reminder_id is None, we match by type and subject content
            approval_notification = db.query(ReminderNotification).filter(
                ReminderNotification.user_id == current_user.id,
                ReminderNotification.notification_type == "expense_approval",
                ReminderNotification.is_read == False,
                ReminderNotification.subject.contains(f"#{approval.expense_id}")
            ).first()

            if approval_notification:
                approval_notification.is_read = True
                db.add(approval_notification)
        except Exception as e:
            logger.warning(f"Failed to key notification as read for expense {approval.expense_id}: {e}")

        now = datetime.now(timezone.utc)
        expense = db.query(Expense).filter(Expense.id == approval.expense_id).first()

        if expense and expense.user_id:
            notification = ReminderNotification(
                reminder_id=None,
                user_id=expense.user_id,
                notification_type="expense_approved",
                channel="in_app",
                scheduled_for=now,
                subject=f"Expense Approved #{approval.expense_id}",  # Include expense_id for navigation
                message=f"Your expense of ${expense.amount} has been approved by {current_user.email}",
                is_sent=True,
                sent_at=now
            )
            db.add(notification)

        # Complete the reminder task for this approval
        reminder = db.query(Reminder).filter(
            Reminder.assigned_to_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata")
        ).params(metadata=f'{{"approval_id": {approval_id}}}').first()

        if reminder:
            reminder.status = ReminderStatus.COMPLETED
            reminder.completed_at = now
            reminder.completed_by_id = current_user.id
            db.add(reminder)

        db.commit()

        # Log audit event
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
                "date": expense.expense_date.isoformat() if expense and expense.expense_date else None
            }
        )

        logger.info(f"User {current_user.id} approved expense approval {approval_id}")

        # Enrich response with approver/rejector information
        from core.services.attribution_service import AttributionService
        response_dict = {
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

        return response_dict

    except ValidationError as e:
        logger.warning(f"Validation error approving {approval_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientApprovalPermissions as e:
        logger.warning(f"Permission denied approving {approval_id} by user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidApprovalState as e:
        logger.warning(f"Invalid state approving {approval_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalServiceError as e:
        logger.error(f"Approval service error approving {approval_id}: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error approving {approval_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{approval_id}/reject", response_model=ExpenseApproval)
async def reject_expense(
    approval_id: int,
    decision_data: ExpenseApprovalDecision,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Reject an expense.

    This endpoint allows authorized approvers to reject expenses assigned to them.
    A rejection reason is required and will be communicated to the expense submitter.

    Args:
        approval_id: ID of the approval record to reject
        decision_data: Rejection decision details including required rejection reason
        current_user: Currently authenticated user
        approval_service: Approval service instance
        db: Database session

    Returns:
        Updated ExpenseApproval record

    Raises:
        HTTPException: 400 if approval is not in pending state or rejection reason missing
        HTTPException: 403 if user lacks permission to approve this expense
        HTTPException: 404 if approval not found
    """
    try:
        require_non_viewer(current_user)
        
        # Validate decision status
        if decision_data.status.value != "rejected":
            raise HTTPException(
                status_code=400,
                detail="Use the reject endpoint only for rejections. Use approve endpoint for approvals."
            )
        
        # Validate rejection reason is provided
        if not decision_data.rejection_reason or not decision_data.rejection_reason.strip():
            raise HTTPException(
                status_code=400,
                detail="Rejection reason is required when rejecting an expense"
            )

        # Reject the expense
        approval = approval_service.reject_expense(
            approval_id=approval_id,
            approver_id=current_user.id,
            rejection_reason=decision_data.rejection_reason,
            notes=decision_data.notes
        )

        # Refresh approval to load relationships
        from sqlalchemy.orm import joinedload
        from core.models.models_per_tenant import ExpenseApproval as ExpenseApprovalModel
        db.refresh(approval)
        approval = db.query(ExpenseApprovalModel).options(
            joinedload(ExpenseApprovalModel.approved_by),
            joinedload(ExpenseApprovalModel.rejected_by)
        ).filter(ExpenseApprovalModel.id == approval_id).first()

        # Create notification for expense submitter and cancel the reminder
        from core.models.models_per_tenant import ReminderNotification, Expense, Reminder, ReminderStatus

        # Mark the original approval notification as read
        try:
            # Find the notification for this user about this expense
            approval_notification = db.query(ReminderNotification).filter(
                ReminderNotification.user_id == current_user.id,
                ReminderNotification.notification_type == "expense_approval",
                ReminderNotification.is_read == False,
                ReminderNotification.subject.contains(f"#{approval.expense_id}")
            ).first()

            if approval_notification:
                approval_notification.is_read = True
                db.add(approval_notification)
        except Exception as e:
            logger.warning(f"Failed to mark notification as read for expense {approval.expense_id}: {e}")

        now = datetime.now(timezone.utc)
        expense = db.query(Expense).filter(Expense.id == approval.expense_id).first()

        if expense and expense.user_id:
            notification = ReminderNotification(
                reminder_id=None,
                user_id=expense.user_id,
                notification_type="expense_rejected",
                channel="in_app",
                scheduled_for=now,
                subject=f"Expense Rejected #{approval.expense_id}",  # Include expense_id for navigation
                message=f"Your expense of ${expense.amount} was rejected by {current_user.email}. Reason: {decision_data.rejection_reason}",
                is_sent=True,
                sent_at=now
            )
            db.add(notification)

        # Cancel the reminder task for this approval (since it's rejected)
        reminder = db.query(Reminder).filter(
            Reminder.assigned_to_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata")
        ).params(metadata=f'{{"approval_id": {approval_id}}}').first()

        if reminder:
            reminder.status = ReminderStatus.CANCELLED
            db.add(reminder)

        db.commit()

        # Log audit event
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
                "notes": decision_data.notes
            }
        )

        logger.info(f"User {current_user.id} rejected expense approval {approval_id}")

        # Enrich response with approver/rejector information
        from core.services.attribution_service import AttributionService
        response_dict = {
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

        return response_dict

    except ValidationError as e:
        logger.warning(f"Validation error rejecting {approval_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientApprovalPermissions as e:
        logger.warning(f"Permission denied rejecting {approval_id} by user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidApprovalState as e:
        logger.warning(f"Invalid state rejecting {approval_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalServiceError as e:
        logger.error(f"Approval service error rejecting {approval_id}: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error rejecting {approval_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/{expense_id}", response_model=ExpenseApprovalHistory)
async def get_approval_history(
    expense_id: int,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service)
):
    """
    Get complete approval history for an expense.

    This endpoint returns the complete audit trail of approval decisions
    for a specific expense, including all approval levels, decisions, and timestamps.

    Args:
        expense_id: ID of the expense to get approval history for
        current_user: Currently authenticated user
        approval_service: Approval service instance

    Returns:
        ExpenseApprovalHistory with complete approval audit trail

    Raises:
        HTTPException: 404 if expense not found
    """
    try:
        require_non_viewer(current_user)

        history = approval_service.get_approval_history(expense_id)

        logger.info(f"Retrieved approval history for expense {expense_id} by user {current_user.id}")

        return history

    except ValidationError as e:
        logger.warning(f"Validation error getting history for expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving approval history for expense {expense_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics", response_model=ApprovalMetrics)
async def get_approval_metrics(
    approver_id: Optional[int] = Query(None, description="Filter by specific approver ID"),
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service)
):
    """
    Get approval workflow metrics.

    This endpoint provides aggregated metrics about the approval workflow
    including approval rates, average approval times, and decision counts.

    Args:
        approver_id: Optional filter by specific approver (defaults to current user)
        current_user: Currently authenticated user
        approval_service: Approval service instance

    Returns:
        ApprovalMetrics with aggregated approval statistics
    """
    try:
        require_non_viewer(current_user)

        # If no approver_id specified, use current user
        target_approver_id = approver_id if approver_id is not None else current_user.id

        metrics = approval_service.get_approval_metrics(approver_id=target_approver_id)

        logger.info(f"Retrieved approval metrics for approver {target_approver_id} by user {current_user.id}")

        return metrics

    except Exception as e:
        logger.error(f"Error retrieving approval metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get approval dashboard statistics for the current user.

    This endpoint provides aggregated statistics about the approval workflow
    for display on the approval dashboard, including both expense and invoice approvals.

    Args:
        current_user: Currently authenticated user
        db: Database session

    Returns:
        Dashboard statistics including pending count, approvals today, etc.
    """
    try:
        require_non_viewer(current_user)

        # Import here to avoid circular imports
        from core.models.models_per_tenant import ExpenseApproval, Expense, InvoiceApproval, Invoice
        from sqlalchemy import func, and_, or_
        from datetime import datetime, timedelta

        # Get current date for "today" calculations
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Get expense approvals for current user
        expense_base_query = db.query(ExpenseApproval).filter(
            ExpenseApproval.approver_id == current_user.id
        )

        # Get invoice approvals for current user
        invoice_base_query = db.query(InvoiceApproval).filter(
            InvoiceApproval.approver_id == current_user.id
        )

        # Pending approvals count (expenses + invoices)
        pending_expense_count = expense_base_query.filter(
            ExpenseApproval.status == "pending"
        ).count()
        pending_invoice_count = invoice_base_query.filter(
            InvoiceApproval.status == "pending"
        ).count()
        pending_count = pending_expense_count + pending_invoice_count

        # Approved today count (expenses + invoices)
        approved_expense_today = expense_base_query.filter(
            and_(
                ExpenseApproval.status == "approved",
                ExpenseApproval.decided_at >= today_start,
                ExpenseApproval.decided_at < today_end
            )
        ).count()
        approved_invoice_today = invoice_base_query.filter(
            and_(
                InvoiceApproval.status == "approved",
                InvoiceApproval.decided_at >= today_start,
                InvoiceApproval.decided_at < today_end
            )
        ).count()
        approved_today = approved_expense_today + approved_invoice_today

        # Rejected today count (expenses + invoices)
        rejected_expense_today = expense_base_query.filter(
            and_(
                ExpenseApproval.status == "rejected",
                ExpenseApproval.decided_at >= today_start,
                ExpenseApproval.decided_at < today_end
            )
        ).count()
        rejected_invoice_today = invoice_base_query.filter(
            and_(
                InvoiceApproval.status == "rejected",
                InvoiceApproval.decided_at >= today_start,
                InvoiceApproval.decided_at < today_end
            )
        ).count()
        rejected_today = rejected_expense_today + rejected_invoice_today

        # Overdue count (pending for more than 3 days) - expenses + invoices
        three_days_ago = datetime.now() - timedelta(days=3)
        overdue_expense_count = expense_base_query.filter(
            and_(
                ExpenseApproval.status == "pending",
                ExpenseApproval.created_at < three_days_ago
            )
        ).count()
        overdue_invoice_count = invoice_base_query.filter(
            and_(
                InvoiceApproval.status == "pending",
                InvoiceApproval.created_at < three_days_ago
            )
        ).count()
        overdue_count = overdue_expense_count + overdue_invoice_count

        # Average approval time in hours (expenses + invoices)
        # Get all completed expense approvals for this user
        completed_expense_approvals = expense_base_query.filter(
            or_(
                ExpenseApproval.status == "approved",
                ExpenseApproval.status == "rejected"
            )
        ).all()

        # Get all completed invoice approvals for this user
        completed_invoice_approvals = invoice_base_query.filter(
            or_(
                InvoiceApproval.status == "approved",
                InvoiceApproval.status == "rejected"
            )
        ).all()

        average_approval_time_hours = 0.0
        total_hours = 0
        count = 0

        # Process expense approvals
        for approval in completed_expense_approvals:
            if approval.decided_at and approval.created_at:
                time_diff = approval.decided_at - approval.created_at
                total_hours += time_diff.total_seconds() / 3600  # Convert to hours
                count += 1

        # Process invoice approvals
        for approval in completed_invoice_approvals:
            if approval.decided_at and approval.created_at:
                time_diff = approval.decided_at - approval.created_at
                total_hours += time_diff.total_seconds() / 3600  # Convert to hours
                count += 1

        if count > 0:
            average_approval_time_hours = total_hours / count

        stats = {
            "pending_count": pending_count,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
            "overdue_count": overdue_count,
            "average_approval_time_hours": round(average_approval_time_hours, 1)
        }

        logger.info(f"Retrieved dashboard stats for user {current_user.id}: {stats}")

        return stats

    except Exception as e:
        logger.error(f"Error retrieving dashboard stats for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/approved-expenses")
async def get_approved_expenses(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get expenses that have been approved by the current user.

    This endpoint returns expenses that the current user has approved,
    allowing approvers to view and track expenses they've processed.

    Args:
        current_user: Currently authenticated user
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of approved expenses with approval details
    """
    try:
        require_non_viewer(current_user)

        # Import here to avoid circular imports
        from core.models.models_per_tenant import ExpenseApproval, Expense
        from sqlalchemy import and_

        # Query for approved expenses where current user is the approver
        approved_expenses = db.query(Expense).join(
            ExpenseApproval,
            and_(
                ExpenseApproval.expense_id == Expense.id,
                ExpenseApproval.approver_id == current_user.id,
                ExpenseApproval.status == "approved"
            )
        ).order_by(
            ExpenseApproval.decided_at.desc()
        ).offset(skip).limit(limit).all()

        # Get total count for pagination
        total_count = db.query(Expense).join(
            ExpenseApproval,
            and_(
                ExpenseApproval.expense_id == Expense.id,
                ExpenseApproval.approver_id == current_user.id,
                ExpenseApproval.status == "approved"
            )
        ).count()

        # Convert to dict format similar to expense API
        result = []
        for expense in approved_expenses:
            expense_dict = {
                "id": expense.id,
                "amount": expense.amount,
                "description": expense.notes or f"{expense.category} - {expense.vendor or 'Unknown vendor'}",
                "category": expense.category,
                "date": expense.expense_date.isoformat() if expense.expense_date else None,
                "status": expense.status,
                "user_id": expense.user_id,
                "created_at": expense.created_at.isoformat() if expense.created_at else None,
                "updated_at": expense.updated_at.isoformat() if expense.updated_at else None,
                "receipt_path": expense.receipt_path,
                "notes": expense.notes,
                "vendor": expense.vendor,
                "tax_amount": expense.tax_amount,
                "currency": expense.currency,
                "labels": expense.labels or [],
                "analysis_status": expense.analysis_status,
                "analysis_error": expense.analysis_error,
                "invoice_id": expense.invoice_id,
                "is_inventory_consumption": expense.is_inventory_consumption,
                "consumption_items": expense.consumption_items or []
            }
            result.append(expense_dict)

        logger.info(f"Retrieved {len(result)} approved expenses for user {current_user.id}")

        return {
            "expenses": result,
            "total": total_count
        }

    except Exception as e:
        logger.error(f"Error retrieving approved expenses for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/processed-expenses")
async def get_processed_expenses(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get expenses that have been approved or rejected by the current user.

    This endpoint returns expenses that the current user has processed (approved or rejected),
    allowing approvers to view and track their decision history.

    Args:
        current_user: Currently authenticated user
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of processed (approved/rejected) expenses with approval details
    """
    try:
        require_non_viewer(current_user)

        # Import here to avoid circular imports
        from core.models.models_per_tenant import ExpenseApproval, Expense
        from sqlalchemy import and_, or_

        # Query for expenses where current user is the approver and status is approved OR rejected
        processed_expenses = db.query(Expense).join(
            ExpenseApproval,
            and_(
                ExpenseApproval.expense_id == Expense.id,
                ExpenseApproval.approver_id == current_user.id,
                or_(
                    ExpenseApproval.status == "approved",
                    ExpenseApproval.status == "rejected"
                )
            )
        ).order_by(
            ExpenseApproval.decided_at.desc()
        ).offset(skip).limit(limit).all()

        # Get total count for pagination
        total_count = db.query(Expense).join(
            ExpenseApproval,
            and_(
                ExpenseApproval.expense_id == Expense.id,
                ExpenseApproval.approver_id == current_user.id,
                or_(
                    ExpenseApproval.status == "approved",
                    ExpenseApproval.status == "rejected"
                )
            )
        ).count()

        # Convert to dict format similar to expense API
        result = []
        for expense in processed_expenses:
            expense_dict = {
                "id": expense.id,
                "amount": expense.amount,
                "description": expense.notes or f"{expense.category} - {expense.vendor or 'Unknown vendor'}",
                "category": expense.category,
                "date": expense.expense_date.isoformat() if expense.expense_date else None,
                "status": expense.status,
                "user_id": expense.user_id,
                "created_at": expense.created_at.isoformat() if expense.created_at else None,
                "updated_at": expense.updated_at.isoformat() if expense.updated_at else None,
                "receipt_path": expense.receipt_path,
                "notes": expense.notes,
                "vendor": expense.vendor,
                "tax_amount": expense.tax_amount,
                "currency": expense.currency,
                "labels": expense.labels or [],
                "analysis_status": expense.analysis_status,
                "analysis_error": expense.analysis_error,
                "invoice_id": expense.invoice_id,
                "is_inventory_consumption": expense.is_inventory_consumption,
                "consumption_items": expense.consumption_items or []
            }
            result.append(expense_dict)

        logger.info(f"Retrieved {len(result)} processed expenses for user {current_user.id}")

        return {
            "expenses": result,
            "total": total_count
        }

    except Exception as e:
        logger.error(f"Error retrieving processed expenses for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/invoices/processed")
async def get_processed_invoices(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get invoices that have been approved or rejected by the current user.

    This endpoint returns invoices that the current user has processed (approved or rejected),
    allowing approvers to view and track their decision history.

    Args:
        current_user: Currently authenticated user
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of processed (approved/rejected) invoices with approval details
    """
    try:
        require_non_viewer(current_user)

        # Import here to avoid circular imports
        from core.models.models_per_tenant import InvoiceApproval, Invoice, Client
        from sqlalchemy import and_, or_

        # Query for invoices where current user is the approver and status is approved OR rejected
        processed_invoices_query = db.query(
            InvoiceApproval.id.label('approval_id'),
            Invoice.id,
            Invoice.number,
            Client.name.label('client_name'),
            Invoice.amount,
            Invoice.currency,
            InvoiceApproval.status,
            InvoiceApproval.decided_at,
            InvoiceApproval.submitted_at
        ).join(
            Invoice, InvoiceApproval.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).filter(
            and_(
                InvoiceApproval.approver_id == current_user.id,
                or_(
                    InvoiceApproval.status == "approved",
                    InvoiceApproval.status == "rejected"
                )
            )
        ).order_by(
            InvoiceApproval.decided_at.desc()
        )

        # Get total count for pagination
        total_count = processed_invoices_query.count()

        # Apply pagination
        results = processed_invoices_query.offset(skip).limit(limit).all()

        # Convert to dict format
        result_list = []
        for row in results:
            invoice_dict = {
                "id": row.id,
                "approval_id": row.approval_id,
                "number": row.number,
                "client_name": row.client_name,
                "amount": row.amount,
                "currency": row.currency or 'USD',
                "status": row.status,
                "decided_at": row.decided_at.isoformat() if row.decided_at else None,
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None
            }
            result_list.append(invoice_dict)

        logger.info(f"Retrieved {len(result_list)} processed invoices for user {current_user.id}")

        return {
            "invoices": result_list,
            "total": total_count
        }

    except Exception as e:
        logger.error(f"Error retrieving processed invoices for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Approval Delegation Endpoints

@router.post("/delegate", response_model=ApprovalDelegate)
async def create_approval_delegation(
    delegation_data: ApprovalDelegateCreate,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Create an approval delegation.

    This endpoint allows users to delegate their approval authority to another user
    for a specified time period. During the delegation period, the delegate will
    receive approval requests instead of the original approver.

    Args:
        delegation_data: Delegation configuration including delegate and time period
        current_user: Currently authenticated user (the approver)
        approval_service: Approval service instance
        db: Database session

    Returns:
        Created ApprovalDelegate record

    Raises:
        HTTPException: 400 if delegation data is invalid or overlaps with existing delegation
        HTTPException: 403 if user lacks permission to create delegations
        HTTPException: 422 if delegate user not found
    """
    try:
        require_non_viewer(current_user)

        # Validate that the approver_id in the data matches the current user
        if delegation_data.approver_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only create delegations for yourself"
            )

        # Create the delegation
        delegation = approval_service.create_delegation(
            approver_id=current_user.id,
            delegate_data=delegation_data
        )

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="approval_delegation_created",
            resource_type="approval_delegate",
            resource_id=str(delegation.id),
            details={
                "delegate_id": delegation.delegate_id,
                "start_date": delegation.start_date.isoformat(),
                "end_date": delegation.end_date.isoformat(),
                "is_active": delegation.is_active
            }
        )

        logger.info(f"User {current_user.id} created approval delegation {delegation.id} to user {delegation.delegate_id}")

        return delegation

    except ValidationError as e:
        logger.warning(f"Validation error creating delegation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalServiceError as e:
        logger.error(f"Approval service error creating delegation: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating delegation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/delegates", response_model=List[ApprovalDelegate])
async def get_approval_delegations(
    include_inactive: bool = Query(False, description="Include inactive delegations"),
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service)
):
    """
    Get approval delegations for the current user.

    This endpoint returns all delegations created by the current user,
    optionally including inactive/expired delegations.

    Args:
        include_inactive: Whether to include inactive or expired delegations
        current_user: Currently authenticated user
        approval_service: Approval service instance

    Returns:
        List of ApprovalDelegate records for the current user
    """
    try:
        require_non_viewer(current_user)

        if include_inactive:
            # Get all delegations for the user
            from core.models.models_per_tenant import ApprovalDelegate as ApprovalDelegateModel
            delegations = approval_service.db.query(ApprovalDelegateModel).filter(
                ApprovalDelegateModel.approver_id == current_user.id
            ).order_by(ApprovalDelegateModel.created_at.desc()).all()
        else:
            # Get only active delegations
            delegations = approval_service.get_active_delegations(current_user.id)

        logger.info(f"Retrieved {len(delegations)} delegations for user {current_user.id}")

        return delegations

    except Exception as e:
        logger.error(f"Error retrieving delegations for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/delegates/{delegation_id}", response_model=ApprovalDelegate)
async def update_approval_delegation(
    delegation_id: int,
    delegation_data: ApprovalDelegateUpdate,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an approval delegation.

    This endpoint allows users to update their existing delegations,
    such as extending the end date or deactivating the delegation.

    Args:
        delegation_id: ID of the delegation to update
        delegation_data: Updated delegation data
        current_user: Currently authenticated user (must be the approver)
        db: Database session

    Returns:
        Updated ApprovalDelegate record

    Raises:
        HTTPException: 403 if user doesn't own the delegation
        HTTPException: 404 if delegation not found
        HTTPException: 400 if update data is invalid
    """
    try:
        require_non_viewer(current_user)

        # Import here to avoid circular imports
        from core.models.models_per_tenant import ApprovalDelegate as ApprovalDelegateModel

        # Get the delegation
        delegation = db.query(ApprovalDelegateModel).filter(
            and_(
                ApprovalDelegateModel.id == delegation_id,
                ApprovalDelegateModel.approver_id == current_user.id
            )
        ).first()

        if not delegation:
            raise HTTPException(
                status_code=404,
                detail=f"Delegation {delegation_id} not found or access denied"
            )

        # Store original values for audit log
        original_values = {
            "start_date": delegation.start_date.isoformat(),
            "end_date": delegation.end_date.isoformat(),
            "is_active": delegation.is_active
        }

        # Update fields that are provided
        update_data = delegation_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(delegation, field, value)

        delegation.updated_at = datetime.now(timezone.utc)

        # Validate the updated delegation
        if delegation.end_date <= delegation.start_date:
            raise HTTPException(
                status_code=400,
                detail="End date must be after start date"
            )

        db.commit()
        db.refresh(delegation)

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="approval_delegation_updated",
            resource_type="approval_delegate",
            resource_id=str(delegation_id),
            details={
                "original_values": original_values,
                "updated_fields": list(update_data.keys()),
                "new_values": {
                    "start_date": delegation.start_date.isoformat(),
                    "end_date": delegation.end_date.isoformat(),
                    "is_active": delegation.is_active
                }
            }
        )

        logger.info(f"User {current_user.id} updated delegation {delegation_id}")

        return delegation

    except ValidationError as e:
        logger.warning(f"Validation error updating delegation {delegation_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating delegation {delegation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/delegates/{delegation_id}")
async def deactivate_approval_delegation(
    delegation_id: int,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Deactivate an approval delegation.

    This endpoint allows users to deactivate their existing delegations,
    effectively ending the delegation immediately.

    Args:
        delegation_id: ID of the delegation to deactivate
        current_user: Currently authenticated user (must be the approver)
        approval_service: Approval service instance
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: 403 if user doesn't own the delegation
        HTTPException: 404 if delegation not found
    """
    try:
        require_non_viewer(current_user)

        # Deactivate the delegation
        delegation = approval_service.deactivate_delegation(
            delegation_id=delegation_id,
            approver_id=current_user.id
        )

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="approval_delegation_deactivated",
            resource_type="approval_delegate",
            resource_id=str(delegation_id),
            details={
                "delegate_id": delegation.delegate_id,
                "original_end_date": delegation.end_date.isoformat()
            }
        )

        logger.info(f"User {current_user.id} deactivated delegation {delegation_id}")

        return {"message": f"Delegation {delegation_id} deactivated successfully"}

    except ValidationError as e:
        logger.warning(f"Validation error deactivating delegation {delegation_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deactivating delegation {delegation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Invoice Approval Endpoints

@router.post("/invoices/{invoice_id}/submit-approval", response_model=List[dict])
async def submit_invoice_for_approval(
    invoice_id: int,
    submission_data: dict,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Submit an invoice for approval.

    This endpoint allows users to submit invoices for approval according to
    configured approval rules.

    Args:
        invoice_id: ID of the invoice to submit for approval
        submission_data: Submission details including approver_id and optional notes
        current_user: Currently authenticated user
        approval_service: Approval service instance
        db: Database session

    Returns:
        List of created InvoiceApproval records

    Raises:
        HTTPException: 400 if invoice is invalid or already in approval workflow
        HTTPException: 403 if user lacks permission to submit this invoice
        HTTPException: 404 if invoice not found
    """
    try:
        require_non_viewer(current_user)

        # Extract approver_id and notes from submission_data
        approver_id = submission_data.get("approver_id")
        notes = submission_data.get("notes")

        if not approver_id:
            raise HTTPException(
                status_code=400,
                detail="approver_id is required"
            )

        # Submit invoice for approval
        approvals = approval_service.submit_invoice_for_approval(
            invoice_id=invoice_id,
            submitter_id=current_user.id,
            approver_id=approver_id,
            notes=notes
        )

        # Create notification and reminder for approvers
        from core.models.models_per_tenant import ReminderNotification, Invoice, Reminder, ReminderStatus, ReminderPriority, RecurrencePattern
        from datetime import timedelta as td
        now = datetime.now(timezone.utc)
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

        for approval in approvals:
            if approval.approver_id:
                # Create in-app notification with invoice_id in subject for navigation
                notification = ReminderNotification(
                    reminder_id=None,
                    user_id=approval.approver_id,
                    notification_type="invoice_approval",
                    channel="in_app",
                    scheduled_for=now,
                    subject=f"Invoice Approval Request #{invoice_id}",  # Include invoice_id for navigation
                    message=f"New invoice approval request from {current_user.email}: Invoice #{invoice.number if invoice else 'N/A'} - ${invoice.amount if invoice else 'N/A'}",
                    is_sent=True,
                    sent_at=now
                )
                db.add(notification)

                # Create a reminder task for the approver
                # Determine priority based on invoice amount
                priority = ReminderPriority.MEDIUM
                if invoice and invoice.amount:
                    if invoice.amount >= 5000:
                        priority = ReminderPriority.HIGH
                    elif invoice.amount >= 10000:
                        priority = ReminderPriority.URGENT

                # Set due date to 3 business days from now
                due_date = now + td(days=3)

                reminder = Reminder(
                    title=f"Approve Invoice: #{invoice.number if invoice else 'N/A'} - ${invoice.amount if invoice else 'N/A'}",
                    description=f"Invoice approval request from {current_user.email}\n\nInvoice Number: {invoice.number if invoice else 'N/A'}\nAmount: ${invoice.amount if invoice else 'N/A'}\nClient: {invoice.client.name if invoice and invoice.client else 'N/A'}\nDue Date: {invoice.due_date if invoice and invoice.due_date else 'N/A'}\n\nNotes: {notes if notes else 'No notes provided'}",
                    due_date=due_date,
                    priority=priority,
                    status=ReminderStatus.PENDING,
                    recurrence_pattern=RecurrencePattern.NONE,
                    assigned_to_id=approval.approver_id,
                    created_by_id=current_user.id,
                    tags=["approval", "invoice", f"invoice-{invoice_id}"],
                    extra_metadata={
                        "invoice_id": invoice_id,
                        "approval_id": approval.id,
                        "approval_level": approval.approval_level,
                        "submitter_id": current_user.id,
                        "submitter_email": current_user.email
                    }
                )
                db.add(reminder)

        # Commit the notifications and reminders
        db.commit()

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="invoice_submitted_for_approval",
            resource_type="invoice",
            resource_id=str(invoice_id),
            details={
                "invoice_id": invoice_id,
                "approval_count": len(approvals),
                "notes": notes
            }
        )

        logger.info(f"User {current_user.id} submitted invoice {invoice_id} for approval")

        return [{"id": a.id, "status": a.status, "approval_level": a.approval_level, "approver_id": a.approver_id} for a in approvals]

    except ValidationError as e:
        logger.warning(f"Validation error submitting invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidApprovalState as e:
        logger.warning(f"Invalid approval state for invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalWorkflowError as e:
        logger.error(f"Workflow error for invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error submitting invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/invoices/pending")
async def get_pending_invoice_approvals(
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Number of results to skip"),
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Get pending invoice approvals for the current user.

    This endpoint returns all invoices that are currently pending approval
    by the authenticated user.

    Args:
        limit: Maximum number of results to return (default: no limit)
        offset: Number of results to skip for pagination (default: 0)
        current_user: Currently authenticated user
        approval_service: Approval service instance

    Returns:
        Object containing approvals list and total count
    """
    try:
        require_non_viewer(current_user)

        from core.models.models_per_tenant import InvoiceApproval, Invoice, Client
        from core.schemas.approval import ApprovalStatus, PendingInvoiceApprovalDetail

        # Build query with joins to get invoice and client details
        query = db.query(
            InvoiceApproval.id,
            InvoiceApproval.invoice_id,
            Invoice.number.label('invoice_number'),
            Client.name.label('client_name'),
            Invoice.amount,
            Invoice.currency,
            InvoiceApproval.status,
            InvoiceApproval.submitted_at,
            InvoiceApproval.approver_id,
            InvoiceApproval.approval_level
        ).join(
            Invoice, InvoiceApproval.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).filter(
            and_(
                InvoiceApproval.approver_id == current_user.id,
                InvoiceApproval.status == ApprovalStatus.PENDING,
                InvoiceApproval.is_current_level == True
            )
        ).order_by(InvoiceApproval.submitted_at.asc())

        # Get total count
        total = query.count()

        # Apply pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        # Execute query and convert to schema
        results = query.all()
        approvals = [
            PendingInvoiceApprovalDetail(
                id=row.id,
                invoice_id=row.invoice_id,
                invoice_number=row.invoice_number,
                client_name=row.client_name,
                amount=row.amount,
                currency=row.currency or 'USD',
                status=row.status,
                submitted_at=row.submitted_at,
                approver_id=row.approver_id,
                approval_level=row.approval_level
            )
            for row in results
        ]

        logger.info(f"Retrieved {len(approvals)} pending invoice approvals (total: {total}) for user {current_user.id}")

        return {
            "approvals": approvals,
            "total": total
        }

    except Exception as e:
        logger.error(f"Error retrieving pending invoice approvals for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/invoices/{approval_id}/approve")
async def approve_invoice(
    approval_id: int,
    decision_data: dict,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Approve an invoice.

    This endpoint allows authorized approvers to approve invoices assigned to them.

    Args:
        approval_id: ID of the approval record to approve
        decision_data: Approval decision details including optional notes
        current_user: Currently authenticated user
        approval_service: Approval service instance
        db: Database session

    Returns:
        Updated InvoiceApproval record

    Raises:
        HTTPException: 400 if approval is not in pending state
        HTTPException: 403 if user lacks permission to approve this invoice
        HTTPException: 404 if approval not found
    """
    try:
        require_non_viewer(current_user)

        notes = decision_data.get("notes")

        # Approve the invoice
        approval = approval_service.approve_invoice(
            approval_id=approval_id,
            approver_id=current_user.id,
            notes=notes
        )

        # Create notification for invoice submitter and complete the reminder
        from core.models.models_per_tenant import ReminderNotification, Invoice, Reminder, ReminderStatus
        from sqlalchemy import text
        # Mark the original approval notification as read
        try:
            # Find the notification for this user about this invoice
            approval_notification = db.query(ReminderNotification).filter(
                ReminderNotification.user_id == current_user.id,
                ReminderNotification.notification_type == "invoice_approval",
                ReminderNotification.is_read == False,
                ReminderNotification.subject.contains(f"#{approval.invoice_id}")
            ).first()

            if approval_notification:
                approval_notification.is_read = True
                db.add(approval_notification)
        except Exception as e:
            logger.warning(f"Failed to mark notification as read for invoice {approval.invoice_id}: {e}")

        now = datetime.now(timezone.utc)
        invoice = db.query(Invoice).filter(Invoice.id == approval.invoice_id).first()

        # Get the submitter from the reminder metadata
        reminder_for_approval = db.query(Reminder).filter(
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata")
        ).params(metadata=f'{{"approval_id": {approval.id}}}').first()

        submitter_id = None
        if reminder_for_approval and reminder_for_approval.extra_metadata:
            submitter_id = reminder_for_approval.extra_metadata.get("submitter_id")

        if submitter_id and invoice:
            notification = ReminderNotification(
                reminder_id=None,
                user_id=submitter_id,
                notification_type="invoice_approved",
                channel="in_app",
                scheduled_for=now,
                subject=f"Invoice Approved #{approval.invoice_id}",
                message=f"Your invoice #{invoice.number} has been approved by {current_user.email}",
                is_sent=True,
                sent_at=now
            )
            db.add(notification)

        # Complete the reminder task for this approval
        reminder = db.query(Reminder).filter(
            Reminder.assigned_to_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata")
        ).params(metadata=f'{{"approval_id": {approval_id}}}').first()

        if reminder:
            reminder.status = ReminderStatus.COMPLETED
            reminder.completed_at = now
            reminder.completed_by_id = current_user.id
            db.add(reminder)

        db.commit()

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="invoice_approved",
            resource_type="invoice_approval",
            resource_id=str(approval_id),
            details={
                "invoice_id": approval.invoice_id,
                "approval_level": approval.approval_level,
                "notes": notes
            }
        )

        logger.info(f"User {current_user.id} approved invoice approval {approval_id}")

        return {"id": approval.id, "status": approval.status, "invoice_id": approval.invoice_id}

    except ValidationError as e:
        logger.warning(f"Validation error approving invoice {approval_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientApprovalPermissions as e:
        logger.warning(f"Permission denied approving invoice {approval_id} by user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidApprovalState as e:
        logger.warning(f"Invalid state approving invoice {approval_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error approving invoice {approval_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/invoices/{approval_id}/reject")
async def reject_invoice(
    approval_id: int,
    decision_data: dict,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Reject an invoice.

    This endpoint allows authorized approvers to reject invoices assigned to them.
    A rejection reason is required and will be communicated to the invoice submitter.

    Args:
        approval_id: ID of the approval record to reject
        decision_data: Rejection decision details including required rejection reason
        current_user: Currently authenticated user
        approval_service: Approval service instance
        db: Database session

    Returns:
        Updated InvoiceApproval record

    Raises:
        HTTPException: 400 if approval is not in pending state or rejection reason missing
        HTTPException: 403 if user lacks permission to approve this invoice
        HTTPException: 404 if approval not found
    """
    try:
        require_non_viewer(current_user)

        rejection_reason = decision_data.get("rejection_reason")
        notes = decision_data.get("notes")

        # Validate rejection reason is provided
        if not rejection_reason or not rejection_reason.strip():
            raise HTTPException(
                status_code=400,
                detail="Rejection reason is required when rejecting an invoice"
            )

        # Reject the invoice
        approval = approval_service.reject_invoice(
            approval_id=approval_id,
            approver_id=current_user.id,
            rejection_reason=rejection_reason,
            notes=notes
        )

        # Create notification for invoice submitter and cancel the reminder
        from core.models.models_per_tenant import ReminderNotification, Invoice, Reminder, ReminderStatus

        # Mark the original approval notification as read
        try:
            # Find the notification for this user about this invoice
            approval_notification = db.query(ReminderNotification).filter(
                ReminderNotification.user_id == current_user.id,
                ReminderNotification.notification_type == "invoice_approval",
                ReminderNotification.is_read == False,
                ReminderNotification.subject.contains(f"#{approval.invoice_id}")
            ).first()

            if approval_notification:
                approval_notification.is_read = True
                db.add(approval_notification)
        except Exception as e:
            logger.warning(f"Failed to mark notification as read for invoice {approval.invoice_id}: {e}")

        now = datetime.now(timezone.utc)
        invoice = db.query(Invoice).filter(Invoice.id == approval.invoice_id).first()

        # Get the submitter from the reminder metadata
        reminder_for_approval = db.query(Reminder).filter(
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata")
        ).params(metadata=f'{{"approval_id": {approval.id}}}').first()

        submitter_id = None
        if reminder_for_approval and reminder_for_approval.extra_metadata:
            submitter_id = reminder_for_approval.extra_metadata.get("submitter_id")

        if submitter_id and invoice:
            notification = ReminderNotification(
                reminder_id=None,
                user_id=submitter_id,
                notification_type="invoice_rejected",
                channel="in_app",
                scheduled_for=now,
                subject=f"Invoice Rejected #{approval.invoice_id}",
                message=f"Your invoice #{invoice.number} was rejected by {current_user.email}. Reason: {rejection_reason}",
                is_sent=True,
                sent_at=now
            )
            db.add(notification)

        # Cancel the reminder task for this approval (since it's rejected)
        reminder = db.query(Reminder).filter(
            Reminder.assigned_to_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            text("extra_metadata::jsonb @> :metadata")
        ).params(metadata=f'{{"approval_id": {approval_id}}}').first()

        if reminder:
            reminder.status = ReminderStatus.CANCELLED
            db.add(reminder)

        db.commit()

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="invoice_rejected",
            resource_type="invoice_approval",
            resource_id=str(approval_id),
            details={
                "invoice_id": approval.invoice_id,
                "approval_level": approval.approval_level,
                "rejection_reason": rejection_reason,
                "notes": notes
            }
        )

        logger.info(f"User {current_user.id} rejected invoice approval {approval_id}")

        return {"id": approval.id, "status": approval.status, "invoice_id": approval.invoice_id}

    except ValidationError as e:
        logger.warning(f"Validation error rejecting invoice {approval_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientApprovalPermissions as e:
        logger.warning(f"Permission denied rejecting invoice {approval_id} by user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidApprovalState as e:
        logger.warning(f"Invalid state rejecting invoice {approval_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error rejecting invoice {approval_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/invoices/history/{invoice_id}")
async def get_invoice_approval_history(
    invoice_id: int,
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service),
    db: Session = Depends(get_db)
):
    """
    Get complete approval history for an invoice.

    This endpoint returns the complete audit trail of approval decisions
    for a specific invoice.

    Args:
        invoice_id: ID of the invoice to get approval history for
        current_user: Currently authenticated user
        approval_service: Approval service instance
        db: Database session

    Returns:
        InvoiceApprovalHistory with complete approval audit trail

    Raises:
        HTTPException: 404 if invoice not found
    """
    try:
        require_non_viewer(current_user)

        history = approval_service.get_invoice_approval_history(invoice_id)

        # Enrich the approval history items with username information
        from core.models.models_per_tenant import InvoiceApproval
        from core.services.attribution_service import AttributionService
        from sqlalchemy.orm import joinedload

        # Get the approvals with user relationships loaded
        approvals = db.query(InvoiceApproval).options(
            joinedload(InvoiceApproval.approved_by),
            joinedload(InvoiceApproval.rejected_by)
        ).filter(
            InvoiceApproval.invoice_id == invoice_id
        ).order_by(
            InvoiceApproval.approval_level.asc(),
            InvoiceApproval.submitted_at.asc()
        ).all()

        # Create a mapping of approval_id to approval for quick lookup
        approval_map = {approval.id: approval for approval in approvals}

        # Enrich the history items with username information
        enriched_history_items = []
        for item in history.approval_history:
            approval = approval_map.get(item.id)
            item_dict = item.dict()

            # Add username fields
            item_dict["approved_by_username"] = None
            item_dict["rejected_by_username"] = None

            if approval:
                if approval.status == "approved" and approval.approved_by:
                    item_dict["approved_by_username"] = AttributionService.get_display_name(approval.approved_by)
                elif approval.status == "rejected" and approval.rejected_by:
                    item_dict["rejected_by_username"] = AttributionService.get_display_name(approval.rejected_by)

            enriched_history_items.append(item_dict)

        # Return enriched response
        response = {
            "invoice_id": history.invoice_id,
            "current_status": history.current_status,
            "approval_history": enriched_history_items
        }

        logger.info(f"Retrieved approval history for invoice {invoice_id} by user {current_user.id}")

        return response

    except ValidationError as e:
        logger.warning(f"Validation error getting history for invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving approval history for invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
