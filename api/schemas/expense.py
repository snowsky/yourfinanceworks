from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class ExpenseBase(BaseModel):
    amount: float = Field(..., description="Expense amount before tax")
    currency: str = Field("USD", description="Currency code for the expense")
    expense_date: date = Field(default_factory=date.today, description="Date of the expense")
    category: str = Field(..., description="Expense category (e.g., Travel, Meals, Software)")
    vendor: Optional[str] = Field(None, description="Vendor or payee")
    label: Optional[str] = Field(None, description="Legacy single label (backward compatible)")
    labels: Optional[List[str]] = Field(None, description="Up to 10 labels for grouping/searching expenses")
    tax_rate: Optional[float] = Field(None, description="Tax rate percentage, e.g., 10 for 10%")
    tax_amount: Optional[float] = Field(None, description="Calculated tax amount, if provided")
    total_amount: Optional[float] = Field(None, description="Total amount including tax")
    payment_method: Optional[str] = Field(None, description="Payment method (e.g., Credit Card, Bank Transfer)")
    reference_number: Optional[str] = Field(None, description="Reference number")
    status: str = Field("recorded", description="Status of the expense (recorded, reimbursed, submitted)")
    notes: Optional[str] = Field(None, description="Additional notes about the expense")
    invoice_id: Optional[int] = Field(None, description="Linked invoice ID (one expense -> at most one invoice)")
    # Inventory purchase fields
    is_inventory_purchase: Optional[bool] = Field(False, description="Whether this expense is an inventory purchase")
    inventory_items: Optional[List[Dict[str, Any]]] = Field(None, description="List of inventory items purchased")

    # OCR/AI analysis flags
    imported_from_attachment: Optional[bool] = Field(False, description="Whether this expense originated from an uploaded file")
    analysis_status: Optional[str] = Field("not_started", description="OCR analysis status: not_started|pending|queued|processing|done|failed|cancelled")
    analysis_result: Optional[dict] = Field(None, description="Raw analysis payload from OCR/LLM")
    analysis_error: Optional[str] = Field(None, description="Error message if analysis failed")
    manual_override: Optional[bool] = Field(False, description="True if user manually edited; stops further analysis")
    disable_ai_recognition: Optional[bool] = Field(False, description="Disable AI document recognition for this expense")


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    expense_date: Optional[date] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    label: Optional[str] = None
    labels: Optional[List[str]] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    # Allow linking/unlinking to an invoice
    invoice_id: Optional[int] = None
    # Inventory purchase fields
    is_inventory_purchase: Optional[bool] = None
    inventory_items: Optional[List[Dict[str, Any]]] = None
    imported_from_attachment: Optional[bool] = None
    analysis_status: Optional[str] = None
    analysis_result: Optional[dict] = None
    analysis_error: Optional[str] = None
    manual_override: Optional[bool] = None
    disable_ai_recognition: Optional[bool] = None


class Expense(ExpenseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    receipt_filename: Optional[str] = None  # legacy single receipt
    attachments_count: Optional[int] = None
    analysis_updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# === Inventory Purchase Schemas ===

class InventoryPurchaseItem(BaseModel):
    """Schema for individual inventory purchase items"""
    item_id: int = Field(..., description="ID of the inventory item being purchased")
    quantity: float = Field(..., gt=0, description="Quantity purchased")
    unit_cost: float = Field(..., ge=0, description="Cost per unit")
    item_name: Optional[str] = Field(None, description="Item name for validation")

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be greater than 0')
        return v

    @field_validator('unit_cost')
    @classmethod
    def validate_unit_cost(cls, v):
        if v < 0:
            raise ValueError('Unit cost cannot be negative')
        return v


class InventoryPurchaseCreate(BaseModel):
    """Schema for creating an inventory purchase expense"""
    vendor: str = Field(..., description="Vendor/Supplier name")
    reference_number: Optional[str] = Field(None, description="Purchase order or invoice number")
    purchase_date: date = Field(default_factory=date.today, description="Date of purchase")
    currency: str = Field("USD", description="Currency code")
    items: List[InventoryPurchaseItem] = Field(..., min_length=1, description="List of items purchased")
    notes: Optional[str] = Field(None, description="Purchase notes")
    payment_method: Optional[str] = Field(None, description="Payment method used")
    tax_rate: Optional[float] = Field(None, description="Tax rate for the purchase")

    @field_validator('items')
    @classmethod
    def validate_items(cls, v):
        if not v:
            raise ValueError('At least one item must be purchased')
        return v


class ExpenseWithInventoryPurchase(Expense):
    """Expense with detailed inventory purchase information"""
    inventory_purchase_details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class InventoryPurchaseSummary(BaseModel):
    """Summary of inventory purchases for reporting"""
    total_expenses: int
    total_purchase_value: float
    total_items_purchased: int
    currency: str
    purchases: List[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


