from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ClientBase(BaseModel):
    name: str = Field(..., description="Client's full name")
    email: Optional[str] = Field(None, description="Client's email address")
    phone: Optional[str] = Field(None, description="Client's phone number")
    address: Optional[str] = Field(None, description="Client's address")
    preferred_currency: Optional[str] = Field(None, description="Client's preferred currency code")

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Client's full name")
    email: Optional[str] = Field(None, description="Client's email address")
    phone: Optional[str] = Field(None, description="Client's phone number")
    address: Optional[str] = Field(None, description="Client's address")
    balance: Optional[float] = Field(None, description="Current balance")
    paid_amount: Optional[float] = Field(None, description="Total amount paid")
    preferred_currency: Optional[str] = Field(None, description="Client's preferred currency code")

class Client(ClientBase):
    id: int
    tenant_id: int
    balance: float = Field(0.0, description="Current balance")
    paid_amount: float = Field(0.0, description="Total amount paid")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        } 