from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from core.constants.expense_status import ExpenseStatus
from core.utils.currency import CURRENCY_SYMBOL_MAP


class ExpenseBase(BaseModel):
    amount: Optional[float] = Field(None, description="Expense amount before tax (optional when attachments present)")
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
    status: str = Field(ExpenseStatus.RECORDED.value, description="Status of the expense")
    notes: Optional[str] = Field(None, description="Additional notes about the expense")
    invoice_id: Optional[int] = Field(None, description="Linked invoice ID (one expense -> at most one invoice)")
    # Inventory purchase fields
    is_inventory_purchase: Optional[bool] = Field(False, description="Whether this expense is an inventory purchase")
    inventory_items: Optional[List[Dict[str, Any]]] = Field(None, description="List of inventory items purchased")

    # Inventory consumption fields
    is_inventory_consumption: Optional[bool] = Field(False, description="Whether this expense is for inventory consumption")
    consumption_items: Optional[List[Dict[str, Any]]] = Field(None, description="List of inventory items consumed")

    # OCR/AI analysis flags
    imported_from_attachment: Optional[bool] = Field(False, description="Whether this expense originated from an uploaded file")
    analysis_status: Optional[str] = Field("not_started", description="OCR analysis status: not_started|pending|queued|processing|done|failed|cancelled")
    analysis_result: Optional[dict] = Field(None, description="Raw analysis payload from OCR/LLM")
    analysis_error: Optional[str] = Field(None, description="Error message if analysis failed")
    manual_override: Optional[bool] = Field(False, description="True if user manually edited; stops further analysis")
    disable_ai_recognition: Optional[bool] = Field(False, description="Disable AI document recognition for this expense")

    # Receipt timestamp fields for expense habit analytics
    receipt_timestamp: Optional[datetime] = Field(None, description="Exact timestamp extracted from receipt")
    receipt_time_extracted: Optional[bool] = Field(False, description="Whether timestamp was successfully extracted from receipt")

    # Review Worker fields
    review_status: Optional[str] = Field("not_started", description="Review process status: not_started|pending|diff_found|no_diff|reviewed|failed")
    review_result: Optional[dict] = Field(None, description="Data extracted by reviewer")
    reviewed_at: Optional[datetime] = Field(None, description="When the review was performed")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Allow None amount when attachments are present (will be extracted via OCR)"""
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        if v is not None:
            # If it's a symbol, convert it
            if v in CURRENCY_SYMBOL_MAP:
                return CURRENCY_SYMBOL_MAP[v]

            # Validate it's a 3-letter code
            v_upper = v.upper().strip()
            if len(v_upper) == 3 and v_upper.isalpha():
                return v_upper

            # Invalid format
            raise ValueError(f'Invalid currency code: "{v}". Must be a 3-letter ISO code (e.g., USD, EUR, GBP) or a recognized currency symbol.')
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v not in ExpenseStatus.get_all_values():
            raise ValueError(f'Invalid status. Must be one of: {", ".join(ExpenseStatus.get_all_values())}')
        return v

    @field_validator('expense_date', mode='before')
    @classmethod
    def convert_datetime_to_date(cls, v):
        """Convert datetime to date if needed for API response validation."""
        if isinstance(v, datetime):
            return v.date()
        return v


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

    # Inventory consumption fields
    is_inventory_consumption: Optional[bool] = None
    consumption_items: Optional[List[Dict[str, Any]]] = None
    imported_from_attachment: Optional[bool] = None
    analysis_status: Optional[str] = None
    analysis_result: Optional[dict] = None
    analysis_error: Optional[str] = None
    manual_override: Optional[bool] = None
    disable_ai_recognition: Optional[bool] = None
    receipt_timestamp: Optional[datetime] = None
    receipt_time_extracted: Optional[bool] = None

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        if v is not None:
            # If it's a symbol, convert it
            if v in CURRENCY_SYMBOL_MAP:
                return CURRENCY_SYMBOL_MAP[v]

            # Validate it's a 3-letter code
            v_upper = v.upper().strip()
            if len(v_upper) == 3 and v_upper.isalpha():
                return v_upper

            # Invalid format
            raise ValueError(f'Invalid currency code: "{v}". Must be a 3-letter ISO code (e.g., USD, EUR, GBP) or a recognized currency symbol.')
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ExpenseStatus.get_all_values():
            raise ValueError(f'Invalid status. Must be one of: {", ".join(ExpenseStatus.get_all_values())}')
        return v
    
    @field_validator('expense_date', mode='before')
    @classmethod
    def convert_datetime_to_date(cls, v):
        """Convert datetime to date if needed for API response validation."""
        if v is not None and isinstance(v, datetime):
            return v.date()
        return v


class Expense(ExpenseBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    receipt_filename: Optional[str] = None  # legacy single receipt
    attachments_count: Optional[int] = None
    analysis_updated_at: Optional[datetime] = None
    receipt_timestamp: Optional[datetime] = None
    receipt_time_extracted: Optional[bool] = None
    # User attribution fields
    created_by_user_id: Optional[int] = None
    created_by_username: Optional[str] = None
    created_by_email: Optional[str] = None
    # Bank statement link (reverse lookup)
    statement_transaction_id: Optional[int] = None  # BankStatementTransaction.id
    statement_id: Optional[int] = None              # BankStatement.id (parent statement)

    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('expense_date', mode='before')
    @classmethod
    def convert_datetime_to_date(cls, v):
        """Convert datetime to date if needed for API response validation."""
        if isinstance(v, datetime):
            return v.date()
        return v


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


# === Inventory Consumption Schemas ===

class InventoryConsumptionItem(BaseModel):
    """Schema for individual inventory consumption items"""
    item_id: int = Field(..., description="ID of the inventory item being consumed")
    quantity: float = Field(..., gt=0, description="Quantity consumed")
    unit_cost: Optional[float] = Field(None, ge=0, description="Cost per unit at time of consumption")
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
        if v is not None and v < 0:
            raise ValueError('Unit cost cannot be negative')
        return v


class InventoryConsumptionCreate(BaseModel):
    """Schema for creating an inventory consumption expense"""
    items: List[InventoryConsumptionItem] = Field(..., description="List of items consumed")
    notes: Optional[str] = Field(None, description="Consumption notes")
    category: str = Field("Inventory Consumption", description="Expense category")

    @field_validator('items')
    @classmethod
    def validate_items(cls, v):
        if not v:
            raise ValueError('At least one item must be consumed')
        return v


class ExpenseWithInventoryConsumption(Expense):
    """Expense with detailed inventory consumption information"""
    consumption_details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# === Recycle Bin Schemas ===

class DeletedExpense(Expense):
    """Schema for displaying deleted expenses in the recycle bin"""
    is_deleted: bool
    deleted_at: Optional[datetime]
    deleted_by: Optional[int]
    deleted_by_username: Optional[str] = None  # Username of who deleted it

    model_config = ConfigDict(from_attributes=True)


class RecycleBinExpenseResponse(BaseModel):
    """Response schema for expense recycle bin operations"""
    message: str
    expense_id: int
    action: str  # "moved_to_recycle", "restored", "permanently_deleted"


class RestoreExpenseRequest(BaseModel):
    """Request schema for restoring an expense"""
    new_status: Optional[str] = "recorded"  # Status to set when restoring


class ExpenseListResponse(BaseModel):
    """Response schema for paginated expense list"""
    success: bool = True
    expenses: List[Expense]
    total: int

    model_config = ConfigDict(from_attributes=True)


class PaginatedDeletedExpenses(BaseModel):
    items: List[DeletedExpense]
    total: int


