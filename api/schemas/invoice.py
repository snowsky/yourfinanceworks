from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

class InvoiceItemBase(BaseModel):
    description: str
    quantity: float
    price: float

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemUpdate(BaseModel):
    id: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None

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
    custom_fields: Optional[Dict[str, Any]] = None
    show_discount_in_pdf: Optional[bool] = True

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
    custom_fields: Optional[Dict[str, Any]] = None
    show_discount_in_pdf: Optional[bool] = None

class Invoice(InvoiceBase):
    id: int
    number: str
    created_at: datetime
    updated_at: datetime
    items: List[InvoiceItem] = []
    custom_fields: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class InvoiceWithClient(Invoice):
    client_name: str
    total_paid: float = 0.0
    items: List[InvoiceItem] = [] 
    custom_fields: Optional[Dict[str, Any]] = Field(default=None, description="Custom fields for the invoice")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class InvoiceHistoryBase(BaseModel):
    action: str
    details: Optional[str] = None
    previous_values: Optional[Dict[str, Any]] = None
    current_values: Optional[Dict[str, Any]] = None

class InvoiceHistoryCreate(InvoiceHistoryBase):
    invoice_id: int
    user_id: int

class InvoiceHistory(InvoiceHistoryBase):
    id: int
    invoice_id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Recycle Bin Schemas
class DeletedInvoice(Invoice):
    """Schema for displaying deleted invoices in the recycle bin"""
    is_deleted: bool
    deleted_at: Optional[datetime]
    deleted_by: Optional[int]
    deleted_by_username: Optional[str] = None  # Username of who deleted it
    custom_fields: Optional[Dict[str, Any]] = None

class RecycleBinResponse(BaseModel):
    """Response schema for recycle bin operations"""
    message: str
    invoice_id: int
    action: str  # "moved_to_recycle", "restored", "permanently_deleted"

class RestoreInvoiceRequest(BaseModel):
    """Request schema for restoring an invoice"""
    new_status: Optional[str] = "draft"  # Status to set when restoring 