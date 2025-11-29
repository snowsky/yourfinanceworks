from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime


class PasswordResetRequest(BaseModel):
    """Schema for requesting a password reset"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for confirming a password reset with token"""
    token: str
    new_password: str
    

class PasswordResetResponse(BaseModel):
    """Schema for password reset response"""
    message: str
    success: bool


class PasswordResetTokenRead(BaseModel):
    """Schema for reading password reset token data"""
    id: int
    token: str
    user_id: int
    expires_at: datetime
    is_used: bool
    used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)