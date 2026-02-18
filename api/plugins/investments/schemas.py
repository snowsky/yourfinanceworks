"""
Investment Management Pydantic Schemas

This module defines the Pydantic schemas for request/response validation
in the investment management plugin. These schemas ensure data integrity
and provide clear API documentation.
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

# Import the enums from models
from .models import PortfolioType, SecurityType, AssetClass, TransactionType, DividendType


# Base schemas with common fields
class TimestampMixin(BaseModel):
    """Mixin for models with timestamp fields"""
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


# Portfolio schemas
class PortfolioBase(BaseModel):
    """Base portfolio schema with common fields"""
    name: str = Field(..., min_length=1, max_length=100, description="Portfolio name")
    portfolio_type: PortfolioType = Field(..., description="Portfolio type")
    currency: str = Field(default="USD", description="Portfolio currency code")

class PortfolioCreate(PortfolioBase):
    """Schema for creating a new portfolio"""
    pass

class PortfolioUpdate(BaseModel):
    """Schema for updating a portfolio"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Portfolio name")
    portfolio_type: Optional[PortfolioType] = Field(None, description="Portfolio type")
    target_allocations: Optional[Dict[AssetClass, Decimal]] = Field(None, description="Target allocation weights (0-100)")

    @validator('target_allocations')
    def validate_targets(cls, v):
        if v is not None:
            total = sum(v.values())
            if total != Decimal('100') and total != Decimal('0'):
                raise ValueError('Total target allocation must sum to 100%')
            for weight in v.values():
                if weight < 0:
                    raise ValueError('Target weights cannot be negative')
        return v

class PortfolioResponse(PortfolioBase, TimestampMixin):
    """Schema for portfolio responses"""
    id: int
    is_archived: bool
    currency: str = Field(default="USD", description="Portfolio currency code")
    holdings_count: Optional[int] = Field(None, description="Number of holdings in portfolio")
    total_value: Optional[Decimal] = Field(None, description="Total portfolio value")
    total_cost: Optional[Decimal] = Field(None, description="Total cost basis of portfolio")
    target_allocations: Optional[Dict[AssetClass, Decimal]] = Field(None, description="Target allocation weights")

    class Config:
        from_attributes = True
        use_enum_values = True


# Rebalancing schemas
class RebalanceAction(BaseModel):
    """Schema for a recommended rebalance action"""
    asset_class: AssetClass
    security_symbol: Optional[str] = None
    action_type: str  # "BUY" or "SELL"
    amount: Decimal
    percentage_drift: Decimal

class RebalanceReport(BaseModel):
    """Schema for a full portfolio rebalance report"""
    portfolio_id: int
    total_value: Decimal
    current_allocations: Dict[AssetClass, Decimal]
    target_allocations: Dict[AssetClass, Decimal]
    drifts: Dict[AssetClass, Decimal]
    recommended_actions: List[RebalanceAction]
    is_balanced: bool
    summary: str

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# Holding schemas
class HoldingBase(BaseModel):
    """Base holding schema with common fields"""
    security_symbol: str = Field(..., min_length=1, max_length=20, description="Security symbol (e.g., AAPL)")
    security_name: Optional[str] = Field(None, max_length=200, description="Security name")
    security_type: SecurityType = Field(..., description="Security type")
    asset_class: AssetClass = Field(..., description="Asset class")
    quantity: Decimal = Field(..., gt=0, description="Quantity of shares")
    cost_basis: Decimal = Field(..., gt=0, description="Total cost basis")
    purchase_date: date = Field(..., description="Initial purchase date")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="ISO 4217 currency code")

    @validator('quantity', 'cost_basis')
    def validate_positive_numbers(cls, v):
        if v <= 0:
            raise ValueError('Must be positive')
        return v

    @validator('purchase_date')
    def validate_not_future_date(cls, v):
        if v > date.today():
            raise ValueError('Purchase date cannot be in the future')
        return v

class HoldingCreate(HoldingBase):
    """Schema for creating a new holding"""
    pass

class HoldingUpdate(BaseModel):
    """Schema for updating a holding"""
    security_name: Optional[str] = Field(None, max_length=200, description="Security name")
    security_type: Optional[SecurityType] = Field(None, description="Security type")
    asset_class: Optional[AssetClass] = Field(None, description="Asset class")
    quantity: Optional[Decimal] = Field(None, gt=0, description="Quantity of shares")
    cost_basis: Optional[Decimal] = Field(None, gt=0, description="Total cost basis")
    currency: Optional[str] = Field(None, min_length=3, max_length=3, description="ISO 4217 currency code")

    @validator('quantity', 'cost_basis')
    def validate_positive_numbers(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Must be positive')
        return v

class PriceUpdate(BaseModel):
    """Schema for updating security price"""
    current_price: Decimal = Field(..., gt=0, description="Current price per share")

    @validator('current_price')
    def validate_positive_price(cls, v):
        if v <= 0:
            raise ValueError('Price must be positive')
        return v

class HoldingResponse(HoldingBase, TimestampMixin):
    """Schema for holding responses"""
    id: int
    portfolio_id: int
    current_price: Optional[Decimal] = Field(None, description="Current price per share")
    price_updated_at: Optional[datetime] = Field(None, description="When price was last updated")
    is_closed: bool
    average_cost_per_share: Decimal = Field(..., description="Average cost per share")
    current_value: Decimal = Field(..., description="Current market value")
    unrealized_gain_loss: Decimal = Field(..., description="Unrealized gain/loss")
    currency: str = Field(..., description="ISO 4217 currency code")

    class Config:
        from_attributes = True
        use_enum_values = True


# Transaction schemas
class TransactionBase(BaseModel):
    """Base transaction schema with common fields"""
    transaction_type: TransactionType = Field(..., description="Transaction type")
    transaction_date: date = Field(..., description="Transaction date")
    total_amount: Decimal = Field(..., description="Total transaction amount")
    fees: Optional[Decimal] = Field(0, ge=0, description="Transaction fees")
    notes: Optional[str] = Field(None, max_length=500, description="Transaction notes")

    @validator('transaction_date')
    def validate_not_future_date(cls, v):
        if v > date.today():
            raise ValueError('Transaction date cannot be in the future')
        return v

    @validator('fees')
    def validate_non_negative_fees(cls, v):
        if v is not None and v < 0:
            raise ValueError('Fees cannot be negative')
        return v

class BuyTransactionCreate(TransactionBase):
    """Schema for creating a buy transaction"""
    transaction_type: TransactionType = Field(TransactionType.BUY, description="Must be BUY")
    holding_id: int = Field(..., description="Holding ID")
    quantity: Decimal = Field(..., gt=0, description="Quantity purchased")
    price_per_share: Decimal = Field(..., gt=0, description="Price per share")

    @validator('transaction_type')
    def validate_buy_type(cls, v):
        if v != TransactionType.BUY:
            raise ValueError('Must be BUY transaction type')
        return v

    @validator('quantity', 'price_per_share')
    def validate_positive_numbers(cls, v):
        if v <= 0:
            raise ValueError('Must be positive')
        return v

class SellTransactionCreate(TransactionBase):
    """Schema for creating a sell transaction"""
    transaction_type: TransactionType = Field(TransactionType.SELL, description="Must be SELL")
    holding_id: int = Field(..., description="Holding ID")
    quantity: Decimal = Field(..., gt=0, description="Quantity sold")
    price_per_share: Decimal = Field(..., gt=0, description="Price per share")

    @validator('transaction_type')
    def validate_sell_type(cls, v):
        if v != TransactionType.SELL:
            raise ValueError('Must be SELL transaction type')
        return v

    @validator('quantity', 'price_per_share')
    def validate_positive_numbers(cls, v):
        if v <= 0:
            raise ValueError('Must be positive')
        return v

class DividendTransactionCreate(TransactionBase):
    """Schema for creating a dividend transaction"""
    transaction_type: TransactionType = Field(TransactionType.DIVIDEND, description="Must be DIVIDEND")
    holding_id: int = Field(..., description="Holding ID")
    dividend_type: DividendType = Field(DividendType.ORDINARY, description="Dividend type")
    payment_date: Optional[date] = Field(None, description="Dividend payment date")
    ex_dividend_date: Optional[date] = Field(None, description="Ex-dividend date")

    @validator('transaction_type')
    def validate_dividend_type(cls, v):
        if v != TransactionType.DIVIDEND:
            raise ValueError('Must be DIVIDEND transaction type')
        return v

class OtherTransactionCreate(TransactionBase):
    """Schema for creating other transaction types (INTEREST, FEE, TRANSFER, CONTRIBUTION)"""
    transaction_type: TransactionType = Field(..., description="Transaction type")
    holding_id: Optional[int] = Field(None, description="Holding ID (optional for cash transactions)")

    @validator('transaction_type')
    def validate_other_types(cls, v):
        allowed_types = {TransactionType.INTEREST, TransactionType.FEE, TransactionType.TRANSFER, TransactionType.CONTRIBUTION}
        if v not in allowed_types:
            raise ValueError(f'Must be one of: {", ".join([t.value for t in allowed_types])}')
        return v

class TransactionResponse(TransactionBase):
    """Schema for transaction responses"""
    id: int
    portfolio_id: int
    holding_id: Optional[int]
    quantity: Optional[Decimal]
    price_per_share: Optional[Decimal]
    realized_gain: Optional[Decimal]
    dividend_type: Optional[DividendType]
    payment_date: Optional[date]
    ex_dividend_date: Optional[date]
    created_at: datetime

    class Config:
        from_attributes = True
        use_enum_values = True


# Analytics schemas
class PerformanceMetrics(BaseModel):
    """Schema for portfolio performance metrics"""
    total_value: Decimal = Field(..., description="Total portfolio value")
    total_cost: Decimal = Field(..., description="Total cost basis")
    total_gain_loss: Decimal = Field(..., description="Total gain/loss")
    total_return_percentage: Decimal = Field(..., description="Total return percentage (inception-to-date)")
    unrealized_gain_loss: Decimal = Field(..., description="Unrealized gain/loss")
    realized_gain_loss: Decimal = Field(..., description="Realized gain/loss")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class AllocationDetail(BaseModel):
    """Schema for asset allocation detail"""
    asset_class: AssetClass
    value: Decimal
    percentage: Decimal
    holdings_count: int

    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class AssetAllocation(BaseModel):
    """Schema for asset allocation analysis"""
    allocations: Dict[AssetClass, AllocationDetail]
    total_value: Decimal

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class DividendSummary(BaseModel):
    """Schema for dividend summary"""
    total_dividends: Decimal
    dividend_transactions: List[TransactionResponse]
    period_start: date
    period_end: date

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class TaxExport(BaseModel):
    """Schema for tax data export"""
    tax_year: int
    total_realized_gains: Decimal = Field(..., description="Total realized gains (raw amount)")
    total_dividends: Decimal = Field(..., description="Total dividends (raw amount)")
    transactions: List[TransactionResponse]

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# Query parameter schemas
class DateRangeQuery(BaseModel):
    """Schema for date range queries"""
    start_date: Optional[date] = Field(None, description="Start date (inclusive)")
    end_date: Optional[date] = Field(None, description="End date (inclusive)")

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v and 'start_date' in values and values['start_date'] and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v

class TaxYearQuery(BaseModel):
    """Schema for tax year queries"""
    tax_year: int = Field(..., ge=1900, le=2100, description="Tax year")


# Error schemas
class ErrorDetail(BaseModel):
    """Schema for error details"""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None

class ErrorResponse(BaseModel):
    """Schema for error responses"""
    error: str
    details: Optional[List[ErrorDetail]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Import FileAttachment enums
from .models import AttachmentStatus, FileType


# File Attachment schemas
class FileAttachmentBase(BaseModel):
    """Base file attachment schema with common fields"""
    original_filename: str = Field(..., min_length=1, max_length=255, description="Original filename")
    file_type: FileType = Field(..., description="File type (PDF or CSV)")


class FileAttachmentCreate(FileAttachmentBase):
    """Schema for creating a file attachment (used internally)"""
    file_size: int = Field(..., gt=0, description="File size in bytes")
    stored_filename: str = Field(..., description="Stored filename")
    local_path: str = Field(..., description="Local storage path")
    created_by: int = Field(..., description="User ID who uploaded the file")


class FileAttachmentResponse(TimestampMixin):
    """Schema for file attachment response"""
    id: int = Field(..., description="Attachment ID")
    portfolio_id: int = Field(..., description="Portfolio ID")
    original_filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: FileType = Field(..., description="File type")
    status: AttachmentStatus = Field(..., description="Processing status")
    extraction_error: Optional[str] = Field(None, description="Error message if extraction failed")
    extracted_holdings_count: int = Field(default=0, description="Number of successfully created holdings")
    failed_holdings_count: int = Field(default=0, description="Number of holdings that failed to create")
    processed_at: Optional[datetime] = Field(None, description="When processing completed")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class FileAttachmentDetailResponse(FileAttachmentResponse):
    """Schema for detailed file attachment response with extracted data"""
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted holdings data")

    @validator('extracted_data', pre=True)
    def parse_extracted_data(cls, v):
        """Parse JSON string to dictionary if needed"""
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class PortfolioWithAttachmentResponse(BaseModel):
    """Schema for portfolio creation response with optional file attachment"""
    portfolio: PortfolioResponse = Field(..., description="Created portfolio")
    attachment: Optional[FileAttachmentResponse] = Field(None, description="File attachment if file was uploaded")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
