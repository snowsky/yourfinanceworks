from fastapi import Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
import logging

from core.models.models import MasterUser
from core.routers.auth import get_current_user

logger = logging.getLogger(__name__)


class PromoteUserRequest(BaseModel):
    email: str


class SuperAdminResetPasswordRequest(BaseModel):
    new_password: str
    confirm_password: str
    force_reset_on_login: bool = False


class TenantSelectionRequest(BaseModel):
    tenant_ids: List[int]


class GlobalSignupSettingsUpdate(BaseModel):
    allow_password_signup: Optional[bool] = None
    allow_sso_signup: Optional[bool] = None
    max_tenants: Optional[int] = None
    max_users: Optional[int] = None


def require_super_admin(current_user: MasterUser = Depends(get_current_user)) -> MasterUser:
    """Require that the current user is a superuser in their primary tenant"""
    from core.models.database import get_tenant_context
    current_tenant_id = get_tenant_context()

    logger.info(f"require_super_admin: user={current_user.email}, is_superuser={current_user.is_superuser}, tenant_context={current_tenant_id}, user_tenant={current_user.tenant_id}")

    if not current_user.is_superuser:
        logger.warning(f"require_super_admin: user {current_user.email} is not a super admin")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )

    # Check if user is in their primary tenant
    if current_tenant_id and current_tenant_id != current_user.tenant_id:
        logger.warning(f"require_super_admin: user {current_user.email} is not in primary tenant")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access restricted to home organization"
        )

    logger.info(f"require_super_admin: user {current_user.email} passed all checks")
    return current_user
