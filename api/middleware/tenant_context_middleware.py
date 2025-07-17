import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import status
from models.database import set_tenant_context, clear_tenant_context, get_master_db
from models.models import MasterUser
from services.tenant_database_manager import tenant_db_manager
import jwt
import os

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"

# Function-based middleware for tenant context
async def tenant_context_middleware(request: Request, call_next):
    clear_tenant_context()
    logger.info(f"Request received: {request.method} {request.url}")
    try:
        # Extract tenant context from authentication token
        try:
            authorization = request.headers.get("Authorization")
            header_tenant_id = request.headers.get("X-Tenant-ID")
            if authorization and authorization.startswith("Bearer "):
                logger.info("Authorization header found.")
                token = authorization.split(" ")[1]
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                email = payload.get("sub")
                if email:
                    logger.info(f"Decoded email from token: {email}")
                    master_db = next(get_master_db())
                    try:
                        user = master_db.query(MasterUser).filter(MasterUser.email == email).first()
                        if user and user.tenant_id:
                            logger.info(f"User found: {user.email}, Tenant ID: {user.tenant_id}")
                            # Cross-check header_tenant_id if present
                            if header_tenant_id and str(header_tenant_id) != str(user.tenant_id):
                                logger.warning(f"Tenant ID header mismatch: header={header_tenant_id}, user={user.tenant_id}")
                                return JSONResponse(
                                    status_code=status.HTTP_403_FORBIDDEN,
                                    content={"detail": "Tenant ID in header does not match authenticated user's tenant."}
                                )
                            # Check if tenant database exists before setting context
                            try:
                                tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)()
                                from sqlalchemy import text
                                tenant_session.execute(text("SELECT 1"))
                                tenant_session.close()
                                set_tenant_context(user.tenant_id)
                                logger.info(f"Successfully set tenant context to {user.tenant_id} for user {email}")
                            except Exception as e:
                                logger.warning(f"Tenant database for tenant {user.tenant_id} does not exist or is inaccessible: {e}")
                                # Try to create the tenant database
                                from models.models import Tenant
                                tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
                                if tenant:
                                    success = tenant_db_manager.create_tenant_database(user.tenant_id, tenant.name)
                                    if success:
                                        logger.info(f"Successfully created tenant database for tenant {user.tenant_id}")
                                        set_tenant_context(user.tenant_id)
                                    else:
                                        logger.error(f"Failed to create tenant database for tenant {user.tenant_id}")
                                else:
                                    logger.error(f"Tenant {user.tenant_id} not found in master database")
                        else:
                            logger.info(f"User not found or tenant_id missing for email: {email}")
                    finally:
                        master_db.close()
                        logger.info(f"Master DB session closed.")
                else:
                    logger.info("Email not found in JWT payload.")
            else:
                logger.info("Authorization header not found or does not start with 'Bearer '.")
        except jwt.InvalidTokenError:
            logger.debug("Invalid JWT token")
        except Exception as e:
            logger.error(f"Error extracting tenant context: {e}")
        response = await call_next(request)
        return response
    finally:
        clear_tenant_context() 