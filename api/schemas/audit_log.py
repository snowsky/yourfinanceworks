from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class AuditLogBase(BaseModel):
    user_id: int
    user_email: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None

class AuditLogCreate(AuditLogBase):
    pass

class AuditLog(AuditLogBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class AuditLogFilter(BaseModel):
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: Optional[int] = 100
    offset: Optional[int] = 0

class AuditLogResponse(BaseModel):
    audit_logs: list[AuditLog]
    total: int
    page: int
    per_page: int
    total_pages: int 