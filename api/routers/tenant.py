from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, get_master_db
from models.models import Tenant, MasterUser
from schemas.tenant import TenantCreate, TenantUpdate, Tenant as TenantSchema
from routers.auth import get_current_user
from services.currency_service import CurrencyService

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.post("/", response_model=TenantSchema)
def create_tenant(
    tenant: TenantCreate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Create a new tenant (only superusers can create tenants)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can create tenants"
        )
    
    # Check if subdomain already exists
    if tenant.subdomain:
        existing_tenant = master_db.query(Tenant).filter(Tenant.subdomain == tenant.subdomain).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subdomain already exists"
            )
    
    # Validate currency code (using master database)
    currency_service = CurrencyService(master_db)
    if not currency_service.validate_currency_code(tenant.default_currency):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid currency code: {tenant.default_currency}"
        )
    
    db_tenant = Tenant(**tenant.dict())
    master_db.add(db_tenant)
    master_db.commit()
    master_db.refresh(db_tenant)
    return db_tenant

@router.get("/", response_model=List[TenantSchema])
def list_tenants(
    skip: int = 0,
    limit: int = 100,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all tenants (only superusers can see all tenants)"""
    if current_user.is_superuser:
        tenants = master_db.query(Tenant).offset(skip).limit(limit).all()
    else:
        # Regular users can only see their own tenant
        tenants = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).offset(skip).limit(limit).all()
    
    return tenants

@router.get("/me", response_model=TenantSchema)
def get_my_tenant(
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get current user's tenant"""
    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    return tenant

@router.get("/{tenant_id}", response_model=TenantSchema)
def get_tenant(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get a specific tenant"""
    # Users can only access their own tenant unless they're superuser
    if not current_user.is_superuser and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this tenant"
        )
    
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    return tenant

@router.put("/{tenant_id}", response_model=TenantSchema)
def update_tenant(
    tenant_id: int,
    tenant_update: TenantUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update a tenant"""
    # Users can only update their own tenant unless they're superuser
    if not current_user.is_superuser and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this tenant"
        )
    
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Validate currency code if being updated
    if tenant_update.default_currency:
        currency_service = CurrencyService(master_db)
        if not currency_service.validate_currency_code(tenant_update.default_currency):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid currency code: {tenant_update.default_currency}"
            )
    
    # Check if subdomain already exists (if being updated)
    if tenant_update.subdomain and tenant_update.subdomain != tenant.subdomain:
        existing_tenant = master_db.query(Tenant).filter(Tenant.subdomain == tenant_update.subdomain).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subdomain already exists"
            )
    
    # Update tenant
    for field, value in tenant_update.dict(exclude_unset=True).items():
        setattr(tenant, field, value)
    
    master_db.commit()
    master_db.refresh(tenant)
    return tenant

@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Delete a tenant (only superusers can delete tenants)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can delete tenants"
        )
    
    # Users cannot delete their own tenant
    if current_user.tenant_id == tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own tenant"
        )
    
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    master_db.delete(tenant)
    master_db.commit()
    return {"message": "Tenant deleted successfully"} 