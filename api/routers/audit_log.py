from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List
from models.database import get_db
from models.models_per_tenant import AuditLog as AuditLogModel
from schemas import AuditLog, AuditLogCreate, AuditLogFilter, AuditLogResponse
from datetime import datetime

router = APIRouter()

# All endpoints in this router require tenant context. The get_db dependency will raise an error if missing.

@router.post("/audit-logs/", response_model=AuditLog)
def create_audit_log(audit_log: AuditLogCreate, db: Session = Depends(get_db)):
    db_audit_log = AuditLogModel(**audit_log.dict())
    db.add(db_audit_log)
    db.commit()
    db.refresh(db_audit_log)
    return db_audit_log

@router.get("/audit-logs/", response_model=AuditLogResponse)
def get_audit_logs(
    user_id: int = None,
    user_email: str = None,
    action: str = None,
    resource_type: str = None,
    resource_id: str = None,
    status: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(AuditLogModel)
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

@router.get("/audit-logs/{audit_log_id}", response_model=AuditLog)
def get_audit_log(audit_log_id: int, db: Session = Depends(get_db)):
    audit_log = db.query(AuditLogModel).filter(AuditLogModel.id == audit_log_id).first()
    if not audit_log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return audit_log 