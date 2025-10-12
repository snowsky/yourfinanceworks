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


# Approval-specific permission functions
def can_submit_for_approval(user: Union[User, MasterUser]) -> bool:
    """Check if a user can submit expenses for approval."""
    return user.role in ["admin", "user"]


def can_approve_expenses(user: Union[User, MasterUser]) -> bool:
    """Check if a user can approve expenses (basic approval permission)."""
    return user.role in ["admin", "user"]


def can_approve_amount(user: Union[User, MasterUser], amount: float, currency: str = "USD") -> bool:
    """
    Check if a user can approve expenses up to a specific amount.
    This is a basic implementation - actual limits should be checked against ApprovalRule.
    
    Args:
        user: The current user
        amount: The expense amount to approve
        currency: The currency of the expense
    
    Returns:
        bool: True if user can approve this amount (basic role check)
    """
    # Basic role-based approval - actual amount limits should be checked in ApprovalService
    if user.role == "admin":
        return True
    elif user.role == "user":
        return True  # Amount limits will be enforced by ApprovalRule evaluation
    else:
        return False


def can_manage_approval_rules(user: Union[User, MasterUser]) -> bool:
    """Check if a user can create and manage approval rules."""
    return user.role == "admin"


def can_delegate_approvals(user: Union[User, MasterUser]) -> bool:
    """Check if a user can set up approval delegations."""
    return user.role in ["admin", "user"]


def can_view_approval_history(user: Union[User, MasterUser]) -> bool:
    """Check if a user can view approval history."""
    return user.role in ["admin", "user"]


def can_view_all_approvals(user: Union[User, MasterUser]) -> bool:
    """Check if a user can view all pending approvals (admin-only feature)."""
    return user.role == "admin"


def require_approval_submission(user: Union[User, MasterUser], action: str = "submit expenses for approval") -> None:
    """
    Check if a user can submit expenses for approval.
    
    Args:
        user: The current user
        action: Description of the action being performed
    
    Raises:
        HTTPException: 403 Forbidden if user cannot submit for approval
    """
    require_roles(user, ["admin", "user"], action)


def require_approval_permission(user: Union[User, MasterUser], action: str = "approve expenses") -> None:
    """
    Check if a user has basic approval permissions.
    
    Args:
        user: The current user
        action: Description of the action being performed
    
    Raises:
        HTTPException: 403 Forbidden if user cannot approve expenses
    """
    require_roles(user, ["admin", "user"], action)


def require_approval_rule_management(user: Union[User, MasterUser], action: str = "manage approval rules") -> None:
    """
    Check if a user can manage approval rules.
    
    Args:
        user: The current user
        action: Description of the action being performed
    
    Raises:
        HTTPException: 403 Forbidden if user cannot manage approval rules
    """
    require_admin(user, action)


def require_delegation_permission(user: Union[User, MasterUser], action: str = "manage approval delegations") -> None:
    """
    Check if a user can set up approval delegations.
    
    Args:
        user: The current user
        action: Description of the action being performed
    
    Raises:
        HTTPException: 403 Forbidden if user cannot manage delegations
    """
    require_roles(user, ["admin", "user"], action)


def require_permission(user: Union[User, MasterUser], permission: str) -> None:
    """
    Generic permission checker that maps permission strings to appropriate role checks.
    
    Args:
        user: The current user (User or MasterUser)
        permission: The permission string to check
    
    Raises:
        HTTPException: 403 Forbidden if user doesn't have the required permission
    """
    permission_mapping = {
        # Approval permissions
        "approval_view": ["admin", "user"],
        "approval_admin": ["admin"],
        "approval_submit": ["admin", "user"],
        "approval_delegate": ["admin", "user"],
        
        # Report permissions
        "report_view": ["admin", "user"],
        "report_manage": ["admin", "user"],
        "report_admin": ["admin"],
        
        # General permissions
        "admin": ["admin"],
        "user": ["admin", "user"],
        "superuser": [],  # Special case for superuser check
    }
    
    # Special case for superuser permission
    if permission == "superuser":
        require_superuser(user, f"access {permission}")
        return
    
    # Check if permission exists in mapping
    if permission not in permission_mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown permission: {permission}"
        )
    
    # Check user role against required roles for this permission
    required_roles = permission_mapping[permission]
    require_roles(user, required_roles, f"access {permission}")