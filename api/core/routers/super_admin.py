from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
import logging
import secrets

from core.models.database import get_master_db
from core.models.models import (
    Tenant, MasterUser, User, Client, ClientNote, Invoice, Payment, Settings, CurrencyRate, DiscountRule, AIConfig, TenantKey,
    OrganizationJoinRequest, InvoiceHistory, AuditLog, user_tenant_association
)
from core.models.api_models import APIClient, ExternalTransaction, ClientPermission
from core.models.models_per_tenant import User as TenantUser
from core.schemas.user import UserCreate, UserUpdate, UserList, UserRoleUpdate
from core.schemas.tenant import TenantCreate, TenantUpdate, Tenant as TenantSchema
from core.routers.auth import get_current_user
from core.services.tenant_database_manager import tenant_db_manager
from core.services.license_service import LicenseService
from core.services.tenant_management_service import TenantManagementService
from core.utils.auth import verify_password, get_password_hash
from core.utils.password_validation import validate_password_strength
from core.utils.rbac import require_superuser

logger = logging.getLogger(__name__)
from core.utils.audit import log_audit_event, log_audit_event_master
from core.constants.error_codes import USER_NOT_FOUND, ONLY_SUPERUSERS, FAILED_TO_IMPORT_DATA
from core.constants.password import MIN_PASSWORD_LENGTH

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

# Add the request model for the promote endpoint
class PromoteUserRequest(BaseModel):
    email: str

class SuperAdminResetPasswordRequest(BaseModel):
    new_password: str
    confirm_password: str
    force_reset_on_login: bool = False

class TenantSelectionRequest(BaseModel):
    tenant_ids: List[int]

class GlobalSignupSettingsUpdate(BaseModel):
    allow_password_signup: Optional[bool] = None
    allow_sso_signup: Optional[bool] = None
    max_tenants: Optional[int] = None
    max_users: Optional[int] = None

def require_super_admin(current_user: MasterUser = Depends(get_current_user)):
    """Require that the current user is a superuser in their primary tenant"""
    from core.models.database import get_tenant_context
    current_tenant_id = get_tenant_context()

    logger.info(f"require_super_admin: user={current_user.email}, is_superuser={current_user.is_superuser}, tenant_context={current_tenant_id}, user_tenant={current_user.tenant_id}")

    if not current_user.is_superuser:
        logger.warning(f"require_super_admin: user {current_user.email} is not a super admin")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )

    # Check if user is in their primary tenant
    if current_tenant_id and current_tenant_id != current_user.tenant_id:
        logger.warning(f"require_super_admin: user {current_user.email} is not in primary tenant")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access restricted to home organization"
        )

    logger.info(f"require_super_admin: user {current_user.email} passed all checks")
    return current_user

# ========== TENANT MANAGEMENT ==========

@router.get("/organizations")
async def get_organizations(
    skip: int = 0,
    limit: int = 1000,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get all organizations for super admin dropdown"""
    tenants = master_db.query(Tenant).offset(skip).limit(limit).all()

    organizations = []
    for tenant in tenants:
        organizations.append({
            'id': tenant.id,
            'name': tenant.name
        })

    # Sort by name for better UX
    organizations.sort(key=lambda x: x['name'])

    return organizations

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

        # Add user count - include users from both primary tenant and memberships
        # Get users with primary tenant
        primary_users = master_db.query(MasterUser.id).filter(
            MasterUser.tenant_id == tenant.id
        )
        # Get users with membership in this tenant
        member_users = master_db.query(user_tenant_association.c.user_id).filter(
            user_tenant_association.c.tenant_id == tenant.id
        )
        # Union and count unique users
        user_count = primary_users.union(member_users).count()
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
        from core.models.models_per_tenant import Client, Invoice, Payment

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
    current_user: MasterUser = Depends(require_super_admin),
    request: Request = None
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

    # Check license tenant limit from super admin's primary tenant
    # The super admin can only create new tenants if their own license allows it
    from core.models.database import set_tenant_context

    try:
        # Get super admin's primary tenant
        admin_tenant_id = current_user.tenant_id
        if not admin_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Super admin must have a primary tenant"
            )

        # Set tenant context and get tenant session
        set_tenant_context(admin_tenant_id)
        tenant_session = tenant_db_manager.get_tenant_session(admin_tenant_id)
        admin_tenant_db = tenant_session()

        try:
            # Check license from super admin's tenant
            license_service = LicenseService(admin_tenant_db)
            max_tenants = license_service.get_max_tenants()
            current_tenants_count = master_db.query(Tenant).count()

            if current_tenants_count >= max_tenants:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Tenant limit reached ({max_tenants}). Please upgrade your license to add more organizations."
                )
            logger.info(f"Super admin {current_user.email} license check passed: {current_tenants_count} < {max_tenants}")
        finally:
            try:
                admin_tenant_db.close()
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check super admin license: {str(e)}")
        # Don't block tenant creation if license check fails
        pass

    try:
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
            # If database creation fails, rollback tenant creation
            master_db.delete(db_tenant)
            master_db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tenant database"
            )

        # Log audit event for successful tenant creation
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE_TENANT",
            resource_type="TENANT",
            resource_id=str(db_tenant.id),
            resource_name=db_tenant.name,
            details={
                "tenant_id": db_tenant.id,
                "tenant_name": db_tenant.name,
                "tenant_email": db_tenant.email,
                "default_currency": db_tenant.default_currency,
                "database_created": True
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="success",
            tenant_id=db_tenant.id
        )

        return db_tenant
    except Exception as e:
        # Log audit event for failed tenant creation
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE_TENANT",
            resource_type="TENANT",
            resource_name=tenant.name,
            details={
                "tenant_name": tenant.name,
                "tenant_email": tenant.email,
                "default_currency": tenant.default_currency,
                "error": str(e)
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message=str(e)
        )
        raise

@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    tenant_update: TenantUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin),
    request: Request = None
):
    """Update any tenant's information"""
    db_tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    try:
        # Store original values for audit
        original_values = {
            "name": db_tenant.name,
            "email": db_tenant.email,
            "default_currency": db_tenant.default_currency,
            "company_logo_url": db_tenant.company_logo_url,
            "is_active": db_tenant.is_active
        }

        # Update tenant fields
        tenant_data = tenant_update.model_dump(exclude_unset=True)
        # Map logo_url to company_logo_url to match the model field
        if 'logo_url' in tenant_data:
            tenant_data['company_logo_url'] = tenant_data.pop('logo_url')

        for field, value in tenant_data.items():
            setattr(db_tenant, field, value)

        master_db.commit()
        master_db.refresh(db_tenant)

        # Log audit event for successful tenant update
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE_TENANT",
            resource_type="TENANT",
            resource_id=str(db_tenant.id),
            resource_name=db_tenant.name,
            details={
                "tenant_id": db_tenant.id,
                "tenant_name": db_tenant.name,
                "original_values": original_values,
                "updated_values": tenant_data,
                "changes": {k: {"old": original_values.get(k), "new": v} for k, v in tenant_data.items() if original_values.get(k) != v}
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="success",
            tenant_id=db_tenant.id
        )

        return db_tenant

    except Exception as e:
        # Log audit event for failed tenant update
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE_TENANT",
            resource_type="TENANT",
            resource_id=str(tenant_id),
            resource_name=f"Tenant {tenant_id}",
            details={
                "tenant_id": tenant_id,
                "update_data": tenant_update.model_dump(exclude_unset=True),
                "error": str(e)
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message=str(e),
            tenant_id=tenant_id
        )
        raise

@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin),
    request: Request = None
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

    try:
        # Store tenant info for audit before deletion
        tenant_info = {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "tenant_email": tenant.email,
            "default_currency": tenant.default_currency,
            "is_active": tenant.is_active,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None
        }

        # Manually delete all related data for this tenant
        # Delete records that reference the tenant (in order to avoid foreign key constraints)

        # Delete API-related records first
        master_db.query(ExternalTransaction).filter(ExternalTransaction.tenant_id == tenant_id).delete()

        # Delete client permissions for API clients belonging to this tenant
        api_client_ids = master_db.query(APIClient.id).filter(APIClient.tenant_id == tenant_id).subquery()
        master_db.query(ClientPermission).filter(ClientPermission.client_id.in_(api_client_ids)).delete(synchronize_session=False)

        master_db.query(APIClient).filter(APIClient.tenant_id == tenant_id).delete()

        # Note: StorageOperationLog and CloudStorageConfiguration are in tenant databases, not master

        # Delete audit logs for this tenant
        master_db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).delete()

        # Delete organization join requests
        master_db.query(OrganizationJoinRequest).filter(OrganizationJoinRequest.tenant_id == tenant_id).delete()

        # Delete tenant keys (encryption keys)
        master_db.query(TenantKey).filter(TenantKey.tenant_id == tenant_id).delete()

        # Delete core business records
        # Delete user-tenant associations first
        master_db.execute(user_tenant_association.delete().where(user_tenant_association.c.tenant_id == tenant_id))

        master_db.query(MasterUser).filter(MasterUser.tenant_id == tenant_id).delete()
        master_db.query(User).filter(User.tenant_id == tenant_id).delete()
        master_db.query(ClientNote).filter(ClientNote.tenant_id == tenant_id).delete()
        master_db.query(InvoiceHistory).filter(InvoiceHistory.tenant_id == tenant_id).delete()
        master_db.query(Payment).filter(Payment.tenant_id == tenant_id).delete()
        master_db.query(Invoice).filter(Invoice.tenant_id == tenant_id).delete()
        master_db.query(Client).filter(Client.tenant_id == tenant_id).delete()
        master_db.query(Settings).filter(Settings.tenant_id == tenant_id).delete()
        master_db.query(CurrencyRate).filter(CurrencyRate.tenant_id == tenant_id).delete()
        master_db.query(DiscountRule).filter(DiscountRule.tenant_id == tenant_id).delete()
        master_db.query(AIConfig).filter(AIConfig.tenant_id == tenant_id).delete()

    except Exception as e:
        master_db.rollback()

        # Log audit event for failed tenant deletion
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE_TENANT",
            resource_type="TENANT",
            resource_id=str(tenant_id),
            resource_name=tenant.name,
            details={
                "tenant_info": tenant_info,
                "error": str(e),
                "stage": "data_deletion"
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message=str(e),
            tenant_id=tenant_id
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tenant data: {str(e)}"
        )

    # Delete tenant database first
    success = tenant_db_manager.drop_tenant_database(tenant_id)
    if not success:
        # Log audit event for failed database deletion
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE_TENANT",
            resource_type="TENANT",
            resource_id=str(tenant_id),
            resource_name=tenant.name,
            details={
                "tenant_info": tenant_info,
                "error": "Failed to delete tenant database",
                "stage": "database_deletion"
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message="Failed to delete tenant database",
            tenant_id=tenant_id
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tenant database"
        )

    # Delete tenant from master database
    master_db.delete(tenant)
    master_db.commit()

    # Log audit event for successful tenant deletion
    from core.utils.audit import log_audit_event_master
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE_TENANT",
        resource_type="TENANT",
        resource_id=str(tenant_id),
        resource_name=tenant.name,
        details={
            "tenant_info": tenant_info,
            "database_deleted": True,
            "all_data_deleted": True
        },
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        status="success",
        tenant_id=tenant_id
    )

    return {"message": f"Tenant {tenant.name} deleted successfully"}

@router.patch("/tenants/{tenant_id}/toggle-status")
async def toggle_tenant_status(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin),
    request: Request = None
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

    try:
        old_status = tenant.is_active
        tenant.is_active = not tenant.is_active
        new_status = tenant.is_active
        master_db.commit()

        # Log audit event for successful tenant status toggle
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="TOGGLE_TENANT_STATUS",
            resource_type="TENANT",
            resource_id=str(tenant_id),
            resource_name=tenant.name,
            details={
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "old_status": old_status,
                "new_status": new_status,
                "status_change": "enabled" if new_status else "disabled"
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="success",
            tenant_id=tenant_id
        )

        status_text = "enabled" if new_status else "disabled"
        return {"message": f"Tenant {tenant.name} {status_text} successfully"}

    except Exception as e:
        # Log audit event for failed tenant status toggle
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="TOGGLE_TENANT_STATUS",
            resource_type="TENANT",
            resource_id=str(tenant_id),
            resource_name=tenant.name if tenant else f"Tenant {tenant_id}",
            details={
                "tenant_id": tenant_id,
                "old_status": tenant.is_active if tenant else "unknown",
                "error": str(e)
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message=str(e),
            tenant_id=tenant_id
        )
        raise

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

    from core.services.license_service import LicenseService
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

        except Exception as e:
            # Continue with other tenants if one fails
            pass

    master_db.commit()

    user_dict = master_user.__dict__.copy()
    user_dict.pop('_sa_instance_state', None)
    user_dict['tenant_names'] = [t.name for t in tenants]

    # Add SSO information to response
    user_dict['is_sso'] = is_sso_user

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
    except Exception as e:
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

# ========== PASSWORD MANAGEMENT ==========

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
        from core.models.models_per_tenant import User as TenantUser
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
    from core.models.models import user_tenant_association
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
        from core.models.models_per_tenant import User as TenantUser
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user_id).first()
        if tenant_user:
            tenant_user.role = role_update.role
            tenant_user.is_active = True  # Ensure active if re-enabling
            tenant_session.commit()
        tenant_session.close()
    except Exception:
        print(f"Failed to update user role in tenant database: {e}")
        pass

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
    current_user: MasterUser = Depends(require_super_admin),
    request: Request = None
):
    """Recreate a tenant's database (WARNING: This will delete all data)"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Prevent super admin from recreating their own tenant's database
    if tenant_id == current_user.tenant_id:
        # Log audit event for attempted self-database recreation
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="RECREATE_DATABASE",
            resource_type="DATABASE",
            resource_id=str(tenant_id),
            resource_name=f"{tenant.name} Database",
            details={
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "error": "Attempted to recreate own tenant database",
                "user_tenant_id": current_user.tenant_id
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message="Cannot recreate your own tenant's database",
            tenant_id=tenant_id
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot recreate your own tenant's database"
        )

    try:
        success = tenant_db_manager.recreate_tenant_database(tenant_id, tenant.name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to recreate tenant database"
            )

        # Log audit event for database recreation
        from core.utils.audit import log_audit_event_master
        logger.info(f"Creating master audit log for database recreation by {current_user.email}")
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="RECREATE_DATABASE",
            resource_type="DATABASE",
            resource_id=str(tenant_id),
            resource_name=f"{tenant.name} Database",
            details={
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "database_name": f"tenant_{tenant_id}_{tenant.name.lower().replace(' ', '_')}"
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="success",
            tenant_id=tenant_id
        )
        logger.info("Master audit log created successfully")

        return {"message": f"Database for tenant {tenant.name} recreated successfully"}

    except Exception as e:
        # Log audit event for failed database recreation
        from core.utils.audit import log_audit_event_master
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="RECREATE_DATABASE",
            resource_type="DATABASE",
            resource_id=str(tenant_id),
            resource_name=f"{tenant.name} Database",
            details={
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "error": str(e)
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            status="error",
            error_message=str(e),
            tenant_id=tenant_id
        )
        raise

@router.get("/database/overview")
async def get_database_overview(
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get overview of all tenant databases"""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    tenants = master_db.query(Tenant).all()

    overview = {
        "total_tenants": len(tenants),
        "databases": []
    }

    def test_tenant_connection(tenant_id: int, tenant_name: str) -> dict:
        """Test database connection for a single tenant with timeout"""
        db_info = {
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "database_name": f"tenant_{tenant_id}",
            "status": "unknown"
        }

        try:
            # Test database connection with a timeout
            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
            tenant_session.execute(text("SELECT 1"))
            tenant_session.close()
            db_info["status"] = "connected"
        except Exception as e:
            db_info["status"] = "error"
            db_info["error"] = str(e)

        return db_info

    # Use ThreadPoolExecutor with timeout to prevent hanging
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for tenant in tenants:
            future = executor.submit(test_tenant_connection, tenant.id, tenant.name)
            futures.append(future)

        # Wait for all futures with a timeout of 30 seconds total
        for future in futures:
            try:
                db_info = future.result(timeout=5)  # 5 second timeout per tenant
                overview["databases"].append(db_info)
            except FuturesTimeoutError:
                # Extract tenant info from the future if possible
                tenant_id = None
                tenant_name = "Unknown"
                for i, tenant in enumerate(tenants):
                    if futures[i] == future:
                        tenant_id = tenant.id
                        tenant_name = tenant.name
                        break

                overview["databases"].append({
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "database_name": f"tenant_{tenant_id}" if tenant_id else "unknown",
                    "status": "timeout",
                    "error": "Database connection test timed out"
                })
            except Exception as e:
                # Handle any other exceptions
                tenant_id = None
                tenant_name = "Unknown"
                for i, tenant in enumerate(tenants):
                    if futures[i] == future:
                        tenant_id = tenant.id
                        tenant_name = tenant.name
                        break

                overview["databases"].append({
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "database_name": f"tenant_{tenant_id}" if tenant_id else "unknown",
                    "status": "error",
                    "error": str(e)
                })

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

    # Also update in tenant DB if user exists there
    try:
        tenant_id = user.tenant_id
        from core.services.tenant_database_manager import tenant_db_manager
        from core.models.models_per_tenant import User as TenantUser
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user.id).first()
        if tenant_user:
            tenant_user.is_superuser = True
            tenant_user.role = 'admin'
            tenant_session.commit()
        tenant_session.close()
    except Exception as e:
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
        from core.services.tenant_database_manager import tenant_db_manager
        from core.models.models_per_tenant import User as TenantUser
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
@router.get("/anomalies")
async def get_all_anomalies(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    risk_level: Optional[str] = Query(None),
    is_dismissed: bool = Query(False),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Aggregate anomalies from all tenants for platform-wide monitoring"""
    from core.services.feature_config_service import FeatureConfigService

    # Debug logging
    logger.info(f"get_all_anomalies called with skip={skip}, limit={limit}, risk_level={risk_level}, is_dismissed={is_dismissed}")

    # Check if anomaly detection is enabled via environment variable or license
    # Note: We check without db to avoid transaction issues with master_db
    is_enabled = FeatureConfigService.is_enabled('anomaly_detection', db=None, check_license=False)

    logger.info(f"Anomaly detection check - enabled: {is_enabled}")

    if not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FinanceWorks Insights feature is not available in your current license"
        )

    tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()

    all_anomalies = []
    total_count = 0

    # First, count total anomalies across all tenants
    for tenant in tenants:
        tenant_session = None
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()
            from core.models.models_per_tenant import Anomaly

            query = tenant_session.query(Anomaly).filter(Anomaly.is_dismissed == is_dismissed)

            if risk_level:
                query = query.filter(Anomaly.risk_level == risk_level)

            # Count total anomalies for this tenant
            total_count += query.count()

        except Exception as e:
            logger.error(f"Failed to count anomalies for tenant {tenant.id}: {e}")
            continue
        finally:
            if tenant_session:
                try:
                    tenant_session.close()
                except Exception as e:
                    logger.error(f"Error closing tenant session for {tenant.id}: {e}")

    # Now fetch paginated results more efficiently
    # Calculate how many records we need to fetch from each tenant
    # For page N with size L, we need to fetch enough records to potentially fill all pages up to N
    # We fetch (skip + limit) records from each tenant to ensure we have enough data
    fetch_per_tenant = skip + limit

    # But cap it to avoid excessive fetching
    max_fetch_per_tenant = min(fetch_per_tenant, 500)  # Increased cap to ensure we have enough data

    logger.info(f"Fetching up to {max_fetch_per_tenant} records per tenant for pagination (skip={skip}, limit={limit})")

    for tenant in tenants:
        tenant_session = None
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()
            from core.models.models_per_tenant import Anomaly

            query = tenant_session.query(Anomaly).filter(Anomaly.is_dismissed == is_dismissed)

            if risk_level:
                query = query.filter(Anomaly.risk_level == risk_level)

            # Get sufficient anomalies from each tenant for sorting and pagination
            anomalies = query.order_by(Anomaly.created_at.desc()).limit(max_fetch_per_tenant).all()

            for a in anomalies:
                all_anomalies.append({
                    "id": a.id,
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "risk_score": a.risk_score,
                    "risk_level": a.risk_level,
                    "reason": a.reason,
                    "rule_id": a.rule_id,
                    "details": a.details,
                    "created_at": a.created_at
                })

        except Exception as e:
            logger.error(f"Failed to fetch anomalies for tenant {tenant.id}: {e}")
            continue
        finally:
            if tenant_session:
                try:
                    tenant_session.close()
                except Exception as e:
                    logger.error(f"Error closing tenant session for {tenant.id}: {e}")

    # Sort results by date across all tenants and apply pagination
    all_anomalies.sort(key=lambda x: x['created_at'], reverse=True)
    paginated_anomalies = all_anomalies[skip:skip + limit]

    logger.info(f"Before pagination: {len(all_anomalies)} total anomalies collected")
    logger.info(f"After pagination: {len(paginated_anomalies)} items returned (skip={skip}, limit={limit})")

    return {
        "items": paginated_anomalies,
        "total": total_count,
        "skip": skip,
        "limit": limit
    }


@router.post("/anomalies/audit")
async def trigger_full_audit(
    days: int = Query(30),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Trigger a forensic audit scan for all active tenants for the last N days"""
    from core.services.feature_config_service import FeatureConfigService
    from core.services.tenant_database_manager import tenant_db_manager

    logger.info(f"trigger_full_audit: Starting audit scan for {days} days")

    # For super admin operations, check license using super admin's tenant database
    # since InstallationInfo is stored in tenant databases, not master
    super_admin_tenant_id = current_user.tenant_id
    tenant_session = tenant_db_manager.get_tenant_session(super_admin_tenant_id)()

    try:
        # Check if anomaly detection is enabled using tenant database for license check
        feature_enabled = FeatureConfigService.is_enabled('anomaly_detection', db=tenant_session)
        logger.info(f"trigger_full_audit: anomaly_detection feature enabled = {feature_enabled}")

        if not feature_enabled:
            logger.error("trigger_full_audit: anomaly_detection feature not enabled")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FinanceWorks Insights feature is not available in your current license"
            )
    finally:
        tenant_session.close()

    logger.info("trigger_full_audit: License check passed, proceeding with audit scan")
    from commercial.ai.services.ocr_service import publish_fraud_audit_task
    from core.models.models_per_tenant import Expense, BankStatementTransaction
    from datetime import datetime, timezone, timedelta

    tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    total_triggered = 0

    for tenant in tenants:
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()

            # Audit Expenses
            expenses = tenant_session.query(Expense).filter(
                Expense.created_at >= cutoff_date
            ).all()
            for exp in expenses:
                if publish_fraud_audit_task(tenant.id, "expense", exp.id, reprocess_mode=False):
                    total_triggered += 1

            # Audit Bank Transactions
            transactions = tenant_session.query(BankStatementTransaction).filter(
                BankStatementTransaction.created_at >= cutoff_date
            ).all()
            for txn in transactions:
                if publish_fraud_audit_task(tenant.id, "bank_statement_transaction", txn.id, reprocess_mode=False):
                    total_triggered += 1

            tenant_session.close()
        except Exception as e:
            logger.error(f"Failed to trigger audit for tenant {tenant.id}: {e}")
            continue

    # Log audit event
    from core.utils.audit import log_audit_event_master
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="TRIGGER_FULL_ANOMALY_AUDIT",
        resource_type="ANOMALY_DETECTION",
        details={
            "days": days,
            "entities_triggered": total_triggered,
            "tenants_scanned": len(tenants)
        }
    )

    return {
        "message": f"Successfully queued {total_triggered} entities for forensic audit across {len(tenants)} active tenants.",
        "entities_queued": total_triggered,
        "tenants_scanned": len(tenants)
    }


@router.post("/anomalies/reprocess")
async def trigger_reprocess_all(
    days: int = Query(30),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Trigger reprocessing of all entities (including previously processed) for last N days"""
    from core.services.feature_config_service import FeatureConfigService
    from core.services.tenant_database_manager import tenant_db_manager

    logger.info(f"trigger_reprocess_all: Starting reprocess scan for {days} days")

    # For super admin operations, check license using super admin's tenant database
    # since InstallationInfo is stored in tenant databases, not master
    super_admin_tenant_id = current_user.tenant_id
    tenant_session = tenant_db_manager.get_tenant_session(super_admin_tenant_id)()

    try:
        # Check if anomaly detection is enabled using tenant database for license check
        feature_enabled = FeatureConfigService.is_enabled('anomaly_detection', db=tenant_session)
        logger.info(f"trigger_reprocess_all: anomaly_detection feature enabled = {feature_enabled}")

        if not feature_enabled:
            logger.error("trigger_reprocess_all: anomaly_detection feature not enabled")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FinanceWorks Insights feature is not available in your current license"
            )
    finally:
        tenant_session.close()

    logger.info("trigger_reprocess_all: License check passed, proceeding with reprocess scan")
    from commercial.ai.services.ocr_service import publish_fraud_audit_task
    from core.models.models_per_tenant import Expense, BankStatementTransaction, Invoice
    from datetime import datetime, timezone, timedelta

    tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    total_triggered = 0

    for tenant in tenants:
        try:
            tenant_session = tenant_db_manager.get_tenant_session(tenant.id)()

            # Reprocess ALL entities without filtering for previous processing
            # This includes entities that may have been processed before

            # Reprocess Expenses
            expenses = tenant_session.query(Expense).filter(
                Expense.created_at >= cutoff_date
            ).all()
            for exp in expenses:
                if publish_fraud_audit_task(tenant.id, "expense", exp.id, reprocess_mode=True):
                    total_triggered += 1

            # Reprocess Invoices
            invoices = tenant_session.query(Invoice).filter(
                Invoice.created_at >= cutoff_date
            ).all()
            for inv in invoices:
                if publish_fraud_audit_task(tenant.id, "invoice", inv.id, reprocess_mode=True):
                    total_triggered += 1

            # Reprocess Bank Transactions
            transactions = tenant_session.query(BankStatementTransaction).filter(
                BankStatementTransaction.created_at >= cutoff_date
            ).all()
            for txn in transactions:
                if publish_fraud_audit_task(tenant.id, "bank_statement_transaction", txn.id, reprocess_mode=True):
                    total_triggered += 1

            tenant_session.close()
        except Exception as e:
            logger.error(f"Failed to trigger reprocess for tenant {tenant.id}: {e}")
            continue

    # Log audit event
    from core.utils.audit import log_audit_event_master
    log_audit_event_master(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="TRIGGER_ANOMALY_REPROCESS_ALL",
        resource_type="ANOMALY_DETECTION",
        details={
            "days": days,
            "entities_triggered": total_triggered,
            "tenants_scanned": len(tenants)
        }
    )

    return {
        "message": f"Successfully queued {total_triggered} entities for reprocessing across {len(tenants)} active tenants.",
        "entities_queued": total_triggered,
        "tenants_scanned": len(tenants)
    }

# ==================== Tenant Management Endpoints ====================

@router.get("/tenants/status")
async def get_tenant_status(
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get current tenant status and license information"""
    try:
        from core.models.database import get_tenant_context

        # Get tenant context and create tenant session
        tenant_id = get_tenant_context()
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()

        try:
            # Create tenant management service
            tenant_service = TenantManagementService(master_db, tenant_db)
            status = tenant_service.get_tenant_status()

            return status

        finally:
            tenant_db.close()

    except Exception as e:
        logger.error(f"Failed to get tenant status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant status: {str(e)}"
        )

@router.post("/tenants/enforce-limits")
async def enforce_tenant_limits(
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Manually enforce tenant limits based on current license"""
    try:
        from core.models.database import get_tenant_context

        # Get tenant context and create tenant session
        tenant_id = get_tenant_context()
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()

        try:
            # Create tenant management service
            tenant_service = TenantManagementService(master_db, tenant_db)
            result = tenant_service.enforce_tenant_limits(current_user)

            if result["success"]:
                # Log the enforcement action
                log_audit_event_master(
                    master_db=master_db,
                    user_id=current_user.id,
                    action="tenant_limits_enforced",
                    resource_type="system",
                    details={
                        "message": result["message"],
                        "enabled_tenants": result.get("enabled_tenants", []),
                        "disabled_tenants": result.get("disabled_tenants", []),
                        "max_tenants": result.get("max_tenants")
                    }
                )

            return result

        finally:
            tenant_db.close()

    except Exception as e:
        logger.error(f"Failed to enforce tenant limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enforce tenant limits: {str(e)}"
        )

@router.post("/tenants/select-enabled")
async def select_enabled_tenants(
    request: TenantSelectionRequest,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Select which tenants to enable (within license limits)"""
    try:
        from core.models.database import get_tenant_context

        # Get tenant context and create tenant session
        tenant_id = get_tenant_context()
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()

        try:
            # Create tenant management service
            tenant_service = TenantManagementService(master_db, tenant_db)
            result = tenant_service.select_enabled_tenants(current_user, request.tenant_ids)

            if result["success"]:
                # Log the tenant selection action
                log_audit_event_master(
                    master_db=master_db,
                    user_id=current_user.id,
                    action="tenants_selected",
                    resource_type="system",
                    details={
                        "enabled_tenants": result.get("enabled_tenants", []),
                        "disabled_tenants": result.get("disabled_tenants", []),
                        "max_tenants": result.get("max_tenants")
                    }
                )

            return result

        finally:
            tenant_db.close()

    except Exception as e:
        logger.error(f"Failed to select enabled tenants: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to select enabled tenants: {str(e)}"
        )

@router.get("/global-signup-settings")
async def get_global_signup_settings(
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Get global signup controls"""
    license_service = LicenseService(master_db, master_db=master_db)
    status = license_service.get_license_status()

    return {
        "allow_password_signup": status.get("allow_password_signup", True),
        "allow_sso_signup": status.get("allow_sso_signup", True),
        "max_tenants": status.get("global_license_info", {}).get("max_tenants", 1) if status.get("global_license_info") else 1,
        "current_tenants_count": master_db.query(Tenant).filter(Tenant.count_against_license == True).count()
    }

@router.patch("/global-signup-settings")
async def update_global_signup_settings(
    settings: GlobalSignupSettingsUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Update global signup controls"""
    license_service = LicenseService(master_db, master_db=master_db)
    success = license_service.update_global_signup_settings(
        allow_password=settings.allow_password_signup,
        allow_sso=settings.allow_sso_signup,
        max_tenants=settings.max_tenants,
        max_users=settings.max_users
    )

    if success:
        log_audit_event_master(
            db=master_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE_GLOBAL_SIGNUP_SETTINGS",
            resource_type="SYSTEM",
            details=settings.model_dump(exclude_unset=True)
        )
        return {"message": "Global signup settings updated successfully"}

    raise HTTPException(status_code=400, detail="Failed to update global signup settings")
