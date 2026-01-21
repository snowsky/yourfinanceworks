from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime

from core.constants.password import MIN_PASSWORD_LENGTH
from core.utils.password_validation import validate_password_strength

class OrganizationJoinRequestBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization_name: str  # Name of organization to join
    requested_role: str = "user"  # user, admin, viewer
    message: Optional[str] = None  # Optional message to admin
    
    @field_validator('requested_role')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ['user', 'admin', 'viewer']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

class OrganizationJoinRequestCreate(OrganizationJoinRequestBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        is_valid, errors = validate_password_strength(v)
        if not is_valid:
            raise ValueError('; '.join(errors))
        return v

class OrganizationJoinRequestRead(OrganizationJoinRequestBase):
    id: int
    tenant_id: int
    status: str
    rejection_reason: Optional[str] = None
    reviewed_by_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Nested data for display
    organization_name: Optional[str] = None  # Populated from tenant relationship
    reviewed_by_name: Optional[str] = None  # Populated from reviewer relationship

    class Config:
        from_attributes = True

class OrganizationJoinRequestUpdate(BaseModel):
    """For admin use to approve/reject requests"""
    status: str  # approved, rejected
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    approved_role: Optional[str] = None  # Role to assign if different from requested
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        allowed_statuses = ['approved', 'rejected']
        if v not in allowed_statuses:
            raise ValueError(f'Status must be one of: {", ".join(allowed_statuses)}')
        return v
    
    @field_validator('approved_role')
    @classmethod
    def validate_approved_role(cls, v):
        if v is not None:
            allowed_roles = ['user', 'admin', 'viewer']
            if v not in allowed_roles:
                raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

class OrganizationJoinRequestList(BaseModel):
    """Simplified version for listing requests"""
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization_name: str
    requested_role: str
    status: str
    message: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrganizationLookup(BaseModel):
    """For looking up organization by name"""
    organization_name: str

class OrganizationLookupResult(BaseModel):
    """Result of organization lookup"""
    exists: bool
    tenant_id: Optional[int] = None
    organization_name: Optional[str] = None
    message: str

class OrganizationJoinResponse(BaseModel):
    """Response after submitting join request"""
    success: bool
    message: str
    request_id: Optional[int] = None
