# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Core module of YourFinanceWORKS.
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
# See LICENSE-AGPLv3.txt for details.

from fastapi import APIRouter

from core.routers.auth import login_register, password, invites, sso

router = APIRouter(prefix="/auth", tags=["authentication"])

router.include_router(login_register.router)
router.include_router(password.router)
router.include_router(invites.router)
router.include_router(sso.router)

# Re-export public symbols consumed by other modules
from core.routers.auth._shared import (  # noqa: F401
    get_current_user,
    get_email_service_for_tenant,
    get_user_organizations,
    authenticate_user,
    generate_invite_token,
    create_password_reset_token,
    oauth2_scheme,
    security,
    AUTH_COOKIE_NAME,
    ChangePasswordRequest,
)
from core.utils.auth import SECRET_KEY, ALGORITHM, create_access_token  # noqa: F401
