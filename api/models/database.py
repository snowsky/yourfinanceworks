from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextvars import ContextVar
import os
import logging

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./invoice_app.db")

SQLALCHEMY_DATABASE_URL = DATABASE_URL

# Context variable to store current tenant ID
current_tenant_id: ContextVar[int] = ContextVar('current_tenant_id', default=None)

# Configure engine based on database type
if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL configuration - This is the master database
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Enable connection health checks
        pool_recycle=300,    # Recycle connections after 5 minutes
        pool_size=10,        # Maximum number of connections in the pool
        max_overflow=20      # Maximum number of connections that can be created beyond pool_size
    )
else:
    # SQLite configuration - This is the master database
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Master database dependency (for tenant management)
def get_master_db():
    """Get database session for master database (tenant management)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Default database dependency - routes to tenant database if context exists
def get_db():
    """
    Get database session - routes to tenant database if context exists,
    otherwise uses master database for backward compatibility
    """
    tenant_id = current_tenant_id.get()
    
    if tenant_id is None:
        # Fallback to master database for backward compatibility
        logger.warning("No tenant context found, using master database")
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        # Import here to avoid circular imports
        from services.tenant_database_manager import tenant_db_manager
        
        SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
        db = SessionLocal_tenant()
        try:
            yield db
        finally:
            db.close()

# Utility function to set tenant context
def set_tenant_context(tenant_id: int):
    """Set the current tenant context"""
    current_tenant_id.set(tenant_id)
    logger.debug(f"Set tenant context to: {tenant_id}")

# Utility function to get current tenant context
def get_tenant_context() -> int:
    """Get the current tenant context"""
    return current_tenant_id.get()

# Utility function to clear tenant context
def clear_tenant_context():
    """Clear the current tenant context"""
    current_tenant_id.set(None)
    logger.debug("Cleared tenant context") 