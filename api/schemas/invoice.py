from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date

class InvoiceItemBase(BaseModel):
    description: str
    quantity: float
    price: float

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemUpdate(InvoiceItemBase):
    id: Optional[int] = None

class InvoiceItem(InvoiceItemBase):
    id: int
    invoice_id: int
    amount: float

    class Config:
        orm_mode = True

class InvoiceBase(BaseModel):
    amount: float = Field(..., description="Total amount of the invoice")
    currency: str = Field("USD", description="Currency code for the invoice")
    due_date: datetime = Field(..., description="Due date of the invoice")
    status: str = Field(..., description="Status of the invoice (draft, sent, paid, etc.)")
    notes: Optional[str] = Field(None, description="Additional notes for the invoice")
    client_id: int = Field(..., description="ID of the client this invoice belongs to")
    is_recurring: Optional[bool] = False
    recurring_frequency: Optional[str] = None
    discount_type: Optional[str] = Field("percentage", description="Type of discount: percentage or fixed")
    discount_value: Optional[float] = Field(0.0, description="Discount value (percentage or fixed amount)")
    subtotal: Optional[float] = Field(None, description="Subtotal before discount")

class InvoiceCreate(InvoiceBase):
    items: List[InvoiceItemCreate]

class InvoiceUpdate(BaseModel):
    amount: Optional[float] = Field(None, description="Total amount of the invoice")
    currency: Optional[str] = Field(None, description="Currency code for the invoice")
    due_date: Optional[datetime] = Field(None, description="Due date of the invoice")
    status: Optional[str] = Field(None, description="Status of the invoice (draft, sent, paid, etc.)")
    notes: Optional[str] = Field(None, description="Additional notes for the invoice")
    client_id: Optional[int] = Field(None, description="ID of the client this invoice belongs to")
    items: Optional[List[InvoiceItemUpdate]] = None
    is_recurring: Optional[bool] = None
    recurring_frequency: Optional[str] = None
    discount_type: Optional[str] = Field(None, description="Type of discount: percentage or fixed")
    discount_value: Optional[float] = Field(None, description="Discount value (percentage or fixed amount)")
    subtotal: Optional[float] = Field(None, description="Subtotal before discount")

class Invoice(InvoiceBase):
    id: int
    number: str
    tenant_id: int
    created_at: datetime
    updated_at: datetime
    items: List[InvoiceItem] = []

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class InvoiceWithClient(Invoice):
    client_name: str
    total_paid: float = 0.0
    items: List[InvoiceItem] = [] 