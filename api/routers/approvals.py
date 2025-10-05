"""
Approval Router

This router provides REST API endpoints for the expense approval workflow.
It handles expense submission for approval, approval decisions, and approval history.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import List, Optional
from datetime import datetime, timezone
import logging

from models.database import get_db, get_tenant_context
from routers.auth import get_current_user, get_email_service_for_tenant
from models.models import MasterUser
from schemas.approval import (
    ExpenseApprovalCreate, ExpenseApprovalDecision, ExpenseApproval,
    PendingApprovalSummary, ExpenseApprovalHistory, ApprovalMetrics,
    ApprovalRuleCreate, ApprovalRuleUpdate, ApprovalRule,
    ApprovalDelegateCreate, ApprovalDelegateUpdate, ApprovalDelegate,
    ApprovalStatus
)
from services.approval_service import ApprovalService
from exceptions.approval_exceptions import (
    ApprovalException, ValidationError, ExpenseValidationError,
    InsufficientApprovalPermissions, ExpenseAlreadyApproved, 
    InvalidApprovalState, ApprovalServiceError, NoApprovalRuleFound,
    ApprovalNotFoundException, ExpenseNotFoundException,
    ApprovalWorkflowError, ApprovalConcurrencyError
)
from services.notification_service import NotificationService
from services.approval_permission_service import ApprovalPermissionService
from utils.rbac import (
    require_non_viewer, require_admin, require_approval_submission,
    require_approval_permission, require_approval_rule_management
)
from utils.audit import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


def get_approval_service(db: Session = Depends(get_db)) -> ApprovalService:
    """Get approval service instance with notification service."""
    # Create notification service without email service for now
    # Email service will be resolved later if needed
    notification_service = NotificationService(db, None)
    return ApprovalService(db, notification_service)


def get_approval_permission_service(db: Session = Depends(get_db)) -> ApprovalPermissionService:
    """Get approval permission service instance."""
    return ApprovalPermissionService(db)


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
            notes=submission_data.notes
        )
        
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


@router.get("/pending", response_model=List[ExpenseApproval])
async def get_pending_approvals(
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Number of results to skip"),
    current_user: MasterUser = Depends(get_current_user),
    approval_service: ApprovalService = Depends(get_approval_service)
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
        List of pending ExpenseApproval records assigned to the current user
    """
    try:
        require_non_viewer(current_user)
        
        pending_approvals = approval_service.get_pending_approvals(
            approver_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Retrieved {len(pending_approvals)} pending approvals for user {current_user.id}")
        
        return pending_approvals
        
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
                "notes": decision_data.notes
            }
        )
        
        logger.info(f"User {current_user.id} approved expense approval {approval_id}")
        
        return approval
        
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
        
        return approval
        
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


# Approval Rule Management Endpoints

@router.post("/approval-rules", response_model=ApprovalRule)
async def create_approval_rule(
    rule_data: ApprovalRuleCreate,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new approval rule (admin only).
    
    This endpoint allows administrators to create new approval rules that define
    which expenses require approval and who should approve them based on amount
    thresholds, categories, and other criteria.
    
    Args:
        rule_data: Approval rule creation data
        current_user: Currently authenticated user (must be admin)
        db: Database session
        
    Returns:
        Created ApprovalRule record
        
    Raises:
        HTTPException: 403 if user is not an admin
        HTTPException: 400 if rule data is invalid
        HTTPException: 422 if approver user not found
    """
    try:
        require_approval_rule_management(current_user, "create approval rules")
        
        # Import here to avoid circular imports
        from models.models_per_tenant import ApprovalRule as ApprovalRuleModel, User
        
        # Validate that the approver exists
        approver = db.query(User).filter(User.id == rule_data.approver_id).first()
        if not approver:
            raise HTTPException(
                status_code=422,
                detail=f"Approver with ID {rule_data.approver_id} not found"
            )
        
        # Create the approval rule
        now = datetime.now(timezone.utc)
        approval_rule = ApprovalRuleModel(
            name=rule_data.name,
            min_amount=rule_data.min_amount,
            max_amount=rule_data.max_amount,
            category_filter=rule_data.category_filter,
            currency=rule_data.currency,
            approval_level=rule_data.approval_level,
            approver_id=rule_data.approver_id,
            is_active=rule_data.is_active,
            priority=rule_data.priority,
            auto_approve_below=rule_data.auto_approve_below,
            created_at=now,
            updated_at=now
        )
        
        db.add(approval_rule)
        db.commit()
        db.refresh(approval_rule)
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="approval_rule_created",
            resource_type="approval_rule",
            resource_id=str(approval_rule.id),
            details={
                "rule_name": rule_data.name,
                "approver_id": rule_data.approver_id,
                "approval_level": rule_data.approval_level,
                "min_amount": rule_data.min_amount,
                "max_amount": rule_data.max_amount
            }
        )
        
        logger.info(f"Admin {current_user.id} created approval rule {approval_rule.id}: {rule_data.name}")
        
        return approval_rule
        
    except ValidationError as e:
        logger.warning(f"Validation error creating approval rule: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating approval rule: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/approval-rules", response_model=List[ApprovalRule])
async def list_approval_rules(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    approver_id: Optional[int] = Query(None, description="Filter by approver ID"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Number of results to skip"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List approval rules.
    
    This endpoint returns approval rules with optional filtering by active status
    and approver. Results can be paginated using limit and offset.
    
    Args:
        is_active: Optional filter by active status
        approver_id: Optional filter by approver ID
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        List of ApprovalRule records
    """
    try:
        require_non_viewer(current_user)
        
        # Import here to avoid circular imports
        from models.models_per_tenant import ApprovalRule as ApprovalRuleModel
        
        # Build query with filters
        query = db.query(ApprovalRuleModel)
        
        if is_active is not None:
            query = query.filter(ApprovalRuleModel.is_active == is_active)
        
        if approver_id is not None:
            query = query.filter(ApprovalRuleModel.approver_id == approver_id)
        
        # Order by priority (descending) then by created_at
        query = query.order_by(desc(ApprovalRuleModel.priority), ApprovalRuleModel.created_at)
        
        # Apply pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        approval_rules = query.all()
        
        logger.info(f"Retrieved {len(approval_rules)} approval rules for user {current_user.id}")
        
        return approval_rules
        
    except Exception as e:
        logger.error(f"Error retrieving approval rules: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/approval-rules/{rule_id}", response_model=ApprovalRule)
async def update_approval_rule(
    rule_id: int,
    rule_data: ApprovalRuleUpdate,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an approval rule (admin only).
    
    This endpoint allows administrators to update existing approval rules.
    Only provided fields will be updated, others will remain unchanged.
    
    Args:
        rule_id: ID of the approval rule to update
        rule_data: Approval rule update data
        current_user: Currently authenticated user (must be admin)
        db: Database session
        
    Returns:
        Updated ApprovalRule record
        
    Raises:
        HTTPException: 403 if user is not an admin
        HTTPException: 404 if approval rule not found
        HTTPException: 400 if update data is invalid
        HTTPException: 422 if approver user not found
    """
    try:
        require_admin(current_user, "update approval rules")
        
        # Import here to avoid circular imports
        from models.models_per_tenant import ApprovalRule as ApprovalRuleModel, User
        
        # Get the approval rule
        approval_rule = db.query(ApprovalRuleModel).filter(ApprovalRuleModel.id == rule_id).first()
        if not approval_rule:
            raise HTTPException(status_code=404, detail=f"Approval rule {rule_id} not found")
        
        # Validate approver if being updated
        if rule_data.approver_id is not None:
            approver = db.query(User).filter(User.id == rule_data.approver_id).first()
            if not approver:
                raise HTTPException(
                    status_code=422,
                    detail=f"Approver with ID {rule_data.approver_id} not found"
                )
        
        # Store original values for audit log
        original_values = {
            "name": approval_rule.name,
            "approver_id": approval_rule.approver_id,
            "is_active": approval_rule.is_active
        }
        
        # Update fields that are provided
        update_data = rule_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(approval_rule, field, value)
        
        approval_rule.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(approval_rule)
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="approval_rule_updated",
            resource_type="approval_rule",
            resource_id=str(rule_id),
            details={
                "rule_name": approval_rule.name,
                "original_values": original_values,
                "updated_fields": list(update_data.keys())
            }
        )
        
        logger.info(f"Admin {current_user.id} updated approval rule {rule_id}")
        
        return approval_rule
        
    except ValidationError as e:
        logger.warning(f"Validation error updating approval rule {rule_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating approval rule {rule_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/approval-rules/{rule_id}")
async def delete_approval_rule(
    rule_id: int,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an approval rule (admin only).
    
    This endpoint allows administrators to delete approval rules. The rule will be
    permanently removed from the system. Active approvals using this rule will not
    be affected, but new expenses will not use this rule for approval assignment.
    
    Args:
        rule_id: ID of the approval rule to delete
        current_user: Currently authenticated user (must be admin)
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: 403 if user is not an admin
        HTTPException: 404 if approval rule not found
        HTTPException: 400 if rule is currently being used in active approvals
    """
    try:
        require_admin(current_user, "delete approval rules")
        
        # Import here to avoid circular imports
        from models.models_per_tenant import ApprovalRule as ApprovalRuleModel, ExpenseApproval
        
        # Get the approval rule
        approval_rule = db.query(ApprovalRuleModel).filter(ApprovalRuleModel.id == rule_id).first()
        if not approval_rule:
            raise HTTPException(status_code=404, detail=f"Approval rule {rule_id} not found")
        
        # Check if rule is being used in active approvals
        active_approvals = db.query(ExpenseApproval).filter(
            and_(
                ExpenseApproval.approval_rule_id == rule_id,
                ExpenseApproval.status == ApprovalStatus.PENDING
            )
        ).first()
        
        if active_approvals:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete approval rule that is currently being used in active approvals"
            )
        
        # Store rule info for audit log
        rule_info = {
            "name": approval_rule.name,
            "approver_id": approval_rule.approver_id,
            "approval_level": approval_rule.approval_level
        }
        
        # Delete the rule
        db.delete(approval_rule)
        db.commit()
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="approval_rule_deleted",
            resource_type="approval_rule",
            resource_id=str(rule_id),
            details=rule_info
        )
        
        logger.info(f"Admin {current_user.id} deleted approval rule {rule_id}: {rule_info['name']}")
        
        return {"message": f"Approval rule {rule_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting approval rule {rule_id}: {str(e)}")
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
            from models.models_per_tenant import ApprovalDelegate as ApprovalDelegateModel
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
        from models.models_per_tenant import ApprovalDelegate as ApprovalDelegateModel
        
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