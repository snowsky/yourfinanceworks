from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.models.database import get_db
from core.models.models_per_tenant import AuditLog as AuditLogModel
from core.models.models import MasterUser
from core.schemas import AuditLog, AuditLogCreate, AuditLogResponse
from datetime import datetime
from core.routers.auth import get_current_user
from core.utils.rbac import require_admin_or_superuser

router = APIRouter()

def get_all_organizations_audit_logs(
    is_super_admin: bool,
    user_id: int = None,
    user_email: str = None,
    action: str = None,
    resource_type: str = None,
    resource_id: str = None,
    status: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    search: str = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Aggregate audit logs from all tenant databases for super admin.
    This is resource-intensive and should be used sparingly.
    """
    from core.services.tenant_database_manager import tenant_db_manager
    from core.models.database import get_master_db
    from core.models.database import set_tenant_context
    
    master_db = next(get_master_db())
    try:
        # Get all tenants
        from core.models.models import Tenant
        tenants = master_db.query(Tenant).all()
        
        all_audit_logs = []
        total_count = 0
        
        # Collect logs from each tenant database
        for tenant in tenants:
            try:
                # Check if tenant database exists before trying to access it
                if not tenant_db_manager.tenant_database_exists(tenant.id):
                    continue
                
                # Get tenant database session
                tenant_db = tenant_db_manager.get_tenant_session(tenant.id)()
                set_tenant_context(tenant.id)
                
                # Build query for this tenant
                query = tenant_db.query(AuditLogModel)
                
                # Apply filters
                if search:
                    from sqlalchemy import or_, String, cast
                    search_param = f"%{search}%"
                    query = query.filter(
                        or_(
                            AuditLogModel.user_email.ilike(search_param),
                            AuditLogModel.action.ilike(search_param),
                            AuditLogModel.resource_type.ilike(search_param),
                            AuditLogModel.resource_name.ilike(search_param),
                            AuditLogModel.error_message.ilike(search_param),
                            cast(AuditLogModel.details, String).ilike(search_param)
                        )
                    )
                
                if user_id:
                    query = query.filter(AuditLogModel.user_id == user_id)
                if user_email:
                    query = query.filter(AuditLogModel.user_email == user_email)
                if action:
                    query = query.filter(AuditLogModel.action == action)
                if resource_type:
                    query = query.filter(AuditLogModel.resource_type == resource_type)
                if resource_id:
                    query = query.filter(AuditLogModel.resource_id == resource_id)
                if status:
                    query = query.filter(AuditLogModel.status == status)
                if start_date:
                    query = query.filter(AuditLogModel.created_at >= start_date)
                if end_date:
                    query = query.filter(AuditLogModel.created_at <= end_date)
                
                # Get logs from this tenant (with a reasonable limit per tenant to prevent overload)
                tenant_limit = min(limit // len(tenants) + 10, 1000)  # Distribute limit among tenants
                tenant_logs = query.order_by(AuditLogModel.created_at.desc()).limit(tenant_limit).all()
                
                # Add tenant info to each log for identification
                for log in tenant_logs:
                    # Add tenant info as attributes (not dict keys since these are SQLAlchemy objects)
                    setattr(log, 'tenant_name', tenant.name)
                    setattr(log, 'tenant_id', tenant.id)
                
                all_audit_logs.extend(tenant_logs)
                tenant_db.close()
                
            except Exception as e:
                # Log error but continue with other tenants
                continue
        
        # Sort all logs by date (most recent first)
        all_audit_logs.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination to the aggregated results
        total = len(all_audit_logs)
        paginated_logs = all_audit_logs[offset:offset + limit]
        
        page = (offset // limit) + 1 if limit else 1
        total_pages = (total // limit) + (1 if total % limit else 0) if limit else 1
        
        return AuditLogResponse(
            audit_logs=paginated_logs,
            total=total,
            page=page,
            per_page=limit,
            total_pages=total_pages
        )
        
    finally:
        master_db.close()

@router.post("/audit-logs", response_model=AuditLog)
def create_audit_log(audit_log: AuditLogCreate, db: Session = Depends(get_db)):
    db_audit_log = AuditLogModel(**audit_log.model_dump())
    db.add(db_audit_log)
    db.commit()
    db.refresh(db_audit_log)
    return db_audit_log

@router.get("/audit-logs", response_model=AuditLogResponse)
def get_audit_logs(
    user_id: int = None,
    user_email: str = None,
    action: str = None,
    resource_type: str = None,
    resource_id: str = None,
    status: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    search: str = None,
    limit: int = 100,
    offset: int = 0,
    organization_id: int = None,
    all_organizations: bool = False,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    require_admin_or_superuser(current_user, "view audit logs")
    
    # Check if user is super admin and organization_id is provided
    is_super_admin = current_user.role == 'super_admin' or current_user.is_superuser
    if (organization_id is not None or all_organizations) and not is_super_admin:
        raise HTTPException(status_code=403, detail="Only super admins can filter by organization")
    
    # Validate pagination parameters
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 100
    if limit > 10000:  # Prevent excessive load
        limit = 10000

    # Use appropriate database session and tenant context
    from core.services.tenant_database_manager import tenant_db_manager
    from core.models.database import set_tenant_context
    
    if all_organizations and is_super_admin:
        # Super admin wants to view all organizations' logs - aggregate from all tenant databases
        return get_all_organizations_audit_logs(
            is_super_admin, user_id, user_email, action, resource_type, 
            resource_id, status, start_date, end_date, search, limit, offset
        )
    elif organization_id is not None and is_super_admin:
        # Super admin wants to view specific organization's logs
        # Use the target organization's database session
        target_db = tenant_db_manager.get_tenant_session(organization_id)()
        set_tenant_context(organization_id)
    else:
        # Use current user's tenant database session
        target_db = db
        set_tenant_context(current_user.tenant_id)

    try:
        query = target_db.query(AuditLogModel)

        if search:
            from sqlalchemy import or_, String, cast
            search_param = f"%{search}%"
            query = query.filter(
                or_(
                    AuditLogModel.user_email.ilike(search_param),
                    AuditLogModel.action.ilike(search_param),
                    AuditLogModel.resource_type.ilike(search_param),
                    AuditLogModel.resource_name.ilike(search_param),
                    AuditLogModel.error_message.ilike(search_param),
                    cast(AuditLogModel.details, String).ilike(search_param)
                )
            )

        if user_id:
            query = query.filter(AuditLogModel.user_id == user_id)
        if user_email:
            query = query.filter(AuditLogModel.user_email == user_email)
        if action:
            query = query.filter(AuditLogModel.action == action)
        if resource_type:
            query = query.filter(AuditLogModel.resource_type == resource_type)
        if resource_id:
            query = query.filter(AuditLogModel.resource_id == resource_id)
        if status:
            query = query.filter(AuditLogModel.status == status)
        if start_date:
            query = query.filter(AuditLogModel.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLogModel.created_at <= end_date)
        total = query.count()
        audit_logs = query.order_by(AuditLogModel.created_at.desc()).offset(offset).limit(limit).all()
        page = (offset // limit) + 1 if limit else 1
        total_pages = (total // limit) + (1 if total % limit else 0) if limit else 1
        
        # Close the target database session if it's different from the default one
        if organization_id is not None and is_super_admin:
            target_db.close()
        
        return AuditLogResponse(
            audit_logs=audit_logs,
            total=total,
            page=page,
            per_page=limit,
            total_pages=total_pages
        )
    except Exception as e:
        # Ensure the target database session is closed on error
        if organization_id is not None and is_super_admin:
            try:
                target_db.close()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit logs: {str(e)}")

@router.get("/audit-logs/{audit_log_id}", response_model=AuditLog)
def get_audit_log(
    audit_log_id: int,
    organization_id: int = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    require_admin_or_superuser(current_user, "view audit logs")

    # Check if user is super admin and organization_id is provided
    is_super_admin = current_user.role == 'super_admin' or current_user.is_superuser
    if organization_id is not None and not is_super_admin:
        raise HTTPException(status_code=403, detail="Only super admins can filter by organization")

    # Use appropriate database session and tenant context
    from core.services.tenant_database_manager import tenant_db_manager
    from core.models.database import set_tenant_context
    
    if organization_id is not None and is_super_admin:
        # Super admin wants to view specific organization's logs
        target_db = tenant_db_manager.get_tenant_session(organization_id)()
        set_tenant_context(organization_id)
    else:
        # Use current user's tenant database session
        target_db = db
        set_tenant_context(current_user.tenant_id)

    try:
        audit_log = target_db.query(AuditLogModel).filter(AuditLogModel.id == audit_log_id).first()
        
        # Close the target database session if it's different from the default one
        if organization_id is not None and is_super_admin:
            target_db.close()
        
        if not audit_log:
            raise HTTPException(status_code=404, detail="Audit log not found")
        return audit_log
    except Exception as e:
        # Ensure the target database session is closed on error
        if organization_id is not None and is_super_admin:
            try:
                target_db.close()
            except:
                pass
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit log: {str(e)}") 