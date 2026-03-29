# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Core module of YourFinanceWORKS.
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
# See LICENSE-AGPLv3.txt for details.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant, PasswordResetToken, Settings
from core.schemas.password_reset import PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse
from core.utils.auth import verify_password, get_password_hash
from core.utils.password_validation import validate_password_strength
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.rate_limiter import record_and_check
from core.constants.error_codes import INCORRECT_PASSWORD
from core.routers.auth._shared import (
    get_current_user, get_email_service_for_tenant,
    create_password_reset_token, ChangePasswordRequest,
    MAX_RESET_ATTEMPTS, RATE_LIMIT_WINDOW_SECONDS,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def create_reset_token_entry(db: Session, user_id: int) -> PasswordResetToken:
    """Create a password reset token entry in the database"""
    existing_tokens = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).all()

    for token in existing_tokens:
        token.is_used = True
        token.used_at = datetime.now(timezone.utc)

    token = create_password_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    reset_token = PasswordResetToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at
    )

    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)

    return reset_token


def verify_reset_token(db: Session, token: str) -> Optional[PasswordResetToken]:
    """Verify a password reset token and return the token object if valid"""
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).first()

    return reset_token


@router.post("/change-password", response_model=PasswordResetResponse)
async def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Allow a logged-in user to change their password and clear must_reset_password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail=INCORRECT_PASSWORD)
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    is_valid, errors = validate_password_strength(payload.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"message": "Password does not meet requirements", "errors": errors})

    current_user.hashed_password = get_password_hash(payload.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    current_user.must_reset_password = False
    db.commit()

    try:
        tenant_session = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == current_user.id).first()
        if tenant_user:
            tenant_user.hashed_password = get_password_hash(payload.new_password)
            tenant_user.updated_at = datetime.now(timezone.utc)
            tenant_user.must_reset_password = False
            tenant_session.commit()
        tenant_session.close()
    except Exception:
        pass

    return PasswordResetResponse(message="Password changed successfully.", success=True)


@router.post("/request-password-reset", response_model=PasswordResetResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    master_db: Session = Depends(get_master_db)
):
    """Request a password reset for a user"""
    email_key = (request.email or "").lower().strip()
    if record_and_check(f"reset:{email_key}", MAX_RESET_ATTEMPTS, RATE_LIMIT_WINDOW_SECONDS):
        return PasswordResetResponse(
            message="If the email address exists in our system, you will receive a password reset email shortly.",
            success=True
        )
    user = master_db.query(MasterUser).filter(
        MasterUser.email.ilike(request.email.strip())
    ).first()

    if not user:
        return PasswordResetResponse(
            message="If the email address exists in our system, you will receive a password reset email shortly.",
            success=True
        )

    if not user.is_active:
        return PasswordResetResponse(
            message="If the email address exists in our system, you will receive a password reset email shortly.",
            success=True
        )

    reset_token = create_reset_token_entry(master_db, user.id)

    tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    email_service = get_email_service_for_tenant(master_db, user.tenant_id)

    if email_service and tenant:
        try:
            email_settings = master_db.query(Settings).filter(
                Settings.tenant_id == user.tenant_id,
                Settings.key == "email_config"
            ).first()

            email_config_data = email_settings.value if email_settings else {}
            from_name = email_config_data.get('from_name', tenant.name)
            from_email = email_config_data.get('from_email', 'noreply@invoiceapp.com')

            user_display_name = f"{user.first_name} {user.last_name}".strip() or user.email

            success = email_service.send_password_reset_email(
                user_email=user.email,
                user_name=user_display_name,
                reset_token=reset_token.token,
                company_name=tenant.name,
                from_name=from_name,
                from_email=from_email
            )

            if success:
                print(f"Password reset email sent successfully to {user.email}")
            else:
                print(f"Failed to send password reset email to {user.email}")

        except Exception as e:
            print(f"Error sending password reset email to {user.email}: {str(e)}")
    else:
        from config import config
        print(f"Email service not configured for tenant {user.tenant_id}")
        print(f"Password reset token for {user.email}: {reset_token.token}")
        print(f"Reset URL: {config.UI_BASE_URL}/reset-password?token={reset_token.token}")

    return PasswordResetResponse(
        message="If the email address exists in our system, you will receive a password reset email shortly.",
        success=True
    )


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    request: PasswordResetConfirm,
    master_db: Session = Depends(get_master_db)
):
    """Reset user password using a valid token"""
    reset_token = verify_reset_token(master_db, request.token)
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )

    user = master_db.query(MasterUser).filter(MasterUser.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )

    is_valid, errors = validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements", "errors": errors}
        )

    user.hashed_password = get_password_hash(request.new_password)
    user.updated_at = datetime.now(timezone.utc)

    reset_token.is_used = True
    reset_token.used_at = datetime.now(timezone.utc)

    try:
        from core.models.database import set_tenant_context
        set_tenant_context(user.tenant_id)

        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)
        tenant_db = tenant_session()
        try:
            tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user.id).first()
            if tenant_user:
                tenant_user.hashed_password = get_password_hash(request.new_password)
                tenant_user.updated_at = datetime.now(timezone.utc)
                tenant_db.commit()
        finally:
            tenant_db.close()
    except Exception as e:
        print(f"Warning: Failed to update tenant user password: {str(e)}")

    master_db.commit()

    return PasswordResetResponse(
        message="Password has been reset successfully. You can now log in with your new password.",
        success=True
    )


@router.get("/password-requirements")
async def get_password_requirements():
    """Get password requirements for frontend validation (public endpoint)"""
    from core.constants.password import MIN_PASSWORD_LENGTH, PASSWORD_COMPLEXITY
    from core.utils.password_validation import get_password_requirements

    return {
        "min_length": MIN_PASSWORD_LENGTH,
        "complexity": PASSWORD_COMPLEXITY,
        "requirements": get_password_requirements()
    }
