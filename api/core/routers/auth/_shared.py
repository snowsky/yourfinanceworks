# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Core module of YourFinanceWORKS.
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
# See LICENSE-AGPLv3.txt for details.

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import os
import secrets
import logging

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant, Invite, PasswordResetToken, Settings, user_tenant_association
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider
from core.utils.auth import SECRET_KEY, ALGORITHM
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager
from core.constants.error_codes import INVALID_CREDENTIALS
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
MAX_RESET_ATTEMPTS = int(os.getenv("MAX_RESET_ATTEMPTS", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
security = HTTPBearer(auto_error=False)

AUTH_COOKIE_NAME = "auth_token"
_is_production = os.getenv("ENVIRONMENT", "development").lower() not in ("development", "dev")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


def create_password_reset_token() -> str:
    """Generate a secure random token for password reset"""
    return secrets.token_urlsafe(32)


def generate_invite_token() -> str:
    """Generate a secure invite token"""
    return secrets.token_urlsafe(32)


def get_email_service_for_tenant(db: Session, tenant_id: int) -> Optional[EmailService]:
    """Get configured email service for a tenant"""
    try:
        email_settings = db.query(Settings).filter(
            Settings.tenant_id == tenant_id,
            Settings.key == "email_config"
        ).first()

        if not email_settings or not email_settings.value:
            return None

        email_config_data = email_settings.value

        if not email_config_data.get('enabled', False):
            return None

        config = EmailProviderConfig(
            provider=EmailProvider(email_config_data['provider']),
            from_email=email_config_data.get('from_email'),
            from_name=email_config_data.get('from_name'),
            aws_access_key_id=email_config_data.get('aws_access_key_id'),
            aws_secret_access_key=email_config_data.get('aws_secret_access_key'),
            aws_region=email_config_data.get('aws_region'),
            azure_connection_string=email_config_data.get('azure_connection_string'),
            mailgun_api_key=email_config_data.get('mailgun_api_key'),
            mailgun_domain=email_config_data.get('mailgun_domain')
        )

        return EmailService(config)

    except Exception as e:
        print(f"Failed to initialize email service for tenant {tenant_id}: {str(e)}")
        return None


def authenticate_user(db: Session, email: str, password: str):
    from core.utils.auth import verify_password
    user = db.query(MasterUser).filter(MasterUser.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_master_db)
) -> MasterUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_CREDENTIALS,
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials if credentials else request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            logger.warning("get_current_user: No email in JWT payload")
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"get_current_user: JWT decode error: {e}")
        raise credentials_exception

    user = db.query(MasterUser).filter(MasterUser.email == email).first()
    if user is None:
        logger.warning(f"get_current_user: User {email} not found in database")
        raise credentials_exception

    from core.models.database import get_tenant_context
    current_tenant_id = get_tenant_context()

    if current_tenant_id and current_tenant_id != user.tenant_id:
        try:
            TenantSession = tenant_db_manager.get_tenant_session(current_tenant_id)
            tenant_db = TenantSession()
            try:
                tenant_db.expire_all()
                tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user.id).first()
                if tenant_user:
                    user_copy = MasterUser(
                        id=user.id,
                        email=user.email,
                        hashed_password=user.hashed_password,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        role=tenant_user.role,
                        tenant_id=current_tenant_id,
                        is_active=user.is_active,
                        is_superuser=user.is_superuser,
                        is_verified=user.is_verified,
                        must_reset_password=bool(getattr(tenant_user, 'must_reset_password', False)),
                        theme=user.theme,
                        google_id=user.google_id,
                        created_at=user.created_at,
                        updated_at=user.updated_at
                    )
                    return user_copy
                else:
                    user_copy = MasterUser(
                        id=user.id,
                        email=user.email,
                        hashed_password=user.hashed_password,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        role='viewer',
                        tenant_id=current_tenant_id,
                        is_active=user.is_active,
                        is_superuser=user.is_superuser,
                        is_verified=user.is_verified,
                        must_reset_password=bool(getattr(user, 'must_reset_password', False)),
                        theme=user.theme,
                        google_id=user.google_id,
                        created_at=user.created_at,
                        updated_at=user.updated_at
                    )
                    return user_copy
            finally:
                tenant_db.close()
        except Exception as e:
            logger.warning(f"Failed to get tenant-specific role for user {user.email} in tenant {current_tenant_id}: {e}")

    return user


def get_user_organizations(db: Session, user: MasterUser) -> List[Dict[str, Any]]:
    """Get all organizations/tenants for a user"""
    organizations = []

    if user.tenant_id:
        primary_tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if primary_tenant:
            organizations.append({
                "id": primary_tenant.id,
                "name": primary_tenant.name,
                "role": user.role,
                "is_primary": True
            })

    additional_tenants = db.query(Tenant, user_tenant_association.c.role).join(
        user_tenant_association, Tenant.id == user_tenant_association.c.tenant_id
    ).filter(
        user_tenant_association.c.user_id == user.id,
        user_tenant_association.c.is_active == True,
        Tenant.id != user.tenant_id
    ).all()

    for tenant, role in additional_tenants:
        organizations.append({
            "id": tenant.id,
            "name": tenant.name,
            "role": role,
            "is_primary": False
        })

    return organizations
