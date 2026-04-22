from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging
import secrets

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant, user_tenant_association
from core.models.models_per_tenant import User as TenantUser
from core.schemas.user import UserRoleUpdate
from core.services.tenant_database_manager import tenant_db_manager
from core.services.license_service import LicenseService
from core.utils.auth import get_password_hash
from core.utils.password_validation import validate_password_strength
from core.utils.audit import log_audit_event, log_audit_event_master
from core.constants.error_codes import USER_NOT_FOUND
from core.routers.super_admin._shared import (
    require_super_admin,
    PromoteUserRequest,
    SuperAdminResetPasswordRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _disable_mfa_fields(user: Any) -> None:
    user.mfa_chain_enabled = False
    user.mfa_chain_mode = "fixed"
    user.mfa_chain_factors = []
    user.mfa_factor_secrets = {}


@router.get("/users", response_model=List[Dict[str, Any]])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    tenant_id: Optional[int] = Query(None),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """List users. If tenant_id is provided, compute role for that tenant; otherwise show role for each user's primary tenant."""
    # Only list active users by default
    query = master_db.query(MasterUser).filter(MasterUser.is_active == True)

    if tenant_id:
        # Users whose primary tenant matches
        primary_users = query.filter(MasterUser.tenant_id == tenant_id).all()
        # Users with membership in the tenant
        membership_rows = master_db.execute(
            user_tenant_association.select().where(user_tenant_association.c.tenant_id == tenant_id)
        ).fetchall()
        member_ids = {row.user_id for row in membership_rows}
        users_map = {u.id: u for u in primary_users}
        if member_ids:
            extra_users = master_db.query(MasterUser).filter(MasterUser.id.in_(list(member_ids))).all()
            for u in extra_users:
                users_map[u.id] = u
        users = list(users_map.values())
    else:
        users = query.offset(skip).limit(limit).all()

    enriched_users: List[Dict[str, Any]] = []
    for user in users:
        user_dict = user.__dict__.copy()
        user_dict.pop('_sa_instance_state', None)

        target_tenant_id = tenant_id or user.tenant_id
        tenant = master_db.query(Tenant).filter(Tenant.id == target_tenant_id).first()
        user_dict['tenant_name'] = tenant.name if tenant else "Unknown"

        # Effective role for the target tenant from association; fallback to user's primary role
        membership = master_db.execute(
            user_tenant_association.select().where(
                user_tenant_association.c.user_id == user.id,
                user_tenant_association.c.tenant_id == target_tenant_id
            )
        ).first()
        user_dict['role'] = getattr(membership, 'role', None) or user.role or 'user'

        enriched_users.append(user_dict)

    return enriched_users


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get detailed information about a specific user"""
    user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

    # Get tenant information
    tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()

    # Get user's tenant memberships
    tenant_memberships = master_db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == user_id
        )
    ).fetchall()

    user_dict = user.__dict__.copy()
    user_dict.pop('_sa_instance_state', None)
    user_dict['tenant_name'] = tenant.name if tenant else "Unknown"
    user_dict['tenant_ids'] = [str(membership.tenant_id) for membership in tenant_memberships]
    user_dict['primary_tenant_id'] = str(user.tenant_id)
    # Map per-tenant roles for the UI (default to 'user' if missing)
    tenant_roles: Dict[str, str] = {}
    for membership in tenant_memberships:
        tid = str(membership.tenant_id)
        role_value = getattr(membership, 'role', None) or 'user'
        tenant_roles[tid] = role_value
    user_dict['tenant_roles'] = tenant_roles

    return user_dict


@router.post("/users", response_model=Dict[str, Any])
async def create_user(
    user_data: dict,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Create a new user for multiple tenants"""
    # Check if this is an SSO user
    is_sso_user = user_data.get('is_sso', False)

    # Validate required fields - password is optional for SSO users
    if is_sso_user:
        required_fields = ['email', 'first_name', 'last_name', 'tenant_ids', 'primary_tenant_id']
    else:
        required_fields = ['email', 'first_name', 'last_name', 'password', 'tenant_ids', 'primary_tenant_id']

    for field in required_fields:
        if field not in user_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Validate email format
    email = user_data['email'].strip()
    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate password strength for non-SSO users
    if not is_sso_user:
        is_valid, errors = validate_password_strength(user_data['password'])
        if not is_valid:
            raise HTTPException(status_code=400, detail={"message": "Password does not meet requirements", "errors": errors})

    # Validate tenant IDs are not empty
    if not user_data['tenant_ids'] or not all(tid.strip() for tid in user_data['tenant_ids']):
        raise HTTPException(status_code=400, detail="Please select at least one organization")

    if not user_data['primary_tenant_id'] or not user_data['primary_tenant_id'].strip():
        raise HTTPException(status_code=400, detail="Please select a primary organization")

    tenant_ids = [int(tid) for tid in user_data['tenant_ids']]
    primary_tenant_id = int(user_data['primary_tenant_id'])
    # Optional per-tenant roles mapping coming from UI
    provided_tenant_roles: Dict[str, str] = user_data.get('tenant_roles', {}) or {}

    # Validate primary tenant is in tenant list
    if primary_tenant_id not in tenant_ids:
        raise HTTPException(status_code=400, detail="Primary tenant must be in selected tenants")

    # Check if tenants exist
    tenants = master_db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
    if len(tenants) != len(tenant_ids):
        raise HTTPException(status_code=404, detail="One or more tenants not found")

    # Check if user already exists
    existing_user = master_db.query(MasterUser).filter(
        MasterUser.email == user_data['email']
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )

    # Check global user limit
    primary_tenant = next((t for t in tenants if t.id == primary_tenant_id), None)
    should_count = primary_tenant.count_against_license if primary_tenant else True

    license_service = LicenseService(master_db, master_db=master_db)
    license_status = license_service.get_license_status()
    user_licensing_info = license_status.get("user_licensing_info")
    if should_count and user_licensing_info and user_licensing_info.get("max_users"):
        max_users = user_licensing_info["max_users"]
        current_users = user_licensing_info["current_users_count"]
        if current_users >= max_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User limit reached ({max_users}). Please upgrade global license or exempt a tenant/user to add more capacity."
            )

    # Create user in master database
    # For SSO users, generate a random password that they won't use
    if is_sso_user:
        hashed_password = get_password_hash(secrets.token_urlsafe(32))
    else:
        hashed_password = get_password_hash(user_data['password'])

    primary_role = provided_tenant_roles.get(str(primary_tenant_id), user_data.get('role', 'user'))

    # Create master user - SSO provider fields will be populated when user first signs in
    master_user = MasterUser(
        email=user_data['email'],
        hashed_password=hashed_password,
        first_name=user_data['first_name'],
        last_name=user_data['last_name'],
        role=primary_role,
        tenant_id=int(user_data['primary_tenant_id']),
        is_verified=True
    )

    master_db.add(master_user)
    master_db.commit()
    master_db.refresh(master_user)

    # Add user to tenant memberships (respect per-tenant roles if provided)
    for tenant_id in tenant_ids:
        role_for_tenant = provided_tenant_roles.get(str(tenant_id), user_data.get('role', 'user'))
        master_db.execute(
            user_tenant_association.insert().values(
                user_id=master_user.id,
                tenant_id=tenant_id,
                role=role_for_tenant
            )
        )

        # Create user in each tenant database
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()

            # Create tenant user - SSO provider fields will be populated when user first signs in
            tenant_user = TenantUser(
                id=master_user.id,
                email=user_data['email'],
                hashed_password=hashed_password,
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                role=role_for_tenant,
                is_verified=True
            )

            tenant_session.add(tenant_user)
            tenant_session.commit()
            tenant_session.close()

        except Exception:
            # Continue with other tenants if one fails
            pass

    master_db.commit()

    user_dict = master_user.__dict__.copy()
    user_dict.pop('_sa_instance_state', None)
    user_dict['tenant_names'] = [t.name for t in tenants]

    # Add SSO information to response
    user_dict['is_sso'] = is_sso_user

    return user_dict


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: dict,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Update a user's info across all systems"""
    user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update basic fields in master database
    basic_fields = ['first_name', 'last_name', 'email', 'role']
    for field in basic_fields:
        if field in user_data:
            setattr(user, field, user_data[field])

    if 'password' in user_data and user_data['password']:
        user.hashed_password = get_password_hash(user_data['password'])

    # Normalize primary tenant id and optionally align master role with per-tenant role
    provided_tenant_roles_update: Dict[str, str] = user_data.get('tenant_roles', {}) or {}
    if 'primary_tenant_id' in user_data:
        user.tenant_id = int(user_data['primary_tenant_id'])
        # If a specific role is provided for the primary tenant, sync it to master user.role
        maybe_primary_role = provided_tenant_roles_update.get(str(user.tenant_id))
        if maybe_primary_role:
            user.role = maybe_primary_role

    # Handle tenant memberships if provided
    if 'tenant_ids' in user_data:
        from core.utils.user_sync import remove_user_from_tenant_database
        tenant_ids = [int(tid) for tid in user_data['tenant_ids']]

        # Find existing memberships to identify removals
        existing_memberships = master_db.execute(
            user_tenant_association.select().where(
                user_tenant_association.c.user_id == user_id
            )
        ).fetchall()
        existing_tenant_ids = {row.tenant_id for row in existing_memberships}
        removed_tenant_ids = existing_tenant_ids - set(tenant_ids)

        # Remove existing memberships
        master_db.execute(
            user_tenant_association.delete().where(
                user_tenant_association.c.user_id == user_id
            )
        )

        # Add new memberships respecting per-tenant roles if provided
        for tenant_id in tenant_ids:
            role_for_tenant = provided_tenant_roles_update.get(str(tenant_id), user_data.get('role', 'user'))
            master_db.execute(
                user_tenant_association.insert().values(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    role=role_for_tenant
                )
            )
            # Also update role in each tenant database if user exists
            try:
                tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
                tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user_id).first()
                if tenant_user:
                    tenant_user.role = role_for_tenant
                    tenant_user.is_active = True  # Ensure active if re-enabling
                    tenant_session.commit()
                tenant_session.close()
            except Exception:
                pass

        # Sync removals to tenant databases
        for tenant_id in removed_tenant_ids:
            try:
                remove_user_from_tenant_database(user_id, tenant_id)
            except Exception as e:
                logger.error(f"Failed to sync removal for user {user_id} in tenant {tenant_id}: {e}")

    master_db.commit()
    master_db.refresh(user)

    return {"message": "User info updated successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Delete a user from all systems"""
    user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Don't allow deleting yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )

    # Delete from tenant database first
    try:
        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(
            TenantUser.id == user_id
        ).first()

        if tenant_user:
            tenant_user.is_active = False
            tenant_session.commit()

        tenant_session.close()
    except Exception:
        pass  # Continue even if tenant deactivation fails

    # Deactivate in master database (soft delete)
    user.is_active = False
    master_db.commit()

    # Log audit event in master database
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE_USER",
        resource_type="user",
        resource_id=str(user_id),
        resource_name=f"{user.first_name} {user.last_name}",
        details={
            "deleted_user_email": user.email,
            "deleted_from_tenant": user.tenant_id,
            "deletion_type": "super_admin_deletion",
            "performed_by_super_admin": True
        },
        tenant_id=current_user.tenant_id,
        status="success"
    )

    return {"message": "User deleted successfully"}


@router.patch("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Toggle user active/inactive status"""
    user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Don't allow disabling yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable yourself"
        )

    user.is_active = not user.is_active
    master_db.commit()

    # Update in tenant database too
    try:
        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user_id).first()
        if tenant_user:
            tenant_user.is_active = user.is_active
            tenant_session.commit()
        tenant_session.close()
    except Exception:
        pass

    status_text = "enabled" if user.is_active else "disabled"
    return {"message": f"User {user.email} {status_text} successfully"}


@router.post("/users/{user_id}/reset-password")
async def super_admin_reset_password(
    user_id: int,
    payload: SuperAdminResetPasswordRequest,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Super admin sets a new password for any user and optionally forces reset on next login."""
    is_valid, errors = validate_password_strength(payload.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"message": "Password does not meet requirements", "errors": errors})
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

    user.hashed_password = get_password_hash(payload.new_password)
    user.updated_at = datetime.now(timezone.utc)
    user.is_verified = True
    user.must_reset_password = bool(payload.force_reset_on_login)
    master_db.commit()

    # Sync to tenant DB
    try:
        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)()
        from core.models.models_per_tenant import User as TenantUserModel
        tenant_user = tenant_session.query(TenantUserModel).filter(TenantUserModel.id == user.id).first()
        if tenant_user:
            tenant_user.hashed_password = get_password_hash(payload.new_password)
            tenant_user.updated_at = datetime.now(timezone.utc)
            tenant_user.must_reset_password = bool(payload.force_reset_on_login)
            tenant_session.commit()
        tenant_session.close()
    except Exception:
        pass

    # Audit
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="user_password",
        resource_id=str(user.id),
        resource_name=f"Password reset for {user.email}",
        details={"force_reset_on_login": payload.force_reset_on_login},
        tenant_id=current_user.tenant_id,
        status="success"
    )

    return {"message": "Password updated"}


@router.post("/users/{user_id}/disable-mfa")
async def super_admin_disable_mfa(
    user_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Super admin disables MFA for any user and clears active MFA sessions."""
    user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

    _disable_mfa_fields(user)
    user.updated_at = datetime.now(timezone.utc)
    master_db.commit()

    try:
        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)()
        from core.models.models_per_tenant import User as TenantUserModel
        tenant_user = tenant_session.query(TenantUserModel).filter(TenantUserModel.id == user.id).first()
        if tenant_user:
            _disable_mfa_fields(tenant_user)
            tenant_user.updated_at = datetime.now(timezone.utc)
            tenant_session.commit()
        tenant_session.close()
    except Exception as exc:
        logger.warning("Failed to sync MFA disable to tenant DB for user %s: %s", user.email, exc)

    try:
        from commercial.mfa_chain.utils import clear_mfa_sessions_for_user
        clear_mfa_sessions_for_user(user.id)
    except Exception as exc:
        logger.warning("Failed to clear MFA sessions for user %s: %s", user.email, exc)

    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DISABLE_MFA",
        resource_type="user_mfa",
        resource_id=str(user.id),
        resource_name=f"MFA disabled for {user.email}",
        details={"target_user_email": user.email},
        tenant_id=current_user.tenant_id,
        status="success"
    )

    return {"message": f"MFA disabled for {user.email}"}


@router.put("/tenants/{tenant_id}/users/{user_id}/role")
async def super_admin_update_user_role_for_tenant(
    tenant_id: int,
    user_id: int,
    role_update: UserRoleUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Super admin: update a user's role within a specific tenant (membership and tenant DB)."""
    # Validate tenant and user exist
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    target_user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

    # Upsert membership with role
    existing_membership = master_db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == user_id,
            user_tenant_association.c.tenant_id == tenant_id
        )
    ).first()

    if existing_membership:
        master_db.execute(
            user_tenant_association.update()
            .where(
                user_tenant_association.c.user_id == user_id,
                user_tenant_association.c.tenant_id == tenant_id
            )
            .values(role=role_update.role, is_active=True)
        )
    else:
        master_db.execute(
            user_tenant_association.insert().values(
                user_id=user_id,
                tenant_id=tenant_id,
                role=role_update.role,
                is_active=True
            )
        )
    master_db.commit()

    # Update in tenant database
    try:
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user_id).first()
        if tenant_user:
            tenant_user.role = role_update.role
            tenant_user.is_active = True  # Ensure active if re-enabling
            tenant_session.commit()
        tenant_session.close()
    except Exception as e:
        print(f"Failed to update user role in tenant database: {e}")

    # Audit
    try:
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="user_role",
            resource_id=str(user_id),
            resource_name=f"Role update for user {target_user.email} in tenant {tenant_id}",
            details={"tenant_id": tenant_id, "new_role": role_update.role},
            tenant_id=current_user.tenant_id,
            status="success"
        )
    except Exception as e:
        # Log error but don't fail the operation
        print(f"Failed to log role update to master audit log: {e}")

    # Also log audit event in tenant database for visibility in regular audit log
    try:
        tenant_db = tenant_db_manager.get_tenant_session(tenant_id)()
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="user_role",
            resource_id=str(user_id),
            resource_name=f"Role update for user {target_user.email} in tenant {tenant_id}",
            details={"tenant_id": tenant_id, "new_role": role_update.role},
            status="success"
        )
        tenant_db.close()
    except Exception as e:
        # Log error but don't fail the operation
        print(f"Failed to log role update to tenant audit log: {e}")

    return {"message": "User role updated for tenant"}


@router.post("/promote", response_model=Dict[str, str])
async def promote_to_super_admin(
    request: PromoteUserRequest,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Promote a user to super admin by email (super admin only)"""
    user = master_db.query(MasterUser).filter(MasterUser.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email '{request.email}' not found")
    if user.is_superuser:
        return {"message": f"User '{request.email}' is already a super admin."}

    # Store old role and superuser status for audit logging
    old_role = user.role
    old_is_superuser = user.is_superuser

    user.is_superuser = True
    user.role = 'admin'
    master_db.commit()

    # Also update in tenant DB if user exists there
    try:
        tenant_id = user.tenant_id
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user.id).first()
        if tenant_user:
            tenant_user.is_superuser = True
            tenant_user.role = 'admin'
            tenant_session.commit()
        tenant_session.close()
    except Exception:
        pass  # Ignore tenant DB errors

    # Log audit event in master database
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="PROMOTE",
        resource_type="user_superuser",
        resource_id=str(user.id),
        resource_name=f"Super admin promotion for {user.email}",
        details={
            "promoted_user_id": user.id,
            "promoted_user_email": user.email,
            "old_role": old_role,
            "new_role": "admin",
            "old_is_superuser": old_is_superuser,
            "new_is_superuser": True,
            "promoted_by": current_user.email
        },
        tenant_id=current_user.tenant_id,
        status="success"
    )

    # Also log audit event in tenant database for visibility in regular audit log
    try:
        tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="PROMOTE",
            resource_type="user_superuser",
            resource_id=str(user.id),
            resource_name=f"Super admin promotion for {user.email}",
            details={
                "promoted_user_id": user.id,
                "promoted_user_email": user.email,
                "old_role": old_role,
                "new_role": "admin",
                "old_is_superuser": old_is_superuser,
                "new_is_superuser": True,
                "promoted_by": current_user.email
            },
            status="success"
        )
        tenant_db.close()
    except Exception as e:
        # Log error but don't fail the operation
        print(f"Failed to log promotion to tenant audit log: {e}")

    return {"message": f"User '{request.email}' has been promoted to super admin."}


@router.post("/demote", response_model=Dict[str, str])
async def demote_super_admin(
    request: PromoteUserRequest,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Demote a super admin to regular admin by email (super admin only)"""
    user = master_db.query(MasterUser).filter(MasterUser.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email '{request.email}' not found")
    if not user.is_superuser:
        return {"message": f"User '{request.email}' is not a super admin."}
    # Prevent demoting the last super admin
    super_admin_count = master_db.query(MasterUser).filter(MasterUser.is_superuser == True).count()
    if super_admin_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot demote the last remaining super admin.")

    # Store old values for audit logging
    old_role = user.role
    old_is_superuser = user.is_superuser

    user.is_superuser = False
    master_db.commit()

    # Also update in tenant DB if user exists there
    try:
        tenant_id = user.tenant_id
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.email == request.email).first()
        if tenant_user:
            tenant_user.is_superuser = False
            tenant_session.commit()
        tenant_session.close()
    except Exception:
        pass  # Ignore tenant DB errors

    # Log audit event in master database
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DEMOTE",
        resource_type="user_superuser",
        resource_id=str(user.id),
        resource_name=f"Super admin demotion for {user.email}",
        details={
            "demoted_user_id": user.id,
            "demoted_user_email": user.email,
            "old_role": old_role,
            "new_role": user.role,
            "old_is_superuser": old_is_superuser,
            "new_is_superuser": False,
            "demoted_by": current_user.email
        },
        tenant_id=current_user.tenant_id,
        status="success"
    )

    # Also log audit event in tenant database for visibility in regular audit log
    try:
        tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DEMOTE",
            resource_type="user_superuser",
            resource_id=str(user.id),
            resource_name=f"Super admin demotion for {user.email}",
            details={
                "demoted_user_id": user.id,
                "demoted_user_email": user.email,
                "old_role": old_role,
                "new_role": user.role,
                "old_is_superuser": old_is_superuser,
                "new_is_superuser": False,
                "demoted_by": current_user.email
            },
            status="success"
        )
        tenant_db.close()
    except Exception as e:
        # Log error but don't fail the operation
        print(f"Failed to log demotion to tenant audit log: {e}")

    return {"message": f"User '{request.email}' has been demoted from super admin."}
