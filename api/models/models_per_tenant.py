from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime, Boolean, JSON, Text, UniqueConstraint, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base
from enum import Enum as PyEnum

# Import encrypted column types for transparent encryption
from utils.column_encryptor import EncryptedColumn, EncryptedJSON

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

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database
    
    name = Column(EncryptedColumn(), index=True)  # Encrypted for privacy
    email = Column(EncryptedColumn(), unique=True, nullable=False, index=True)  # Encrypted for privacy
    phone = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    address = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    company = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    balance = Column(Float, default=0.0)  # Keep unencrypted for calculations
    paid_amount = Column(Float, default=0)  # Keep unencrypted for calculations
    preferred_currency = Column(String, nullable=True)  # Optional, fallback to tenant default
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships (no tenant relationship needed)
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    notes = relationship("ClientNote", back_populates="client", cascade="all, delete-orphan")

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
    status = Column(String, nullable=False, default="draft")
    notes = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    # No tenant_id needed since each tenant has its own database
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    is_recurring = Column(Boolean, default=False)
    recurring_frequency = Column(String, nullable=True)
    discount_type = Column(String, default="percentage", nullable=False)  # percentage or fixed
    discount_value = Column(Float, default=0.0, nullable=False)  # percentage or fixed amount
    subtotal = Column(Float, nullable=False)  # Amount before discount
    custom_fields = Column(EncryptedJSON(),nullable=True)  # Encrypted JSON for sensitive custom data
    show_discount_in_pdf = Column(Boolean, default=True, nullable=False)
    attachment_path = Column(String, nullable=True)  # Path to uploaded attachment file
    attachment_filename = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    
    # Soft delete fields for recycle bin functionality
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Track who deleted it
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships (no tenant relationship needed)
    client = relationship("Client", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    deleted_by_user = relationship("User", foreign_keys=[deleted_by])
    expenses = relationship("Expense", back_populates="invoice")
    attachments = relationship("InvoiceAttachment", back_populates="invoice", cascade="all, delete-orphan")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database
    
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
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

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    # No tenant_id needed since each tenant has its own database

    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    expense_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    category = Column(String, nullable=False)
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

    # Inventory purchase fields
    is_inventory_purchase = Column(Boolean, default=False, nullable=False)
    inventory_items = Column(EncryptedJSON(),nullable=True)  # Encrypted sensitive inventory data

    # Inventory consumption fields
    is_inventory_consumption = Column(Boolean, default=False, nullable=False)
    consumption_items = Column(EncryptedJSON(),nullable=True)  # Encrypted sensitive consumption data

    # OCR/AI analysis fields
    imported_from_attachment = Column(Boolean, default=False, nullable=False)
    analysis_status = Column(String, default="not_started", nullable=False)  # not_started|queued|processing|done|failed|cancelled
    analysis_result = Column(EncryptedJSON(),nullable=True)  # Encrypted sensitive analysis data
    analysis_error = Column(Text, nullable=True)  # Keep unencrypted for debugging
    manual_override = Column(Boolean, default=False, nullable=False)
    analysis_updated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User")
    invoice = relationship("Invoice", back_populates="expenses")
    approvals = relationship("ExpenseApproval", back_populates="expense", cascade="all, delete-orphan")

class ExpenseAttachment(Base):
    __tablename__ = "expense_attachments"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    expense = relationship("Expense")
    uploader = relationship("User")

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
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
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
    details = Column(EncryptedJSON(),nullable=True)  # Encrypted sensitive audit details
    ip_address = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    user_agent = Column(EncryptedColumn(), nullable=True)  # Encrypted for privacy
    status = Column(String, default="success", nullable=False)  # success, error, warning
    error_message = Column(String, nullable=True)  # Keep unencrypted for debugging
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

# --- Statements ---

class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False)

    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="processed", nullable=False)  # uploaded|processing|processed|failed
    extracted_count = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)
    labels = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    transactions = relationship("BankStatementTransaction", back_populates="statement", cascade="all, delete-orphan")


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
    # Optional link to an invoice created from this transaction (prevents duplicates)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    # Optional link to an expense created from this transaction (prevents duplicates)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    statement = relationship("BankStatement", back_populates="transactions")
    # Note: No explicit relationship to Invoice to avoid circular import in some tooling environments

class AIChatHistory(Base):
    __tablename__ = "ai_chat_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(Integer, nullable=True)  # If multitenant
    message = Column(Text, nullable=False)
    sender = Column(String, nullable=False)  # 'user' or 'ai'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class EmailNotificationSettings(Base):
    __tablename__ = "email_notification_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # User operation notifications
    user_created = Column(Boolean, default=False)
    user_updated = Column(Boolean, default=False)
    user_deleted = Column(Boolean, default=False)
    user_login = Column(Boolean, default=False)
    
    # Client operation notifications
    client_created = Column(Boolean, default=True)
    client_updated = Column(Boolean, default=False)
    client_deleted = Column(Boolean, default=True)
    
    # Invoice operation notifications
    invoice_created = Column(Boolean, default=True)
    invoice_updated = Column(Boolean, default=False)
    invoice_deleted = Column(Boolean, default=True)
    invoice_sent = Column(Boolean, default=True)
    invoice_paid = Column(Boolean, default=True)
    invoice_overdue = Column(Boolean, default=True)
    
    # Payment operation notifications
    payment_created = Column(Boolean, default=True)
    payment_updated = Column(Boolean, default=False)
    payment_deleted = Column(Boolean, default=True)
    
    # Settings operation notifications
    settings_updated = Column(Boolean, default=False)
    
    # Approval operation notifications
    expense_submitted_for_approval = Column(Boolean, default=True)
    expense_approved = Column(Boolean, default=True)
    expense_rejected = Column(Boolean, default=True)
    expense_level_approved = Column(Boolean, default=True)
    expense_fully_approved = Column(Boolean, default=True)
    expense_auto_approved = Column(Boolean, default=True)
    approval_reminder = Column(Boolean, default=True)
    approval_escalation = Column(Boolean, default=True)
    
    # Approval notification frequency preferences
    approval_notification_frequency = Column(String, default="immediate", nullable=False)  # immediate, daily_digest
    approval_reminder_frequency = Column(String, default="daily", nullable=False)  # daily, weekly, disabled
    
    # Approval notification channel preferences
    approval_notification_channels = Column(JSON, default=["email"], nullable=False)  # ["email", "in_app"] or ["email"] or ["in_app"]
    
    # Additional notification preferences
    notification_email = Column(String, nullable=True)  # Override email for notifications
    daily_summary = Column(Boolean, default=False)
    weekly_summary = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User")


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
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    expense = relationship("Expense")
    approver = relationship("User", foreign_keys=[approver_id])
    approval_rule = relationship("ApprovalRule")


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
    extra_metadata = Column("metadata", JSON, nullable=True)  # Additional flexible data
    
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
