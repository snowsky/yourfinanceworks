"""
License Management Router

This router provides customer-side endpoints for:
- Viewing license and trial status
- Activating license keys
- Validating licenses manually
- Checking feature availability

SECURITY MODEL:
- /license/features (PUBLIC): Returns generic feature metadata for UI display
  - No authentication required
  - No tenant-specific data exposed
  - Used by UI before login to show available features

- /license/status (PROTECTED): Returns actual tenant license status
  - Requires authentication
  - Returns real trial/license data for the authenticated tenant
  - Use this for actual license enforcement

- All other endpoints (PROTECTED): Require authentication
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import os
from typing import Optional
from pydantic import BaseModel, Field

from core.models.database import get_db, get_master_db
from core.routers.auth import get_current_user
from core.services.license_service import LicenseService
from core.services.feature_config_service import FeatureConfigService
from core.utils.rbac import require_admin_or_superuser, require_superuser
from core.utils.audit import log_audit_event, log_audit_event_master
from pathlib import Path


router = APIRouter(prefix="/license", tags=["license"])


# ==================== Request/Response Models ====================

class UsageTypeSelectionRequest(BaseModel):
    """Request model for usage type selection"""
    usage_type: str = Field(..., description="Usage type: 'personal' or 'business'")


class UsageTypeSelectionResponse(BaseModel):
    """Response model for usage type selection"""
    success: bool
    message: str
    usage_type: str
    license_status: str
    trial_days_remaining: Optional[int] = None
    trial_end_date: Optional[str] = None
    error: Optional[str] = None


class UsageTypeStatusResponse(BaseModel):
    """Response model for usage type status"""
    usage_type: Optional[str]
    usage_type_selected: bool
    usage_type_selected_at: Optional[str]
    license_status: str


class LicenseActivationRequest(BaseModel):
    """Request model for license activation"""
    license_key: str = Field(..., description="JWT license key to activate")


class LicenseActivationResponse(BaseModel):
    """Response model for license activation"""
    success: bool
    message: str
    features: Optional[list] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None


class LicenseStatusResponse(BaseModel):
    """Response model for license status"""
    installation_id: str
    license_status: str
    usage_type: Optional[str]
    usage_type_selected: bool
    is_licensed: bool
    is_personal: bool
    is_trial: bool
    is_license_expired: bool  # True if license was active but now expired
    effective_source: str     # 'local', 'global', or 'none'
    license_scope: Optional[str] = None # 'local' or 'global'
    license_type: Optional[str] = None
    trial_info: dict
    license_info: Optional[dict] = None
    global_license_info: Optional[dict] = None
    enabled_features: list
    expired_features: list  # Features that were licensed but now expired
    has_all_features: bool
    allow_password_signup: bool = True
    allow_sso_signup: bool = True
    allow_password_signup: bool = True
    allow_sso_signup: bool = True
    user_licensing_info: Optional[dict] = None
    is_exempt_from_global_license: bool = False
    custom_installation_id: Optional[str] = None
    original_installation_id: Optional[str] = None


class RegenerateIdResponse(BaseModel):
    """Response model for ID regeneration"""
    success: bool
    message: str
    installation_id: str


class SwitchModeRequest(BaseModel):
    """Request model for switching license mode"""
    mode: str = Field(..., description="Mode to switch to: 'global' or 'local'")


class SwitchModeResponse(BaseModel):
    """Response model for mode switching"""
    success: bool
    message: str


class UpdateInstallationIdRequest(BaseModel):
    """Request model for updating installation ID"""
    installation_id: str = Field(..., description="New installation ID (UUID format)")


class UpdateInstallationIdResponse(BaseModel):
    """Response model for installation ID update"""
    success: bool
    message: str



class LicenseValidationResponse(BaseModel):
    """Response model for license validation"""
    valid: bool
    message: str
    payload: Optional[dict] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class FeatureAvailabilityResponse(BaseModel):
    """Response model for feature availability"""
    features: list
    trial_status: dict
    license_status: str


class TenantCapacityControlRequest(BaseModel):
    """Request model for updating tenant capacity control (counts vs exempt)"""
    counts: bool


class TenantLicenseInfo(BaseModel):
    """Model for tenant license monitoring info"""
    id: int
    name: str
    is_active: bool
    is_enabled: bool
    count_against_license: bool


class UserLicenseInfo(BaseModel):
    """Model for user license monitoring info"""
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    count_against_license: bool


# ==================== Endpoints ====================

@router.post("/select-usage-type", response_model=UsageTypeSelectionResponse)
async def select_usage_type(
    request_data: UsageTypeSelectionRequest,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Select usage type: personal (free) or business (30-day trial).

    This endpoint must be called when the user first sets up the application.
    - Personal use: Free forever with all features
    - Business use: 30-day trial, then requires license

    Can only be called once per installation.
    """
    try:
        license_service = LicenseService(db, master_db=master_db)

        # Extract request metadata
        user_id = current_user.id if hasattr(current_user, 'id') else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Select usage type
        result = license_service.select_usage_type(
            usage_type=request_data.usage_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": result.get("error", "SELECTION_FAILED"),
                    "message": result["message"]
                }
            )

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="SELECT_USAGE_TYPE",
            resource_type="LICENSE",
            details={
                "usage_type": request_data.usage_type,
                "message": result["message"]
            },
            ip_address=ip_address,
            user_agent=user_agent
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to select usage type: {str(e)}"
        )


@router.get("/usage-type-status", response_model=UsageTypeStatusResponse)
async def get_usage_type_status(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Get current usage type selection status.

    Returns whether the user has selected a usage type and what type was selected.
    """
    try:
        license_service = LicenseService(db, master_db=master_db)
        status = license_service.get_usage_type_status()
        return status
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve usage type status: {str(e)}"
        )


@router.get("/status", response_model=LicenseStatusResponse)
async def get_license_status(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Get current license and trial status.

    Returns comprehensive information about:
    - License status (trial, active, expired)
    - Trial information (days remaining, grace period)
    - Licensed features
    - Customer information

    **Requirements: 1.7**
    """
    try:
        license_service = LicenseService(db, master_db=master_db)
        status = license_service.get_license_status()

        # Convert datetime objects to ISO format strings for JSON serialization
        if status.get("trial_info"):
            trial_info = status["trial_info"]
            if trial_info.get("trial_start_date"):
                trial_info["trial_start_date"] = trial_info["trial_start_date"].isoformat()
            if trial_info.get("trial_end_date"):
                trial_info["trial_end_date"] = trial_info["trial_end_date"].isoformat()
            if trial_info.get("grace_period_end"):
                trial_info["grace_period_end"] = trial_info["grace_period_end"].isoformat()

            # Add trial info to top level for frontend compatibility
            status["trial_start_date"] = trial_info.get("trial_start_date")
            status["trial_end_date"] = trial_info.get("trial_end_date")
            status["trial_days_remaining"] = trial_info.get("days_remaining")
            status["in_grace_period"] = trial_info.get("in_grace_period", False)

        if status.get("license_info"):
            license_info = status["license_info"]
            if license_info.get("activated_at"):
                license_info["activated_at"] = license_info["activated_at"].isoformat()
            if license_info.get("expires_at"):
                license_info["expires_at"] = license_info["expires_at"].isoformat()

            # Add license info to top level for frontend compatibility
            status["license_expires_at"] = license_info.get("expires_at")
            status["license_activated_at"] = license_info.get("activated_at")

            # Calculate days remaining for license
            if license_info.get("expires_at"):
                from datetime import datetime, timezone
                try:
                    expires_at = datetime.fromisoformat(license_info["expires_at"].replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    days_remaining = (expires_at - now).days
                    status["license_days_remaining"] = max(0, days_remaining)
                except:
                    status["license_days_remaining"] = None

        return status
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve license status: {str(e)}"
        )


@router.post("/activate", response_model=LicenseActivationResponse)
async def activate_license(
    request_data: LicenseActivationRequest,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Activate a license key.

    Validates the provided license key and activates it for this installation.
    The license key should be a JWT token signed with the vendor's private key.

    **Requirements: 1.7**
    """
    try:
        license_service = LicenseService(db, master_db=master_db)

        # Extract request metadata
        user_id = current_user.id if hasattr(current_user, 'id') else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Activate license
        result = license_service.activate_license(
            license_key=request_data.license_key,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Convert datetime to ISO format string if present
        if result.get("expires_at"):
            result["expires_at"] = result["expires_at"].isoformat()

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "ACTIVATION_FAILED",
                    "message": result["message"],
                    "details": result.get("error")
                }
            )

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="ACTIVATE_LICENSE",
            resource_type="LICENSE",
            resource_name=result.get("customer_name"),
            details={
                "features": result.get("features"),
                "expires_at": result.get("expires_at"),
                "message": result["message"]
            },
            ip_address=ip_address,
            user_agent=user_agent
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate license: {str(e)}"
        )


@router.post("/validate", response_model=LicenseValidationResponse)
async def validate_license(
    request_data: LicenseActivationRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Manually validate a license key without activating it.

    This endpoint allows checking if a license key is valid before activation.
    Useful for pre-validation in the UI or testing license keys.

    **Requirements: 1.7**
    """
    try:
        license_service = LicenseService(db, master_db=master_db)

        # Verify license
        verification = license_service.verify_license(request_data.license_key)

        if verification["valid"]:
            return {
                "valid": True,
                "message": "License key is valid",
                "payload": verification["payload"],
                "error": None,
                "error_code": None
            }
        else:
            return {
                "valid": False,
                "message": verification["error"],
                "payload": verification.get("payload"),
                "error": verification["error"],
                "error_code": verification["error_code"]
            }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate license: {str(e)}"
        )


@router.post("/regenerate-id", response_model=RegenerateIdResponse)
async def regenerate_installation_id(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Regenerate the installation ID for the current tenant.

    This allows a tenant to break away from the global license system and use a dedicated license.
    This action can only be performed ONCE per tenant.

    Requires Admin privileges.
    """
    require_admin_or_superuser(current_user, "regenerate installation id")

    try:
        license_service = LicenseService(db, master_db=master_db)

        # Extract request metadata
        user_id = current_user.id if hasattr(current_user, 'id') else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = license_service.regenerate_installation_id(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="REGENERATE_INSTALLATION_ID",
            resource_type="LICENSE",
            details={
                "message": result["message"],
                "new_id": result.get("installation_id")
            },
            ip_address=ip_address,
            user_agent=user_agent
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate installation ID: {str(e)}"
        )


@router.post("/switch-mode", response_model=SwitchModeResponse)
async def switch_license_mode(
    request_data: SwitchModeRequest,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Switch between 'global' and 'local' license modes.

    - 'global': Reverts to using the system-wide global installation ID.
    - 'local': Uses the custom tenant-specific installation ID.

    Requires Admin privileges.
    """
    require_admin_or_superuser(current_user, "switch license mode")

    try:
        license_service = LicenseService(db, master_db=master_db)

        # Extract request metadata
        user_id = current_user.id if hasattr(current_user, 'id') else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = license_service.switch_license_mode(
            mode=request_data.mode,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="SWITCH_LICENSE_MODE",
            resource_type="LICENSE",
            details={
                "mode": request_data.mode,
                "message": result["message"]
            },
            ip_address=ip_address,
            user_agent=user_agent
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch license mode: {str(e)}"
        )


@router.post("/update-installation-id", response_model=UpdateInstallationIdResponse)
async def update_installation_id(
    request_data: UpdateInstallationIdRequest,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Update the installation ID for the current tenant.
    
    This allows setting a custom installation ID for license management.
    
    Requires Admin privileges.
    """
    require_admin_or_superuser(current_user, "update installation id")
    
    try:
        license_service = LicenseService(db, master_db=master_db)
        
        # Validate UUID format
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
        if not uuid_pattern.match(request_data.installation_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid UUID format. Expected format: 123e4567-e89b-12d3-a456-426614174000"
            )
        
        # Extract request metadata
        user_id = current_user.id if hasattr(current_user, 'id') else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        result = license_service.update_installation_id(
            new_installation_id=request_data.installation_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
        
        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE_INSTALLATION_ID",
            resource_type="LICENSE",
            details={
                "old_id": result.get("old_installation_id"),
                "new_id": request_data.installation_id,
                "message": result["message"]
            },
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update installation ID: {str(e)}"
        )


@router.get("/features", response_model=FeatureAvailabilityResponse)
async def get_feature_availability():
    """
    Get list of all features with their availability status.

    This endpoint is public and returns generic feature information.
    It does NOT expose any tenant-specific or sensitive data.

    What it returns:
    - Feature metadata (names, descriptions, categories) - public information
    - All features marked as "enabled" - this is just for UI display
    - Generic trial status - no actual tenant data

    Security note: This is intentionally public to allow the UI to load
    and display available features before authentication. Actual feature
    enforcement happens server-side in protected endpoints.

    **Requirements: 1.7, 1.8**
    """
    try:
        # Get all features with metadata (public information)
        all_features = FeatureConfigService.get_all_features()

        # Return all features as "available" for display purposes
        # Actual feature gating happens in protected endpoints
        features_with_status = []
        for feature in all_features:
            features_with_status.append({
                "id": feature["id"],
                "name": feature["name"],
                "description": feature["description"],
                "category": feature["category"],
                "enabled": True  # For UI display only - not actual authorization
            })

        # Return generic trial status (no tenant-specific data)
        trial_status = {
            "is_trial": True,
            "trial_days_remaining": 30,
            "in_grace_period": False,
            "grace_period_days_remaining": 0
        }

        return {
            "features": features_with_status,
            "trial_status": trial_status,
            "license_status": "trial"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve feature availability: {str(e)}"
        )


@router.post("/deactivate")
async def deactivate_license(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Deactivate the current license and revert to trial mode.

    This removes the active license and returns the installation to trial status.
    Useful for testing or switching licenses.
    """
    try:
        license_service = LicenseService(db, master_db=master_db)

        # Extract request metadata
        user_id = current_user.id if hasattr(current_user, 'id') else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Deactivate license
        result = license_service.deactivate_license(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Log audit event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DEACTIVATE_LICENSE",
            resource_type="LICENSE",
            details={"message": result["message"]},
            ip_address=ip_address,
            user_agent=user_agent
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deactivate license: {str(e)}"
        )


@router.get("/license-request-data")
async def get_license_request_data(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """
    Get the license request data including public key, installation ID, and license request URL.
    Requires admin or superuser privileges.
    """
    require_admin_or_superuser(current_user, "get license request data")

    try:
        # Get installation ID from license service
        license_service = LicenseService(db, master_db=master_db)
        status = license_service.get_license_status()
        installation_id = status.get("installation_id")

        if not installation_id:
            raise HTTPException(status_code=500, detail="Installation ID not found")

        # Define keys directory relative to this file
        keys_dir = Path(__file__).parent.parent / "keys"
        public_key_path = keys_dir / "public_key.pem"

        if not public_key_path.exists() or public_key_path.stat().st_size < 100:
            # If symlink doesn't exist or is a placeholder, try to find the latest versioned key
            versioned_keys = list(keys_dir.glob("public_key_v*.pem"))
            if versioned_keys:
                # Sort by version number (e.g., v2, v3)
                def version_key(v):
                    try:
                        return int(v.stem.split('_')[-1][1:])
                    except:
                        return 0
                public_key_path = sorted(versioned_keys, key=version_key)[-1]
            else:
                if not public_key_path.exists():
                    raise HTTPException(status_code=404, detail="Public key file not found")
                # If it exists but is too small and no versioned keys found, we use it

        # Read the public key content
        with open(public_key_path, "r") as f:
            content = f.read()

        # Log sensitive data access
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="GET_LICENSE_REQUEST_DATA",
            resource_type="LICENSE_KEY",
            details={
                "installation_id": installation_id,
                "note": "User accessed public key for license activation"
            }
        )

        return {
            "public_key": content,
            "installation_id": installation_id,
            "license_request_url": os.getenv("LICENSE_KEY_REQUEST_URL")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get license request data: {str(e)}")


@router.post("/activate-global", response_model=LicenseActivationResponse)
async def activate_global_license(
    request_data: LicenseActivationRequest,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """Activate a system-wide license (Super Admin only)."""
    require_superuser(current_user, "activate global license")

    try:
        license_service = LicenseService(db, master_db=master_db)

        user_id = current_user.id if hasattr(current_user, 'id') else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = license_service.activate_global_license(
            license_key=request_data.license_key,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        if result.get("expires_at"):
            result["expires_at"] = result["expires_at"].isoformat()

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result)

        # Log audit event in master database
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="ACTIVATE_GLOBAL_LICENSE",
            resource_type="GLOBAL_LICENSE",
            details={
                "expires_at": result.get("expires_at"),
                "message": result.get("message")
            },
            ip_address=ip_address,
            user_agent=user_agent
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deactivate-global")
async def deactivate_global_license(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """Deactivate the system-wide license (Super Admin only)."""
    require_superuser(current_user, "deactivate global license")

    try:
        license_service = LicenseService(db, master_db=master_db)

        user_id = current_user.id if hasattr(current_user, 'id') else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = license_service.deactivate_global_license(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Log audit event in master database
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DEACTIVATE_GLOBAL_LICENSE",
            resource_type="GLOBAL_LICENSE",
            details={"message": result.get("message")},
            ip_address=ip_address,
            user_agent=user_agent
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tenants", response_model=list[TenantLicenseInfo])
async def get_tenants_license_info(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """Get license monitoring info for all tenants (Super Admin only)."""
    require_superuser(current_user, "view tenant license info")

    try:
        license_service = LicenseService(db, master_db=master_db)
        return license_service.get_all_tenants_license_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tenants/{tenant_id}/update-capacity-control")
async def update_tenant_capacity_control(
    tenant_id: int,
    request_data: TenantCapacityControlRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """Update whether a tenant counts against the global limit (Super Admin only)."""
    require_superuser(current_user, "update tenant capacity control")

    try:
        license_service = LicenseService(db, master_db=master_db)
        success = license_service.update_tenant_capacity_control(tenant_id, request_data.counts)
        if not success:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Log audit event in master database
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE_TENANT_CAPACITY_CONTROL",
            resource_type="TENANT",
            resource_id=str(tenant_id),
            details={"counts_against_license": request_data.counts}
        )

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/users", response_model=list[UserLicenseInfo])
async def get_users_license_info(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """Get license monitoring info for all users (Super Admin only)."""
    require_superuser(current_user, "view user license info")

    try:
        license_service = LicenseService(db, master_db=master_db)
        return license_service.get_all_users_license_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/users/{user_id}/update-capacity-control")
async def update_user_capacity_control(
    user_id: int,
    request_data: TenantCapacityControlRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
):
    """Update whether a user counts against the global limit (Super Admin only)."""
    require_superuser(current_user, "update user capacity control")

    try:
        license_service = LicenseService(db, master_db=master_db)
        success = license_service.update_user_capacity_control(user_id, request_data.counts)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")

        # Log audit event in master database
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE_USER_CAPACITY_CONTROL",
            resource_type="USER",
            resource_id=str(user_id),
            details={"counts_against_license": request_data.counts}
        )

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
