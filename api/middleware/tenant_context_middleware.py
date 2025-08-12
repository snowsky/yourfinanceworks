import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import status
from models.database import set_tenant_context, clear_tenant_context, get_master_db, get_tenant_context
from models.models import MasterUser, user_tenant_association
from services.tenant_database_manager import tenant_db_manager
from services.analytics_service import analytics_service
from jose import jwt, JWTError
import os
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY") or ("dev-insecure-key" if DEBUG else None)
if not SECRET_KEY:
    # Fail early if running in production without SECRET_KEY
    raise RuntimeError("SECRET_KEY must be set in the environment for production use")
ALGORITHM = "HS256"

# Function-based middleware for tenant context
async def tenant_context_middleware(request: Request, call_next):
    clear_tenant_context()
    logger.info(f"Middleware processing: {request.method} {request.url.path}")
    logger.info(f"Authorization header: {'Present' if request.headers.get('Authorization') else 'Missing'}")
    
    # Skip tenant context for Slack endpoints
    if request.url.path.startswith("/api/v1/slack/"):
        logger.info(f"Skipping tenant context for Slack endpoint: {request.url.path}")
        return await call_next(request)
    
    # Skip tenant context for super admin endpoints
    if request.url.path.startswith("/api/v1/super-admin/"):
        logger.info(f"Skipping tenant context for super admin endpoint: {request.url.path}")
        return await call_next(request)
    
    # Skip tenant context for specific endpoints that don't need it or handle it manually
    skip_tenant_paths = [
        "/health", "/", "/docs", "/openapi.json",
        "/api/v1/auth/login", "/api/v1/auth/register",
        "/api/v1/auth/check-email-availability", "/api/v1/auth/request-password-reset",
        "/api/v1/auth/reset-password", "/api/v1/tenants/check-name-availability",
        "/api/v1/auth/change-password"
    ]
    
    if request.url.path in skip_tenant_paths:
        return await call_next(request)
    
    try:
        # Extract tenant context from authentication token
        try:
            authorization = request.headers.get("Authorization")
            header_tenant_id = request.headers.get("X-Tenant-ID")
            logger.info(f"Auth header: {authorization[:20] if authorization else 'None'}...")
            
            if not authorization or not authorization.startswith("Bearer "):
                logger.info("No valid Bearer token found")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required. Please log in."}
                )
            
            logger.info("Processing Bearer token")
            token = authorization.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            logger.info(f"Token payload email: {email}")
            
            if email:
                logger.info(f"Decoded email from token: {email}")
                master_db = next(get_master_db())
                try:
                    from sqlalchemy.orm import joinedload
                    user = master_db.query(MasterUser).options(joinedload(MasterUser.tenants)).filter(MasterUser.email == email).first()
                    if user and user.tenant_id:
                        # Use header tenant ID if provided and user has access, otherwise use default tenant
                        tenant_id = user.tenant_id
                        
                        # Get tenant IDs from association table - always do this
                        tenant_memberships = master_db.execute(
                            user_tenant_association.select().where(
                                user_tenant_association.c.user_id == user.id
                            )
                        ).fetchall()
                        user_tenant_ids = [membership.tenant_id for membership in tenant_memberships] + [user.tenant_id]
                        
                        logger.info(f"User {email} has access to tenants: {user_tenant_ids}")
                        
                        if header_tenant_id:
                            # Check if user has access to the requested tenant
                            logger.info(f"User {email} has access to tenants: {user_tenant_ids}")
                            
                            if int(header_tenant_id) in user_tenant_ids:
                                tenant_id = int(header_tenant_id)
                                logger.info(f"Switching to tenant {tenant_id} for user {email}")
                            else:
                                logger.warning(f"User {email} does not have access to tenant {header_tenant_id}")
                                return JSONResponse(
                                    status_code=status.HTTP_401_UNAUTHORIZED,
                                    content={"detail": "Access denied to requested organization."}
                                )
                        
                        logger.info(f"User found: {user.email}, Using Tenant ID: {tenant_id}")
                        # Check if tenant database exists before setting context
                        try:
                            tenant_session = tenant_db_manager.get_tenant_session(tenant_id)()
                            from sqlalchemy import text
                            tenant_session.execute(text("SELECT 1"))
                            tenant_session.close()
                            
                            # Only sync user if they still have access to this tenant
                            if tenant_id in user_tenant_ids:
                                from utils.user_sync import sync_user_to_tenant_database
                                sync_user_to_tenant_database(user, tenant_id)
                            
                            set_tenant_context(tenant_id)
                            logger.info(f"✅ Successfully set tenant context to {tenant_id} for user {email}")
                        except Exception as e:
                            logger.warning(f"Tenant database for tenant {tenant_id} does not exist or is inaccessible: {e}")
                            # Try to create the tenant database
                            from models.models import Tenant
                            tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
                            if tenant:
                                success = tenant_db_manager.create_tenant_database(tenant_id, tenant.name)
                                if success:
                                    logger.info(f"Successfully created tenant database for tenant {tenant_id}")
                                    # Only sync if user has access to this tenant
                                    if tenant_id in user_tenant_ids:
                                        from utils.user_sync import sync_user_to_tenant_database
                                        sync_user_to_tenant_database(user, tenant_id)
                                    set_tenant_context(tenant_id)
                                else:
                                    logger.error(f"Failed to create tenant database for tenant {tenant_id}")
                            else:
                                logger.error(f"Tenant {tenant_id} not found in master database")
                    else:
                        logger.warning(f"User not found or tenant_id missing for email: {email}")
                        return JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={"detail": "Invalid or expired token. Please log in again."}
                        )
                finally:
                    master_db.close()
                    logger.debug(f"Master DB session closed.")
            else:
                logger.debug("Email not found in JWT payload.")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or expired token. Please log in again."}
                )

        except JWTError as e:
            logger.error(f"Invalid JWT token: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token. Please log in again."}
            )
        except Exception as e:
            logger.error(f"Error extracting tenant context: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        # Enforce forced password reset if required
        try:
            forced_reset_required = bool(user and getattr(user, "must_reset_password", False))
            if forced_reset_required:
                allowed_paths_when_forced = {
                    "/api/v1/auth/change-password",
                    "/api/v1/auth/me",
                    "/api/v1/auth/logout",
                }
                path = request.url.path
                if (path not in skip_tenant_paths) and (path not in allowed_paths_when_forced):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "detail": "Password reset required",
                            "code": "PASSWORD_RESET_REQUIRED"
                        }
                    )
        except Exception:
            pass

        # Ensure tenant context is set before proceeding
        current_tenant = get_tenant_context()
        logger.info(f"Current tenant context before handler: {current_tenant}")
        
        logger.info(f"Calling next middleware/handler for {request.url.path}")
        start_time = time.time()
        response = await call_next(request)
        response_time_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Response status: {response.status_code}")
        
        # Track page view for API endpoints (skip static files and health checks)
        if (request.url.path.startswith("/api/v1/") and 
            not request.url.path.startswith("/api/v1/auth/") and
            email and current_tenant):
            try:
                client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
                user_agent = request.headers.get("User-Agent", "")
                analytics_service.track_page_view(
                    user_email=email,
                    tenant_id=current_tenant,
                    path=request.url.path,
                    method=request.method,
                    user_agent=user_agent,
                    ip_address=client_ip,
                    response_time_ms=response_time_ms,
                    status_code=response.status_code
                )
            except Exception as e:
                logger.error(f"Analytics tracking failed: {e}")
        
        return response
    finally:
        # Don't clear tenant context here - let it persist for the request duration
        pass 