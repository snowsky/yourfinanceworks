"""
Feature Gate Decorator and Utilities

This module provides decorators and helper functions for gating API endpoints
and code execution behind license checks.
"""

from functools import wraps
from typing import Optional
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from core.models.database import get_db, set_tenant_context
from core.services.license_service import LicenseService


def check_feature(feature_id: str, db: Session, error_message: Optional[str] = None):
    """
    Check if a feature is enabled and raise HTTPException if not.

    This is a helper function to be called inside endpoint functions after
    dependencies are resolved. Use this instead of the decorator for endpoints
    that need tenant context to be set first (like API key authenticated endpoints).

    Usage:
        @router.post("/batch/upload")
        async def upload_batch(
            service: BatchProcessingService = Depends(get_batch_processing_service)
        ):
            check_feature("batch_processing", service.db)
            # ... rest of endpoint

    Args:
        feature_id: Feature ID to check (e.g., "batch_processing")
        db: Database session (must have tenant context set)
        error_message: Optional custom error message

    Raises:
        HTTPException: 402 Payment Required if feature is not licensed
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        license_service = LicenseService(db)
        has_feature = license_service.has_feature_for_gating(feature_id)
        
        # Log for debugging
        license_status = license_service.get_license_status()
        logger.debug(f"Feature gate check for '{feature_id}': has_feature={has_feature}, license_status={license_status}")

        if not has_feature:
            # Get trial status for better error message
            trial_status = license_service.get_trial_status()
            license_status = license_service.get_license_status()

            # Determine appropriate message
            if trial_status["is_trial"] and not trial_status["trial_active"]:
                if trial_status["in_grace_period"]:
                    message = (
                        f"Your trial has expired. You are in a grace period. "
                        f"Please activate a license to continue using the '{feature_id}' feature."
                    )
                else:
                    message = (
                        f"Your trial has expired. Please activate a license to use the '{feature_id}' feature."
                    )
            elif license_status["is_licensed"]:
                message = (
                    f"The '{feature_id}' feature is not included in your current license. "
                    f"Please upgrade your license to access this feature."
                )
            else:
                message = (
                    f"The '{feature_id}' feature requires a valid license. "
                    f"Please activate a license or start a trial."
                )

            # Use custom message if provided
            if error_message:
                message = error_message

            raise HTTPException(
                status_code=402,
                detail={
                    "error": "FEATURE_NOT_LICENSED",
                    "message": message,
                    "feature_id": feature_id,
                    "license_status": license_status["license_status"],
                    "trial_active": trial_status["trial_active"],
                    "in_grace_period": trial_status["in_grace_period"],
                    "upgrade_required": True
                }
            )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # If license table doesn't exist or other DB error, allow access
        # This handles cases where the database hasn't been fully initialized
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"License check failed for feature '{feature_id}': {str(e)}. Allowing access.")
        pass


def check_feature_read_only(feature_id: str, db: Session, error_message: Optional[str] = None):
    """
    Check if a feature is enabled for read-only access and raise HTTPException if not.
    This allows users to view existing resources even with expired licenses.

    Args:
        feature_id: Feature ID to check (e.g., "cloud_storage", "batch_processing")
        db: Database session (must have tenant context set)
        error_message: Optional custom error message

    Raises:
        HTTPException: 402 Payment Required if feature is not licensed for read access
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        license_service = LicenseService(db)
        has_feature = license_service.has_feature_read_only(feature_id)
        
        # Log for debugging
        license_status = license_service.get_license_status()
        logger.debug(f"Feature gate check for '{feature_id}': has_feature={has_feature}, license_status={license_status}")

        if not has_feature:
            # Get trial status for better error message
            trial_status = license_service.get_trial_status()
            license_status = license_service.get_license_status()

            # Determine appropriate message
            if trial_status["is_trial"] and not trial_status["trial_active"]:
                if trial_status["in_grace_period"]:
                    message = (
                        f"Your trial has expired. You are in a grace period. "
                        f"Please activate a license to continue viewing the '{feature_id}' resources."
                    )
                else:
                    message = (
                        f"Your trial has expired. Please activate a license to view the '{feature_id}' resources."
                    )
            elif license_status["is_licensed"]:
                message = (
                    f"The '{feature_id}' feature is not included in your current license. "
                    f"Please upgrade your license to access these resources."
                )
            else:
                message = (
                    f"The '{feature_id}' feature requires a valid license. "
                    f"Please activate a license or start a trial."
                )

            # Use custom message if provided
            if error_message:
                message = error_message

            raise HTTPException(
                status_code=402,
                detail={
                    "error": "FEATURE_NOT_LICENSED",
                    "message": message,
                    "feature_id": feature_id,
                    "license_status": license_status["license_status"],
                    "trial_active": trial_status["trial_active"],
                    "in_grace_period": trial_status["in_grace_period"],
                    "upgrade_required": True
                }
            )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # If license table doesn't exist or other DB error, allow access
        # This handles cases where the database hasn't been fully initialized
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"License check failed for feature '{feature_id}': {str(e)}. Allowing access.")
        pass


def require_feature(feature_id: str, error_message: Optional[str] = None):
    """
    Decorator to gate API endpoints behind feature license checks.
    
    Returns HTTP 402 (Payment Required) when feature is not licensed.
    
    NOTE: This decorator works best with JWT authentication where tenant context
    is set before decorator runs. For API key authentication, use check_feature()
    inside endpoint function instead.
    
    Usage:
        @router.post("/ai/chat")
        @require_feature("ai_chat")
        async def chat_endpoint(...):
            pass
    
    Args:
        feature_id: Feature ID to check (e.g., "ai_invoice", "tax_integration")
        error_message: Optional custom error message
        
    Returns:
        Decorator function that checks feature availability
        
    Raises:
        HTTPException: 402 Payment Required if feature is not licensed
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract db session from kwargs or create new one
            db: Optional[Session] = kwargs.get('db')
            tenant_db: Optional[Session] = kwargs.get('tenant_db')
            close_db = False
            
            if db is None:
                # Try to get db from args (if it's a dependency)
                for arg in args:
                    if isinstance(arg, Session):
                        db = arg
                        break
            
            # For feature checking, prefer tenant_db if available, otherwise use db
            feature_check_db = tenant_db if tenant_db is not None else db
            
            if feature_check_db is None:
                # Create a new session - this will check tenant context
                # If tenant context is not set, get_db() will raise TENANT_CONTEXT_REQUIRED
                try:
                    feature_check_db = next(get_db())
                    close_db = True
                except HTTPException:
                    # If tenant context not set and we have a user, try to set it
                    # Extract user from args/kwargs
                    user = None
                    for arg in args:
                        if hasattr(arg, 'tenant_id'):
                            user = arg
                            break
                    
                    if user is None:
                        # Try to get user from kwargs
                        user = kwargs.get('current_user')
                    
                    if user and hasattr(user, 'tenant_id'):
                        # Set tenant context manually
                        set_tenant_context(user.tenant_id)
                        try:
                            feature_check_db = next(get_db())
                            close_db = True
                        except Exception as e:
                            # If still fails, raise original error
                            raise HTTPException(
                                status_code=402,
                                detail={
                                    "error": "FEATURE_CHECK_FAILED",
                                    "message": f"Unable to verify feature license: {str(e)}",
                                    "feature_id": feature_id
                                }
                            )
                    else:
                        # Re-raise HTTPException (like TENANT_CONTEXT_REQUIRED)
                        raise
            
            try:
                check_feature(feature_id, feature_check_db, error_message)
                # Feature is enabled, execute the function
                return await func(*args, **kwargs)
            finally:
                if close_db:
                    feature_check_db.close()
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract db session from kwargs or create new one
            db: Optional[Session] = kwargs.get('db')
            tenant_db: Optional[Session] = kwargs.get('tenant_db')
            close_db = False
            
            if db is None:
                # Try to get db from args (if it's a dependency)
                for arg in args:
                    if isinstance(arg, Session):
                        db = arg
                        break
            
            # For feature checking, prefer tenant_db if available, otherwise use db
            feature_check_db = tenant_db if tenant_db is not None else db
            
            if feature_check_db is None:
                # Create a new session - this will check tenant context
                # If tenant context is not set, get_db() will raise TENANT_CONTEXT_REQUIRED
                try:
                    feature_check_db = next(get_db())
                    close_db = True
                except HTTPException:
                    # If tenant context not set and we have a user, try to set it
                    # Extract user from args/kwargs
                    user = None
                    for arg in args:
                        if hasattr(arg, 'tenant_id'):
                            user = arg
                            break
                    
                    if user is None:
                        # Try to get user from kwargs
                        user = kwargs.get('current_user')
                    
                    if user and hasattr(user, 'tenant_id'):
                        # Set tenant context manually
                        set_tenant_context(user.tenant_id)
                        try:
                            feature_check_db = next(get_db())
                            close_db = True
                        except Exception as e:
                            # If still fails, raise original error
                            raise HTTPException(
                                status_code=402,
                                detail={
                                    "error": "FEATURE_CHECK_FAILED",
                                    "message": f"Unable to verify feature license: {str(e)}",
                                    "feature_id": feature_id
                                }
                            )
                    else:
                        # Re-raise HTTPException (like TENANT_CONTEXT_REQUIRED)
                        raise
            
            try:
                check_feature(feature_id, feature_check_db, error_message)
                # Feature is enabled, execute the function
                return func(*args, **kwargs)
                
            finally:
                if close_db:
                    feature_check_db.close()
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def feature_enabled(feature_id: str, db: Optional[Session] = None) -> bool:
    """
    Helper function to check feature status in code.
    
    This is useful for conditional execution within endpoints or services.
    
    Usage:
        if feature_enabled("ai_invoice", db):
            # Execute AI processing
        else:
            # Use fallback method
    
    Args:
        feature_id: Feature ID to check (e.g., "ai_invoice", "tax_integration")
        db: Database session (optional, will create new one if not provided)
        
    Returns:
        True if feature is enabled, False otherwise
    """
    close_db = False
    
    if db is None:
        db = next(get_db())
        close_db = True
    
    try:
        license_service = LicenseService(db)
        return license_service.has_feature_for_gating(feature_id)
    finally:
        if close_db:
            db.close()


def get_enabled_features(db: Optional[Session] = None) -> list:
    """
    Get list of all enabled features.
    
    Args:
        db: Database session (optional, will create new one if not provided)
        
    Returns:
        List of enabled feature IDs
    """
    close_db = False
    
    if db is None:
        db = next(get_db())
        close_db = True
    
    try:
        license_service = LicenseService(db)
        return license_service.get_enabled_features()
    finally:
        if close_db:
            db.close()
