"""
Approval delegation management endpoints.

Covers: create, list, update, deactivate delegations.
"""

from datetime import datetime, timezone
from typing import List

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.schemas.approval import ApprovalDelegate, ApprovalDelegateCreate, ApprovalDelegateUpdate
from core.exceptions.approval_exceptions import ApprovalServiceError, ValidationError
from core.utils.audit import log_audit_event
from core.utils.rbac import require_non_viewer
from commercial.workflows.approvals.routers._shared import get_approval_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["approvals"])


@router.post("/delegate", response_model=ApprovalDelegate)
async def create_approval_delegation(
    delegation_data: ApprovalDelegateCreate,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Delegate approval authority to another user for a specified time period."""
    try:
        require_non_viewer(current_user)

        if delegation_data.approver_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only create delegations for yourself")

        delegation = approval_service.create_delegation(
            approver_id=current_user.id,
            delegate_data=delegation_data,
        )

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
                "is_active": delegation.is_active,
            },
        )

        logger.info("User %s created delegation %s to user %s", current_user.id, delegation.id, delegation.delegate_id)
        return delegation

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error creating delegation: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/delegates", response_model=List[ApprovalDelegate])
async def get_approval_delegations(
    include_inactive: bool = Query(False, description="Include inactive delegations"),
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
):
    """Get approval delegations for the current user."""
    try:
        require_non_viewer(current_user)

        if include_inactive:
            from core.models.models_per_tenant import ApprovalDelegate as ApprovalDelegateModel
            delegations = (
                approval_service.db.query(ApprovalDelegateModel)
                .filter(ApprovalDelegateModel.approver_id == current_user.id)
                .order_by(ApprovalDelegateModel.created_at.desc())
                .all()
            )
        else:
            delegations = approval_service.get_active_delegations(current_user.id)

        logger.info("Retrieved %d delegations for user %s", len(delegations), current_user.id)
        return delegations

    except Exception as e:
        logger.error("Error retrieving delegations for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/delegates/{delegation_id}", response_model=ApprovalDelegate)
async def update_approval_delegation(
    delegation_id: int,
    delegation_data: ApprovalDelegateUpdate,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing approval delegation (e.g. extend end date or deactivate)."""
    try:
        require_non_viewer(current_user)

        from core.models.models_per_tenant import ApprovalDelegate as ApprovalDelegateModel

        delegation = db.query(ApprovalDelegateModel).filter(
            and_(
                ApprovalDelegateModel.id == delegation_id,
                ApprovalDelegateModel.approver_id == current_user.id,
            )
        ).first()

        if not delegation:
            raise HTTPException(status_code=404, detail=f"Delegation {delegation_id} not found or access denied")

        original_values = {
            "start_date": delegation.start_date.isoformat(),
            "end_date": delegation.end_date.isoformat(),
            "is_active": delegation.is_active,
        }

        update_data = delegation_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(delegation, field, value)

        delegation.updated_at = datetime.now(timezone.utc)

        if delegation.end_date <= delegation.start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        db.commit()
        db.refresh(delegation)

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
                    "is_active": delegation.is_active,
                },
            },
        )

        logger.info("User %s updated delegation %s", current_user.id, delegation_id)
        return delegation

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error updating delegation %s: %s", delegation_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/delegates/{delegation_id}")
async def deactivate_approval_delegation(
    delegation_id: int,
    current_user: MasterUser = Depends(get_current_user),
    approval_service=Depends(get_approval_service),
    db: Session = Depends(get_db),
):
    """Deactivate an approval delegation immediately."""
    try:
        require_non_viewer(current_user)

        delegation = approval_service.deactivate_delegation(
            delegation_id=delegation_id,
            approver_id=current_user.id,
        )

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="approval_delegation_deactivated",
            resource_type="approval_delegate",
            resource_id=str(delegation_id),
            details={
                "delegate_id": delegation.delegate_id,
                "original_end_date": delegation.end_date.isoformat(),
            },
        )

        logger.info("User %s deactivated delegation %s", current_user.id, delegation_id)
        return {"message": f"Delegation {delegation_id} deactivated successfully"}

    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error deactivating delegation %s: %s", delegation_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")
