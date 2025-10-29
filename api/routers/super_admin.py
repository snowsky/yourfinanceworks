from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel

from models.database import get_master_db
from models.models import (
    Tenant, MasterUser, User, Client, ClientNote, Invoice, Payment, Settings, CurrencyRate, DiscountRule, AIConfig, user_tenant_association
)
from models.models_per_tenant import User as TenantUser
from schemas.user import UserCreate, UserUpdate, UserList, UserRoleUpdate
from schemas.tenant import TenantCreate, TenantUpdate, Tenant as TenantSchema
from routers.auth import get_current_user
from services.tenant_database_manager import tenant_db_manager
from utils.auth import get_password_hash
from utils.rbac import require_superuser
from utils.audit import log_audit_event, log_audit_event_master
from constants.error_codes import USER_NOT_FOUND, ONLY_SUPERUSERS, FAILED_TO_IMPORT_DATA

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

# Add the request model for the promote endpoint
class PromoteUserRequest(BaseModel):
    email: str

class SuperAdminResetPasswordRequest(BaseModel):
    new_password: str
    confirm_password: str
    force_reset_on_login: bool = False

def require_super_admin(current_user: MasterUser = Depends(get_current_user)):
    """Require that the current user is a superuser in their primary tenant"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    
    # Check if user is in their primary tenant
    from models.database import get_tenant_context
    current_tenant_id = get_tenant_context()
    if current_tenant_id and current_tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access restricted to home organization"
        )
    
    return current_user

# ========== TENANT MANAGEMENT ==========

@router.get("/tenants")
async def get_tenants(
    skip: int = 0,
    limit: int = 100,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """List all tenants with their statistics"""
    tenants = master_db.query(Tenant).offset(skip).limit(limit).all()
    
    # Add user counts for each tenant
    enriched_tenants = []
    for tenant in tenants:
        tenant_dict = tenant.__dict__.copy()
        # Remove SQLAlchemy internal attributes
        tenant_dict.pop('_sa_instance_state', None)
        
        # Map company_logo_url back to logo_url for schema compatibility
        if 'company_logo_url' in tenant_dict:
            tenant_dict['logo_url'] = tenant_dict.pop('company_logo_url')
        
        # Add user count
        user_count = master_db.query(MasterUser).filter(
            MasterUser.tenant_id == tenant.id
        ).count()
        tenant_dict['user_count'] = user_count
        
        enriched_tenants.append(tenant_dict)
    
    return enriched_tenants

@router.get("/tenants/{tenant_id}/stats")
async def get_tenant_stats(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get detailed statistics for a specific tenant"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Get user count from master database
    user_count = master_db.query(MasterUser).filter(
        MasterUser.tenant_id == tenant_id
    ).count()
    
    # Get data from tenant database
    tenant_stats = {"users": user_count, "clients": 0, "invoices": 0, "payments": 0}
    
    try:
        # Get tenant database session
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
        
        # Import tenant models
        from models.models_per_tenant import Client, Invoice, Payment
        
        # Get counts from tenant database
        tenant_stats["clients"] = tenant_session.query(Client).count()
        tenant_stats["invoices"] = tenant_session.query(Invoice).count()
        tenant_stats["payments"] = tenant_session.query(Payment).count()
        
        tenant_session.close()
    except Exception as e:
        # If tenant database doesn't exist or has issues, just return basic stats
        pass
    
    return {
        "tenant": tenant,
        "stats": tenant_stats
    }

@router.post("/tenants", response_model=TenantSchema)
async def create_tenant(
    tenant: TenantCreate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Create a new tenant and its database"""
    # Check if tenant name already exists
    existing_tenant = master_db.query(Tenant).filter(
        func.lower(Tenant.name) == func.lower(tenant.name)
    ).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant name already exists"
        )
    
    # Create tenant in master database
    tenant_data = tenant.model_dump()
    # Map logo_url to company_logo_url to match the model field
    if 'logo_url' in tenant_data:
        tenant_data['company_logo_url'] = tenant_data.pop('logo_url')
    
    db_tenant = Tenant(**tenant_data)
    master_db.add(db_tenant)
    master_db.commit()
    master_db.refresh(db_tenant)
    
    # Create tenant database
    success = tenant_db_manager.create_tenant_database(db_tenant.id, db_tenant.name)
    if not success:
        # Rollback tenant creation if database creation fails
        master_db.delete(db_tenant)
        master_db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tenant database"
        )
    
    # Create a user with the tenant's email if provided
    if db_tenant.email:
        try:
            # Check if user already exists
            existing_user = master_db.query(MasterUser).filter(
                MasterUser.email == db_tenant.email
            ).first()
            
            if not existing_user:
                # Create user in master database
                hashed_password = get_password_hash("password123")  # Default password
                master_user = MasterUser(
                    email=db_tenant.email,
                    hashed_password=hashed_password,
                    first_name=db_tenant.name,
                    last_name="Admin",
                    role="admin",
                    tenant_id=db_tenant.id,
                    is_verified=True
                )
                
                master_db.add(master_user)
                master_db.commit()
                master_db.refresh(master_user)
                
                # Create user in tenant database
                tenant_session = tenant_db_manager.get_tenant_session(db_tenant.id)()
                
                tenant_user = TenantUser(
                    id=master_user.id,
                    email=db_tenant.email,
                    hashed_password=hashed_password,
                    first_name=db_tenant.name,
                    last_name="Admin",
                    role="admin",
                    is_verified=True
                )
                
                tenant_session.add(tenant_user)
                tenant_session.commit()
                tenant_session.close()
        except Exception as e:
            # Don't fail tenant creation if user creation fails
            pass
    
    return db_tenant

@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    tenant_update: TenantUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Update any tenant's information"""
    db_tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Update tenant fields
    tenant_data = tenant_update.model_dump(exclude_unset=True)
    # Map logo_url to company_logo_url to match the model field
    if 'logo_url' in tenant_data:
        tenant_data['company_logo_url'] = tenant_data.pop('logo_url')
    
    for field, value in tenant_data.items():
        setattr(db_tenant, field, value)
    
    master_db.commit()
    master_db.refresh(db_tenant)
    return db_tenant

@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Delete a tenant and its database"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Don't allow deleting your own tenant
    if tenant_id == current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own tenant"
        )

    # Manually delete all related data for this tenant
    master_db.query(MasterUser).filter(MasterUser.tenant_id == tenant_id).delete()
    master_db.query(User).filter(User.tenant_id == tenant_id).delete()
    master_db.query(ClientNote).filter(ClientNote.tenant_id == tenant_id).delete()
    master_db.query(Payment).filter(Payment.tenant_id == tenant_id).delete()
    master_db.query(Invoice).filter(Invoice.tenant_id == tenant_id).delete()
    master_db.query(Client).filter(Client.tenant_id == tenant_id).delete()
    master_db.query(Settings).filter(Settings.tenant_id == tenant_id).delete()
    master_db.query(CurrencyRate).filter(CurrencyRate.tenant_id == tenant_id).delete()
    master_db.query(DiscountRule).filter(DiscountRule.tenant_id == tenant_id).delete()
    master_db.query(AIConfig).filter(AIConfig.tenant_id == tenant_id).delete()

    # Delete tenant database first
    success = tenant_db_manager.drop_tenant_database(tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tenant database"
        )

    # Delete tenant from master database
    master_db.delete(tenant)
    master_db.commit()

    return {"message": f"Tenant {tenant.name} deleted successfully"}

@router.patch("/tenants/{tenant_id}/toggle-status")
async def toggle_tenant_status(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Toggle tenant active/inactive status"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Don't allow disabling your own tenant
    if tenant_id == current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable your own tenant"
        )
    
    tenant.is_active = not tenant.is_active
    master_db.commit()
    
    status_text = "enabled" if tenant.is_active else "disabled"
    return {"message": f"Tenant {tenant.name} {status_text} successfully"}

# ========== CROSS-TENANT USER MANAGEMENT ==========

@router.get("/users", response_model=List[Dict[str, Any]])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    tenant_id: Optional[int] = Query(None),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """List users. If tenant_id is provided, compute role for that tenant; otherwise show role for each user's primary tenant."""
    query = master_db.query(MasterUser)

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
    # Validate required fields
    required_fields = ['email', 'first_name', 'last_name', 'password', 'tenant_ids', 'primary_tenant_id']
    for field in required_fields:
        if field not in user_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
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
    
    # Create user in master database
    hashed_password = get_password_hash(user_data['password'])
    primary_role = provided_tenant_roles.get(str(primary_tenant_id), user_data.get('role', 'user'))
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
        membership = master_db.execute(
            user_tenant_association.insert().values(
                user_id=master_user.id,
                tenant_id=tenant_id,
                role=role_for_tenant
            )
        )
        
        # Create user in each tenant database
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
            
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
            
        except Exception as e:
            # Continue with other tenants if one fails
            pass
    
    master_db.commit()
    
    user_dict = master_user.__dict__.copy()
    user_dict.pop('_sa_instance_state', None)
    user_dict['tenant_names'] = [t.name for t in tenants]
    
    return user_dict

# Removed global role update endpoint - use tenant-specific endpoint instead
# PUT /super-admin/tenants/{tenant_id}/users/{user_id}/role

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
        if field in user_data and user_data[field]:
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
        tenant_ids = [int(tid) for tid in user_data['tenant_ids']]
        
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
                    tenant_session.commit()
                tenant_session.close()
            except Exception:
                pass
    
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
            tenant_session.delete(tenant_user)
            tenant_session.commit()
        
        tenant_session.close()
    except Exception as e:
        pass  # Continue even if tenant deletion fails
    
    # Delete from master database
    master_db.delete(user)
    master_db.commit()
    
    # Log audit event in master database
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE",
        resource_type="user",
        resource_id=str(user_id),
        resource_name=f"{user.first_name} {user.last_name}",
        details={"deleted_user_email": user.email},
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

# ========== PASSWORD MANAGEMENT ==========

@router.post("/users/{user_id}/reset-password")
async def super_admin_reset_password(
    user_id: int,
    payload: SuperAdminResetPasswordRequest,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Super admin sets a new password for any user and optionally forces reset on next login."""
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
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
        from models.models_per_tenant import User as TenantUser
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user.id).first()
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

# ========== CROSS-TENANT USER ROLE MANAGEMENT ==========

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
    from models.models import user_tenant_association
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
        from models.models_per_tenant import User as TenantUser
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user_id).first()
        if tenant_user:
            tenant_user.role = role_update.role
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
        resource_type="user_role",
        resource_id=str(user_id),
        resource_name=f"Role update for user {target_user.email} in tenant {tenant_id}",
        details={"tenant_id": tenant_id, "new_role": role_update.role},
        tenant_id=current_user.tenant_id,
        status="success"
    )

    return {"message": "User role updated for tenant"}

# ========== DATABASE OPERATIONS ==========

@router.get("/tenants/{tenant_id}/database/status")
async def get_tenant_database_status(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get the status of a tenant's database"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    try:
        # Try to connect to tenant database
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
        
        # Test connection with a simple query
        tenant_session.execute(text("SELECT 1"))
        
        tenant_session.close()
        
        return {
            "tenant_id": tenant_id,
            "database_name": f"tenant_{tenant_id}",
            "status": "connected",
            "message": "Database is accessible"
        }
    except Exception as e:
        return {
            "tenant_id": tenant_id,
            "database_name": f"tenant_{tenant_id}",
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        }

@router.post("/tenants/{tenant_id}/database/recreate")
async def recreate_tenant_database(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Recreate a tenant's database (WARNING: This will delete all data)"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    success = tenant_db_manager.recreate_tenant_database(tenant_id, tenant.name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to recreate tenant database"
        )
    
    return {"message": f"Database for tenant {tenant.name} recreated successfully"}

@router.get("/database/overview")
async def get_database_overview(
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get overview of all tenant databases"""
    tenants = master_db.query(Tenant).all()
    
    overview = {
        "total_tenants": len(tenants),
        "databases": []
    }
    
    for tenant in tenants:
        db_info = {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "database_name": f"tenant_{tenant.id}",
            "status": "unknown"
        }
        
        try:
            # Test database connection
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()
            tenant_session.execute(text("SELECT 1"))
            tenant_session.close()
            db_info["status"] = "connected"
        except Exception as e:
            db_info["status"] = "error"
            db_info["error"] = str(e)
        
        overview["databases"].append(db_info)
    
    return overview 

@router.post("/promote", response_model=Dict[str, str])
async def promote_to_super_admin(
    request: PromoteUserRequest,  # Accept email in request body
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
    request: PromoteUserRequest,  # Accept email in request body
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
        from services.tenant_database_manager import tenant_db_manager
        from models.models_per_tenant import User as TenantUser
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.email == request.email).first()
        if tenant_user:
            tenant_user.is_superuser = False
            tenant_session.commit()
        tenant_session.close()
    except Exception as e:
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
