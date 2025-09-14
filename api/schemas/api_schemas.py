"""
Pydantic schemas for API key management and external transactions.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal


# API Key Management Schemas
class APIKeyCreateRequest(BaseModel):
    """Request schema for creating API keys."""
    client_name: str = Field(..., min_length=1, max_length=255, description="Name of the API client")
    client_description: Optional[str] = Field(None, description="Description of the API client")
    allowed_transaction_types: List[str] = Field(..., min_items=1, description="Allowed transaction types")
    allowed_currencies: Optional[List[str]] = Field(None, description="Allowed currencies (null = all)")
    max_transaction_amount: Optional[float] = Field(None, gt=0, description="Maximum transaction amount")
    rate_limit_per_minute: int = Field(60, ge=1, le=10000, description="Requests per minute limit")
    rate_limit_per_hour: int = Field(1000, ge=1, le=100000, description="Requests per hour limit")
    rate_limit_per_day: int = Field(10000, ge=1, le=1000000, description="Requests per day limit")
    allowed_ip_addresses: Optional[List[str]] = Field(None, description="Allowed IP addresses/ranges")
    webhook_url: Optional[str] = Field(None, max_length=500, description="Webhook URL for notifications")
    is_sandbox: bool = Field(False, description="Whether this is a sandbox client for testing")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="API key expiration in days")


class APIKeyResponse(BaseModel):
    """Response schema for API key creation."""
    client_id: str
    api_key: str = Field(..., description="The generated API key (only shown once)")
    api_key_prefix: str
    client_name: str
    allowed_transaction_types: List[str]
    rate_limits: Dict[str, int]
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class APIClientResponse(BaseModel):
    """Response schema for API client information."""
    id: int
    client_id: str
    client_name: str
    client_description: Optional[str]
    user_id: int
    api_key_prefix: str
    allowed_transaction_types: List[str]
    allowed_currencies: Optional[List[str]]
    max_transaction_amount: Optional[float]
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    rate_limit_per_day: int
    is_active: bool
    is_sandbox: bool
    total_requests: int
    total_transactions_submitted: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class APIClientUpdateRequest(BaseModel):
    """Request schema for updating API clients."""
    client_name: Optional[str] = Field(None, min_length=1, max_length=255)
    client_description: Optional[str] = None
    allowed_transaction_types: Optional[List[str]] = None
    allowed_currencies: Optional[List[str]] = None
    max_transaction_amount: Optional[float] = Field(None, gt=0)
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=10000)
    rate_limit_per_hour: Optional[int] = Field(None, ge=1, le=100000)
    rate_limit_per_day: Optional[int] = Field(None, ge=1, le=1000000)
    allowed_ip_addresses: Optional[List[str]] = None
    webhook_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class OAuthClientCreateRequest(BaseModel):
    """Request schema for creating OAuth clients."""
    client_name: str = Field(..., min_length=1, max_length=255)
    client_description: Optional[str] = None
    redirect_uris: List[str] = Field(..., min_items=1, description="Allowed redirect URIs")
    scopes: List[str] = Field(..., min_items=1, description="Allowed OAuth scopes")
    allowed_transaction_types: List[str] = Field(..., min_items=1)
    rate_limit_per_minute: int = Field(100, ge=1, le=10000)
    rate_limit_per_hour: int = Field(2000, ge=1, le=100000)
    rate_limit_per_day: int = Field(20000, ge=1, le=1000000)


class OAuthClientResponse(BaseModel):
    """Response schema for OAuth client creation."""
    client_id: str
    oauth_client_id: str
    oauth_client_secret: str = Field(..., description="The OAuth client secret (only shown once)")
    client_name: str
    redirect_uris: List[str]
    scopes: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


# External Transaction Schemas
class ExternalTransactionCreate(BaseModel):
    """Request schema for creating external transactions."""
    external_reference_id: Optional[str] = Field(None, description="Client's internal reference ID")
    transaction_type: str = Field(..., description="Transaction type: income or expense")
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field("USD", min_length=3, max_length=3, description="Currency code")
    date: datetime = Field(..., description="Transaction date")
    description: str = Field(..., min_length=1, description="Transaction description")
    
    # Multi-currency support
    original_amount: Optional[Decimal] = Field(None, description="Original amount if converted")
    original_currency: Optional[str] = Field(None, description="Original currency if converted")
    exchange_rate: Optional[Decimal] = Field(None, description="Exchange rate used for conversion")
    conversion_date: Optional[datetime] = Field(None, description="Date of currency conversion")
    
    # Categorization
    category: Optional[str] = Field(None, description="Transaction category")
    subcategory: Optional[str] = Field(None, description="Transaction subcategory")
    source_system: str = Field(..., description="Name of the external system")
    
    # Income-specific fields
    invoice_reference: Optional[str] = Field(None, description="Invoice reference for income")
    payment_method: Optional[str] = Field(None, description="Payment method")
    
    # Tax components
    sales_tax_amount: Optional[Decimal] = Field(None, description="Sales tax amount")
    vat_amount: Optional[Decimal] = Field(None, description="VAT amount")
    other_tax_amount: Optional[Decimal] = Field(None, description="Other tax amount")
    
    # Expense-specific fields
    business_purpose: Optional[str] = Field(None, description="Business purpose for expense")
    receipt_url: Optional[str] = Field(None, description="URL to receipt image/document")
    vendor_name: Optional[str] = Field(None, description="Vendor name for expense")
    
    # Metadata
    submission_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    disable_ai_recognition: Optional[bool] = Field(False, description="Disable AI document recognition for this transaction")


class ExternalTransactionResponse(BaseModel):
    """Response schema for external transactions."""
    id: int
    external_transaction_id: str
    external_reference_id: Optional[str]
    transaction_type: str
    amount: Decimal
    currency: str
    date: datetime
    description: str
    
    # Multi-currency support
    original_amount: Optional[Decimal]
    original_currency: Optional[str]
    exchange_rate: Optional[Decimal]
    conversion_date: Optional[datetime]
    
    # Categorization
    category: Optional[str]
    subcategory: Optional[str]
    source_system: str
    
    # Income-specific fields
    invoice_reference: Optional[str]
    payment_method: Optional[str]
    
    # Tax components
    sales_tax_amount: Optional[Decimal]
    vat_amount: Optional[Decimal]
    other_tax_amount: Optional[Decimal]
    
    # Expense-specific fields
    business_purpose: Optional[str]
    receipt_url: Optional[str]
    vendor_name: Optional[str]
    
    # Status and workflow
    status: str
    requires_review: bool
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    
    # Duplicate detection
    is_duplicate: bool
    original_transaction_id: Optional[str]
    
    # Metadata
    submission_metadata: Optional[Dict[str, Any]]
    api_version: Optional[str]
    client_ip_address: Optional[str]
    disable_ai_recognition: Optional[bool]
    
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExternalTransactionUpdate(BaseModel):
    """Request schema for updating external transactions."""
    description: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    business_purpose: Optional[str] = None
    receipt_url: Optional[str] = None
    vendor_name: Optional[str] = None
    status: Optional[str] = None
    review_notes: Optional[str] = None


class ExternalTransactionList(BaseModel):
    """Response schema for listing external transactions."""
    transactions: List[ExternalTransactionResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

    class Config:
        from_attributes = True


# Permission Management Schemas
class UserPermissionsRequest(BaseModel):
    """Request schema for managing user permissions."""
    user_id: int
    permissions: List[str] = Field(..., description="List of permission names to grant")


class PermissionResponse(BaseModel):
    """Response schema for permissions."""
    name: str
    description: str

    class Config:
        from_attributes = True


class UserPermissionsResponse(BaseModel):
    """Response schema for user permissions."""
    user_id: int
    username: str
    email: str
    roles: List[str]
    permissions: List[str]

    class Config:
        from_attributes = True
