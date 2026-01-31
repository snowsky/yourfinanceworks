from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from core.models.models_per_tenant import Base

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

    # Invoice Approval notifications (added from first version)
    invoice_submitted_for_approval = Column(Boolean, default=True)
    invoice_fully_approved = Column(Boolean, default=True)
    invoice_rejected = Column(Boolean, default=True)
    
    # Payment operation notifications
    payment_created = Column(Boolean, default=True)
    payment_updated = Column(Boolean, default=False)
    payment_deleted = Column(Boolean, default=True)

    # Expense operation notifications
    expense_created = Column(Boolean, default=True)
    expense_updated = Column(Boolean, default=False)
    expense_deleted = Column(Boolean, default=True)
    expense_approved = Column(Boolean, default=True)
    expense_rejected = Column(Boolean, default=True)
    expense_level_approved = Column(Boolean, default=True)
    expense_fully_approved = Column(Boolean, default=True)
    expense_auto_approved = Column(Boolean, default=True)
    expense_submitted = Column(Boolean, default=True)
    expense_submitted_for_approval = Column(Boolean, default=True)
    expense_imported = Column(Boolean, default=True)
    expense_analysis_completed = Column(Boolean, default=True)
    expense_analysis_failed = Column(Boolean, default=True)

    # Inventory operation notifications
    inventory_created = Column(Boolean, default=True)
    inventory_updated = Column(Boolean, default=False)
    inventory_deleted = Column(Boolean, default=True)
    inventory_low_stock = Column(Boolean, default=True)
    inventory_out_of_stock = Column(Boolean, default=True)
    inventory_stock_movement = Column(Boolean, default=False)
    inventory_category_created = Column(Boolean, default=False)
    inventory_category_updated = Column(Boolean, default=False)
    inventory_category_deleted = Column(Boolean, default=True)

    # Statement operation notifications
    statement_generated = Column(Boolean, default=True)
    statement_sent = Column(Boolean, default=True)
    statement_overdue = Column(Boolean, default=True)
    statement_uploaded = Column(Boolean, default=True)
    statement_processed = Column(Boolean, default=True)
    statement_processing_failed = Column(Boolean, default=True)
    statement_transaction_created = Column(Boolean, default=False)
    
    # Settings operation notifications
    settings_updated = Column(Boolean, default=False)
    
    # Organization join request notifications
    organization_join_request_created = Column(Boolean, default=True)  # Admin gets notified of new requests
    
    # Reminder notifications
    reminder_created = Column(Boolean, default=True)
    reminder_sent = Column(Boolean, default=True)
    reminder_due = Column(Boolean, default=True)
    reminder_overdue = Column(Boolean, default=True)
    reminder_upcoming = Column(Boolean, default=True)
    reminder_assigned = Column(Boolean, default=True)
    reminder_completed = Column(Boolean, default=False)
    
    # Reminder notification preferences
    reminder_advance_days = Column(Integer, default=1)
    reminder_notification_frequency = Column(String, default="immediate")
    
    # General Approval preferences
    approval_reminder = Column(Boolean, default=True)
    approval_escalation = Column(Boolean, default=True)
    approval_notification_frequency = Column(String, default="immediate", nullable=False)
    approval_reminder_frequency = Column(String, default="daily", nullable=False)
    approval_notification_channels = Column(JSON, default=["email"], nullable=False)
    
    # Additional notification preferences
    notification_email = Column(String, nullable=True)
    daily_summary = Column(Boolean, default=False)
    weekly_summary = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User")