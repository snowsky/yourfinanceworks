from fastapi import Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import jwt
import logging

from models.database import set_tenant_context, clear_tenant_context, get_master_db
from models.models import MasterUser

logger = logging.getLogger(__name__)

# JWT settings - should match your auth configuration
import os
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"

class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically sets the tenant context based on the authenticated user.
    This ensures all database operations are routed to the correct tenant database.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security = HTTPBearer(auto_error=False)
        
    async def dispatch(self, request: Request, call_next):
        # Clear any existing tenant context
        clear_tenant_context()
        
        try:
            # Extract tenant context from authenticated user
            await self._set_tenant_context_from_auth(request)
            
            # Process the request
            response = await call_next(request)
            
            return response
            
        except Exception as e:
            logger.error(f"Error in tenant context middleware: {e}")
            # Continue without tenant context on error
            response = await call_next(request)
            return response
        
        finally:
            # Always clear context after request
            clear_tenant_context()
    
    async def _set_tenant_context_from_auth(self, request: Request):
        """Extract tenant context from authentication token"""
        try:
            # Get authorization header
            authorization = request.headers.get("Authorization")
            
            if not authorization or not authorization.startswith("Bearer "):
                logger.debug("No authorization header found")
                return
            
            # Extract token
            token = authorization.split(" ")[1]
            
            # Decode JWT token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            
            if not email:
                logger.debug("No email found in token")
                return
            
            # Get user from master database
            master_db = next(get_master_db())
            try:
                user = master_db.query(MasterUser).filter(MasterUser.email == email).first()
                
                if user and user.tenant_id:
                    # Set tenant context
                    set_tenant_context(user.tenant_id)
                    logger.debug(f"Set tenant context to {user.tenant_id} for user {email}")
                else:
                    logger.debug(f"User {email} not found or has no tenant_id")
                    
            finally:
                master_db.close()
                
        except jwt.InvalidTokenError:
            logger.debug("Invalid JWT token")
        except Exception as e:
            logger.error(f"Error extracting tenant context: {e}")
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if the endpoint is public (doesn't require tenant context)"""
        public_endpoints = [
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/docs",
            "/openapi.json",
            "/",
            "/health"
        ]
        
        return any(path.startswith(endpoint) for endpoint in public_endpoints) 