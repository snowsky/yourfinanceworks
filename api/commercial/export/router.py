"""
Export Destinations Router

API endpoints for managing export destination configurations.
Supports AWS S3, Azure Blob Storage, Google Cloud Storage, and Google Drive.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from core.models.database import get_db, get_master_db
from core.models.models import MasterUser
from core.models.models_per_tenant import ExportDestinationConfig
from core.routers.auth import get_current_user
from core.services.export_destination_service import ExportDestinationService
from core.schemas.export_destination import (
    ExportDestinationCreate,
    ExportDestinationUpdate,
    ExportDestinationResponse,
    ExportDestinationTestResult,
    ExportDestinationList
)
from core.utils.feature_gate import require_feature
from core.utils.rbac import require_non_viewer, require_admin
from core.utils.audit import log_audit_event
from core.utils.feature_gate import check_feature, check_feature_read_only

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export-destinations", tags=["export-destinations"])


def get_api_key_auth(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_master_db)
) -> tuple[int, int, str]:
    """
    Authenticate using API key and return tenant_id, user_id, and api_client_id.
    
    This is a simplified version for now. In production, this should:
    1. Validate the API key against the APIClient table
    2. Check rate limits
    3. Verify permissions
    4. Return proper context
    
    For now, we'll raise an error as API key auth is not yet fully implemented.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header."
        )
    
    # TODO: Implement full API key authentication
    # For now, this is a placeholder that will be implemented when
    # the batch processing API is fully integrated
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key authentication not yet implemented. Use JWT authentication."
    )


def get_export_destination_service(
    tenant_db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
) -> ExportDestinationService:
    """
    Dependency to get ExportDestinationService with tenant context.
    Uses JWT authentication (standard user authentication).
    """
    return ExportDestinationService(tenant_db, current_user.tenant_id)


# ============================================================================
# Export Destination Management Endpoints
# ============================================================================

@router.post(
    "/",
    response_model=ExportDestinationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create export destination",
    description="Create a new export destination configuration with encrypted credentials"
)
@require_feature("advanced_export")
async def create_export_destination(
    destination: ExportDestinationCreate,
    db: Session = Depends(get_master_db),
    tenant_db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    service: ExportDestinationService = Depends(get_export_destination_service)
):
    """
    Create a new export destination.
    
    Requires admin or write permissions.
    Credentials are encrypted before storage.
    """
    
    # Check permissions
    require_non_viewer(current_user, "create export destinations")
    
    try:
        # Create destination
        destination_config = service.create_destination(
            name=destination.name,
            destination_type=destination.destination_type,
            credentials=destination.credentials,
            config=destination.config,
            user_id=current_user.id,
            is_default=destination.is_default
        )
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="export_destination",
            resource_id=str(destination_config.id),
            resource_name=destination_config.name,
            details={
                "destination_type": destination_config.destination_type,
                "is_default": destination_config.is_default
            },
            status="success"
        )
        
        # Return response with masked credentials
        masked_credentials = service.mask_credentials(destination.credentials)
        
        return ExportDestinationResponse(
            id=destination_config.id,
            tenant_id=destination_config.tenant_id,
            name=destination_config.name,
            destination_type=destination_config.destination_type,
            is_active=destination_config.is_active,
            is_default=destination_config.is_default,
            config=destination_config.config,
            masked_credentials=masked_credentials,
            last_test_at=destination_config.last_test_at,
            last_test_success=destination_config.last_test_success,
            last_test_error=destination_config.last_test_error,
            created_at=destination_config.created_at,
            updated_at=destination_config.updated_at,
            created_by=destination_config.created_by,
            testable=destination_config.destination_type != 'local'
        )
        
    except ValueError as e:
        logger.error(f"Validation error creating export destination: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating export destination: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create export destination"
        )


@router.get(
    "/",
    response_model=ExportDestinationList,
    summary="List export destinations",
    description="List all export destinations for the authenticated tenant"
)
@require_feature("advanced_export")
async def list_export_destinations(
    active_only: bool = True,
    destination_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_master_db),
    tenant_db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    service: ExportDestinationService = Depends(get_export_destination_service)
):
    """
    List all export destinations for the tenant.
    
    By default, only returns active destinations (soft-deleted destinations are excluded).
    Set active_only=false to include inactive destinations.
    Returns masked credentials (only last 4 characters shown).
    Includes connection test status.
    Supports pagination.
    """
    
    try:
        # Get destinations
        destinations = service.list_destinations(
            active_only=active_only,
            destination_type=destination_type
        )
        
        # Apply pagination
        total = len(destinations)
        destinations = destinations[skip:skip + limit]
        
        # Build response with masked credentials
        destination_responses = []
        for dest in destinations:
            try:
                # Get and mask credentials
                credentials = service.get_decrypted_credentials(dest.id)
                masked_credentials = service.mask_credentials(credentials)
            except Exception as e:
                logger.warning(f"Failed to decrypt credentials for destination {dest.id}: {str(e)}")
                masked_credentials = {"error": "Failed to decrypt credentials"}
            
            destination_responses.append(
                ExportDestinationResponse(
                    id=dest.id,
                    tenant_id=dest.tenant_id,
                    name=dest.name,
                    destination_type=dest.destination_type,
                    is_active=dest.is_active,
                    is_default=dest.is_default,
                    config=dest.config,
                    masked_credentials=masked_credentials,
                    last_test_at=dest.last_test_at,
                    last_test_success=dest.last_test_success,
                    last_test_error=dest.last_test_error,
                    created_at=dest.created_at,
                    updated_at=dest.updated_at,
                    created_by=dest.created_by,
                    testable=dest.destination_type != 'local'
                )
            )
        
        return ExportDestinationList(
            destinations=destination_responses,
            total=total
        )
        
    except Exception as e:
        logger.error(f"Error listing export destinations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list export destinations"
        )


@router.get(
    "/{destination_id}",
    response_model=ExportDestinationResponse,
    summary="Get export destination",
    description="Get a specific export destination by ID"
)
async def get_export_destination(
    destination_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    service: ExportDestinationService = Depends(get_export_destination_service)
):
    """
    Get a specific export destination.
    
    Returns masked credentials.
    """
    # Check if advanced_export feature is enabled for read access
    check_feature_read_only("advanced_export", db)
    
    try:
        # Get destination
        destination = service.get_destination(destination_id)
        
        if not destination:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export destination {destination_id} not found"
            )
        
        # Get and mask credentials
        try:
            credentials = service.get_decrypted_credentials(destination_id)
            masked_credentials = service.mask_credentials(credentials)
        except Exception as e:
            logger.warning(f"Failed to decrypt credentials for destination {destination_id}: {str(e)}")
            masked_credentials = {"error": "Failed to decrypt credentials"}
        
        return ExportDestinationResponse(
            id=destination.id,
            tenant_id=destination.tenant_id,
            name=destination.name,
            destination_type=destination.destination_type,
            is_active=destination.is_active,
            is_default=destination.is_default,
            config=destination.config,
            masked_credentials=masked_credentials,
            last_test_at=destination.last_test_at,
            last_test_success=destination.last_test_success,
            last_test_error=destination.last_test_error,
            created_at=destination.created_at,
            updated_at=destination.updated_at,
            created_by=destination.created_by,
            testable=destination.destination_type != 'local'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting export destination {destination_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get export destination"
        )


@router.put(
    "/{destination_id}",
    response_model=ExportDestinationResponse,
    summary="Update export destination",
    description="Update an existing export destination configuration"
)
async def update_export_destination(
    destination_id: int,
    updates: ExportDestinationUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    service: ExportDestinationService = Depends(get_export_destination_service)
):
    """
    Update an export destination.
    
    Allows updating individual credential fields without requiring all fields.
    Re-encrypts credentials after update.
    Requires admin or write permissions.
    """
    # Check if advanced_export feature is enabled
    check_feature("advanced_export", db)
    
    # Check permissions
    require_non_viewer(current_user, "update export destinations")
    
    try:
        # Update destination
        update_dict = updates.model_dump(exclude_unset=True)
        destination_config = service.update_destination(
            destination_id=destination_id,
            updates=update_dict
        )
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="export_destination",
            resource_id=str(destination_config.id),
            resource_name=destination_config.name,
            details={
                "updated_fields": list(update_dict.keys())
            },
            status="success"
        )
        
        # Get and mask credentials
        try:
            credentials = service.get_decrypted_credentials(destination_id)
            masked_credentials = service.mask_credentials(credentials)
        except Exception as e:
            logger.warning(f"Failed to decrypt credentials for destination {destination_id}: {str(e)}")
            masked_credentials = {"error": "Failed to decrypt credentials"}
        
        return ExportDestinationResponse(
            id=destination_config.id,
            tenant_id=destination_config.tenant_id,
            name=destination_config.name,
            destination_type=destination_config.destination_type,
            is_active=destination_config.is_active,
            is_default=destination_config.is_default,
            config=destination_config.config,
            masked_credentials=masked_credentials,
            last_test_at=destination_config.last_test_at,
            last_test_success=destination_config.last_test_success,
            last_test_error=destination_config.last_test_error,
            created_at=destination_config.created_at,
            updated_at=destination_config.updated_at,
            created_by=destination_config.created_by,
            testable=destination_config.destination_type != 'local'
        )
        
    except ValueError as e:
        logger.error(f"Validation error updating export destination {destination_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating export destination {destination_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update export destination"
        )


@router.post(
    "/{destination_id}/test",
    response_model=ExportDestinationTestResult,
    summary="Test export destination connection",
    description="Test connection to an export destination using stored credentials"
)
async def test_export_destination(
    destination_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    service: ExportDestinationService = Depends(get_export_destination_service)
):
    """
    Test connection to an export destination.
    
    Updates last_test_at and last_test_success fields.
    Returns test result with error details if failed.
    """
    # Check if advanced_export feature is enabled
    check_feature("advanced_export", db)
    
    try:
        # Test connection
        success, error_message = await service.test_connection(destination_id)
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="TEST",
            resource_type="export_destination",
            resource_id=str(destination_id),
            resource_name=f"Destination {destination_id}",
            details={
                "success": success,
                "error": error_message
            },
            status="success" if success else "failure"
        )
        
        from datetime import datetime, timezone
        
        return ExportDestinationTestResult(
            success=success,
            message="Connection test successful" if success else "Connection test failed",
            error_details=error_message,
            tested_at=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        logger.error(f"Error testing export destination {destination_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test export destination: {str(e)}"
        )


@router.delete(
    "/{destination_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete export destination",
    description="Soft delete an export destination (set is_active=false)"
)
async def delete_export_destination(
    destination_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    service: ExportDestinationService = Depends(get_export_destination_service)
):
    """
    Soft delete an export destination.
    
    Sets is_active=false.
    Validates no active batch jobs are using this destination.
    Requires admin permissions.
    """
    # Check if advanced_export feature is enabled
    check_feature("advanced_export", db)
    
    # Check permissions - require admin for deletion
    require_admin(current_user, "delete export destinations")
    
    try:
        # Get destination name for audit log
        destination = service.get_destination(destination_id)
        if not destination:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export destination {destination_id} not found"
            )
        
        destination_name = destination.name
        
        # Delete destination
        service.delete_destination(destination_id)
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE",
            resource_type="export_destination",
            resource_id=str(destination_id),
            resource_name=destination_name,
            details={
                "soft_delete": True
            },
            status="success"
        )
        
        return None
        
    except ValueError as e:
        logger.error(f"Validation error deleting export destination {destination_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting export destination {destination_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete export destination"
        )
