from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Table, DateTime, Boolean, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    subdomain = Column(String, unique=True, nullable=True, index=True)  # Optional subdomain
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Company details
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    clients = relationship("Client", back_populates="tenant")
    invoices = relationship("Invoice", back_populates="tenant")
    payments = relationship("Payment", back_populates="tenant")
    settings = relationship("Settings", back_populates="tenant")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Tenant relationship
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    # User role within tenant
    role = Column(String, default="user")  # admin, user, viewer
    
    # Additional user fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)  # For Google SSO
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="clients")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, index=True, nullable=False)  # Make number unique
    amount = Column(Float, nullable=False)
    due_date = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="draft")
    notes = Column(String, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    is_recurring = Column(Boolean, default=False)
    recurring_frequency = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="invoices")
    client = relationship("Client", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    amount = Column(Float, nullable=False)
    payment_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    payment_method = Column(String, nullable=False, default="system")
    reference_number = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="payments")
    invoice = relationship("Invoice", back_populates="payments")

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    key = Column(String, index=True)  # Removed unique constraint for multi-tenancy
    value = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="settings") 