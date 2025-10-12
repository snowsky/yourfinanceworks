from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# === Inventory Category Schemas ===

class InventoryCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, max_length=500, description="Category description")
    color: Optional[str] = Field(None, description="Hex color code for UI display")

class InventoryCategoryCreate(InventoryCategoryBase):
    pass

class InventoryCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)

class InventoryCategory(InventoryCategoryBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# === Inventory Item Schemas ===

class InventoryItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Item name")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")
    sku: Optional[str] = Field(None, max_length=50, description="Stock Keeping Unit")
    category_id: Optional[int] = Field(None, description="Category ID")

    # Pricing
    unit_price: float = Field(..., gt=0, description="Selling price per unit")
    cost_price: Optional[float] = Field(None, ge=0, description="Cost price per unit")
    currency: str = Field("USD", min_length=3, max_length=3, description="Currency code")

    # Stock tracking
    track_stock: bool = Field(False, description="Whether to track stock levels")
    current_stock: float = Field(0.0, ge=0, description="Current stock quantity")
    minimum_stock: float = Field(0.0, ge=0, description="Minimum stock threshold")
    unit_of_measure: str = Field("each", min_length=1, max_length=20, description="Unit of measure")

    # Item type and status
    item_type: str = Field("product", description="Type: product, material, service")
    is_active: bool = Field(True, description="Whether item is active")

    # Barcode support
    barcode: Optional[str] = Field(None, max_length=100, description="Barcode value")
    barcode_type: Optional[str] = Field(None, max_length=20, description="Barcode type: UPC, EAN, CODE128, QR")
    barcode_format: Optional[str] = Field(None, max_length=10, description="Barcode format: 1D, 2D")

    @field_validator('item_type')
    @classmethod
    def validate_item_type(cls, v):
        allowed_types = ['product', 'material', 'service']
        if v not in allowed_types:
            raise ValueError(f'item_type must be one of: {allowed_types}')
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        if not v.isalpha() or len(v) != 3:
            raise ValueError('currency must be a 3-letter currency code')
        return v.upper()

    @model_validator(mode='after')
    def validate_stock_tracking(self):
        # For services, allow unlimited stock even if not tracking stock
        if self.item_type == 'service':
            return self

        # For products and materials, apply normal stock validation
        if not self.track_stock and self.current_stock > 0:
            raise ValueError('Cannot have current_stock > 0 when track_stock is False')
        if not self.track_stock and self.minimum_stock > 0:
            raise ValueError('Cannot have minimum_stock > 0 when track_stock is False')
        return self

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    sku: Optional[str] = Field(None, max_length=50)
    category_id: Optional[int] = Field(None)

    # Pricing
    unit_price: Optional[float] = Field(None, gt=0)
    cost_price: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)

    # Stock tracking
    track_stock: Optional[bool] = Field(None)
    current_stock: Optional[float] = Field(None, ge=0)
    minimum_stock: Optional[float] = Field(None, ge=0)
    unit_of_measure: Optional[str] = Field(None, min_length=1, max_length=20)

    # Item type and status
    item_type: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)

    # Barcode support
    barcode: Optional[str] = Field(None, max_length=100)
    barcode_type: Optional[str] = Field(None, max_length=20)
    barcode_format: Optional[str] = Field(None, max_length=10)

    @field_validator('item_type')
    @classmethod
    def validate_item_type(cls, v):
        if v is not None:
            allowed_types = ['product', 'material', 'service']
            if v not in allowed_types:
                raise ValueError(f'item_type must be one of: {allowed_types}')
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        if v is not None:
            if not v.isalpha() or len(v) != 3:
                raise ValueError('currency must be a 3-letter currency code')
            return v.upper()
        return v

class InventoryItem(InventoryItemBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    category: Optional[InventoryCategory]

    model_config = ConfigDict(from_attributes=True)


# === Stock Movement Schemas ===

class StockMovementBase(BaseModel):
    item_id: int = Field(..., description="ID of the inventory item")
    movement_type: str = Field(..., description="Type of movement")
    quantity: float = Field(..., description="Quantity change (positive for increases, negative for decreases)")
    unit_cost: Optional[float] = Field(None, ge=0, description="Cost per unit")
    reference_type: Optional[str] = Field(None, description="Source type: invoice, expense, manual, system")
    reference_id: Optional[int] = Field(None, description="ID of the related record")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")

    @field_validator('movement_type')
    @classmethod
    def validate_movement_type(cls, v):
        allowed_types = ['purchase', 'sale', 'adjustment', 'usage', 'return', 'transfer']
        if v not in allowed_types:
            raise ValueError(f'movement_type must be one of: {allowed_types}')
        return v

    @field_validator('reference_type')
    @classmethod
    def validate_reference_type(cls, v):
        if v is not None:
            allowed_types = ['invoice', 'expense', 'manual', 'system']
            if v not in allowed_types:
                raise ValueError(f'reference_type must be one of: {allowed_types}')
        return v

class StockMovementCreate(StockMovementBase):
    user_id: int = Field(..., description="ID of the user making the movement")
    movement_date: Optional[datetime] = Field(None, description="Date of the movement")

class StockMovementUpdate(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)

class StockMovement(StockMovementBase):
    id: int
    user_id: int
    movement_date: datetime
    created_at: datetime
    item: Optional[InventoryItem] = None

    model_config = ConfigDict(from_attributes=True)


# === Inventory Purchase Schemas ===

class InventoryPurchaseItem(BaseModel):
    item_id: int = Field(..., description="ID of the inventory item")
    quantity: float = Field(..., gt=0, description="Quantity purchased")
    unit_cost: float = Field(..., ge=0, description="Cost per unit")

class InventoryPurchaseCreate(BaseModel):
    items: List[InventoryPurchaseItem] = Field(..., description="List of items purchased")
    vendor: Optional[str] = Field(None, description="Vendor name")
    reference_number: Optional[str] = Field(None, description="Purchase reference number")
    notes: Optional[str] = Field(None, description="Purchase notes")


# === Inventory Search and Filter Schemas ===

class InventorySearchFilters(BaseModel):
    query: Optional[str] = Field(None, description="Search query for name, description, or SKU")
    category_id: Optional[int] = Field(None, description="Filter by category")
    item_type: Optional[str] = Field(None, description="Filter by item type")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    track_stock: Optional[bool] = Field(None, description="Filter by stock tracking")
    low_stock_only: Optional[bool] = Field(None, description="Show only low stock items")
    min_price: Optional[float] = Field(None, ge=0, description="Minimum unit price")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum unit price")

class InventoryListResponse(BaseModel):
    items: List[InventoryItem]
    total: int
    page: int
    page_size: int
    has_more: bool


# === Analytics and Reporting Schemas ===

class InventoryAnalytics(BaseModel):
    total_items: int
    active_items: int
    low_stock_items: int
    total_value: float
    currency: str

class StockMovementSummary(BaseModel):
    item_id: int
    item_name: str
    total_movements: int
    total_quantity_change: float
    last_movement_date: Optional[datetime]

class InventoryValueReport(BaseModel):
    total_inventory_value: float
    total_cost_value: float
    potential_profit: float
    currency: str
    items: List[Dict[str, Any]]


# === Enhanced Invoice/Expense Schemas with Inventory Support ===

class InvoiceItemWithInventory(BaseModel):
    id: Optional[int] = None
    description: str
    quantity: float
    price: float
    amount: float
    inventory_item_id: Optional[int] = None
    unit_of_measure: Optional[str] = None
    inventory_item: Optional[InventoryItem] = None

class ExpenseWithInventoryPurchase(BaseModel):
    id: Optional[int] = None
    amount: float
    currency: str
    expense_date: datetime
    category: str
    vendor: Optional[str] = None
    is_inventory_purchase: bool = False
    inventory_items: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None


# === Error Response Schemas ===

class InventoryErrorResponse(BaseModel):
    error: str
    error_code: str
    details: Optional[Dict[str, Any]] = None

class ValidationErrorDetail(BaseModel):
    field: str
    message: str

class InventoryValidationErrorResponse(BaseModel):
    error: str
    error_code: str
    validation_errors: List[ValidationErrorDetail]
