from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class PaymentBase(BaseModel):
    amount: float = Field(..., description="Payment amount")
    currency: str = Field("USD", description="Currency code for the payment")
    payment_date: date = Field(default_factory=date.today, description="Date of payment")
    payment_method: str = Field(..., description="Payment method (e.g., Credit Card, Bank Transfer)")
    reference_number: Optional[str] = Field(None, description="Payment reference number")
    notes: Optional[str] = Field(None, description="Additional notes about the payment")
    invoice_id: int = Field(..., description="ID of the associated invoice")

class PaymentCreate(PaymentBase):
    pass

class PaymentUpdate(BaseModel):
    amount: Optional[float] = Field(None, description="Payment amount")
    currency: Optional[str] = Field(None, description="Currency code for the payment")
    payment_date: Optional[date] = Field(None, description="Date of payment")
    payment_method: Optional[str] = Field(None, description="Payment method")
    reference_number: Optional[str] = Field(None, description="Payment reference number")
    notes: Optional[str] = Field(None, description="Additional notes about the payment")
    invoice_id: Optional[int] = Field(None, description="ID of the associated invoice")

class Payment(PaymentBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime
    status: str = Field(default="completed", description="Payment status")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat() if v else None
        }

class PaymentWithInvoice(Payment):
    invoice_number: str = Field(..., description="Invoice number")
    client_name: str = Field(..., description="Client name")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat() if v else None
        } 