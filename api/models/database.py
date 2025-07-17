from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextvars import ContextVar
import os
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

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
    otherwise raises an error for tenant-specific endpoints
    """
    tenant_id = current_tenant_id.get()
    
    if tenant_id is None:
        # Instead of falling back, raise an error
        logger.error("No tenant context found, refusing to use master database for tenant-specific endpoint")
        raise HTTPException(
            status_code=400,
            detail="Tenant context required for this operation. Please ensure you are sending the correct tenant information."
        )
    else:
        # Import here to avoid circular imports
        from services.tenant_database_manager import tenant_db_manager
        
        try:
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db = SessionLocal_tenant()
            try:
                yield db
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to connect to tenant database for tenant {tenant_id}: {e}")
            
            # Try to create the tenant database if it doesn't exist
            try:
                logger.info(f"Attempting to create missing tenant database for tenant {tenant_id}")
                
                # Get tenant info from master database
                master_db = SessionLocal()
                try:
                    from models.models import Tenant
                    tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
                    
                    if tenant:
                        success = tenant_db_manager.create_tenant_database(tenant_id, tenant.name)
                        if success:
                            logger.info(f"Successfully created tenant database for tenant {tenant_id}")
                            # Try to get the session again after creation
                            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
                            db = SessionLocal_tenant()
                            try:
                                yield db
                            finally:
                                db.close()
                            return
                        else:
                            logger.error(f"Failed to create tenant database for tenant {tenant_id}")
                    else:
                        logger.error(f"Tenant {tenant_id} not found in master database")
                        
                finally:
                    master_db.close()
                    
            except Exception as create_error:
                logger.error(f"Error creating tenant database for tenant {tenant_id}: {create_error}")
            
            # If all fails, raise the original error
            raise HTTPException(
                status_code=500,
                detail=f"Unable to connect to tenant database. Please contact support."
            )

def set_tenant_context(tenant_id: int):
    """Set the current tenant context"""
    current_tenant_id.set(tenant_id)

def clear_tenant_context():
    """Clear the current tenant context"""
    current_tenant_id.set(None)

def get_tenant_context() -> int:
    """Get the current tenant context"""
    return current_tenant_id.get() 