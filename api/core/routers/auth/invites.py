# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Core module of YourFinanceWORKS.
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
# See LICENSE-AGPLv3.txt for details.

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
import os
import secrets
import logging

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant, Invite, Settings
from core.schemas.user import (
    Token, UserList, InviteCreate, InviteRead, InviteAccept, UserRoleUpdate, AdminActivateUser
)
from core.utils.auth import get_password_hash, create_access_token
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager
from core.middleware.tenant_context_middleware import set_tenant_context
from core.utils.rbac import require_admin
from core.utils.audit import log_audit_event, log_audit_event_master
from core.routers.auth._shared import (
    get_current_user, get_email_service_for_tenant, generate_invite_token,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def send_invite_email(email: str, invite_url: str, inviter_name: str, tenant_name: str):
    """Send invite email (placeholder - implement with your email service)"""
    # TODO: Implement with your email service (SendGrid, AWS SES, etc.)
    print(f"Invite email to {email}: {invite_url}")
    return True


@router.post("/invite", response_model=InviteRead)
async def invite_user(
    invite_data: InviteCreate,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Invite a user to the organization (admin only)"""
    require_admin(current_user, "invite users")

    invite_email = (invite_data.email or "").strip()
    if not invite_email:
        raise HTTPException(status_code=400, detail="Email is required")

    existing_master_user = db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(invite_email)
    ).first()

    if existing_master_user:
        from core.models.models import user_tenant_association
        membership = db.execute(
            user_tenant_association.select().where(
                user_tenant_association.c.user_id == existing_master_user.id,
                user_tenant_association.c.tenant_id == current_user.tenant_id
            )
        ).first()
        if membership or existing_master_user.tenant_id == current_user.tenant_id:
            raise HTTPException(status_code=400, detail="User already exists in this organization")

    existing_invite = db.query(Invite).filter(
        func.lower(Invite.email) == func.lower(invite_email),
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == False,
        Invite.expires_at > datetime.now(timezone.utc)
    ).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="User already has a valid pending invite that has not expired")

    accepted_invite = db.query(Invite).filter(
        func.lower(Invite.email) == func.lower(invite_email),
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == True
    ).first()
    if accepted_invite:
        raise HTTPException(status_code=400, detail="User already accepted an invite for this organization")

    try:
        tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
        try:
            tenant_user_exists = tenant_db.query(TenantUser).filter(func.lower(TenantUser.email) == func.lower(invite_email)).first()
            if tenant_user_exists:
                raise HTTPException(status_code=400, detail="User already exists in this organization")
        finally:
            tenant_db.close()
    except Exception:
        pass

    invite = Invite(
        email=invite_email,
        first_name=invite_data.first_name,
        last_name=invite_data.last_name,
        role=invite_data.role,
        token=generate_invite_token(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        tenant_id=current_user.tenant_id,
        invited_by_id=current_user.id
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    invite_path = f"/accept-invite?token={invite.token}"
    inviter_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    tenant_name = tenant.name if tenant else "Organization"
    ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
    accept_url = f"{ui_base}{invite_path}"

    email_service = get_email_service_for_tenant(db, current_user.tenant_id)
    if email_service and tenant:
        try:
            email_settings = db.query(Settings).filter(
                Settings.tenant_id == current_user.tenant_id,
                Settings.key == "email_config"
            ).first()
            email_config_data = email_settings.value if email_settings else {}
            from_name = email_config_data.get('from_name', tenant_name)
            from_email = email_config_data.get('from_email', 'noreply@invoiceapp.com')
            invitee_name = (invite.first_name or "") + (" " + invite.last_name if invite.last_name else "")

            email_service.send_invitation_email(
                invitee_email=invite.email,
                invitee_name=invitee_name.strip() or invite.email,
                accept_url=accept_url,
                company_name=tenant_name,
                inviter_name=inviter_name,
                from_name=from_name,
                from_email=from_email,
                role=invite.role
            )
        except Exception:
            send_invite_email(invite.email, accept_url, inviter_name, tenant_name)
    else:
        send_invite_email(invite.email, accept_url, inviter_name, tenant_name)

    log_audit_event_master(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="invite",
        resource_id=str(invite.id),
        resource_name=f"Invite for {invite.email}",
        details=invite_data.dict(),
        tenant_id=current_user.tenant_id,
        status="success"
    )

    tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="invite",
            resource_id=str(invite.id),
            resource_name=f"Invite for {invite.email}",
            details=invite_data.dict(),
            status="success"
        )
    finally:
        tenant_db.close()

    invite_response = InviteRead(
        id=invite.id,
        email=invite.email,
        first_name=invite.first_name,
        last_name=invite.last_name,
        role=invite.role,
        is_accepted=invite.is_accepted,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        invited_by=current_user.email
    )

    return invite_response


@router.get("/invites", response_model=List[InviteRead])
async def list_invites(
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all invites for the organization (admin only)"""
    require_admin(current_user, "view invites")
    invites = db.query(Invite).filter(
        Invite.tenant_id == current_user.tenant_id
    ).all()

    result = []
    for invite in invites:
        inviter = db.query(MasterUser).filter(MasterUser.id == invite.invited_by_id).first()
        invite_dict = {
            "id": invite.id,
            "email": invite.email,
            "first_name": invite.first_name,
            "last_name": invite.last_name,
            "role": invite.role,
            "is_accepted": invite.is_accepted,
            "expires_at": invite.expires_at,
            "created_at": invite.created_at,
            "invited_by": inviter.email if inviter else None
        }
        result.append(InviteRead(**invite_dict))

    return result


@router.delete("/invites/{invite_id}", response_model=Dict[str, str])
async def cancel_invite(
    invite_id: int,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Cancel a pending invite (admin only)"""
    require_admin(current_user, "cancel invites")

    invite = db.query(Invite).filter(
        Invite.id == invite_id,
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == False
    ).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already accepted")

    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot cancel an expired invite")

    invite_email = invite.email
    invite_role = invite.role

    db.delete(invite)
    db.commit()

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE",
        resource_type="invite",
        resource_id=str(invite_id),
        resource_name=f"Invite for {invite_email}",
        details={
            "cancelled_invite_id": invite_id,
            "cancelled_email": invite_email,
            "cancelled_role": invite_role,
            "cancelled_by": current_user.email,
            "cancelled_at": datetime.now(timezone.utc).isoformat()
        },
        status="success"
    )

    return {"message": f"Invite for {invite_email} has been cancelled"}


@router.post("/accept-invite", response_model=Token)
async def accept_invite(
    invite_data: InviteAccept,
    db: Session = Depends(get_master_db)
):
    """Accept an invite and create user account"""
    invite = db.query(Invite).filter(
        Invite.token == invite_data.token,
        Invite.is_accepted == False,
        Invite.expires_at > datetime.now(timezone.utc)
    ).first()

    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")

    existing_user = db.query(MasterUser).filter(
        MasterUser.email == invite.email,
        MasterUser.tenant_id == invite.tenant_id
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_password = get_password_hash(invite_data.password)

    existing_master_user = db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(invite.email)
    ).first()

    if existing_master_user:
        master_user = existing_master_user
    else:
        master_user = MasterUser(
            email=invite.email,
            hashed_password=hashed_password,
            first_name=invite_data.first_name or invite.first_name,
            last_name=invite_data.last_name or invite.last_name,
            role=invite.role,
            tenant_id=invite.tenant_id,
            is_verified=True,
            is_superuser=False
        )
        db.add(master_user)
        db.commit()
        db.refresh(master_user)

    from core.models.models import user_tenant_association
    existing_membership = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == master_user.id,
            user_tenant_association.c.tenant_id == invite.tenant_id
        )
    ).first()
    if not existing_membership:
        db.execute(
            user_tenant_association.insert().values(
                user_id=master_user.id,
                tenant_id=invite.tenant_id,
                role=invite.role
            )
        )
        db.commit()

    set_tenant_context(invite.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    try:
        existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == master_user.id).first()
        if not existing_tenant_user:
            existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.email == invite.email).first()

        if existing_tenant_user:
            existing_tenant_user.email = invite.email
            existing_tenant_user.hashed_password = master_user.hashed_password
            existing_tenant_user.first_name = invite_data.first_name or invite.first_name
            existing_tenant_user.last_name = invite_data.last_name or invite.last_name
            existing_tenant_user.role = invite.role
            existing_tenant_user.is_verified = True
            existing_tenant_user.is_superuser = False
            existing_tenant_user.updated_at = datetime.now(timezone.utc)
            tenant_db.commit()
        else:
            tenant_user = TenantUser(
                id=master_user.id,
                email=invite.email,
                hashed_password=master_user.hashed_password,
                first_name=invite_data.first_name or invite.first_name,
                last_name=invite_data.last_name or invite.last_name,
                role=invite.role,
                is_verified=True,
                is_superuser=False
            )
            tenant_db.add(tenant_user)
            tenant_db.commit()
        user = master_user
    except Exception as e:
        db.delete(master_user)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to create tenant user: {str(e)}")
    finally:
        tenant_db.close()

    invite.is_accepted = True
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()

    set_tenant_context(invite.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=0,
            user_email=invite.email,
            action="ACCEPT_INVITE",
            resource_type="invite",
            resource_id=str(invite.id),
            resource_name=f"Invite accepted by {invite.email}",
            details={
                "invite_id": invite.id,
                "accepted_email": invite.email,
                "role": invite.role,
                "accepted_at": datetime.now(timezone.utc).isoformat()
            },
            status="success"
        )
    finally:
        tenant_db.close()

    access_token = create_access_token(data={"sub": user.email})

    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.get("/users", response_model=List[UserList])
async def list_users(
    current_user: MasterUser = Depends(get_current_user),
    master_db: Session = Depends(get_master_db)
):
    """List all users who have access to the current organization"""
    from core.models.database import get_tenant_context
    current_tenant_id = get_tenant_context()
    if not current_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")

    from core.models.models import user_tenant_association

    user_tenant_memberships = master_db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.tenant_id == current_tenant_id
        )
    ).fetchall()

    user_ids = [membership.user_id for membership in user_tenant_memberships]

    primary_users = master_db.query(MasterUser).filter(
        MasterUser.tenant_id == current_tenant_id
    ).all()

    for user in primary_users:
        if user.id not in user_ids:
            user_ids.append(user.id)

    if user_ids:
        users = master_db.query(MasterUser).filter(MasterUser.id.in_(user_ids)).all()

        try:
            tenant_session = tenant_db_manager.get_tenant_session(current_tenant_id)
            tenant_db = tenant_session()
            try:
                tenant_users = tenant_db.query(TenantUser).filter(
                    TenantUser.id.in_(user_ids)
                ).all()

                tenant_role_map = {tu.id: tu.role for tu in tenant_users}
                logger.info(f"Found {len(tenant_role_map)} tenant-specific roles: {tenant_role_map}")

                for user in users:
                    if user.id in tenant_role_map:
                        user.role = tenant_role_map[user.id]
                        logger.info(f"Including user {user.email} with tenant role '{user.role}'")
                    else:
                        logger.info(f"Including user {user.email} with master role '{user.role}' (not yet activated in tenant)")

            finally:
                tenant_db.close()
        except Exception as e:
            logger.warning(f"Failed to get tenant-specific roles for users in tenant {current_tenant_id}: {e}")
            users = []

        logger.info(f"Returning {len(users)} users with roles: {[(u.email, u.role) for u in users]}")
        return users
    else:
        return []


@router.put("/users/{user_id}/role", response_model=UserList)
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    tenant_id: Optional[int] = Query(None),
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update user role (admin only)"""
    require_admin(current_user, "update user roles")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot update your own role")

    from core.models.database import get_tenant_context
    current_tenant_id = tenant_id or get_tenant_context()
    if not current_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")

    if not current_user.is_superuser:
        try:
            auth_tenant_db = tenant_db_manager.get_tenant_session(current_tenant_id)()
            try:
                me_in_tenant = auth_tenant_db.query(TenantUser).filter(TenantUser.id == current_user.id).first()
                if not me_in_tenant or me_in_tenant.role != 'admin':
                    raise HTTPException(status_code=403, detail="ROLE_NOT_ALLOWED")
            finally:
                auth_tenant_db.close()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=403, detail="ROLE_NOT_ALLOWED")

    user = db.query(MasterUser).filter(MasterUser.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_target_owner_of_current_tenant = (user.tenant_id == current_tenant_id)
    if is_target_owner_of_current_tenant and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot change role of the organization owner")

    from core.models.models import user_tenant_association
    membership = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == user_id,
            user_tenant_association.c.tenant_id == current_tenant_id
        )
    ).first()
    if not membership:
        db.execute(
            user_tenant_association.insert().values(
                user_id=user_id,
                tenant_id=current_tenant_id,
                role=role_update.role,
                is_active=True
            )
        )
    else:
        logger.info(f"Updating EXISTING membership for user {user_id} in tenant {current_tenant_id} to role {role_update.role}")
        db.execute(
            user_tenant_association.update()
            .where(
                user_tenant_association.c.user_id == user_id,
                user_tenant_association.c.tenant_id == current_tenant_id
            )
            .values(role=role_update.role, is_active=True)
        )
    db.commit()

    old_role = user.role
    logger.info(f"Updating role for user {user.email} (ID: {user_id}) from '{old_role}' to '{role_update.role}'")

    try:
        tenant_db = tenant_db_manager.get_tenant_session(current_tenant_id)()
        try:
            tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user_id).first()
            if tenant_user:
                tenant_user.role = role_update.role
                tenant_user.is_active = True
                tenant_db.commit()
                logger.info(f"Updated role and active status in tenant database for user {user.email}")
            else:
                new_tenant_user = TenantUser(
                    id=user.id,
                    email=user.email,
                    hashed_password=user.hashed_password,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    role=role_update.role,
                    is_active=True,
                    is_verified=user.is_verified,
                    is_superuser=False
                )
                tenant_db.add(new_tenant_user)
                tenant_db.commit()
        finally:
            tenant_db.close()
    except Exception as e:
        logger.error(f"Failed to update role in tenant database for user {user.email}: {e}")

    response_user = MasterUser(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=role_update.role,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        tenant_id=user.tenant_id,
        theme=user.theme,
        google_id=user.google_id,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

    log_audit_event_master(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="user_role",
        resource_id=str(user_id),
        resource_name=f"Role update for {user.email}",
        details={
            "updated_user_id": user_id,
            "updated_user_email": user.email,
            "old_role": old_role,
            "new_role": role_update.role,
            "updated_by": current_user.email
        },
        tenant_id=current_tenant_id,
        status="success"
    )

    tenant_db = tenant_db_manager.get_tenant_session(current_tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="user_role",
            resource_id=str(user_id),
            resource_name=f"Role update for {user.email}",
            details={
                "updated_user_id": user_id,
                "updated_user_email": user.email,
                "old_role": old_role,
                "new_role": role_update.role,
                "updated_by": current_user.email
            },
            status="success"
        )
    finally:
        tenant_db.close()

    return response_user


@router.post("/invites/{invite_id}/activate", response_model=UserList)
async def admin_activate_user(
    invite_id: int,
    activation_data: AdminActivateUser,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Admin activates a pending invite by setting password and creating user account"""
    require_admin(current_user, "activate users")

    invite = db.query(Invite).filter(
        Invite.id == invite_id,
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == False
    ).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already accepted")

    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite has expired")

    existing_user = db.query(MasterUser).filter(
        MasterUser.email == invite.email,
        MasterUser.tenant_id == current_user.tenant_id
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    generated_temp_password: Optional[str] = None
    if activation_data.password and len(activation_data.password) >= 6:
        hashed_password = get_password_hash(activation_data.password)
    else:
        generated_temp_password = secrets.token_urlsafe(12)
        hashed_password = get_password_hash(generated_temp_password)

    invite.is_accepted = True
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()

    existing_master_user = db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(invite.email)
    ).first()
    if existing_master_user:
        master_user = existing_master_user
    else:
        master_user = MasterUser(
            email=invite.email,
            hashed_password=hashed_password,
            first_name=activation_data.first_name or invite.first_name,
            last_name=activation_data.last_name or invite.last_name,
            role=invite.role,
            tenant_id=invite.tenant_id,
            is_verified=True,
            is_superuser=False
        )
        db.add(master_user)
        db.commit()
        db.refresh(master_user)
        try:
            master_user.must_reset_password = bool(generated_temp_password is not None)
            db.commit()
        except Exception:
            db.rollback()

    from core.models.models import user_tenant_association
    existing_membership = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == master_user.id,
            user_tenant_association.c.tenant_id == invite.tenant_id
        )
    ).first()
    if not existing_membership:
        db.execute(
            user_tenant_association.insert().values(
                user_id=master_user.id,
                tenant_id=invite.tenant_id,
                role=invite.role
            )
        )
        db.commit()

    set_tenant_context(invite.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    try:
        existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == master_user.id).first()
        if not existing_tenant_user:
            existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.email == invite.email).first()

        if existing_tenant_user:
            existing_tenant_user.email = invite.email
            existing_tenant_user.hashed_password = master_user.hashed_password
            existing_tenant_user.first_name = activation_data.first_name or invite.first_name
            existing_tenant_user.last_name = activation_data.last_name or invite.last_name
            existing_tenant_user.role = invite.role
            existing_tenant_user.is_active = True
            existing_tenant_user.is_verified = True
            existing_tenant_user.is_superuser = False
            existing_tenant_user.must_reset_password = master_user.must_reset_password
            existing_tenant_user.updated_at = datetime.now(timezone.utc)
            tenant_db.commit()
        else:
            tenant_user = TenantUser(
                id=master_user.id,
                email=invite.email,
                hashed_password=master_user.hashed_password,
                first_name=activation_data.first_name or invite.first_name,
                last_name=activation_data.last_name or invite.last_name,
                role=invite.role,
                is_verified=True,
                is_superuser=False,
                must_reset_password=master_user.must_reset_password
            )
            tenant_db.add(tenant_user)
            tenant_db.commit()

        user = master_user

        if generated_temp_password:
            try:
                ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
                accept_path = f"/accept-invite?token={invite.token}"
                accept_url = f"{ui_base}{accept_path}"
                tenant = db.query(Tenant).filter(Tenant.id == invite.tenant_id).first()
                email_service = get_email_service_for_tenant(db, invite.tenant_id)
                if email_service and tenant:
                    email_settings = db.query(Settings).filter(
                        Settings.tenant_id == invite.tenant_id,
                        Settings.key == "email_config"
                    ).first()
                    email_config_data = email_settings.value if email_settings else {}
                    from_name = email_config_data.get('from_name', tenant.name)
                    from_email = email_config_data.get('from_email', 'noreply@invoiceapp.com')
                    inviter = db.query(MasterUser).filter(MasterUser.id == invite.invited_by_id).first()
                    inviter_name = (f"{inviter.first_name or ''} {inviter.last_name or ''}").strip() or (inviter.email if inviter else tenant.name)
                    invitee_name = (activation_data.first_name or invite.first_name or "") + (" " + (activation_data.last_name or invite.last_name) if (activation_data.last_name or invite.last_name) else "")
                    email_service.send_invitation_email(
                        invitee_email=invite.email,
                        invitee_name=invitee_name.strip() or invite.email,
                        accept_url=accept_url,
                        company_name=tenant.name,
                        inviter_name=inviter_name,
                        from_name=from_name,
                        from_email=from_email,
                        role=invite.role
                    )
            except Exception:
                pass
    except Exception as e:
        db.delete(master_user)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to create tenant user: {str(e)}")
    finally:
        tenant_db.close()

    activation_details = activation_data.dict()
    if 'password' in activation_details:
        activation_details.pop('password', None)
    log_audit_event_master(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="ACTIVATE",
        resource_type="user",
        resource_id=str(user.id) if hasattr(user, 'id') else None,
        resource_name=f"User {invite.email}",
        details={
            "invite_id": invite.id,
            "activated_email": invite.email,
            "role": invite.role,
            "activation_data": activation_details
        },
        tenant_id=current_user.tenant_id,
        status="success"
    )

    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="ACTIVATE",
            resource_type="user",
            resource_id=str(user.id) if hasattr(user, 'id') else None,
            resource_name=f"User {invite.email}",
            details={
                "invite_id": invite.id,
                "activated_email": invite.email,
                "role": invite.role,
                "activation_data": activation_details
            },
            status="success"
        )
    finally:
        tenant_db.close()

    return user


@router.delete("/users/{user_id}", response_model=Dict[str, str])
async def remove_user_from_organization(
    user_id: int,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Remove a user from the current organization (admin only)"""
    require_admin(current_user, "remove users")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")

    from core.models.models import user_tenant_association
    from core.utils.user_sync import remove_user_from_tenant_database
    from core.models.database import get_tenant_context

    current_tenant_id = get_tenant_context()
    if not current_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")

    user = db.query(MasterUser).filter(
        MasterUser.id == user_id,
        MasterUser.tenant_id == current_tenant_id
    ).first()

    is_primary = user is not None

    if not is_primary:
        membership = db.execute(
            user_tenant_association.select().where(
                user_tenant_association.c.user_id == user_id,
                user_tenant_association.c.tenant_id == current_tenant_id
            )
        ).first()

        if not membership:
            raise HTTPException(status_code=404, detail="User not found in this organization")

        user = db.query(MasterUser).filter(MasterUser.id == user_id).first()

    user_email = user.email
    user_name = f"{user.first_name} {user.last_name}" if user.first_name or user.last_name else user.email

    logger.info(f"[USER REMOVAL] Deactivating user {user_id} in tenant {current_tenant_id}")
    success = remove_user_from_tenant_database(user_id, current_tenant_id)
    logger.info(f"[USER REMOVAL] Deactivation result: {success}")

    db.execute(
        user_tenant_association.delete().where(
            user_tenant_association.c.user_id == user_id,
            user_tenant_association.c.tenant_id == current_tenant_id
        )
    )

    if is_primary:
        logger.info(f"[USER REMOVAL] Deactivating master record for primary user {user_id}")
        user.is_active = False

    db.commit()

    try:
        tenant_session = tenant_db_manager.get_tenant_session(current_tenant_id)()

        log_audit_event(
            db=tenant_session,
            user_id=current_user.id,
            user_email=current_user.email,
            action="REMOVE_USER_FROM_ORGANIZATION",
            resource_type="user",
            resource_id=str(user_id),
            resource_name=user_name,
            details={
                "removed_user_email": user_email,
                "removed_from_tenant": current_tenant_id,
                "was_primary": is_primary
            },
            status="success"
        )
        tenant_session.close()
    except Exception as e:
        logger.error(f"Failed to log tenant audit event: {e}")

    return {"message": "User has been removed from the organization"}
