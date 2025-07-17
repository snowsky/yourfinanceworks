from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel

from models.database import get_master_db
from models.models import (
    Tenant, MasterUser, User, Client, ClientNote, Invoice, Payment, Settings, CurrencyRate, DiscountRule, AIConfig
)
from models.models_per_tenant import User as TenantUser
from schemas.user import UserCreate, UserUpdate, UserList, UserRoleUpdate
from schemas.tenant import TenantCreate, TenantUpdate, Tenant as TenantSchema
from routers.auth import get_current_user
from services.tenant_database_manager import tenant_db_manager
from utils.auth import get_password_hash
from utils.rbac import require_superuser
from utils.audit import log_audit_event

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

# Add the request model for the promote endpoint
class PromoteUserRequest(BaseModel):
    email: str

def require_super_admin(current_user: MasterUser = Depends(get_current_user)):
    """Require that the current user is a superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user

# ========== TENANT MANAGEMENT ==========

@router.get("/tenants", response_model=List[TenantSchema])
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
    db_tenant = Tenant(**tenant.dict())
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
    
    return db_tenant

@router.put("/tenants/{tenant_id}", response_model=TenantSchema)
async def update_tenant(
    tenant_id: int,
    tenant: TenantUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Update any tenant's information"""
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Update tenant fields
    for field, value in tenant.dict(exclude_unset=True).items():
        setattr(tenant, field, value)
    
    master_db.commit()
    master_db.refresh(tenant)
    return tenant

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

# ========== CROSS-TENANT USER MANAGEMENT ==========

@router.get("/users", response_model=List[Dict[str, Any]])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """List all users across all tenants or from a specific tenant"""
    query = master_db.query(MasterUser)
    
    # The original code had tenant_id here, but the new code doesn't.
    # Assuming the intent was to list all users across all tenants.
    # If a specific tenant_id is needed, it should be passed as a query parameter.
    # For now, removing the filter to list all users.
    
    users = query.offset(skip).limit(limit).all()
    
    # Enrich with tenant information
    enriched_users = []
    for user in users:
        user_dict = user.__dict__.copy()
        user_dict.pop('_sa_instance_state', None)
        
        # Add tenant information
        tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        user_dict['tenant_name'] = tenant.name if tenant else "Unknown"
        
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
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get tenant information
    tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    
    user_dict = user.__dict__.copy()
    user_dict.pop('_sa_instance_state', None)
    user_dict['tenant_name'] = tenant.name if tenant else "Unknown"
    
    return user_dict

@router.post("/users", response_model=Dict[str, Any])
async def create_user(
    user: UserCreate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Create a new user for a specific tenant"""
    # Check if tenant exists
    tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Check if user already exists
    existing_user = master_db.query(MasterUser).filter(
        MasterUser.email == user.email
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    # Create user in master database
    hashed_password = get_password_hash(user.password)
    master_user = MasterUser(
        email=user.email,
        hashed_password=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        tenant_id=user.tenant_id,
        is_verified=True
    )
    
    master_db.add(master_user)
    master_db.commit()
    master_db.refresh(master_user)
    
    # Create user in tenant database
    try:
        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)()
        
        tenant_user = TenantUser(
            id=master_user.id,  # Use same ID as master
            email=user.email,
            hashed_password=hashed_password,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            is_verified=True
        )
        
        tenant_session.add(tenant_user)
        tenant_session.commit()
        tenant_session.close()
        
    except Exception as e:
        # Rollback master user creation if tenant user creation fails
        master_db.delete(master_user)
        master_db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user in tenant database: {str(e)}"
        )
    
    user_dict = master_user.__dict__.copy()
    user_dict.pop('_sa_instance_state', None)
    user_dict['tenant_name'] = tenant.name
    
    # Log audit event
    log_audit_event(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="user",
        resource_id=str(master_user.id),
        resource_name=f"{master_user.first_name} {master_user.last_name}",
        details=user.dict(),
        status="success"
    )
    
    return user_dict

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Update a user's role across all systems"""
    user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update role in master database
    user.role = role_update.role
    master_db.commit()
    master_db.refresh(user)
    
    # Update role in tenant database
    try:
        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(
            TenantUser.id == user_id
        ).first()
        
        if tenant_user:
            tenant_user.role = role_update.role
            tenant_session.commit()
        
        tenant_session.close()
    except Exception as e:
        pass  # Continue even if tenant update fails
    
    return {"message": "User role updated successfully"}

@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(require_super_admin)
):
    """Update a user's info (name, email, etc.) across all systems"""
    user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields in master database
    for field, value in user_update.dict(exclude_unset=True).items():
        if field == "password":
            user.hashed_password = get_password_hash(value)
        elif hasattr(user, field):
            setattr(user, field, value)
    master_db.commit()
    master_db.refresh(user)

    # Update fields in tenant database
    try:
        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == user_id).first()
        if tenant_user:
            for field, value in user_update.dict(exclude_unset=True).items():
                if field == "password":
                    tenant_user.hashed_password = get_password_hash(value)
                elif hasattr(tenant_user, field):
                    setattr(tenant_user, field, value)
            tenant_session.commit()
        tenant_session.close()
    except Exception as e:
        pass  # Continue even if tenant update fails

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
    
    # Log audit event
    log_audit_event(
        db=master_db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE",
        resource_type="user",
        resource_id=str(user_id),
        resource_name=f"{user.first_name} {user.last_name}",
        details={"deleted_user_email": user.email},
        status="success"
    )
    
    return {"message": "User deleted successfully"}

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
    user.is_superuser = True
    user.role = 'admin'
    master_db.commit()
    return {"message": f"User '{request.email}' has been promoted to super admin."} 