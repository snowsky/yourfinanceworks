from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class ClientBase(BaseModel):
    name: str = Field(..., description="Client's full name")
    email: Optional[str] = Field(None, description="Client's email address (optional)")
    phone: Optional[str] = Field(None, description="Client's phone number")
    address: Optional[str] = Field(None, description="Client's address")
    company: Optional[str] = Field(None, description="Client's company name")
    preferred_currency: Optional[str] = Field(None, description="Client's preferred currency code")
    labels: Optional[List[str]] = Field(None, description="Client's labels")
    owner_user_id: Optional[int] = Field(None, description="Owner user ID")
    stage: Optional[str] = Field("active_client", description="Relationship stage")
    relationship_status: Optional[str] = Field("healthy", description="Relationship health status")
    source: Optional[str] = Field(None, description="Client acquisition source")
    last_contact_at: Optional[datetime] = Field(None, description="Last contact timestamp")
    next_follow_up_at: Optional[datetime] = Field(None, description="Next follow-up timestamp")

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Client's full name")
    email: Optional[str] = Field(None, description="Client's email address")
    phone: Optional[str] = Field(None, description="Client's phone number")
    address: Optional[str] = Field(None, description="Client's address")
    company: Optional[str] = Field(None, description="Client's company name")
    balance: Optional[float] = Field(None, description="Current balance")
    paid_amount: Optional[float] = Field(None, description="Total amount paid")
    preferred_currency: Optional[str] = Field(None, description="Client's preferred currency code")
    labels: Optional[List[str]] = Field(None, description="Client's labels")
    owner_user_id: Optional[int] = Field(None, description="Owner user ID")
    stage: Optional[str] = Field(None, description="Relationship stage")
    relationship_status: Optional[str] = Field(None, description="Relationship health status")
    source: Optional[str] = Field(None, description="Client acquisition source")
    last_contact_at: Optional[datetime] = Field(None, description="Last contact timestamp")
    next_follow_up_at: Optional[datetime] = Field(None, description="Next follow-up timestamp")

class Client(ClientBase):
    id: int
    balance: float = Field(0.0, description="Current balance")
    paid_amount: float = Field(0.0, description="Total amount paid")
    outstanding_balance: Optional[float] = Field(0.0, description="Outstanding balance")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PaginatedClients(BaseModel):
    items: List[Client]
    total: int
