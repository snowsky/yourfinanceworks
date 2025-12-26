from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Dict, Any, Union
from datetime import datetime
import json

class AuditLogBase(BaseModel):
    user_id: int
    user_email: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    details: Optional[Union[Dict[str, Any], str]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None

class AuditLogCreate(AuditLogBase):
    pass

class AuditLog(AuditLogBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('details', mode='before')
    @classmethod
    def parse_details(cls, v):
        """Parse details field - handle both string and dict formats"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                # Try to parse JSON string
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                # If parsing fails, return as a dict with the string value
                return {"raw_data": v}
        return v

class AuditLogFilter(BaseModel):
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = None
    limit: Optional[int] = 100
    offset: Optional[int] = 0

class AuditLogResponse(BaseModel):
    audit_logs: list[AuditLog]
    total: int
    page: int
    per_page: int
    total_pages: int 