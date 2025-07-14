from fastapi import HTTPException, status
from typing import List, Union
from models.models_per_tenant import User
from models.models import MasterUser


def require_roles(
    user: Union[User, MasterUser], 
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
        role_list = ", ".join(required_roles)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only users with roles [{role_list}] can {action}. Your role: {user.role}"
        )


def require_non_viewer(user: Union[User, MasterUser], action: str = "perform this action") -> None:
    """
    Check if a user is not a viewer (shortcut for common case).
    
    Args:
        user: The current user (User or MasterUser)
        action: Description of the action being performed (for error message)
    
    Raises:
        HTTPException: 403 Forbidden if user is a viewer
    """
    require_roles(user, ["admin", "user"], action)


def require_admin(user: Union[User, MasterUser], action: str = "perform this action") -> None:
    """
    Check if a user is an admin (shortcut for admin-only actions).
    
    Args:
        user: The current user (User or MasterUser)
        action: Description of the action being performed (for error message)
    
    Raises:
        HTTPException: 403 Forbidden if user is not an admin
    """
    require_roles(user, ["admin"], action)


def can_user_perform_action(user: Union[User, MasterUser], required_roles: List[str]) -> bool:
    """
    Check if a user can perform an action without raising an exception.
    
    Args:
        user: The current user (User or MasterUser)
        required_roles: List of roles that are allowed to perform the action
    
    Returns:
        bool: True if user has required role, False otherwise
    """
    return user.role in required_roles


def is_admin(user: Union[User, MasterUser]) -> bool:
    """Check if a user is an admin."""
    return user.role == "admin"


def is_viewer(user: Union[User, MasterUser]) -> bool:
    """Check if a user is a viewer."""
    return user.role == "viewer" 