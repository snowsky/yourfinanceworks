"""
API models for external API integration and API key management.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Numeric, ForeignKey, JSON
from sqlalchemy.orm import relationship
import uuid

from .models import Base


class ExternalTransactionType(str, Enum):
    """External transaction type enumeration."""
    INCOME = "income"
    EXPENSE = "expense"


class ExternalTransactionStatus(str, Enum):
    """External transaction status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_REVIEW = "under_review"


class APIClient(Base):
    """API client model for managing external API access."""
    
    __tablename__ = "api_clients"
    
    # Client identification
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True)
    client_name = Column(String(255), nullable=False)
    client_description = Column(Text, nullable=True)
    
    # Owner information (references MasterUser)
    user_id = Column(Integer, ForeignKey("master_users.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    
    # Authentication
    api_key_hash = Column(String(255), nullable=False, unique=True)  # Hashed API key
    api_key_prefix = Column(String(10), nullable=False)  # First few characters for identification
    
    # OAuth 2.0 support (for enterprise clients)
    oauth_client_id = Column(String(255), nullable=True, unique=True)
    oauth_client_secret_hash = Column(String(255), nullable=True)
    oauth_redirect_uris = Column(JSON, nullable=True)  # Array of allowed redirect URIs
    oauth_scopes = Column(JSON, nullable=True)  # Array of allowed scopes
    
    # Permissions and capabilities
    allowed_transaction_types = Column(JSON, nullable=False, default=list)  # ["income", "expense"]
    allowed_currencies = Column(JSON, nullable=True)  # Allowed currencies, null = all
    max_transaction_amount = Column(Numeric(precision=15, scale=2), nullable=True)  # Maximum transaction amount
    
    # Rate limiting
    rate_limit_per_minute = Column(Integer, nullable=False, default=60)
    rate_limit_per_hour = Column(Integer, nullable=False, default=1000)
    rate_limit_per_day = Column(Integer, nullable=False, default=10000)
    
    # Status and lifecycle
    status = Column(String(20), nullable=False, default="active")  # active, suspended, revoked, pending_approval
    is_active = Column(Boolean, nullable=False, default=True)
    is_sandbox = Column(Boolean, nullable=False, default=False)  # Sandbox mode for testing
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Integer, ForeignKey("master_users.id"), nullable=True)
    
    # Suspension tracking
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    suspension_reason = Column(Text, nullable=True)
    reactivated_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Key rotation tracking
    key_rotated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Usage tracking
    total_requests = Column(Integer, nullable=False, default=0)
    total_transactions_submitted = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Security
    allowed_ip_addresses = Column(JSON, nullable=True)  # Array of allowed IP addresses/ranges
    webhook_url = Column(String(500), nullable=True)  # Optional webhook for notifications
    webhook_secret = Column(String(255), nullable=True)  # Secret for webhook verification
    
    # Audit and compliance
    created_by = Column(Integer, ForeignKey("master_users.id"), nullable=True)
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)
    privacy_policy_accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("MasterUser", foreign_keys=[user_id])
    tenant = relationship("Tenant")
    approver = relationship("MasterUser", foreign_keys=[approved_by])
    creator = relationship("MasterUser", foreign_keys=[created_by])
    transactions = relationship("ExternalTransaction", back_populates="external_client")
    permissions = relationship("ClientPermission", back_populates="client", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<APIClient(id={self.client_id}, name={self.client_name}, active={self.is_active})>"


class ExternalTransaction(Base):
    """External transaction model for API-submitted financial data."""
    
    __tablename__ = "external_transactions"
    
    # Transaction identification
    id = Column(Integer, primary_key=True, index=True)
    external_transaction_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("master_users.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    external_client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=False, index=True)
    external_reference_id = Column(String(255), nullable=True, index=True)  # Client's internal ID
    
    # Transaction details
    transaction_type = Column(String(20), nullable=False)  # INCOME or EXPENSE
    amount = Column(Numeric(precision=15, scale=2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    # Multi-currency support
    original_amount = Column(Numeric(precision=15, scale=2), nullable=True)
    original_currency = Column(String(3), nullable=True)
    exchange_rate = Column(Numeric(precision=18, scale=8), nullable=True)
    conversion_date = Column(DateTime(timezone=True), nullable=True)
    
    # Categorization
    category = Column(String(100), nullable=True, index=True)
    subcategory = Column(String(100), nullable=True)
    source_system = Column(String(100), nullable=False)  # Name of the external system
    
    # Income-specific fields
    invoice_reference = Column(String(255), nullable=True)
    payment_method = Column(String(50), nullable=True)
    
    # Tax components (for income transactions)
    sales_tax_amount = Column(Numeric(precision=15, scale=2), nullable=True, default=0)
    vat_amount = Column(Numeric(precision=15, scale=2), nullable=True, default=0)
    other_tax_amount = Column(Numeric(precision=15, scale=2), nullable=True, default=0)
    
    # Expense-specific fields
    business_purpose = Column(Text, nullable=True)
    receipt_url = Column(String(500), nullable=True)
    vendor_name = Column(String(255), nullable=True)
    
    # Status and approval workflow
    status = Column(String(20), nullable=False, default=ExternalTransactionStatus.PENDING)
    requires_review = Column(Boolean, nullable=False, default=True)
    reviewed_by = Column(Integer, ForeignKey("master_users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # Duplicate detection
    duplicate_check_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hash for duplicate detection
    is_duplicate = Column(Boolean, nullable=False, default=False)
    original_transaction_id = Column(String(36), nullable=True)  # Reference to original if duplicate
    
    # Metadata and audit
    submission_metadata = Column(JSON, nullable=True)  # Additional data from external system
    api_version = Column(String(10), nullable=True)
    client_ip_address = Column(String(45), nullable=True)
    disable_ai_recognition = Column(Boolean, nullable=False, default=False)  # Disable AI document recognition
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("MasterUser", foreign_keys=[user_id])
    tenant = relationship("Tenant")
    external_client = relationship("APIClient", back_populates="transactions")
    reviewer = relationship("MasterUser", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<ExternalTransaction(id={self.external_transaction_id}, type={self.transaction_type}, amount={self.amount}, status={self.status})>"


class ClientPermission(Base):
    """Client permission model for managing API client permissions."""
    
    __tablename__ = "client_permissions"
    
    # Permission identification
    id = Column(Integer, primary_key=True, index=True)
    permission_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True)
    
    # Foreign key relationships
    client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=False, index=True)
    
    # Permission details
    permission_type = Column(String(50), nullable=False)  # submit_income, submit_expenses, etc.
    
    # Audit information
    granted_by = Column(Integer, ForeignKey("master_users.id"), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, ForeignKey("master_users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    client = relationship("APIClient", back_populates="permissions")
    granter = relationship("MasterUser", foreign_keys=[granted_by])
    revoker = relationship("MasterUser", foreign_keys=[revoked_by])
    
    def __repr__(self):
        return f"<ClientPermission(id={self.permission_id}, client_id={self.client_id}, type={self.permission_type})>"
