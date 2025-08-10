from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


class ExpenseBase(BaseModel):
    amount: float = Field(..., description="Expense amount before tax")
    currency: str = Field("USD", description="Currency code for the expense")
    expense_date: date = Field(default_factory=date.today, description="Date of the expense")
    category: str = Field(..., description="Expense category (e.g., Travel, Meals, Software)")
    vendor: Optional[str] = Field(None, description="Vendor or payee")
    tax_rate: Optional[float] = Field(None, description="Tax rate percentage, e.g., 10 for 10%")
    tax_amount: Optional[float] = Field(None, description="Calculated tax amount, if provided")
    total_amount: Optional[float] = Field(None, description="Total amount including tax")
    payment_method: Optional[str] = Field(None, description="Payment method (e.g., Credit Card, Bank Transfer)")
    reference_number: Optional[str] = Field(None, description="Reference number")
    status: str = Field("recorded", description="Status of the expense (recorded, reimbursed, submitted)")
    notes: Optional[str] = Field(None, description="Additional notes about the expense")
    invoice_id: Optional[int] = Field(None, description="Linked invoice ID (one expense -> at most one invoice)")


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    expense_date: Optional[date] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    # Allow linking/unlinking to an invoice
    invoice_id: Optional[int] = None


class Expense(ExpenseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    receipt_filename: Optional[str] = None  # legacy single receipt
    attachments_count: Optional[int] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat() if v else None,
        }


