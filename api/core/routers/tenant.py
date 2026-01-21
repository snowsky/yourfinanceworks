from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
import tempfile
import os
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import logging
from datetime import datetime

from core.models.database import get_db, get_master_db
from core.models.models import Tenant, MasterUser
from core.schemas.tenant import TenantCreate, TenantUpdate, Tenant as TenantSchema
from core.routers.auth import get_current_user
from core.services.currency_service import CurrencyService
from core.utils.rbac import require_admin
from core.constants.error_codes import ONLY_SUPERUSERS, SUBDOMAIN_EXISTS, INVALID_CURRENCY_CODE, NOT_AUTHORIZED

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.get("/check-name-availability")
async def check_organization_name_availability(
    name: str,
    master_db: Session = Depends(get_master_db)
):
    """Check if an organization name is available (public endpoint for signup)"""
    if not name or len(name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name must be at least 2 characters long"
        )
    
    # Check if name already exists (case-insensitive)
    existing_tenant = master_db.query(Tenant).filter(
        func.lower(Tenant.name) == func.lower(name.strip())
    ).first()
    
    return {
        "available": existing_tenant is None,
        "name": name.strip()
    }

@router.post("/", response_model=TenantSchema)
async def create_tenant(
    tenant: TenantCreate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Create a new tenant (only superusers can create tenants)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ONLY_SUPERUSERS
        )
    
    # Check if subdomain already exists
    if tenant.subdomain:
        existing_tenant = master_db.query(Tenant).filter(Tenant.subdomain == tenant.subdomain).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=SUBDOMAIN_EXISTS
            )
    
    # Validate currency code (using master database)
    currency_service = CurrencyService(master_db)
    if not currency_service.validate_currency_code(tenant.default_currency):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_CURRENCY_CODE
        )
    
    db_tenant = Tenant(**tenant.model_dump())
    master_db.add(db_tenant)
    master_db.commit()
    master_db.refresh(db_tenant)
    return db_tenant

@router.get("/", response_model=List[TenantSchema])
async def read_tenants(
    skip: int = 0,
    limit: int = 100,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all tenants (only superusers can see all tenants, regular users see only enabled tenants)"""
    if current_user.is_superuser:
        tenants = master_db.query(Tenant).offset(skip).limit(limit).all()
    else:
        # Regular users can only see their own tenant if it's enabled
        tenants = master_db.query(Tenant).filter(
            Tenant.id == current_user.tenant_id,
            Tenant.is_enabled == True
        ).offset(skip).limit(limit).all()
    
    return tenants

@router.get("/me", response_model=TenantSchema)
async def read_tenant_me(
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get current user's tenant"""
    tenant = master_db.query(Tenant).filter(
        Tenant.id == current_user.tenant_id,
        Tenant.is_enabled == True
    ).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your organization is currently disabled. Please contact your administrator."
        )
    return tenant

@router.get("/{tenant_id}", response_model=TenantSchema)
async def read_tenant(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get a specific tenant"""
    # Users can only access their own tenant unless they're superuser
    if not current_user.is_superuser and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=NOT_AUTHORIZED
        )
    
    # For regular users, also check if tenant is enabled
    if current_user.is_superuser:
        tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    else:
        tenant = master_db.query(Tenant).filter(
            Tenant.id == tenant_id,
            Tenant.is_enabled == True
        ).first()
    
    if not tenant:
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your organization is currently disabled. Please contact your administrator."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
    return tenant

@router.put("/{tenant_id}", response_model=TenantSchema)
async def update_tenant(
    tenant_id: int,
    tenant: TenantUpdate,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update a tenant"""
    # Users can only update their own tenant unless they're superuser
    if not current_user.is_superuser and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=NOT_AUTHORIZED
        )
    
    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Validate currency code if being updated
    if tenant.default_currency:
        currency_service = CurrencyService(master_db)
        if not currency_service.validate_currency_code(tenant.default_currency):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=INVALID_CURRENCY_CODE
            )
    
    # Check if subdomain already exists (if being updated)
    if tenant.subdomain and tenant.subdomain != tenant.subdomain:
        existing_tenant = master_db.query(Tenant).filter(Tenant.subdomain == tenant.subdomain).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=SUBDOMAIN_EXISTS
            )
    
    # Update tenant
    for field, value in tenant.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    
    master_db.commit()
    master_db.refresh(tenant)
    return tenant

@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Delete a tenant (only superusers can delete tenants)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ONLY_SUPERUSERS
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

@router.post("/import-sql", response_model=None)
async def import_sql_to_tenant(
    file: UploadFile = File(...),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
    dry_run: bool = Query(False, description="If true, only validate the SQL file without executing")
):
    require_admin(current_user)
    # Limit file size (e.g., 5MB)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="SQL file too large (max 5MB)")

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file.file.read())
        sql_path = tmp.name

    try:
        with open(sql_path, 'r') as sql_file:
            sql_commands = sql_file.read()

        # Basic forbidden statement filtering
        forbidden = ["drop ", "alter ", "truncate ", "create ", "replace ", "grant ", "revoke ", "set "]
        for word in forbidden:
            if word in sql_commands.lower():
                raise HTTPException(status_code=400, detail=f"Forbidden SQL statement detected: {word.strip()}")

        # Only allow certain statement types
        allowed = ("insert ", "update ", "delete ", "copy ", "select ")
        statements = [s.strip() for s in sql_commands.split(';') if s.strip()]
        if len(statements) > 1000:
            raise HTTPException(status_code=400, detail="Too many SQL statements (max 1000)")
        for stmt in statements:
            if not stmt.lower().startswith(allowed):
                raise HTTPException(status_code=400, detail=f"Only INSERT, UPDATE, DELETE, COPY, SELECT statements are allowed. Offending statement: {stmt[:40]}")

        # Dry-run mode: just validate
        if dry_run:
            return {"message": "SQL file validated successfully (dry run)", "statements": len(statements)}

        # Execute all statements in a transaction
        try:
            with master_db.begin_nested():  # Ensures rollback on any error
                for idx, stmt in enumerate(statements):
                    master_db.execute(stmt)
            master_db.commit()
        except Exception as e:
            master_db.rollback()
            return {"error": f"SQL import failed at statement {idx+1}: {e}", "statement": statements[idx][:100]}

        # Audit log
        logging.info(f"[SQL IMPORT] user={current_user.email} tenant_id={current_user.tenant_id} file={file.filename} time={datetime.utcnow().isoformat()}")

        return {"message": "SQL import completed successfully", "statements": len(statements)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")
    finally:
        os.remove(sql_path) 