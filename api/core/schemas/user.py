from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from core.utils.password_validation import validate_password_strength

class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    must_reset_password: bool = False
    role: str = "user"  # admin, user, viewer
    theme: Optional[str] = "system"

class UserCreate(UserBase):
    password: str
    tenant_id: Optional[int] = None  # Optional for signup flow
    organization_name: Optional[str] = None  # For creating new tenant during signup
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        is_valid, errors = validate_password_strength(v)
        if not is_valid:
            raise ValueError('; '.join(errors))
        return v
    
    @field_validator('organization_name')
    @classmethod
    def validate_organization_name(cls, v):
        if v is not None and len(v.strip()) < 2:
            raise ValueError('Organization name must be at least 2 characters long')
        return v.strip() if v else v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
    must_reset_password: Optional[bool] = None
    role: Optional[str] = None
    password: Optional[str] = None
    theme: Optional[str] = None
    show_analytics: Optional[bool] = None

class UserRead(UserBase):
    id: int
    tenant_id: int
    google_id: Optional[str] = None
    azure_ad_id: Optional[str] = None
    sso_provider: Optional[str] = None
    has_sso: Optional[bool] = None
    show_analytics: Optional[bool] = True
    created_at: datetime
    updated_at: datetime
    organizations: Optional[List[Dict[str, Any]]] = []

    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserRead 

class InviteCreate(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "user"  # admin, user, viewer

class InviteRead(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_accepted: bool
    expires_at: datetime
    created_at: datetime
    invited_by: Optional[str] = None  # email of inviter

    model_config = ConfigDict(from_attributes=True)

class InviteAccept(BaseModel):
    token: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        is_valid, errors = validate_password_strength(v)
        if not is_valid:
            raise ValueError('; '.join(errors))
        return v

class UserList(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserRoleUpdate(BaseModel):
    role: str  # admin, user, viewer 

class AdminActivateUser(BaseModel):
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None 