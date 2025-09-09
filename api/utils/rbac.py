from fastapi import HTTPException, status
from typing import List, Union
from models.models_per_tenant import User
from models.models import MasterUser
from constants.error_codes import ONLY_SUPERUSERS, ROLE_NOT_ALLOWED


def require_roles(
    user, 
    required_roles: List[str], 
    action: str = "perform this action"
) -> None:
    """
    Check if a user has one of the required roles.
    
    Args:
        user: The current user (User or MasterUser)
        required_roles: List of roles that are allowed to perform the action
        action: Description of the action being performed (for error message)
    
    Raises:
        HTTPException: 403 Forbidden if user doesn't have required role
    """
    if user.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ROLE_NOT_ALLOWED
        )


def require_non_viewer(user, action: str = "perform this action") -> None:
    """
    Check if a user is not a viewer (shortcut for common case).
    
    Args:
        user: The current user (User or MasterUser)
        action: Description of the action being performed (for error message)
    
    Raises:
        HTTPException: 403 Forbidden if user is a viewer
    """
    require_roles(user, ["admin", "user"], action)


def require_admin(user, action: str = "perform this action") -> None:
    """
    Check if a user is an admin (shortcut for admin-only actions).
    
    Args:
        user: The current user (User or MasterUser)
        action: Description of the action being performed (for error message)
    
    Raises:
        HTTPException: 403 Forbidden if user is not an admin
    """
    require_roles(user, ["admin"], action)


def require_superuser(user, action: str = "perform this action") -> None:
    """
    Check if a user is a superuser (for cross-tenant operations).
    
    Args:
        user: The current user (User or MasterUser)
        action: Description of the action being performed (for error message)
    
    Raises:
        HTTPException: 403 Forbidden if user is not a superuser
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ONLY_SUPERUSERS
        )


def can_user_perform_action(user, required_roles: List[str]) -> bool:
    """
    Check if a user can perform an action without raising an exception.
    
    Args:
        user: The current user (User or MasterUser)
        required_roles: List of roles that are allowed to perform the action
    
    Returns:
        bool: True if user has required role, False otherwise
    """
    return user.role in required_roles


def is_admin(user) -> bool:
    """Check if a user is an admin."""
    return user.role == "admin"


def is_viewer(user) -> bool:
    """Check if a user is a viewer."""
    return user.role == "viewer"

def is_superuser(user) -> bool:
    """Check if a user is a superuser."""
    return user.is_superuser


# Reporting-specific permission functions
def can_generate_reports(user: Union[User, MasterUser]) -> bool:
    """Check if a user can generate reports."""
    return user.role in ["admin", "user"]


def can_manage_report_templates(user: Union[User, MasterUser]) -> bool:
    """Check if a user can create and manage report templates."""
    return user.role in ["admin", "user"]


def can_schedule_reports(user: Union[User, MasterUser]) -> bool:
    """Check if a user can schedule automated reports."""
    return user.role in ["admin", "user"]


def can_access_report_history(user: Union[User, MasterUser]) -> bool:
    """Check if a user can access report history."""
    return user.role in ["admin", "user"]


def can_share_report_templates(user: Union[User, MasterUser]) -> bool:
    """Check if a user can share report templates with others."""
    return user.role in ["admin", "user"]


def can_access_all_reports(user: Union[User, MasterUser]) -> bool:
    """Check if a user can access all reports (admin-only feature)."""
    return user.role == "admin"


def require_report_access(user: Union[User, MasterUser], action: str = "access reports") -> None:
    """
    Check if a user can access reporting features.
    
    Args:
        user: The current user (User or MasterUser)
        action: Description of the action being performed (for error message)
    
    Raises:
        HTTPException: 403 Forbidden if user doesn't have report access
    """
    require_roles(user, ["admin", "user"], action)


def require_report_management(user: Union[User, MasterUser], action: str = "manage reports") -> None:
    """
    Check if a user can manage reports (create templates, schedule, etc.).
    
    Args:
        user: The current user (User or MasterUser)
        action: Description of the action being performed (for error message)
    
    Raises:
        HTTPException: 403 Forbidden if user doesn't have report management access
    """
    require_roles(user, ["admin", "user"], action)