from sqlalchemy import Column, Integer, String, Float, ForeignKey, Table, DateTime, Boolean, JSON, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Association table for many-to-many relationship between users and tenants
user_tenant_association = Table(
    'user_tenant_memberships',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('master_users.id'), primary_key=True),
    Column('tenant_id', Integer, ForeignKey('tenants.id'), primary_key=True),
    Column('role', String, default='user', nullable=False),
    Column('is_active', Boolean, default=True, nullable=False),
    Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    Column('updated_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
)

# User model for master database (tenant management)
class MasterUser(Base):
    __tablename__ = "master_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    must_reset_password = Column(Boolean, default=False, nullable=False)
    theme = Column(String, default="system")
    show_analytics = Column(Boolean, default=False, nullable=False)  # Show/hide analytics menu
    count_against_license = Column(Boolean, default=True, nullable=False)  # Whether this user counts against global license limits
    mfa_chain_enabled = Column(Boolean, default=False, nullable=False)
    mfa_chain_mode = Column(String, default="fixed", nullable=False)
    mfa_chain_factors = Column(JSON, nullable=True)
    mfa_factor_secrets = Column(JSON, nullable=True)

    # Tenant relationship (keeping for backward compatibility)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    # User role within tenant
    role = Column(String, default="user")  # admin, user, viewer

    # Additional user fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)  # For Google SSO
    azure_ad_id = Column(String, unique=True, nullable=True)  # For Azure AD SSO (Object ID)
    azure_tenant_id = Column(String, nullable=True)  # Azure AD Tenant ID

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant")
    tenants = relationship("Tenant", secondary=user_tenant_association, back_populates="members")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    role = Column(String, default="user", nullable=False)  # admin, user, viewer
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_accepted = Column(Boolean, default=False, nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Tenant relationship
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    invited_by_id = Column(Integer, ForeignKey("master_users.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant")
    invited_by = relationship("MasterUser")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("master_users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("MasterUser", back_populates="password_reset_tokens")

class ShareToken(Base):
    __tablename__ = "share_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    record_type = Column(String(32), nullable=False)  # invoice|expense|payment|client|bank_statement|portfolio
    record_id = Column(Integer, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("master_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant")

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    subdomain = Column(String, unique=True, nullable=True, index=True)  # Optional subdomain
    is_active = Column(Boolean, default=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)  # License-based tenant control
    count_against_license = Column(Boolean, default=True, nullable=False)  # Whether this tenant counts against global capacity
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archived_by_id = Column(Integer, nullable=True)
    archive_reason = Column(Text, nullable=True)

    # Company details
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    company_logo_url = Column(String, nullable=True)
    enable_ai_assistant = Column(Boolean, default=False)
    allow_join_lookup = Column(Boolean, default=True, nullable=False)
    join_lookup_exact_match = Column(Boolean, default=False, nullable=False)

    # Currency settings
    default_currency = Column(String, default="USD", nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    users = relationship("User", back_populates="tenant")
    members = relationship("MasterUser", secondary=user_tenant_association, back_populates="tenants")
    clients = relationship("Client", back_populates="tenant")
    invoices = relationship("Invoice", back_populates="tenant")
    payments = relationship("Payment", back_populates="tenant")
    settings = relationship("Settings", back_populates="tenant")
    currency_rates = relationship("CurrencyRate", back_populates="tenant")
    client_notes = relationship("ClientNote", back_populates="tenant")
    discount_rules = relationship("DiscountRule", back_populates="tenant")
    ai_configs = relationship("AIConfig", back_populates="tenant")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    theme = Column(String, default="system")

    # Tenant relationship
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    # User role within tenant
    role = Column(String, default="user")  # admin, user, viewer

    # Additional user fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)  # For Google SSO
    azure_ad_id = Column(String, unique=True, nullable=True)  # For Azure AD SSO (Object ID)
    azure_tenant_id = Column(String, nullable=True)  # Azure AD Tenant ID
    mfa_chain_enabled = Column(Boolean, default=False, nullable=False)
    mfa_chain_mode = Column(String, default="fixed", nullable=False)
    mfa_chain_factors = Column(JSON, nullable=True)
    mfa_factor_secrets = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    notes = relationship("ClientNote", back_populates="user")

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    name = Column(String, index=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    paid_amount = Column(Float, default=0)
    preferred_currency = Column(String, nullable=True)  # Optional, fallback to tenant default
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="clients")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    notes = relationship("ClientNote", back_populates="client", cascade="all, delete-orphan")

class ClientNote(Base):
    __tablename__ = "client_notes"

    id = Column(Integer, primary_key=True, index=True)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Foreign keys
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    # Relationships
    client = relationship("Client", back_populates="notes")
    user = relationship("User", back_populates="notes")
    tenant = relationship("Tenant", back_populates="client_notes")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, index=True, nullable=False)  # Make number unique
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    due_date = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="draft")
    notes = Column(String, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    is_recurring = Column(Boolean, default=False)
    recurring_frequency = Column(String, nullable=True)
    discount_type = Column(String, default="percentage", nullable=False)  # percentage or fixed
    discount_value = Column(Float, default=0.0, nullable=False)  # percentage or fixed amount
    subtotal = Column(Float, nullable=False)  # Amount before discount
    custom_fields = Column(JSON, nullable=True)
    payer = Column(String, default="Client", nullable=False)  # "You" or "Client"
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # User attribution
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="invoices")
    client = relationship("Client", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    payment_method = Column(String, nullable=False, default="system")
    reference_number = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="payments")
    invoice = relationship("Invoice", back_populates="payments")

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    key = Column(String, nullable=False)  # Removed unique constraint for multi-tenancy
    value = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    # Add retention days for AI chat history (default 7, max 30)
    ai_chat_history_retention_days = Column(Integer, default=7)

    # Relationships
    tenant = relationship("Tenant", back_populates="settings")

class DiscountRule(Base):
    __tablename__ = "discount_rules"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    name = Column(String, nullable=False)  # e.g., "High Value Discount", "Bulk Order Discount"
    min_amount = Column(Float, nullable=False)  # Minimum amount to trigger the rule
    discount_type = Column(String, default="percentage", nullable=False)  # percentage or fixed
    discount_value = Column(Float, nullable=False)  # percentage or fixed amount
    currency = Column(String, default="USD", nullable=False)  # New field for currency
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Higher priority rules are applied first

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="discount_rules")

class SupportedCurrency(Base):
    __tablename__ = "supported_currencies"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    decimal_places = Column(Integer, default=2, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=True)

class CurrencyRate(Base):
    __tablename__ = "currency_rates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    from_currency = Column(String, nullable=False)
    to_currency = Column(String, nullable=False)
    rate = Column(Float, nullable=False)
    effective_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="currency_rates")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    description = Column(String, nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    price = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    invoice = relationship("Invoice", back_populates="items")

class InvoiceHistory(Base):
    __tablename__ = "invoice_history"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    action = Column(String, nullable=False)  # 'creation', 'update', 'payment', 'currency_change', 'discount_change'
    details = Column(String, nullable=True)
    previous_values = Column(JSON, nullable=True)  # Store previous values for comparison
    current_values = Column(JSON, nullable=True)   # Store current values

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    invoice = relationship("Invoice")
    tenant = relationship("Tenant")
    user = relationship("User") 

class AIConfig(Base):
    __tablename__ = "ai_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    provider_name = Column(String, nullable=False)  # e.g., "openai", "ollama"
    provider_url = Column(String, nullable=True)  # For custom endpoints
    api_key = Column(String, nullable=True)  # API key/token
    model_name = Column(String, nullable=False)  # e.g., "gpt-4", "llama2"
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Only one default per tenant
    tested = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="ai_configs") 

# --- AuditLog for master DB ---
from sqlalchemy import Integer, String, DateTime, JSON, Column
from datetime import datetime, timezone

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True)  # Optional: link to tenant if relevant
    user_id = Column(Integer, nullable=False)
    user_email = Column(String, nullable=False)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    resource_name = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, default="success", nullable=False)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TenantKey(Base):
    """
    Model for storing tenant encryption keys in the master database.
    This ensures all containers/services can access the same encryption keys.
    """
    __tablename__ = "tenant_keys"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    key_id = Column(String, nullable=False)  # e.g., "tenant_1_v1"
    encrypted_key_material = Column(Text, nullable=False)  # Master key encrypted key material
    algorithm = Column(String, default="AES-256-GCM", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<TenantKey(tenant_id={self.tenant_id}, key_id='{self.key_id}', version={self.version})>"


class OrganizationJoinRequest(Base):
    """
    Model for tracking requests to join existing organizations.
    Users can request to join an organization, and admins can approve/reject.
    """
    __tablename__ = "organization_join_requests"

    id = Column(Integer, primary_key=True, index=True)

    # User information for the request
    email = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)  # Stored temporarily until approved

    # Organization they want to join
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    requested_role = Column(String, default="user", nullable=False)  # user, admin, viewer

    # Request status and workflow
    status = Column(String, default="pending", nullable=False)  # pending, approved, rejected, expired
    rejection_reason = Column(Text, nullable=True)

    # Admin who processed the request
    reviewed_by_id = Column(Integer, ForeignKey("master_users.id"), nullable=True)

    # Additional information
    message = Column(Text, nullable=True)  # Optional message from requester
    notes = Column(Text, nullable=True)  # Admin notes

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Auto-expire requests after X days

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    reviewed_by = relationship("MasterUser", foreign_keys=[reviewed_by_id])

    def __repr__(self):
        return f"<OrganizationJoinRequest(id={self.id}, email='{self.email}', tenant_id={self.tenant_id}, status='{self.status}')>"


class CloudStorageConfiguration(Base):
    """
    Model for storing cloud storage provider configurations per tenant.
    Supports multiple providers with encrypted credentials.
    """
    __tablename__ = "cloud_storage_configurations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # None for global config
    provider = Column(String(50), nullable=False, index=True)  # aws_s3, azure_blob, gcp_storage, local
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)

    # Encrypted configuration JSON containing provider-specific settings
    encrypted_configuration = Column(Text, nullable=False)

    # Configuration metadata
    configuration_version = Column(Integer, default=1, nullable=False)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    test_status = Column(String(20), nullable=True)  # success, failed, pending
    test_error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<CloudStorageConfiguration(id={self.id}, tenant_id={self.tenant_id}, provider='{self.provider}', enabled={self.is_enabled})>"


class GlobalInstallationInfo(Base):
    """
    System-wide license and installation information.
    There should only ever be one record in this table.
    """
    __tablename__ = "global_installation_info"

    id = Column(Integer, primary_key=True, index=True)
    installation_id = Column(String(36), unique=True, nullable=False, index=True)

    # Global License Info
    license_key = Column(Text, nullable=True)
    license_activated_at = Column(DateTime(timezone=True), nullable=True)
    license_expires_at = Column(DateTime(timezone=True), nullable=True)
    license_scope = Column(String(20), nullable=True)  # 'local' or 'global'
    license_status = Column(String(20), default="invalid", nullable=False)
    is_licensed = Column(Boolean, default=False, nullable=False)

    max_tenants = Column(Integer, nullable=True)
    max_users = Column(Integer, nullable=True)
    licensed_features = Column(JSON, nullable=True)

    customer_email = Column(String, nullable=True)
    customer_name = Column(String, nullable=True)
    organization_name = Column(String, nullable=True)

    # Signup Controls
    allow_password_signup = Column(Boolean, default=True, nullable=False)
    allow_sso_signup = Column(Boolean, default=True, nullable=False)

    # Trial Info
    trial_start_date = Column(DateTime(timezone=True), nullable=True)
    trial_end_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class GlobalLicenseValidationLog(Base):
    """
    Centralized log for all license-related actions (activation, verification, etc.)
    across all installations/tenants.
    """
    __tablename__ = "global_license_validation_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)  # 'activation', 'verification', 'deactivation'
    status = Column(String, nullable=False)  # 'success', 'failed'

    installation_id = Column(String(36), nullable=False)
    tenant_id = Column(Integer, nullable=True) # Which tenant triggered the action
    user_id = Column(Integer, nullable=True)

    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    details = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TenantPluginSettings(Base):
    """
    Model for storing enabled plugins per tenant.
    Replaces localStorage-based plugin state with persistent database storage.
    """
    __tablename__ = "tenant_plugin_settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True, index=True)

    # JSON array of enabled plugin IDs: ["investments", "reports", ...]
    enabled_plugins = Column(JSON, default=list, nullable=False)

    # Plugin configuration: {"investments": {"enable_ai_import": true}, ...}
    plugin_config = Column(JSON, default=dict, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<TenantPluginSettings(tenant_id={self.tenant_id}, enabled_plugins={self.enabled_plugins})>"

class PluginUser(Base):
    """
    User model for public-facing plugin interactions.
    Separated from MasterUser to prevent dashboard access crossing over.
    """
    __tablename__ = "plugin_users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    plugin_id = Column(String, nullable=False, index=True)
    
    email = Column(String, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Null for SSO
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    
    # SSO Information
    google_id = Column(String, nullable=True)
    azure_ad_id = Column(String, nullable=True)
    
    # Payment Information
    stripe_customer_id = Column(String, nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<PluginUser(id={self.id}, email='{self.email}', plugin_id='{self.plugin_id}', tenant_id={self.tenant_id})>"


class ServerPluginAccess(Base):
    """
    Tracks which plugins a super admin has granted to which tenants.
    Tenant admins can only enable plugins that appear in this table for their tenant.
    Super admins manage this table; tenant admins are consumers.
    """
    __tablename__ = "server_plugin_access"

    id = Column(Integer, primary_key=True, index=True)
    plugin_id = Column(String, nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    granted_by_id = Column(Integer, ForeignKey("master_users.id"), nullable=False)
    granted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("plugin_id", "tenant_id", name="uq_server_plugin_access"),
    )

    tenant = relationship("Tenant")
    granted_by = relationship("MasterUser")

    def __repr__(self) -> str:
        return f"<ServerPluginAccess(plugin_id='{self.plugin_id}', tenant_id={self.tenant_id})>"
