from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    role: str = "user"  # admin, user, viewer
    theme: Optional[str] = "system"

class UserCreate(UserBase):
    password: str
    tenant_id: Optional[int] = None  # Optional for signup flow
    organization_name: Optional[str] = None  # For creating new tenant during signup

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
    role: Optional[str] = None
    password: Optional[str] = None
    theme: Optional[str] = None

class UserRead(UserBase):
    id: int
    tenant_id: int
    google_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

class InviteAccept(BaseModel):
    token: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserList(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserRoleUpdate(BaseModel):
    role: str  # admin, user, viewer 

class AdminActivateUser(BaseModel):
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None 