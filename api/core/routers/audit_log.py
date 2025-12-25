from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.models.database import get_db
from core.models.models_per_tenant import AuditLog as AuditLogModel
from core.models.models import MasterUser
from core.schemas import AuditLog, AuditLogCreate, AuditLogResponse
from datetime import datetime
from core.routers.auth import get_current_user
from core.utils.rbac import require_admin

router = APIRouter()

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
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    require_admin(current_user, "view audit logs")

    # Set tenant context for proper decryption
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        query = db.query(AuditLogModel)

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
        return AuditLogResponse(
            audit_logs=audit_logs,
            total=total,
            page=page,
            per_page=limit,
            total_pages=total_pages
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit logs: {str(e)}")

@router.get("/audit-logs/{audit_log_id}", response_model=AuditLog)
def get_audit_log(
    audit_log_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    require_admin(current_user, "view audit logs")

    # Set tenant context for proper decryption
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        audit_log = db.query(AuditLogModel).filter(AuditLogModel.id == audit_log_id).first()
        if not audit_log:
            raise HTTPException(status_code=404, detail="Audit log not found")
        return audit_log
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit log: {str(e)}") 