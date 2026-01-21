from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List
import logging
from pydantic import BaseModel

from db_init import get_master_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.services.organization_join_service import OrganizationJoinService
from core.services.user_role_service import UserRoleService
from core.schemas.organization_join import (
    OrganizationJoinRequestCreate,
    OrganizationJoinRequestRead,
    OrganizationJoinRequestUpdate,
    OrganizationLookup,
    OrganizationLookupResult,
    OrganizationJoinResponse,
    OrganizationJoinRequestList
)

router = APIRouter(prefix="/organization-join", tags=["organization-join"])
logger = logging.getLogger(__name__)

@router.post("/lookup", response_model=OrganizationLookupResult)
async def lookup_organization(
    request: OrganizationLookup,
    db: Session = Depends(get_master_db)
):
    """
    Look up an organization by name to check if it exists.
    This endpoint is used during signup to see if a user can request to join.
    """
    service = OrganizationJoinService(db)
    return service.lookup_organization(request.organization_name)

@router.post("/request", response_model=OrganizationJoinResponse)
async def create_join_request(
    request_data: OrganizationJoinRequestCreate,
    db: Session = Depends(get_master_db)
):
    """
    Create a request to join an existing organization.
    This is an alternative to the regular signup flow.
    """
    service = OrganizationJoinService(db)
    return service.create_join_request(request_data)

@router.get("/pending", response_model=List[OrganizationJoinRequestRead])
async def get_pending_requests(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db)
):
    """
    Get pending join requests for the current user's organization.
    Only admins can view join requests.
    """
    # Check if user has admin privileges using centralized service
    if not UserRoleService.is_admin_user(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only administrators can view join requests. Current role: {UserRoleService.get_user_role(db, current_user.id)}"
        )
    
    service = OrganizationJoinService(db)
    return service.get_pending_requests(tenant_id=current_user.tenant_id)

@router.get("/all-pending", response_model=List[OrganizationJoinRequestRead])
async def get_all_pending_requests(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db)
):
    """
    Get all pending join requests across all organizations.
    Only superusers can view all requests.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can view all join requests"
        )
    
    service = OrganizationJoinService(db)
    return service.get_pending_requests()

@router.get("/{request_id}", response_model=OrganizationJoinRequestRead)
async def get_join_request(
    request_id: int,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db)
):
    """
    Get details of a specific join request.
    """
    service = OrganizationJoinService(db)
    request = service.get_request_by_id(request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Join request not found"
        )
    
    # Check permissions - admin can view requests for their org, superuser can view all
    if not current_user.is_superuser and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view this request"
        )
    
    if current_user.role == "admin" and request.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view requests for your organization"
        )
    
    return request

@router.post("/{request_id}/approve", response_model=OrganizationJoinResponse)
async def approve_join_request(
    request_id: int,
    approval_data: OrganizationJoinRequestUpdate,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db)
):
    """
    Approve or reject a join request.
    Only admins can approve requests for their organization.
    """
    if current_user.role not in ["admin"] and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can approve join requests"
        )
    
    service = OrganizationJoinService(db)
    
    # Get the request to check permissions
    request = service.get_request_by_id(request_id)
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Join request not found"
        )
    
    # Check if admin can approve this request (must be for their org)
    if current_user.role == "admin" and request.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only approve requests for your organization"
        )
    
    return service.approve_join_request(request_id, current_user.id, approval_data)

@router.post("/cleanup-expired")
async def cleanup_expired_requests(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db)
):
    """
    Clean up expired join requests.
    Only superusers can run cleanup operations.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can run cleanup operations"
        )
    
    service = OrganizationJoinService(db)
    count = service.cleanup_expired_requests()
    
    return {
        "message": f"Cleaned up {count} expired join requests",
        "count": count
    }
