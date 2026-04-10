from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime, Boolean, JSON, Text, UniqueConstraint, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base
from enum import Enum as PyEnum

# Import encrypted column types for transparent encryption
from core.utils.column_encryptor import EncryptedColumn, EncryptedJSON

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(EncryptedColumn(), unique=True, index=True, nullable=False)  # Encrypted for privacy
    hashed_password = Column(String, nullable=False)  # Keep hashed password unencrypted for auth
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    must_reset_password = Column(Boolean, default=False, nullable=False)

    # User role within tenant (no tenant_id needed since each tenant has its own database)
    role = Column(String, default="user")  # admin, user, viewer

    # Additional user fields - encrypt personal information
    first_name = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    last_name = Column(EncryptedColumn(), nullable=True)   # Encrypted for privacy
    google_id = Column(EncryptedColumn(), unique=True, nullable=True)  # Encrypted for privacy
    azure_ad_id = Column(EncryptedColumn(), unique=True, nullable=True)  # Encrypted for privacy
    azure_tenant_id = Column(String, nullable=True)  # Azure AD Tenant ID - keep unencrypted for system use
    theme = Column(String, default="system")
    show_analytics = Column(Boolean, default=False)  # Show/hide analytics menu

    # Business type preference (helps with UI customization)
    business_type = Column(String, default="service")  # service, retail, wholesale, individual

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships (no tenant relationship needed)
    notes = relationship("ClientNote", back_populates="user")
    gamification_profile = relationship("UserGamificationProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database

    name = Column(EncryptedColumn(), index=True)  # Encrypted for privacy
    email = Column(EncryptedColumn(), unique=True, nullable=True, index=True)  # Encrypted for privacy, nullable to allow clients without email
    phone = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    address = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    company = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    balance = Column(Float, default=0.0)  # Keep unencrypted for calculations
    paid_amount = Column(Float, default=0)  # Keep unencrypted for calculations
    preferred_currency = Column(String, nullable=True)  # Optional, fallback to tenant default
    labels = Column(JSON, nullable=True)  # Multiple labels (tags) stored as JSON array of strings
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    stage = Column(String, nullable=False, default="active_client")
    relationship_status = Column(String, nullable=False, default="healthy")
    source = Column(String, nullable=True)
    last_contact_at = Column(DateTime(timezone=True), nullable=True)
    next_follow_up_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships (no tenant relationship needed)
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    notes = relationship("ClientNote", back_populates="client", cascade="all, delete-orphan")
    owner = relationship("User", foreign_keys=[owner_user_id])

class ClientNote(Base):
    __tablename__ = "client_notes"

    id = Column(Integer, primary_key=True, index=True)
    note = Column(EncryptedColumn(), nullable=False)  # Encrypted for privacy
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Foreign keys (no tenant_id needed)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships (no tenant relationship needed)
    client = relationship("Client", back_populates="notes")
    user = relationship("User", back_populates="notes")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, index=True, nullable=False)  # Unique within tenant database
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    due_date = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="draft", index=True)
    notes = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    # No tenant_id needed since each tenant has its own database
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    is_recurring = Column(Boolean, default=False)
    recurring_frequency = Column(String, nullable=True)
    discount_type = Column(String, default="percentage", nullable=False)  # percentage or fixed
    discount_value = Column(Float, default=0.0, nullable=False)  # percentage or fixed amount
    subtotal = Column(Float, nullable=False)  # Amount before discount
    custom_fields = Column(EncryptedJSON(),nullable=True)  # Encrypted JSON for sensitive custom data
    show_discount_in_pdf = Column(Boolean, default=True, nullable=False)
    payer = Column(String, default="Client", nullable=False)  # Who is paying the invoice: 'You' or 'Client'
    attachment_path = Column(String, nullable=True)  # Path to uploaded attachment file
    attachment_filename = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    description = Column(String, nullable=True)  # Short description of the invoice
    labels = Column(JSON, nullable=True)  # Multiple labels (tags) stored as JSON array of strings

    # Anomaly detection audit fields
    is_audited = Column(Boolean, default=False, nullable=False)  # Track if entity has been audited
    last_audited_at = Column(DateTime(timezone=True), nullable=True)  # When entity was last audited

    # Soft delete fields for recycle bin functionality
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Track who deleted it

    # User attribution
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Review Worker fields
    review_status = Column(String, default="not_started", nullable=False)  # not_started|pending|reviewed|diff_found
    review_result = Column(EncryptedJSON(), nullable=True)  # Encrypted sensitive review data
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships (no tenant relationship needed)
    client = relationship("Client", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    deleted_by_user = relationship("User", foreign_keys=[deleted_by])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    expenses = relationship("Expense", back_populates="invoice")
    attachments = relationship("InvoiceAttachment", back_populates="invoice", cascade="all, delete-orphan")
    approvals = relationship("InvoiceApproval", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def created_by_username(self):
        """Get creator username for API responses"""
        # User model implies email is the identifier as there is no username column
        if self.created_by:
            if self.created_by.first_name and self.created_by.last_name:
                return f"{self.created_by.first_name} {self.created_by.last_name}"
            if self.created_by.first_name:
                return self.created_by.first_name
            return self.created_by.email
        return None

    @property
    def created_by_email(self):
        """Get creator email for API responses"""
        if self.created_by:
            return self.created_by.email
        return None

    @property
    def paid_amount(self):
        """Calculate total paid amount from all associated payments"""
        if self.payments:
            return sum(payment.amount for payment in self.payments)
        return 0.0

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database

    invoice_id = Column(Integer, ForeignKey("invoices.id"), index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    payment_method = Column(String, nullable=False, default="system")
    reference_number = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    notes = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NEW: Track who created/updated the payment

    # Relationships (no tenant relationship needed)
    invoice = relationship("Invoice", back_populates="payments")
    user = relationship("User")  # NEW: Relationship to User

    @property
    def created_by_username(self):
        """Get creator username for API responses"""
        # User model implies email is the identifier
        if self.user:
            if self.user.first_name and self.user.last_name:
                return f"{self.user.first_name} {self.user.last_name}"
            if self.user.first_name:
                return self.user.first_name
            return self.user.email
        return None

    @property
    def created_by_email(self):
        """Get creator email for API responses"""
        if self.user:
            return self.user.email
        return None

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database

    amount = Column(Float, nullable=True)
    currency = Column(String, default="USD", nullable=False)
    expense_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    category = Column(String, nullable=False, index=True)
    vendor = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    # Optional label to categorize or tag expenses (legacy single label)
    label = Column(String, nullable=True, index=True)  # Keep unencrypted for indexing/filtering
    # Optional multiple labels (tags) stored as JSON array of strings
    labels = Column(JSON, nullable=True)  # Keep unencrypted for querying
    tax_rate = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True)
    payment_method = Column(String, nullable=True)
    reference_number = Column(String, nullable=True)
    status = Column(String, nullable=False, default="recorded")
    notes = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    receipt_path = Column(String, nullable=True)  # Keep unencrypted for file system access
    receipt_filename = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # User attribution

    # Inventory purchase fields
    is_inventory_purchase = Column(Boolean, default=False, nullable=False)
    inventory_items = Column(EncryptedJSON(),nullable=True)  # Encrypted sensitive inventory data

    # Inventory consumption fields
    is_inventory_consumption = Column(Boolean, default=False, nullable=False)
    consumption_items = Column(EncryptedJSON(),nullable=True)  # Encrypted sensitive consumption data

    # OCR/AI analysis fields
    imported_from_attachment = Column(Boolean, default=False, nullable=False)
    analysis_status = Column(String, default="not_started", nullable=False, index=True)  # not_started|queued|processing|done|failed|cancelled
    analysis_result = Column(EncryptedJSON(),nullable=True)  # Encrypted sensitive analysis data
    analysis_error = Column(Text, nullable=True)  # Keep unencrypted for debugging
    manual_override = Column(Boolean, default=False, nullable=False)
    analysis_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Receipt timestamp fields for expense habit analytics
    receipt_timestamp = Column(DateTime(timezone=True), nullable=True)  # Exact timestamp from receipt
    receipt_time_extracted = Column(Boolean, default=False, nullable=False)  # Whether timestamp was extracted from receipt

    # Anomaly detection audit fields
    is_audited = Column(Boolean, default=False, nullable=False)  # Track if entity has been audited
    last_audited_at = Column(DateTime(timezone=True), nullable=True)  # When entity was last audited

    # Soft delete fields for recycle bin functionality
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Track who deleted it

    # Review Worker fields
    review_status = Column(String, default="not_started", nullable=False)  # not_started|pending|reviewed|diff_found
    review_result = Column(EncryptedJSON(), nullable=True)  # Encrypted sensitive review data
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    invoice = relationship("Invoice", back_populates="expenses")
    client = relationship("Client")
    approvals = relationship("ExpenseApproval", back_populates="expense", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    deleted_by_user = relationship("User", foreign_keys=[deleted_by])

    @property
    def client_name(self):
        """Get linked client name for API responses"""
        if self.client:
            return self.client.name
        return None

    @property
    def created_by_username(self):
        """Get creator username for API responses"""
        # Check for pre-set override (used by routes when tenant DB decryption fails)
        override = self.__dict__.get('_creator_display_name')
        if override is not None:
            return override
        if self.created_by:
            first = self.created_by.first_name
            last = self.created_by.last_name
            email = self.created_by.email
            if first and last:
                return f"{first} {last}"
            if first:
                return first
            return email
        return None

    @property
    def created_by_email(self):
        """Get creator email for API responses"""
        if self.created_by:
            return self.created_by.email
        return None

class ExpenseAttachment(Base):
    __tablename__ = "expense_attachments"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    expense = relationship("Expense")
    uploader = relationship("User")

    # OCR / Analysis Fields
    analysis_status = Column(String, default="not_started")  # not_started, processing, done, failed
    analysis_result = Column(JSON, nullable=True)  # Raw OCR result
    analysis_error = Column(Text, nullable=True)
    extracted_amount = Column(Float, nullable=True)

    # Cloud Storage Cache - stores local path after downloading from cloud storage
    # This prevents re-downloading the same file on retries
    local_cache_path = Column(String, nullable=True)

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database

    key = Column(String, unique=True, index=True)  # Can be unique within tenant database
    value = Column(JSON)
    description = Column(String, nullable=True)  # Human readable description
    category = Column(String, default="general")  # general, features, appearance, etc.
    is_public = Column(Boolean, default=True)  # Whether users can see/modify this setting

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class DiscountRule(Base):
    __tablename__ = "discount_rules"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database

    name = Column(String, nullable=False)  # e.g., "High Value Discount", "Bulk Order Discount"
    min_amount = Column(Float, nullable=False)  # Minimum amount to trigger the rule
    discount_type = Column(String, default="percentage", nullable=False)  # percentage or fixed
    discount_value = Column(Float, nullable=False)  # percentage or fixed amount
    currency = Column(String, default="USD", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Higher priority rules are applied first

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    # No tenant_id needed since each tenant has its own database
    from_currency = Column(String, nullable=False)
    to_currency = Column(String, nullable=False)
    rate = Column(Float, nullable=False)
    effective_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=True)  # Optional link to inventory item
    description = Column(String, nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    price = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    unit_of_measure = Column(String, nullable=True)  # Unit of measure from inventory item
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    invoice = relationship("Invoice", back_populates="items")
    inventory_item = relationship("InventoryItem", back_populates="invoice_items")

class InvoiceHistory(Base):
    __tablename__ = "invoice_history"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    # No tenant_id needed since each tenant has its own database
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    action = Column(String, nullable=False)  # 'creation', 'update', 'payment', 'currency_change', 'discount_change'
    details = Column(String, nullable=True)
    previous_values = Column(JSON, nullable=True)  # Store previous values for comparison
    current_values = Column(JSON, nullable=True)   # Store current values

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    invoice = relationship("Invoice")
    user = relationship("User") 

class AIConfig(Base):
    __tablename__ = "ai_configs"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database
    provider_name = Column(String, nullable=False)  # e.g., "openai", "ollama"
    provider_url = Column(EncryptedColumn(), nullable=True)  # Encrypted for security
    api_key = Column(EncryptedColumn(), nullable=True)  # Encrypted for security - API keys are sensitive
    model_name = Column(String, nullable=False)  # e.g., "gpt-4", "llama2"
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Only one default per tenant
    tested = Column(Boolean, default=False)  # Track if configuration has been successfully tested

    # OCR specific settings
    ocr_enabled = Column(Boolean, default=False, nullable=False)
    max_tokens = Column(Integer, default=4096, nullable=False)
    temperature = Column(Float, default=0.1, nullable=False)

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Audit fields
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # ID of the user who performed the action
    user_email = Column(EncryptedColumn(), nullable=False)  # Encrypted for privacy
    action = Column(String, nullable=False)  # CREATE, READ, UPDATE, DELETE, LOGIN, LOGOUT, etc.
    resource_type = Column(String, nullable=False)  # user, client, invoice, payment, settings, etc.
    resource_id = Column(String, nullable=True)  # ID of the affected resource
    resource_name = Column(String, nullable=True)  # Human-readable name of the resource
    details = Column(JSON, nullable=True)  # Audit details (not encrypted to avoid JSON parsing issues)
    ip_address = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    user_agent = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    status = Column(String, default="success", nullable=False)  # success, error, warning
    error_message = Column(String, nullable=True)  # Keep unencrypted for debugging
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

# --- Statements ---

class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False)

    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    cloud_file_url = Column(String, nullable=True)  # Cloud storage URL (S3, etc.)
    status = Column(String, default="processing", nullable=False)  # uploaded|processing|processed|failed
    extracted_count = Column(Integer, default=0, nullable=False)
    extraction_method = Column(String, nullable=True)  # llm|regex|csv
    card_type = Column(String, default="debit", nullable=False)  # debit|credit
    analysis_error = Column(Text, nullable=True)
    analysis_updated_at = Column(DateTime(timezone=True), nullable=True)
    local_cache_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    bank_name = Column(String, nullable=True)
    labels = Column(JSON, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # User attribution
    is_possible_receipt = Column(Boolean, default=False, nullable=False)  # AI detected this may be a receipt
    file_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hex digest of uploaded file

    # Soft delete fields for recycle bin functionality
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Track who deleted it

    # Review Worker fields
    review_status = Column(String, default="not_started", nullable=False)  # not_started|pending|reviewed|diff_found
    review_result = Column(EncryptedJSON(), nullable=True)  # Encrypted sensitive review data
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    transactions = relationship("BankStatementTransaction", back_populates="statement", cascade="all, delete-orphan")
    attachments = relationship("BankStatementAttachment", back_populates="statement", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    deleted_by_user = relationship("User", foreign_keys=[deleted_by])


class BankStatementTransaction(Base):
    __tablename__ = "bank_statement_transactions"

    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False)

    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)  # debit|credit
    balance = Column(Float, nullable=True)
    category = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    # Optional link to an invoice created from this transaction (prevents duplicates)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    # Optional link to an expense created from this transaction (prevents duplicates)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=True)

    # Anomaly detection audit fields
    is_audited = Column(Boolean, default=False, nullable=False)  # Track if entity has been audited
    last_audited_at = Column(DateTime(timezone=True), nullable=True)  # When entity was last audited

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    statement = relationship("BankStatement", back_populates="transactions")
    links_as_a = relationship("TransactionLink", foreign_keys="TransactionLink.transaction_a_id", cascade="all, delete-orphan")
    links_as_b = relationship("TransactionLink", foreign_keys="TransactionLink.transaction_b_id", cascade="all, delete-orphan")


class TransactionLink(Base):
    """Links two bank statement transactions that represent the same real-world event
    (e.g., inter-account transfer, USD→CAD conversion)."""
    __tablename__ = "transaction_links"

    id = Column(Integer, primary_key=True, index=True)
    transaction_a_id = Column(Integer, ForeignKey("bank_statement_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_b_id = Column(Integer, ForeignKey("bank_statement_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type = Column(String, nullable=False, default="transfer")  # "transfer" | "fx_conversion"
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    transaction_a = relationship("BankStatementTransaction", foreign_keys=[transaction_a_id], overlaps="links_as_a")
    transaction_b = relationship("BankStatementTransaction", foreign_keys=[transaction_b_id], overlaps="links_as_b")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        UniqueConstraint("transaction_a_id", "transaction_b_id", name="unique_transaction_link_pair"),
    )


class BankStatementAttachment(Base):
    __tablename__ = "bank_statement_attachments"

    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False)

    # File information
    filename = Column(String, nullable=False)  # Original filename
    stored_filename = Column(String, nullable=False)  # Stored filename (usually UUID-based)
    file_path = Column(String, nullable=False)  # Full path to stored file
    cloud_file_url = Column(String, nullable=True)  # Cloud storage URL (S3, etc.)
    file_size = Column(Integer, nullable=False)  # File size in bytes
    content_type = Column(String, nullable=True)  # MIME type
    file_hash = Column(String, nullable=True)  # SHA-256 hash for integrity

    # Attachment metadata
    attachment_type = Column(String, nullable=False)  # 'image' or 'document'
    document_type = Column(String, nullable=True)  # For documents: statement, supporting_doc, etc.
    description = Column(Text, nullable=True)  # User-provided description

    # Display and organization
    display_order = Column(Integer, default=0, nullable=False)  # Order for display

    # Upload tracking
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_ip = Column(String, nullable=True)  # IP address of uploader

    # Status
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete support

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    statement = relationship("BankStatement", back_populates="attachments")
    uploader = relationship("User")

class AIChatHistory(Base):
    __tablename__ = "ai_chat_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(Integer, nullable=True)  # If multitenant
    message = Column(Text, nullable=False)
    sender = Column(String, nullable=False)  # 'user' or 'ai'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class RawEmail(Base):
    __tablename__ = "raw_emails"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(Integer, index=True, nullable=True)  # IMAP UID for sync
    message_id = Column(String, index=True, nullable=True)  # IMAP Message-ID
    subject = Column(String, nullable=True)  # Temporary staging, no encryption needed
    sender = Column(String, nullable=True)  # Temporary staging, no encryption needed
    recipient = Column(String, nullable=True)  # Temporary staging, no encryption needed
    date = Column(DateTime(timezone=True), nullable=True)

    # Raw content storage
    raw_content = Column(Text, nullable=True)  # Store full raw email content
    content_type = Column(String, nullable=True)

    # Processing status
    status = Column(String, default="pending", index=True, nullable=False)  # pending, processing, processed, failed, ignored
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    # Links
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True), nullable=True)

# --- Reporting Module Models ---

class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    report_type = Column(String, nullable=False)  # client, invoice, payment, expense, statement
    filters = Column(JSON, nullable=True)  # Stored filter configuration
    columns = Column(JSON, nullable=True)  # Selected columns for the report
    formatting = Column(JSON, nullable=True)  # Formatting preferences
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_shared = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User")
    scheduled_reports = relationship("ScheduledReport", back_populates="template", cascade="all, delete-orphan")
    report_history = relationship("ReportHistory", back_populates="template")


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("report_templates.id", ondelete="CASCADE"), nullable=False)
    schedule_type = Column(String, nullable=False)  # daily, weekly, monthly, yearly, cron
    schedule_config = Column(JSON, nullable=False)  # Cron expression or schedule configuration
    recipients = Column(JSON, nullable=False)  # List of email addresses
    is_active = Column(Boolean, default=True, nullable=False)
    last_run = Column(DateTime(timezone=True), nullable=True)
    next_run = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    template = relationship("ReportTemplate", back_populates="scheduled_reports")


class ReportHistory(Base):
    __tablename__ = "report_history"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("report_templates.id"), nullable=True)  # Nullable for ad-hoc reports
    report_type = Column(String, nullable=False)  # client, invoice, payment, expense, statement
    parameters = Column(JSON, nullable=False)  # Report generation parameters and filters
    file_path = Column(String, nullable=True)  # Path to generated report file
    status = Column(String, nullable=False, default="pending")  # pending, generating, completed, failed
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    error_message = Column(Text, nullable=True)  # Error details if generation failed

    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)  # When the report file should be cleaned up

    # Relationships
    template = relationship("ReportTemplate", back_populates="report_history")
    user = relationship("User")


# --- Inventory Management Models ---

class InventoryCategory(Base):
    __tablename__ = "inventory_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    color = Column(String, nullable=True)  # For UI display (hex color code)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    items = relationship("InventoryItem", back_populates="category", cascade="all, delete-orphan")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    sku = Column(String, nullable=True, unique=True, index=True)  # Stock Keeping Unit
    category_id = Column(Integer, ForeignKey("inventory_categories.id"), nullable=True)

    # Pricing
    unit_price = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=True)  # Cost to purchase/acquire
    currency = Column(String, default="USD", nullable=False)

    # Stock tracking (optional - items can exist without stock tracking)
    track_stock = Column(Boolean, default=False, nullable=False)
    current_stock = Column(Float, default=0.0, nullable=False)
    minimum_stock = Column(Float, default=0.0, nullable=False)
    unit_of_measure = Column(String, default="each", nullable=False)  # each, kg, lb, liters, etc.

    # Item type and status
    item_type = Column(String, default="product", nullable=False)  # product, material, service
    is_active = Column(Boolean, default=True, nullable=False)

    # Barcode support
    barcode = Column(String, nullable=True, unique=True, index=True)  # Barcode value
    barcode_type = Column(String, nullable=True)  # UPC, EAN, CODE128, QR, etc.
    barcode_format = Column(String, nullable=True)  # 1D, 2D, etc.

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    category = relationship("InventoryCategory", back_populates="items")
    stock_movements = relationship("StockMovement", back_populates="item", cascade="all, delete-orphan")
    invoice_items = relationship("InvoiceItem", back_populates="inventory_item")
    inventory_levels = relationship("InventoryLevel", back_populates="item", cascade="all, delete-orphan")
    attachments = relationship("ItemAttachment", back_populates="item", cascade="all, delete-orphan")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=True)  # Can be null for legacy movements

    # Movement details
    movement_type = Column(String, nullable=False)  # purchase, sale, adjustment, usage, return, transfer
    quantity = Column(Float, nullable=False)  # Positive for increases, negative for decreases
    unit_cost = Column(Float, nullable=True)  # Cost per unit for purchases

    # Transfer specific fields
    from_warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    to_warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)

    # Reference information for tracking source
    reference_type = Column(String, nullable=True)  # invoice, expense, manual, system, transfer
    reference_id = Column(Integer, nullable=True)  # ID of the related record
    notes = Column(Text, nullable=True)  # Additional context for the movement

    # User and timestamp (for audit trail)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    movement_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    item = relationship("InventoryItem", back_populates="stock_movements")
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    from_warehouse = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse = relationship("Warehouse", foreign_keys=[to_warehouse_id])
    user = relationship("User")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False, unique=True, index=True)  # Short code like WH001
    description = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Manager/Responsible person
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    manager = relationship("User")

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    inventory_levels = relationship("InventoryLevel", back_populates="warehouse", cascade="all, delete-orphan")


class InventoryLevel(Base):
    __tablename__ = "inventory_levels"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)

    # Stock levels
    current_stock = Column(Float, default=0.0, nullable=False)
    minimum_stock = Column(Float, default=0.0, nullable=False)
    maximum_stock = Column(Float, nullable=True)  # Optional maximum capacity

    # Location within warehouse (aisle, shelf, bin)
    location_code = Column(String, nullable=True)  # e.g., "A-01-05" for Aisle 1, Shelf 1, Bin 5

    # Last inventory count
    last_count_date = Column(DateTime(timezone=True), nullable=True)
    last_count_quantity = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    item = relationship("InventoryItem", back_populates="inventory_levels")
    warehouse = relationship("Warehouse", back_populates="inventory_levels")

    # Unique constraint to prevent duplicate item-warehouse combinations
    __table_args__ = (
        UniqueConstraint('item_id', 'warehouse_id', name='unique_item_warehouse'),
    )


class ItemAttachment(Base):
    __tablename__ = "item_attachments"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)

    # File information
    filename = Column(String, nullable=False)  # Original filename
    stored_filename = Column(String, nullable=False)  # Stored filename (usually UUID-based)
    file_path = Column(String, nullable=False)  # Full path to stored file
    file_size = Column(Integer, nullable=False)  # File size in bytes
    content_type = Column(String, nullable=True)  # MIME type
    file_hash = Column(String, nullable=True)  # SHA-256 hash for integrity

    # Attachment metadata
    attachment_type = Column(String, nullable=False)  # 'image' or 'document'
    document_type = Column(String, nullable=True)  # For documents: manual, certificate, warranty, etc.
    description = Column(Text, nullable=True)  # User-provided description
    alt_text = Column(String, nullable=True)  # Alt text for images (accessibility)

    # Display and organization
    is_primary = Column(Boolean, default=False, nullable=False)  # Primary image for item
    display_order = Column(Integer, default=0, nullable=False)  # Order for display

    # Image-specific fields
    image_width = Column(Integer, nullable=True)  # Original image width
    image_height = Column(Integer, nullable=True)  # Original image height
    has_thumbnail = Column(Boolean, default=False, nullable=False)  # Whether thumbnails exist
    thumbnail_path = Column(String, nullable=True)  # Path to thumbnail image

    # Upload tracking
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_ip = Column(String, nullable=True)  # IP address of uploader

    # Status
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete support

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    item = relationship("InventoryItem", back_populates="attachments")
    uploader = relationship("User")


class InvoiceAttachment(Base):
    __tablename__ = "invoice_attachments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)

    # File information
    filename = Column(String, nullable=False)  # Original filename
    stored_filename = Column(String, nullable=False)  # Stored filename (usually UUID-based)
    file_path = Column(String, nullable=False)  # Full path to stored file
    file_size = Column(Integer, nullable=False)  # File size in bytes
    content_type = Column(String, nullable=True)  # MIME type
    file_hash = Column(String, nullable=True)  # SHA-256 hash for integrity

    # Attachment metadata
    attachment_type = Column(String, nullable=False)  # 'image' or 'document'
    document_type = Column(String, nullable=True)  # For documents: receipt, contract, etc.
    description = Column(Text, nullable=True)  # User-provided description

    # Display and organization
    display_order = Column(Integer, default=0, nullable=False)  # Order for display

    # Upload tracking
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_ip = Column(String, nullable=True)  # IP address of uploader

    # Status
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete support

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    invoice = relationship("Invoice", back_populates="attachments")
    uploader = relationship("User")


class InvoiceProcessingTask(Base):
    """Track async invoice PDF processing tasks"""
    __tablename__ = "invoice_processing_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, nullable=False, index=True)  # UUID for tracking

    # File information
    file_path = Column(String, nullable=False)
    filename = Column(String, nullable=False)

    # Processing status
    status = Column(String, nullable=False, default="queued")  # queued, processing, completed, failed
    error_message = Column(Text, nullable=True)

    # Result data (JSON)
    result_data = Column(JSON, nullable=True)  # Extracted invoice data

    # User tracking
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")

# --- Expense Approval Workflow Models ---

class ExpenseApproval(Base):
    __tablename__ = "expense_approvals"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approval_rule_id = Column(Integer, ForeignKey("approval_rules.id"), nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending, approved, rejected
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    approval_level = Column(Integer, nullable=False, default=1)
    is_current_level = Column(Boolean, nullable=False, default=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # User who approved
    rejected_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # User who rejected

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    expense = relationship("Expense")
    approver = relationship("User", foreign_keys=[approver_id])
    approval_rule = relationship("ApprovalRule")
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])
    rejected_by = relationship("User", foreign_keys=[rejected_by_user_id])


class InvoiceApproval(Base):
    __tablename__ = "invoice_approvals"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approval_rule_id = Column(Integer, ForeignKey("approval_rules.id"), nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending, approved, rejected
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    approval_level = Column(Integer, nullable=False, default=1)
    is_current_level = Column(Boolean, nullable=False, default=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # User who approved
    rejected_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # User who rejected

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    invoice = relationship("Invoice")
    approver = relationship("User", foreign_keys=[approver_id])
    approval_rule = relationship("ApprovalRule")
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])
    rejected_by = relationship("User", foreign_keys=[rejected_by_user_id])


class ApprovalRule(Base):
    __tablename__ = "approval_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    min_amount = Column(Float, nullable=True)
    max_amount = Column(Float, nullable=True)
    category_filter = Column(String, nullable=True)  # JSON array of categories
    currency = Column(String, default="USD", nullable=False)
    approval_level = Column(Integer, nullable=False, default=1)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    auto_approve_below = Column(Float, nullable=True)  # Auto-approve below this amount

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    approver = relationship("User", foreign_keys=[approver_id])
    expense_approvals = relationship("ExpenseApproval", back_populates="approval_rule")


class ApprovalDelegate(Base):
    __tablename__ = "approval_delegates"

    id = Column(Integer, primary_key=True, index=True)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    delegate_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    approver = relationship("User", foreign_keys=[approver_id])
    delegate = relationship("User", foreign_keys=[delegate_id])

    # Ensure unique active delegation per approver
    __table_args__ = (
        UniqueConstraint('approver_id', 'delegate_id', 'start_date', name='unique_active_delegation'),
    )


# --- Reminder System Models ---

class RecurrencePattern(str, PyEnum):
    """Recurrence pattern enumeration"""
    NONE = "none"           # One-time reminder
    DAILY = "daily"         # Every day
    WEEKLY = "weekly"       # Every week
    MONTHLY = "monthly"     # Every month
    YEARLY = "yearly"       # Every year


class ReminderStatus(str, PyEnum):
    """Reminder status enumeration"""
    PENDING = "pending"     # Not yet due or completed
    COMPLETED = "completed" # Marked as done
    SNOOZED = "snoozed"    # Temporarily postponed
    CANCELLED = "cancelled" # No longer needed


class ReminderPriority(str, PyEnum):
    """Reminder priority enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Scheduling information
    due_date = Column(DateTime(timezone=True), nullable=False)
    next_due_date = Column(DateTime(timezone=True), nullable=True)  # For recurring reminders
    recurrence_pattern = Column(Enum(RecurrencePattern), default=RecurrencePattern.NONE, nullable=False)
    recurrence_interval = Column(Integer, default=1, nullable=False)  # Every N days/weeks/months/years
    recurrence_end_date = Column(DateTime(timezone=True), nullable=True)  # When to stop recurring

    # Status and priority
    status = Column(Enum(ReminderStatus), default=ReminderStatus.PENDING, nullable=False)
    priority = Column(Enum(ReminderPriority), default=ReminderPriority.MEDIUM, nullable=False)

    # Ordering and Pinning
    position = Column(Integer, default=0, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)

    # Assignment
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Snooze functionality
    snoozed_until = Column(DateTime(timezone=True), nullable=True)
    snooze_count = Column(Integer, default=0, nullable=False)

    # Completion tracking
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completion_notes = Column(Text, nullable=True)

    # Metadata
    tags = Column(JSON, nullable=True)  # Array of tags for categorization
    extra_metadata = Column(JSON, nullable=True)  # Additional flexible data

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    completed_by = relationship("User", foreign_keys=[completed_by_id])
    deleted_by = relationship("User", foreign_keys=[deleted_by_id])
    notifications = relationship("ReminderNotification", back_populates="reminder", cascade="all, delete-orphan")


class ReminderNotification(Base):
    __tablename__ = "reminder_notifications"

    id = Column(Integer, primary_key=True, index=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id", ondelete="CASCADE"), nullable=True)  # Nullable for system notifications
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Notification details
    notification_type = Column(String, nullable=False)  # 'due', 'overdue', 'reminder', 'assigned'
    channel = Column(String, nullable=False)  # 'email', 'in_app', 'both'

    # Scheduling
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    is_sent = Column(Boolean, default=False, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)  # For in-app notifications
    send_attempts = Column(Integer, default=0, nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # Content
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    reminder = relationship("Reminder", back_populates="notifications")
    user = relationship("User")

    # Ensure we don't send duplicate notifications
    __table_args__ = (
        UniqueConstraint('reminder_id', 'user_id', 'notification_type', 'scheduled_for',
                        name='unique_reminder_notification'),
    )


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    key = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    trigger_type = Column(String, nullable=False, index=True)
    conditions = Column(JSON, nullable=True)
    actions = Column(JSON, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    execution_logs = relationship("WorkflowExecutionLog", back_populates="workflow", cascade="all, delete-orphan")


class WorkflowExecutionLog(Base):
    __tablename__ = "workflow_execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_key = Column(String, nullable=False)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="success")
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    workflow = relationship("WorkflowDefinition", back_populates="execution_logs")

    __table_args__ = (
        UniqueConstraint('workflow_id', 'event_key', name='uq_workflow_execution_event'),
    )


# --- Cloud Storage Models ---

class CloudStorageConfiguration(Base):
    """
    Model for storing cloud storage provider configurations per tenant.
    Supports multiple providers with encrypted credentials.
    """
    __tablename__ = "cloud_storage_configurations"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database
    provider = Column(String(50), nullable=False, index=True)  # aws_s3, azure_blob, gcp_storage, local
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)

    # Encrypted configuration JSON containing provider-specific settings
    encrypted_configuration = Column(String, nullable=False)  # Use plain string instead of encrypted column

    # Configuration metadata
    configuration_version = Column(Integer, default=1, nullable=False)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    test_status = Column(String(20), nullable=True)  # success, failed, pending
    test_error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<CloudStorageConfiguration(id={self.id}, provider='{self.provider}', enabled={self.is_enabled})>"


class StorageOperationLog(Base):
    """
    Log of storage operations for audit and monitoring purposes.
    Tracks all file operations across different storage providers.
    """
    __tablename__ = "storage_operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database

    # Operation details
    operation_type = Column(String(20), nullable=False, index=True)  # upload, download, delete, migrate
    file_key = Column(String(500), nullable=False, index=True)  # Storage key/path
    original_filename = Column(String(255), nullable=True)

    # Provider and result information
    provider = Column(String(50), nullable=False, index=True)  # aws_s3, azure_blob, gcp_storage, local
    success = Column(Boolean, nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    # File metadata
    file_size = Column(Integer, nullable=True)  # File size in bytes
    content_type = Column(String(100), nullable=True)
    checksum = Column(String(64), nullable=True)  # SHA-256 checksum for integrity

    # Performance metrics
    duration_ms = Column(Integer, nullable=True)  # Operation duration in milliseconds
    retry_count = Column(Integer, default=0, nullable=False)

    # User and context information
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # User who initiated the operation
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6 address
    user_agent = Column(String(500), nullable=True)

    # Additional metadata
    operation_metadata = Column(JSON, nullable=True)  # Additional operation-specific data

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<StorageOperationLog(id={self.id}, operation='{self.operation_type}', provider='{self.provider}', success={self.success})>"


# --- Batch File Processing and Export Models ---

class BatchProcessingJob(Base):
    """Tracks batch file processing jobs for external API clients"""
    __tablename__ = "batch_processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    tenant_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    api_client_id = Column(String(100), nullable=False)  # Reference to API client

    # Job configuration
    document_types = Column(JSON, nullable=True)  # ["invoice", "expense", "statement"]
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)  # Client ID for invoice documents
    total_files = Column(Integer, nullable=False)
    export_destination_type = Column(String(50), nullable=True)  # s3, azure, gcs, google_drive
    export_destination_config_id = Column(Integer, ForeignKey("export_destination_configs.id"), nullable=True)
    custom_fields = Column(JSON, nullable=True)  # Optional field selection
    webhook_url = Column(String(500), nullable=True)  # Optional webhook for completion notification

    # Status tracking
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, processing, completed, failed, partial_failure
    processed_files = Column(Integer, default=0, nullable=False)
    successful_files = Column(Integer, default=0, nullable=False)
    failed_files = Column(Integer, default=0, nullable=False)
    progress_percentage = Column(Float, default=0.0, nullable=False)

    # Export results
    export_file_url = Column(String(2000), nullable=True)
    export_file_key = Column(String(500), nullable=True)
    export_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    files = relationship("BatchFileProcessing", back_populates="job", cascade="all, delete-orphan")
    export_destination = relationship("ExportDestinationConfig")

    def __repr__(self):
        return f"<BatchProcessingJob(job_id='{self.job_id}', status='{self.status}', total_files={self.total_files})>"


class BatchFileProcessing(Base):
    """Tracks individual file processing within a batch job"""
    __tablename__ = "batch_file_processing"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), ForeignKey("batch_processing_jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)

    # File information
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=True)
    file_path = Column(String(1000), nullable=True)
    cloud_file_url = Column(String(1000), nullable=True)
    file_size = Column(Integer, nullable=True)
    document_type = Column(String(50), nullable=True, index=True)  # invoice, expense, statement

    # Processing status
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, processing, completed, failed
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    # Extracted data (stored as JSON for flexibility)
    extracted_data = Column(JSON, nullable=True)  # Vendor, amount, date, line items, etc.

    # Created record IDs (links to actual Invoice/Expense/BankStatement records)
    created_invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    created_expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, index=True)
    created_statement_id = Column(Integer, ForeignKey("bank_statements.id", ondelete="SET NULL"), nullable=True, index=True)

    # Kafka tracking
    kafka_topic = Column(String(100), nullable=True)
    kafka_message_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    job = relationship("BatchProcessingJob", back_populates="files")
    created_invoice = relationship("Invoice", foreign_keys=[created_invoice_id])
    created_expense = relationship("Expense", foreign_keys=[created_expense_id])
    created_statement = relationship("BankStatement", foreign_keys=[created_statement_id])

    def __repr__(self):
        return f"<BatchFileProcessing(id={self.id}, job_id='{self.job_id}', filename='{self.original_filename}', status='{self.status}')>"


class ExportDestinationConfig(Base):
    """Stores export destination configurations per tenant"""
    __tablename__ = "export_destination_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)

    # Destination details
    name = Column(String(200), nullable=False)  # User-friendly name
    destination_type = Column(String(50), nullable=False)  # s3, azure, gcs, google_drive
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    # Encrypted credentials (using tenant encryption key)
    encrypted_credentials = Column(Text, nullable=True)  # Encrypted JSON blob

    # Destination-specific configuration
    config = Column(JSON, nullable=True)  # Bucket name, container, folder ID, path prefix, etc.

    # Connection testing
    last_test_at = Column(DateTime(timezone=True), nullable=True)
    last_test_success = Column(Boolean, nullable=True)
    last_test_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    batch_jobs = relationship("BatchProcessingJob", back_populates="export_destination")

    def __repr__(self):
        return f"<ExportDestinationConfig(id={self.id}, name='{self.name}', type='{self.destination_type}', active={self.is_active})>"


# --- Anomaly Detection Models ---

class Anomaly(Base):
    """
    Model for tracking detected anomalies and high-risk items.
    """
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True)  # expense, invoice, bank_transaction
    entity_id = Column(Integer, nullable=False, index=True)

    # Risk assessment
    risk_score = Column(Float, default=0.0, nullable=False)
    risk_level = Column(String(20), nullable=False, default="low")  # low, medium, high, critical

    # Description and evidence
    reason = Column(Text, nullable=False)
    rule_id = Column(String(100), nullable=True)  # ID of the rule that triggered it
    details = Column(JSON, nullable=True)  # JSON blob with evidence/metadata

    # Status
    is_dismissed = Column(Boolean, default=False, nullable=False)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    dismiss_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    dismissed_by = relationship("User", foreign_keys=[dismissed_by_id])

    def __repr__(self):
        return f"<Anomaly(id={self.id}, entity='{self.entity_type}:{self.entity_id}', risk='{self.risk_level}')>"


# --- License Management Models ---
# NOTE: InstallationInfo and LicenseValidationLog are stored in tenant databases
# Each tenant has its own license configuration and validation logs

class InstallationInfo(Base):
    """
    License and installation information for a tenant.
    Each tenant has exactly one InstallationInfo record.
    """
    __tablename__ = "installation_info"

    id = Column(Integer, primary_key=True, index=True)
    installation_id = Column(String(36), unique=True, nullable=False, index=True)
    custom_installation_id = Column(String(36), unique=True, nullable=True) # User-generated custom ID (max 1 per tenant)
    original_installation_id = Column(String(36), nullable=True) # Original global ID for switching back

    # License status: invalid, personal, trial, active, expired, suspended
    license_status = Column(String(20), default="invalid", nullable=False)
    is_licensed = Column(Boolean, default=False, nullable=False)

    # Usage type selection: personal (free) or business (trial/paid)
    usage_type = Column(String(20), nullable=True)  # personal or business
    usage_type_selected_at = Column(DateTime(timezone=True), nullable=True)

    # Trial management
    trial_start_date = Column(DateTime(timezone=True), nullable=True)
    trial_end_date = Column(DateTime(timezone=True), nullable=True)
    trial_extended_until = Column(DateTime(timezone=True), nullable=True)  # For grace period extensions

    # License key storage
    license_key = Column(Text, nullable=True)  # Encrypted in practice
    license_activated_at = Column(DateTime(timezone=True), nullable=True)
    license_expires_at = Column(DateTime(timezone=True), nullable=True)
    license_scope = Column(String(20), nullable=True)  # 'local' or 'global'

    # Feature tracking
    max_tenants = Column(Integer, nullable=True)  # From license
    features = Column(JSON, nullable=True)  # List of enabled features from license
    licensed_features = Column(JSON, nullable=True)  # List of licensed features (from activated license)

    # Customer information from license
    customer_email = Column(String, nullable=True)  # Email from license
    customer_name = Column(String, nullable=True)  # Name from license
    organization_name = Column(String, nullable=True)  # Organization name from license

    # Validation cache for performance
    last_validation_at = Column(DateTime(timezone=True), nullable=True)  # When license was last validated
    last_validation_result = Column(Boolean, nullable=True)  # Result of last validation (True/False)
    validation_cache_expires_at = Column(DateTime(timezone=True), nullable=True)  # When cache expires

    # Audit fields
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class LicenseValidationLog(Base):
    """
    Audit log for license validation attempts and changes.
    Tracks all license-related operations for compliance and debugging.
    """
    __tablename__ = "license_validation_logs"

    id = Column(Integer, primary_key=True, index=True)
    installation_id = Column(Integer, ForeignKey("installation_info.id", ondelete="CASCADE"), nullable=False, index=True)

    # Validation details
    validation_type = Column(String(50), nullable=False, index=True)  # activation, trial_start, usage_type_selected, etc.
    validation_result = Column(String(20), nullable=False)  # success, failed

    # License information
    license_key_hash = Column(String(64), nullable=True)  # SHA-256 hash for privacy
    features_validated = Column(JSON, nullable=True)  # Features that were validated
    expiration_date = Column(DateTime(timezone=True), nullable=True)
    max_tenants_validated = Column(Integer, nullable=True)

    # Error tracking
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Request context
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    installation = relationship("InstallationInfo")


# Import split-off models to ensure they are registered with SQLAlchemy
# This prevents "failed to locate a name" errors during mapper initialization
try:
    from core.models.gamification import UserGamificationProfile  # and others as needed
    # Investment plugin models
    from plugins.investments.models import (
        InvestmentPortfolio,
        InvestmentHolding,
        InvestmentTransaction,
        FileAttachment
    )
except ImportError:
    pass
