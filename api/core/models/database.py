from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from contextvars import ContextVar
import os
import logging
from fastapi import HTTPException
from pydantic import ValidationError
from fastapi.exceptions import RequestValidationError
from core.constants.error_codes import TENANT_CONTEXT_REQUIRED

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

SQLALCHEMY_DATABASE_URL = DATABASE_URL

# Context variable to store current tenant ID
current_tenant_id: ContextVar[int] = ContextVar('current_tenant_id', default=None)

# Configure engine based on database type
if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
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
    # Use a default SQLite URL if DATABASE_URL is None
    sqlite_url = DATABASE_URL or "sqlite:///./test.db"
    engine = create_engine(
        sqlite_url, 
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
        logger.error("This usually indicates a session expiry or missing authentication token")
        raise HTTPException(
            status_code=401,
            detail=TENANT_CONTEXT_REQUIRED
        )
    
    # Import here to avoid circular imports
    from core.services.tenant_database_manager import tenant_db_manager
    
    db = None
    try:
        # Try to get tenant session
        SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
        db = SessionLocal_tenant()
        yield db
        
    except Exception as e:
        import re
        from sqlalchemy.exc import StatementError, DataError, IntegrityError, OperationalError
        
        # Rollback any failed transaction before closing
        if db is not None:
            try:
                db.rollback()
                db.close()
            except Exception:
                pass
            db = None
        
        # If it's an HTTPException, it's an application-level error, not a database connection issue
        if isinstance(e, HTTPException):
            logger.debug(f"HTTPException raised in tenant database context: {e.status_code} - {e.detail}")
            raise
        
        logger.error(f"Failed to connect to tenant database for tenant {tenant_id}: {e}")
        # Robust safeguard: Only attempt to create tenant DB for connection/operational errors, not validation errors
        if isinstance(e, (ValidationError, RequestValidationError, StatementError, DataError, IntegrityError)):
            logger.error(f"Validation or schema error encountered, not attempting to recreate tenant DB: {e}")
            raise
        
        # Don't recreate database for HTTP errors (like 404, 400, etc.)
        if isinstance(e, HTTPException):
            logger.error(f"HTTP exception encountered, not attempting to recreate tenant DB: {e.status_code} - {e.detail}")
            raise
        
        # Regex to catch any error message that hints at validation/schema issues
        error_str = str(e).lower()
        if re.search(r"(validation|pydantic|schema|statement|integrity|data) error|field required|missing|unprocessable entity|404|not found|bad request", error_str):
            logger.error(f"Validation-related or HTTP error (regex caught), not attempting to recreate tenant DB: {e}")
            raise
            
        # Only recreate database for actual database connection errors
        from sqlalchemy.exc import OperationalError, DatabaseError
        if not isinstance(e, (OperationalError, DatabaseError)):
            logger.error(f"Non-database error encountered, not attempting to recreate tenant DB: {type(e).__name__}: {e}")
            raise
            
        # Try to create the tenant database if it doesn't exist (for connection errors only)
        master_db = None
        try:
            logger.info(f"Attempting to create missing tenant database for tenant {tenant_id}")
            
            # Get tenant info from master database
            master_db = SessionLocal()
            from core.models.models import Tenant
            tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
            
            if tenant:
                success = tenant_db_manager.create_tenant_database(tenant_id, tenant.name)
                if success:
                    logger.info(f"Successfully created tenant database for tenant {tenant_id}")
                    # Try to get the session again after creation
                    SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
                    db = SessionLocal_tenant()
                    yield db
                    return
                else:
                    logger.error(f"Failed to create tenant database for tenant {tenant_id}")
            else:
                logger.error(f"Tenant {tenant_id} not found in master database")
                
        except Exception as create_error:
            logger.error(f"Error creating tenant database for tenant {tenant_id}: {create_error}")
        finally:
            if master_db is not None:
                try:
                    master_db.close()
                except Exception:
                    pass
        
        # If all fails, raise the original error
        raise HTTPException(
            status_code=500,
            detail=f"Unable to connect to tenant database. Please contact support."
        )
        
    finally:
        # Ensure database session is always closed
        if db is not None:
            try:
                db.rollback()
                db.close()
            except Exception:
                pass

def set_tenant_context(tenant_id: int):
    """Set the current tenant context"""
    current_tenant_id.set(tenant_id)

def clear_tenant_context():
    """Clear the current tenant context"""
    current_tenant_id.set(None)

def get_tenant_context() -> int:
    """Get the current tenant context"""
    return current_tenant_id.get() 