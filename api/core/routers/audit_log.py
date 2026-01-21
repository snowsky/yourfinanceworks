from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.models.database import get_db, get_master_db
from core.models.models_per_tenant import AuditLog as AuditLogModel
from core.models.models import MasterUser, AuditLog as MasterAuditLog
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
    from sqlalchemy.orm import object_session
    
    master_db = next(get_master_db())
    try:
        # Get all tenants
        from core.models.models import Tenant
        tenants = master_db.query(Tenant).all()

        all_audit_logs = []

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

                # Get all logs from this tenant (no per-tenant limit)
                tenant_logs = query.order_by(AuditLogModel.created_at.desc()).all()

                # Convert to dict and add tenant info
                for log in tenant_logs:
                    log_dict = {
                        'id': log.id,
                        'user_id': log.user_id,
                        'user_email': log.user_email,
                        'action': log.action,
                        'resource_type': log.resource_type,
                        'resource_id': log.resource_id,
                        'resource_name': log.resource_name,
                        'details': log.details,
                        'ip_address': log.ip_address,
                        'user_agent': log.user_agent,
                        'status': log.status,
                        'error_message': log.error_message,
                        'created_at': log.created_at,
                        'tenant_name': tenant.name,
                        'tenant_id': tenant.id
                    }
                    all_audit_logs.append(log_dict)

                tenant_db.close()
            except Exception as e:
                print(f"Error fetching logs from tenant {tenant.id}: {str(e)}")
                # Log error but continue with other tenants
                continue

        # Sort all logs by date (most recent first)
        all_audit_logs.sort(key=lambda x: x['created_at'], reverse=True)

        # Apply pagination to the aggregated results
        total = len(all_audit_logs)
        paginated_logs = all_audit_logs[offset:offset + limit]

        page = (offset // limit) + 1 if limit else 1
        total_pages = (total // limit) + (1 if total % limit else 0) if limit else 1

        # Convert dicts back to AuditLog objects for response
        audit_log_objects = []
        for log_dict in paginated_logs:
            audit_log_objects.append(AuditLog(**log_dict))

        return AuditLogResponse(
            audit_logs=audit_log_objects,
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

@router.get("/audit-logs/master-list", response_model=AuditLogResponse)
def get_master_audit_logs(
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
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get audit logs from master database (super admin only)"""
    # Only super admins can access master database audit logs
    is_super_admin = current_user.role == 'super_admin' or current_user.is_superuser
    if not is_super_admin:
        raise HTTPException(status_code=403, detail="Only super admins can access master audit logs")

    # Validate pagination parameters
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 100
    if limit > 10000:  # Prevent excessive load
        limit = 10000

    try:
        query = master_db.query(MasterAuditLog)

        if search:
            from sqlalchemy import or_, String, cast
            search_param = f"%{search}%"
            query = query.filter(
                or_(
                    MasterAuditLog.user_email.ilike(search_param),
                    MasterAuditLog.action.ilike(search_param),
                    MasterAuditLog.resource_type.ilike(search_param),
                    MasterAuditLog.resource_name.ilike(search_param),
                    MasterAuditLog.error_message.ilike(search_param),
                    cast(MasterAuditLog.details, String).ilike(search_param)
                )
            )

        if user_id:
            query = query.filter(MasterAuditLog.user_id == user_id)
        if user_email:
            query = query.filter(MasterAuditLog.user_email == user_email)
        if action:
            query = query.filter(MasterAuditLog.action == action)
        if resource_type:
            query = query.filter(MasterAuditLog.resource_type == resource_type)
        if resource_id:
            query = query.filter(MasterAuditLog.resource_id == resource_id)
        if status:
            query = query.filter(MasterAuditLog.status == status)
        if start_date:
            query = query.filter(MasterAuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(MasterAuditLog.created_at <= end_date)

        total = query.count()
        audit_logs = query.order_by(MasterAuditLog.created_at.desc()).offset(offset).limit(limit).all()
        page = (offset // limit) + 1 if limit else 1
        total_pages = (total // limit) + (1 if total % limit else 0) if limit else 1

        return AuditLogResponse(
            audit_logs=audit_logs,
            total=total,
            page=page,
            per_page=limit,
            total_pages=total_pages
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch master audit logs: {str(e)}")

@router.get("/audit-logs/master/{audit_log_id}", response_model=AuditLog)
def get_master_audit_log(
    audit_log_id: int,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get a specific master database audit log (super admin only)"""
    # Only super admins can access master database audit logs
    is_super_admin = current_user.role == 'super_admin' or current_user.is_superuser
    if not is_super_admin:
        raise HTTPException(status_code=403, detail="Only super admins can access master audit logs")

    try:
        audit_log = master_db.query(MasterAuditLog).filter(MasterAuditLog.id == audit_log_id).first()

        if not audit_log:
            raise HTTPException(status_code=404, detail="Master audit log not found")
        return audit_log
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to fetch master audit log: {str(e)}")

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

        # Hide super admin audit logs from regular users and viewers
        if not is_super_admin:
            from sqlalchemy import or_
            # Exclude logs where the user who performed the action is a super admin
            # We need to check the user who created the audit log, not the current user
            # This requires joining with the users table or checking specific super admin actions
            super_admin_actions = [
                'CREATE_TENANT', 'UPDATE_TENANT', 'DELETE_TENANT', 'TOGGLE_TENANT_STATUS',
                'RECREATE_DATABASE', 'PROMOTE', 'DEMOTE', 'CREATE_USER', 'UPDATE_USER', 
                'DELETE_USER', 'TOGGLE_USER_STATUS', 'RESET_PASSWORD', 'UPDATE_USER_ROLE',
                'SUPER_ADMIN_LOGIN', 'SUPER_ADMIN_LOGOUT', 'MASTER_DB_OPERATION',
                'CROSS_TENANT_OPERATION', 'SYSTEM_CONFIGURATION', 'BULK_OPERATION'
            ]
            query = query.filter(~AuditLogModel.action.in_(super_admin_actions))

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
