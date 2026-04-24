from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.models.database import get_master_db
from core.models.models import MasterUser, user_tenant_association
from core.models.models_per_tenant import User as TenantUser
from core.routers.auth import create_access_token, get_current_user
from core.routers.auth._shared import get_user_organizations
from core.routers.auth.login_register import register as register_user
from core.schemas.user import Token, UserCreate, UserRead
from core.services.tenant_database_manager import tenant_db_manager
from core.services.expense_mobile_service import get_expense_mobile_config, resolve_expense_mobile_binding
from core.utils.auth import ACCESS_TOKEN_EXPIRE_MINUTES, verify_password


router = APIRouter(prefix="/mobile/expenses", tags=["mobile-expenses"])


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


def _ensure_existing_user_membership(
    db: Session,
    user: MasterUser,
    tenant_id: int,
    role: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> None:
    if user.tenant_id != tenant_id:
        membership = db.execute(
            user_tenant_association.select().where(
                and_(
                    user_tenant_association.c.user_id == user.id,
                    user_tenant_association.c.tenant_id == tenant_id,
                )
            )
        ).first()
        if membership:
            db.execute(
                user_tenant_association.update()
                .where(
                    and_(
                        user_tenant_association.c.user_id == user.id,
                        user_tenant_association.c.tenant_id == tenant_id,
                    )
                )
                .values(role=role, is_active=True)
            )
        else:
            db.execute(
                user_tenant_association.insert().values(
                    user_id=user.id,
                    tenant_id=tenant_id,
                    role=role,
                    is_active=True,
                )
            )

    if first_name and not user.first_name:
        user.first_name = first_name
    if last_name and not user.last_name:
        user.last_name = last_name
    db.commit()


def _ensure_tenant_user(
    user: MasterUser,
    tenant_id: int,
    role: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> None:
    tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
    tenant_db = tenant_session()
    try:
        tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user.id).first()
        if tenant_user:
            tenant_user.email = user.email
            tenant_user.role = role
            tenant_user.is_active = user.is_active
            tenant_user.is_superuser = user.is_superuser
            tenant_user.is_verified = True
            if first_name:
                tenant_user.first_name = first_name
            if last_name:
                tenant_user.last_name = last_name
        else:
            tenant_db.add(
                TenantUser(
                    id=user.id,
                    email=user.email,
                    hashed_password=user.hashed_password,
                    first_name=first_name or user.first_name,
                    last_name=last_name or user.last_name,
                    role=role,
                    is_active=user.is_active,
                    is_superuser=user.is_superuser,
                    is_verified=True,
                )
            )
        tenant_db.commit()
    finally:
        tenant_db.close()


@router.get("/config", response_model=ExpenseMobileConfigResponse)
async def get_mobile_expense_config(
    app_id: str = Query(...),
    db: Session = Depends(get_master_db),
):
    tenant, config = resolve_expense_mobile_binding(db, app_id)
    resolved = get_expense_mobile_config(db, tenant)
    return ExpenseMobileConfigResponse(
        **resolved,
        branding=BrandingPayload(**resolved["branding"]),
        allowed_auth_methods=AllowedAuthMethods(**resolved["allowed_auth_methods"]),
    )


@router.post("/auth/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup_mobile_expense_user(
    payload: ExpenseMobileSignupRequest,
    db: Session = Depends(get_master_db),
):
    tenant, config = resolve_expense_mobile_binding(db, payload.app_id)
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

    existing_user = db.query(MasterUser).filter(MasterUser.email == payload.email).first()
    if existing_user:
        if not verify_password(payload.password, existing_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password for existing user",
            )
        if not existing_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your account has been disabled.",
            )
        role = _get_user_role_for_tenant(db, existing_user, tenant.id) or config["default_role"]
        _ensure_existing_user_membership(
            db,
            existing_user,
            tenant.id,
            role,
            payload.first_name,
            payload.last_name,
        )
        _ensure_tenant_user(existing_user, tenant.id, role, payload.first_name, payload.last_name)

        access_token = create_access_token(
            data={"sub": existing_user.email},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": _build_bound_user_response(db, existing_user, tenant.id, role),
        }

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
async def login_mobile_expense_user(
    payload: ExpenseMobileLoginRequest,
    db: Session = Depends(get_master_db),
):
    tenant, config = resolve_expense_mobile_binding(db, payload.app_id)
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
async def get_mobile_expense_me(
    app_id: str = Query(...),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    tenant, _ = resolve_expense_mobile_binding(db, app_id)
    role = _get_user_role_for_tenant(db, current_user, tenant.id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not a member of the configured organization.",
        )
    return _build_bound_user_response(db, current_user, tenant.id, role)
