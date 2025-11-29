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
from typing import Optional
from pydantic import BaseModel, Field

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.services.license_service import LicenseService
from core.services.feature_config_service import FeatureConfigService


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
    trial_info: dict
    license_info: Optional[dict] = None
    enabled_features: list
    has_all_features: bool


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


# ==================== Endpoints ====================

@router.post("/select-usage-type", response_model=UsageTypeSelectionResponse)
async def select_usage_type(
    request_data: UsageTypeSelectionRequest,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Select usage type: personal (free) or business (30-day trial).
    
    This endpoint must be called when the user first sets up the application.
    - Personal use: Free forever with all features
    - Business use: 30-day trial, then requires license
    
    Can only be called once per installation.
    """
    try:
        license_service = LicenseService(db)
        
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
    db: Session = Depends(get_db)
):
    """
    Get current usage type selection status.
    
    Returns whether the user has selected a usage type and what type was selected.
    """
    try:
        license_service = LicenseService(db)
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
    db: Session = Depends(get_db)
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
        license_service = LicenseService(db)
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
    db: Session = Depends(get_db)
):
    """
    Activate a license key.
    
    Validates the provided license key and activates it for this installation.
    The license key should be a JWT token signed with the vendor's private key.
    
    **Requirements: 1.7**
    """
    try:
        license_service = LicenseService(db)
        
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
    db: Session = Depends(get_db)
):
    """
    Manually validate a license key without activating it.
    
    This endpoint allows checking if a license key is valid before activation.
    Useful for pre-validation in the UI or testing license keys.
    
    **Requirements: 1.7**
    """
    try:
        license_service = LicenseService(db)
        
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
    db: Session = Depends(get_db)
):
    """
    Deactivate the current license and revert to trial mode.
    
    This removes the active license and returns the installation to trial status.
    Useful for testing or switching licenses.
    """
    try:
        license_service = LicenseService(db)
        
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
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deactivate license: {str(e)}"
        )
