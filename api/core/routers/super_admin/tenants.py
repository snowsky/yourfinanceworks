from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any

from core.models.database import get_master_db
from core.models.models import (
    Tenant, MasterUser, User, Client, ClientNote, Invoice, Payment, Settings,
    CurrencyRate, DiscountRule, AIConfig, TenantKey, OrganizationJoinRequest,
    InvoiceHistory, AuditLog, TenantPluginSettings, user_tenant_association,
)
from core.models.api_models import APIClient, ExternalTransaction, ClientPermission
from core.schemas.tenant import TenantCreate, TenantUpdate, Tenant as TenantSchema
from core.services.tenant_database_manager import tenant_db_manager
from core.services.license_service import LicenseService
from core.services.tenant_management_service import TenantManagementService
from core.utils.audit import log_audit_event_master
from core.routers.super_admin._shared import (
    require_super_admin,
    TenantSelectionRequest,
    GlobalSignupSettingsUpdate,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


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
    except Exception:
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
        master_db.query(TenantPluginSettings).filter(TenantPluginSettings.tenant_id == tenant_id).delete()

    except Exception as e:
        master_db.rollback()

        # Log audit event for failed tenant deletion
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


# ==================== License-Aware Tenant Management ====================

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
            result = tenant_service.get_tenant_status()

            return result

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
    result = license_service.get_license_status()

    return {
        "allow_password_signup": result.get("allow_password_signup", True),
        "allow_sso_signup": result.get("allow_sso_signup", True),
        "max_tenants": result.get("global_license_info", {}).get("max_tenants", 1) if result.get("global_license_info") else 1,
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
