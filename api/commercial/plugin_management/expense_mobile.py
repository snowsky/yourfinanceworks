from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant, TenantPluginSettings, user_tenant_association
from core.routers.auth import create_access_token, get_current_user
from core.routers.auth._shared import get_user_organizations
from core.routers.auth.login_register import register as register_user
from core.schemas.user import UserCreate, UserRead
from core.utils.auth import ACCESS_TOKEN_EXPIRE_MINUTES, verify_password


router = APIRouter(prefix="/expense/mobile", tags=["expense_mobile"])

_PLUGIN_ID = "expense"
_MOBILE_KEY = "mobile_app"
_DEFAULT_ACCENT = "#0f766e"


class BrandingPayload(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None


class AllowedAuthMethods(BaseModel):
    password: bool = True
    google: bool = False
    microsoft: bool = False


class ExpenseMobileConfigResponse(BaseModel):
    enabled: bool
    app_id: str
    signup_enabled: bool
    default_role: str
    allowed_auth_methods: AllowedAuthMethods
    branding: BrandingPayload


class ExpenseMobileLoginRequest(BaseModel):
    app_id: str
    email: EmailStr
    password: str


class ExpenseMobileSignupRequest(ExpenseMobileLoginRequest):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


def _default_mobile_config(plugin_config: dict[str, Any] | None, tenant: Tenant) -> dict[str, Any]:
    cfg = (plugin_config or {}).get(_PLUGIN_ID, {}).get(_MOBILE_KEY, {})
    branding = cfg.get("branding") or {}
    auth_methods = cfg.get("allowed_auth_methods") or {}
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "app_id": str(cfg.get("app_id") or ""),
        "signup_enabled": bool(cfg.get("signup_enabled", True)),
        "default_role": str(cfg.get("default_role") or "user"),
        "allowed_auth_methods": {
            "password": bool(auth_methods.get("password", True)),
            "google": bool(auth_methods.get("google", False)),
            "microsoft": bool(auth_methods.get("microsoft", False)),
        },
        "branding": {
            "title": branding.get("title") or tenant.name,
            "subtitle": branding.get("subtitle") or "Capture receipts and voice expenses in seconds.",
            "accent_color": branding.get("accent_color") or _DEFAULT_ACCENT,
            "logo_url": branding.get("logo_url") or tenant.company_logo_url,
        },
    }


def _resolve_expense_mobile_binding(db: Session, app_id: str) -> tuple[Tenant, TenantPluginSettings, dict[str, Any]]:
    normalized_app_id = (app_id or "").strip()
    if not normalized_app_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="app_id is required",
        )

    settings_records = db.query(TenantPluginSettings).all()
    for settings in settings_records:
        tenant = db.query(Tenant).filter(Tenant.id == settings.tenant_id).first()
        if not tenant or not tenant.is_active or not tenant.is_enabled:
            continue

        config = _default_mobile_config(settings.plugin_config, tenant)
        if not config["enabled"]:
            continue
        if config["app_id"] != normalized_app_id:
            continue
        if _PLUGIN_ID not in (settings.enabled_plugins or []):
            continue
        return tenant, settings, config

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Expense mobile service is not configured for this app.",
    )


def _get_user_role_for_tenant(db: Session, user: MasterUser, tenant_id: int) -> Optional[str]:
    if user.tenant_id == tenant_id:
        return user.role

    membership = db.execute(
        user_tenant_association.select().where(
            and_(
                user_tenant_association.c.user_id == user.id,
                user_tenant_association.c.tenant_id == tenant_id,
                user_tenant_association.c.is_active == True,
            )
        )
    ).first()
    return membership.role if membership else None


def _build_bound_user_response(db: Session, user: MasterUser, tenant_id: int, role: str) -> UserRead:
    user_copy = MasterUser(
        id=user.id,
        email=user.email,
        hashed_password=user.hashed_password,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        must_reset_password=user.must_reset_password,
        theme=user.theme,
        show_analytics=user.show_analytics,
        count_against_license=user.count_against_license,
        mfa_chain_enabled=user.mfa_chain_enabled,
        mfa_chain_mode=user.mfa_chain_mode,
        mfa_chain_factors=user.mfa_chain_factors,
        mfa_factor_secrets=user.mfa_factor_secrets,
        tenant_id=tenant_id,
        role=role,
        first_name=user.first_name,
        last_name=user.last_name,
        google_id=user.google_id,
        azure_ad_id=user.azure_ad_id,
        azure_tenant_id=user.azure_tenant_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
    user_response = UserRead.model_validate(user_copy)
    user_response.organizations = get_user_organizations(db, user)
    return user_response


@router.get("/config", response_model=ExpenseMobileConfigResponse)
async def get_expense_mobile_config(
    app_id: str = Query(...),
    db: Session = Depends(get_master_db),
):
    tenant, _, config = _resolve_expense_mobile_binding(db, app_id)
    return ExpenseMobileConfigResponse(
        **config,
        branding=BrandingPayload(**config["branding"]),
        allowed_auth_methods=AllowedAuthMethods(**config["allowed_auth_methods"]),
    )


@router.post("/auth/signup")
async def signup_expense_mobile_user(
    payload: ExpenseMobileSignupRequest,
    db: Session = Depends(get_master_db),
):
    tenant, _, config = _resolve_expense_mobile_binding(db, payload.app_id)
    if not config["signup_enabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sign up is disabled for this expense service.",
        )
    if not config["allowed_auth_methods"]["password"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password sign up is disabled for this expense service.",
        )

    user = UserCreate(
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        tenant_id=tenant.id,
        role=config["default_role"],
    )
    return await register_user(user=user, db=db)


@router.post("/auth/login")
async def login_expense_mobile_user(
    payload: ExpenseMobileLoginRequest,
    db: Session = Depends(get_master_db),
):
    tenant, _, config = _resolve_expense_mobile_binding(db, payload.app_id)
    if not config["allowed_auth_methods"]["password"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password sign in is disabled for this expense service.",
        )

    user = db.query(MasterUser).filter(MasterUser.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been disabled.",
        )

    role = _get_user_role_for_tenant(db, user, tenant.id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not a member of the configured organization.",
        )

    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    user_response = _build_bound_user_response(db, user, tenant.id, role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response,
    }


@router.get("/auth/me", response_model=UserRead)
async def get_expense_mobile_me(
    app_id: str = Query(...),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    tenant, _, _ = _resolve_expense_mobile_binding(db, app_id)
    role = _get_user_role_for_tenant(db, current_user, tenant.id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not a member of the configured organization.",
        )
    return _build_bound_user_response(db, current_user, tenant.id, role)
