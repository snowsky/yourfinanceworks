from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date

class InvoiceItemBase(BaseModel):
    description: str
    quantity: float
    price: float
    inventory_item_id: Optional[int] = Field(None, description="ID of inventory item to populate from")
    unit_of_measure: Optional[str] = Field(None, description="Unit of measure")

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemUpdate(BaseModel):
    id: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    inventory_item_id: Optional[int] = None
    unit_of_measure: Optional[str] = None

class InvoiceItem(InvoiceItemBase):
    id: int
    invoice_id: int
    amount: float
    inventory_item_id: Optional[int]
    unit_of_measure: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class InvoiceItemWithInventory(InvoiceItem):
    """Invoice item with full inventory information"""
    inventory_item: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

class InvoiceBase(BaseModel):
    amount: float = Field(..., description="Total amount of the invoice")
    currency: str = Field("USD", description="Currency code for the invoice")
    # Optional invoice date provided by client (used to set created_at server-side)
    date: Optional[datetime] = Field(None, description="Invoice date; will be stored as created_at")
    due_date: Optional[datetime] = Field(None, description="Due date of the invoice")
    paid_amount: Optional[float] = Field(0.0, description="Sum of payments at creation time (backend will create a payment entry if provided)")
    status: str = Field("draft", description="Status of the invoice (draft, sent, paid, etc.)")
    description: Optional[str] = Field(None, description="Short description of the invoice")
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
    number: Optional[str] = Field(None, description="Invoice number (optional - will be auto-generated if not provided)")
    items: Optional[List[InvoiceItemCreate]] = None

class InvoiceUpdate(BaseModel):
    amount: Optional[float] = Field(None, description="Total amount of the invoice")
    currency: Optional[str] = Field(None, description="Currency code for the invoice")
    # Allow updating invoice date (mapped to created_at on server)
    date: Optional[datetime] = Field(None, description="Invoice date; will update created_at")
    due_date: Optional[datetime] = Field(None, description="Due date of the invoice")
    paid_amount: Optional[float] = Field(None, description="Update paid amount (will create payment record). For already paid invoices, only status changes are allowed.")
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
    attachment_filename: Optional[str] = Field(None, description="Attachment filename; set to null to delete attachment")

class Invoice(InvoiceBase):
    id: int
    number: str
    created_at: datetime
    updated_at: datetime
    items: List[InvoiceItem] = []
    custom_fields: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class InvoiceWithClient(Invoice):
    client_name: str
    total_paid: float = 0.0
    items: List[InvoiceItemWithInventory] = [] 
    custom_fields: Optional[Dict[str, Any]] = Field(default=None, description="Custom fields for the invoice")
    has_attachment: Optional[bool] = False
    attachment_filename: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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