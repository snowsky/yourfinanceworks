from sqlalchemy.orm import Session
from models.models_per_tenant import AuditLog
from typing import Optional, Dict, Any
from datetime import datetime

def log_audit_event(
    db: Session,
    user_id: int,
    user_email: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
):
    audit_log = AuditLog(
        user_id=user_id,
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        error_message=error_message,
        created_at=datetime.utcnow(),
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log 