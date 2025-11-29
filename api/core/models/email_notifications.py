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
    
    # Payment operation notifications
    payment_created = Column(Boolean, default=True)
    payment_updated = Column(Boolean, default=False)
    payment_deleted = Column(Boolean, default=True)
    
    # Settings operation notifications
    settings_updated = Column(Boolean, default=False)
    
    # Organization join request notifications
    organization_join_request_created = Column(Boolean, default=True)  # Admin gets notified of new requests
    
    # Reminder notifications
    reminder_due = Column(Boolean, default=True)  # Reminder is due
    reminder_overdue = Column(Boolean, default=True)  # Reminder is overdue
    reminder_upcoming = Column(Boolean, default=True)  # Reminder is due soon
    reminder_assigned = Column(Boolean, default=True)  # Reminder assigned to user
    reminder_completed = Column(Boolean, default=False)  # Reminder completed by someone else
    
    # Reminder notification preferences
    reminder_advance_days = Column(Integer, default=1)  # How many days in advance to send upcoming notifications
    reminder_notification_frequency = Column(String, default="immediate")  # immediate, daily_digest
    
    # Additional notification preferences
    notification_email = Column(String, nullable=True)  # Override email for notifications
    daily_summary = Column(Boolean, default=False)
    weekly_summary = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User")