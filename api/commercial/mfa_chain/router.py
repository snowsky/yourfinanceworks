from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.models.database import get_master_db
from core.models.models import MasterUser
from core.models.models_per_tenant import User as TenantUser
from core.routers.auth._shared import AUTH_COOKIE_NAME, _is_production, get_current_user, get_user_organizations
from core.schemas.user import UserRead
from core.services.tenant_database_manager import tenant_db_manager
from core.utils.auth import ACCESS_TOKEN_EXPIRE_MINUTES
from core.utils.feature_gate import check_feature

from commercial.mfa_chain.utils import (
    finalize_mfa_login,
    get_session_prompt,
    get_user_mfa_settings,
    maybe_start_mfa_session,
    normalize_factor_ids,
    validate_settings_payload,
    verify_mfa_step,
    create_mfa_enrollment,
    MFA_LOGIN_SESSIONS,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


class MFAChainSettingsUpdate(BaseModel):
    enabled: bool = False
    mode: str = Field(default="fixed")
    factors: list[str] = Field(default_factory=list)


class MFAChainVerifyRequest(BaseModel):
    session_id: str = Field(min_length=1)
    factor_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    window: int = Field(default=1, ge=0)


def _check_mfa_chain_feature_for_tenant(tenant_id: int) -> None:
    tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
    tenant_db = tenant_session()
    try:
        check_feature("mfa_chain", tenant_db)
    finally:
        tenant_db.close()


@router.get("/mfa-chain/settings")
async def get_mfa_chain_settings(
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    _check_mfa_chain_feature_for_tenant(current_user.tenant_id)
    db_user = db.query(MasterUser).filter(MasterUser.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return get_user_mfa_settings(db_user)


@router.put("/mfa-chain/settings")
async def update_mfa_chain_settings(
    payload: MFAChainSettingsUpdate,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    _check_mfa_chain_feature_for_tenant(current_user.tenant_id)
    db_user = db.query(MasterUser).filter(MasterUser.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db_user.mfa_chain_enabled = bool(payload.enabled)
    db_user.mfa_chain_mode = payload.mode if payload.mode in ("fixed", "random") else "fixed"
    db_user.mfa_chain_factors = normalize_factor_ids(payload.factors)

    secrets = dict(db_user.mfa_factor_secrets or {})
    ok, message = validate_settings_payload(payload.model_dump(), secrets)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    tenant_session = tenant_db_manager.get_tenant_session(db_user.tenant_id)
    tenant_db = tenant_session()
    try:
        tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == db_user.id).first()
        if tenant_user:
            tenant_user.mfa_chain_enabled = db_user.mfa_chain_enabled
            tenant_user.mfa_chain_mode = db_user.mfa_chain_mode
            tenant_user.mfa_chain_factors = db_user.mfa_chain_factors
            tenant_user.mfa_factor_secrets = db_user.mfa_factor_secrets
            tenant_db.commit()
    finally:
        tenant_db.close()

    return get_user_mfa_settings(db_user)


@router.post("/mfa-chain/factors/{factor_id}/enroll")
async def enroll_mfa_factor(
    factor_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    _check_mfa_chain_feature_for_tenant(current_user.tenant_id)
    db_user = db.query(MasterUser).filter(MasterUser.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        enrollment = create_mfa_enrollment(db_user, factor_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db_user.mfa_factor_secrets = enrollment["secrets"]
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    tenant_session = tenant_db_manager.get_tenant_session(db_user.tenant_id)
    tenant_db = tenant_session()
    try:
        tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == db_user.id).first()
        if tenant_user:
            tenant_user.mfa_factor_secrets = db_user.mfa_factor_secrets
            tenant_db.commit()
    finally:
        tenant_db.close()

    return {
        "factor_id": enrollment["factor_id"],
        "factor_label": enrollment["factor_label"],
        "otpauth_uri": enrollment["otpauth_uri"],
        "secret": enrollment["secret"],
        "qr_png_base64": enrollment["qr_png_base64"],
    }


@router.get("/mfa-chain/attempt/{session_id}")
async def get_mfa_attempt(session_id: str):
    try:
        return get_session_prompt(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/mfa-chain/attempt/verify")
async def verify_mfa_attempt(
    payload: MFAChainVerifyRequest,
    response: Response,
    db: Session = Depends(get_master_db),
):
    try:
        result = verify_mfa_step(
            session_id=payload.session_id,
            factor_id=payload.factor_id,
            user_input=payload.user_input,
            window=payload.window,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not result.get("is_complete"):
        return result

    state = MFA_LOGIN_SESSIONS.get(payload.session_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown or expired MFA session")

    user = db.query(MasterUser).filter(MasterUser.id == state["user_id"]).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User no longer exists")

    login_payload = finalize_mfa_login(payload.session_id, user)
    organizations = get_user_organizations(db, user)
    user_response = UserRead.model_validate(user)
    user_response.organizations = organizations

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=login_payload["access_token"],
        httponly=True,
        samesite="lax",
        secure=_is_production,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {
        "success": True,
        "is_complete": True,
        "access_token": login_payload["access_token"],
        "token_type": "bearer",
        "user": user_response,
    }


def maybe_require_mfa_for_user(user: MasterUser, next_path: str = "/dashboard") -> dict | None:
    try:
        _check_mfa_chain_feature_for_tenant(user.tenant_id)
    except HTTPException:
        return None
    return maybe_start_mfa_session(user, next_path)
