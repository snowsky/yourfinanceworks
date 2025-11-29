#!/usr/bin/env python3
"""
Migration script to add invites table to master database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import os

# Import existing models to ensure foreign key relationships work
from core.models.models import Base, MasterUser, Tenant

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./master.db")

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

def create_invites_table():
    """Create the invites table"""
    try:
        # Create the table
        Base.metadata.create_all(bind=engine, tables=[Invite.__table__])
        print("✅ Invites table created successfully!")
        
        # Verify the table exists
        with engine.connect() as conn:
            result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invites'")
            if result.fetchone():
                print("✅ Invites table verified in database")
            else:
                print("❌ Invites table not found in database")
                
    except Exception as e:
        print(f"❌ Error creating invites table: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔄 Creating invites table...")
    success = create_invites_table()
    
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("💥 Migration failed!")
        sys.exit(1) 