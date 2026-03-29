# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Core module of YourFinanceWORKS.
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
# See LICENSE-AGPLv3.txt for details.

from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import func
import os
import logging
import traceback

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant
from core.schemas.user import UserCreate, UserLogin, Token, UserRead, UserUpdate
from core.utils.auth import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager
from core.middleware.tenant_context_middleware import set_tenant_context
from core.utils.rate_limiter import record_and_check
from core.constants.error_codes import USER_NOT_FOUND, INCORRECT_PASSWORD
from core.utils.audit import log_audit_event_master
from core.routers.auth._shared import (
    get_current_user, get_user_organizations,
    AUTH_COOKIE_NAME, _is_production,
    MAX_LOGIN_ATTEMPTS, RATE_LIMIT_WINDOW_SECONDS,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=Token, status_code=201)
async def register(user: UserCreate, db: Session = Depends(get_master_db)):
    logger = logging.getLogger("registration")
    logger.info(f"Starting registration for {user.email}")

    user_total_count = db.query(MasterUser).count()
    is_global_first_user = user_total_count == 0

    from core.services.license_service import LicenseService
    license_service = LicenseService(db, master_db=db)
    license_status = license_service.get_license_status()

    if not license_status.get("allow_password_signup", True):
        if not is_global_first_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public registration is currently disabled. Please contact an administrator."
            )

    existing_user = db.query(MasterUser).filter(MasterUser.email == user.email).first()
    is_existing_user = existing_user is not None

    if is_existing_user:
        logger.info(f"Existing user creating new organization: {user.email}")
        if not verify_password(user.password, existing_user.hashed_password):
            logger.warning(f"Invalid password for existing user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password for existing user"
            )
        if user.first_name and not existing_user.first_name:
            existing_user.first_name = user.first_name
        if user.last_name and not existing_user.last_name:
            existing_user.last_name = user.last_name
        db.commit()
    else:
        logger.info(f"New user registration: {user.email}")

        user_licensing_info = license_status.get("user_licensing_info")
        if user_licensing_info and user_licensing_info.get("max_users"):
            should_count = True
            if user.tenant_id:
                target_tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
                if target_tenant and not target_tenant.count_against_license:
                    should_count = False

            if should_count:
                max_users = user_licensing_info["max_users"]
                current_users = user_licensing_info["current_users_count"]
                user_total_count = db.query(MasterUser).count()
                if user_total_count > 0 and current_users >= max_users:
                    logger.error(f"User limit reached: {current_users} >= {max_users}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"User limit reached ({max_users}). Please contact an administrator to upgrade your license or exempt a tenant."
                    )

    if not user.tenant_id:
        tenant_name = getattr(user, 'organization_name', None)
        if not tenant_name:
            first_name = existing_user.first_name if is_existing_user and existing_user.first_name else user.first_name
            last_name = existing_user.last_name if is_existing_user and existing_user.last_name else user.last_name
            tenant_name = f"{first_name or 'User'}'s Organization"
            if first_name and last_name:
                tenant_name = f"{first_name} {last_name}'s Organization"

        tenant_address = getattr(user, 'organization_address', None) or getattr(user, 'address', None)

        logger.info(f"Creating new tenant for {user.email} with name {tenant_name}")
        base_name = tenant_name
        suffix_attempt = 0
        from sqlalchemy.exc import IntegrityError
        while True:
            try:
                db_tenant = Tenant(
                    name=tenant_name,
                    email=user.email,
                    is_active=True,
                    address=tenant_address if tenant_address else None
                )
                db.add(db_tenant)
                db.commit()
                db.refresh(db_tenant)
                break
            except IntegrityError:
                db.rollback()
                suffix_attempt += 1
                import uuid
                short = uuid.uuid4().hex[:6]
                tenant_name = f"{base_name} {short}"
        tenant_id = db_tenant.id
        logger.info(f"Created tenant {tenant_id} for {user.email}")

        success = tenant_db_manager.create_tenant_database(tenant_id, tenant_name)
        logger.info(f"Tenant DB creation for {tenant_id}: {success}")
        if not success:
            logger.error(f"Failed to create tenant database for {tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tenant database"
            )

        from core.services.license_service import LicenseService
        from core.models.database import set_tenant_context

        set_tenant_context(tenant_id)
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db_for_license = tenant_session()

        try:
            license_service = LicenseService(tenant_db_for_license, master_db=db)
            max_tenants = license_service.get_max_tenants()
            current_tenants_count = db.query(Tenant).filter(Tenant.count_against_license == True).count()

            if not is_global_first_user and current_tenants_count >= max_tenants:
                logger.error(f"Tenant limit reached: {current_tenants_count} >= {max_tenants}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Organization limit reached ({max_tenants}). Please upgrade your license to add more organizations."
                )
            logger.info(f"License check passed: {current_tenants_count} < {max_tenants}")
        finally:
            try:
                tenant_db_for_license.close()
            except Exception:
                pass

        user_role = "admin"
    else:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant"
            )
        tenant_id = user.tenant_id
        user_role = user.role or "user"
        logger.info(f"Using existing tenant {tenant_id} for {user.email}")

    if is_existing_user:
        db_user = existing_user
        is_global_first_user = False
        logger.info(f"Using existing user {db_user.id} for {user.email}")
    else:
        is_org_first_user = not user.tenant_id

        logger.info(f"Creating user in master DB: {user.email}")
        db_user = MasterUser(
            email=user.email,
            hashed_password=get_password_hash(user.password),
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=True,
            is_superuser=is_global_first_user,
            role="admin" if is_org_first_user else user_role,
            tenant_id=tenant_id,
            is_verified=True
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"Created user {db_user.id} in master DB for {user.email}")

    if is_existing_user and tenant_id != existing_user.tenant_id:
        try:
            from core.models.models import user_tenant_association
            db.execute(
                user_tenant_association.insert().values(
                    user_id=existing_user.id,
                    tenant_id=tenant_id,
                    role=user_role
                )
            )
            db.commit()
            logger.info(f"Created user-tenant association for user {existing_user.id} with tenant {tenant_id}")

            existing_user.tenant_id = tenant_id
            existing_user.role = user_role
            db.commit()
            logger.info(f"Updated user's primary tenant to {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to create user-tenant association: {str(e)}")

    from core.models.database import set_tenant_context
    set_tenant_context(tenant_id)

    try:
        logger.info(f"Creating/updating user in tenant DB {tenant_id} for {user.email}")
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()
        try:
            if not is_global_first_user:
                pass

            existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == db_user.id).first()

            if existing_tenant_user:
                existing_tenant_user.email = user.email
                if not is_existing_user:
                    existing_tenant_user.hashed_password = db_user.hashed_password
                if user.first_name:
                    existing_tenant_user.first_name = user.first_name
                if user.last_name:
                    existing_tenant_user.last_name = user.last_name
                existing_tenant_user.role = user_role
                existing_tenant_user.is_active = user.is_active
                existing_tenant_user.is_superuser = db_user.is_superuser
                existing_tenant_user.is_verified = True
                existing_tenant_user.updated_at = datetime.now(timezone.utc)
                tenant_db.commit()
                logger.info(f"Updated existing user {existing_tenant_user.id} in tenant DB {tenant_id} for {user.email}")
            else:
                if is_existing_user:
                    hashed_password = existing_user.hashed_password
                else:
                    hashed_password = db_user.hashed_password

                tenant_user = TenantUser(
                    id=db_user.id,
                    email=user.email,
                    hashed_password=hashed_password,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    role=user_role,
                    is_active=user.is_active,
                    is_superuser=db_user.is_superuser,
                    is_verified=True
                )

                tenant_db.add(tenant_user)
                tenant_db.commit()
                logger.info(f"Created user {tenant_user.id} in tenant DB {tenant_id} for {user.email}")

        finally:
            try:
                tenant_db.close()
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create/update tenant user for {user.email} in tenant DB {tenant_id}: {str(e)}")
        logger.error(traceback.format_exc())
        if not is_existing_user:
            db.delete(db_user)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant user: {str(e)}"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )

    organizations = get_user_organizations(db, db_user)

    user_response = UserRead.model_validate(db_user)
    user_response.organizations = organizations

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", samesite="lax")
    return {"message": "Logged out successfully"}


@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, response: Response, db: Session = Depends(get_master_db)):
    email_key = (user_credentials.email or "").lower().strip()
    if record_and_check(f"login:{email_key}", MAX_LOGIN_ATTEMPTS, RATE_LIMIT_WINDOW_SECONDS):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    user = db.query(MasterUser).filter(MasterUser.email == user_credentials.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND,
        )

    if not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INCORRECT_PASSWORD,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been disabled. Please contact your administrator."
        )

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your organization has been disabled. Please contact support."
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    organizations = get_user_organizations(db, user)

    user_response = UserRead.model_validate(user)
    user_response.organizations = organizations

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=_is_production,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response
    }


@router.get("/me", response_model=UserRead)
async def read_users_me(current_user: MasterUser = Depends(get_current_user), db: Session = Depends(get_master_db)):
    from core.models.models import user_tenant_association

    tenant_memberships = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == current_user.id
        )
    ).fetchall()

    tenant_role_map = {membership.tenant_id: membership.role for membership in tenant_memberships}

    tenant_ids = [membership.tenant_id for membership in tenant_memberships]
    if current_user.tenant_id and current_user.tenant_id not in tenant_ids:
        tenant_ids.append(current_user.tenant_id)

    organizations = []
    if tenant_ids:
        tenants = db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
        tenants = sorted(tenants, key=lambda t: t.id)
        for tenant in tenants:
            org_data = {'id': tenant.id, 'name': tenant.name}
            if tenant.id in tenant_role_map:
                org_data['role'] = tenant_role_map[tenant.id]
            elif tenant.id == current_user.tenant_id:
                org_data['role'] = current_user.role
            organizations.append(org_data)

    user_data = UserRead.model_validate(current_user)
    user_dict = user_data.model_dump()
    user_dict['organizations'] = organizations

    user_dict['sso_provider'] = None
    if current_user.google_id:
        user_dict['sso_provider'] = 'google'
    elif current_user.azure_ad_id:
        user_dict['sso_provider'] = 'microsoft'

    user_dict['has_sso'] = user_dict['sso_provider'] is not None

    return user_dict


@router.put("/me", response_model=UserRead)
async def update_current_user(
    user_update: UserUpdate,
    request: Request,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update current user's profile (first_name, last_name)"""
    updated = False
    show_analytics_changed: Optional[bool] = None
    if user_update.first_name is not None:
        current_user.first_name = user_update.first_name
        updated = True
    if user_update.last_name is not None:
        current_user.last_name = user_update.last_name
        updated = True
    if user_update.theme is not None:
        current_user.theme = user_update.theme
        updated = True
    if hasattr(user_update, 'show_analytics') and user_update.show_analytics is not None:
        show_analytics_changed = user_update.show_analytics
        current_user.show_analytics = user_update.show_analytics
        updated = True
    if not updated:
        raise HTTPException(status_code=400, detail="No updatable fields provided.")
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    if show_analytics_changed is not None:
        log_audit_event_master(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE_USER_SETTING",
            resource_type="user_setting",
            resource_id=str(current_user.id),
            resource_name="show_analytics",
            details={"show_analytics": show_analytics_changed},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    from core.services.tenant_database_manager import tenant_db_manager
    from core.models.models_per_tenant import User as TenantUser
    tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == current_user.id).first()
        if tenant_user:
            if user_update.first_name is not None:
                tenant_user.first_name = user_update.first_name
            if user_update.last_name is not None:
                tenant_user.last_name = user_update.last_name
            if user_update.theme is not None:
                tenant_user.theme = user_update.theme
            if hasattr(user_update, 'show_analytics') and user_update.show_analytics is not None:
                tenant_user.show_analytics = user_update.show_analytics
            tenant_db.commit()
            tenant_db.refresh(tenant_user)
    finally:
        tenant_db.close()

    return UserRead.model_validate(current_user)


@router.get("/check-email-availability")
async def check_email_availability(
    email: str,
    master_db: Session = Depends(get_master_db)
):
    """Check if an email address is available (public endpoint for signup)"""
    if not email or len(email.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must be at least 3 characters long"
        )

    import re
    email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_pattern, email.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )

    existing_user = master_db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(email.strip())
    ).first()

    return {
        "available": True,
        "email": email.strip(),
        "user_exists": existing_user is not None
    }
