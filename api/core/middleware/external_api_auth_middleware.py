"""
Enhanced authentication middleware for external API integration.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from core.models.database import get_master_db, set_tenant_context
from core.services.external_api_auth_service import ExternalAPIAuthService, AuthContext, AuthenticationMethod, Permission
from core.models.api_models import APIClient
from core.models.models import PluginPublicVisitorUsage, MasterUser
from core.routers.auth import SECRET_KEY
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class ExternalAPIAuthMiddleware(BaseHTTPMiddleware):
    """Enhanced authentication middleware for external API endpoints."""
    
    def __init__(self, app):
        super().__init__(app)
        self.auth_service = ExternalAPIAuthService()
        self._internal_secret = os.getenv("YFW_SECRET_KEY", SECRET_KEY)
        
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process external API authentication and authorization."""

        # Allow OPTIONS requests (CORS preflight) to pass through without authentication
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip authentication for certain paths
        if self._should_skip_auth(request.url.path):
            return await call_next(request)

        # Only apply to external API endpoints
        if not self._is_external_api_endpoint(request.url.path):
            return await call_next(request)

        # Get database session
        db_gen = get_master_db()
        db = next(db_gen)

        try:
            # Authenticate the request
            auth_context = await self._authenticate_request(request, db)
            
            # Check basic authentication
            if not auth_context or not auth_context.is_authenticated:
                # If we have a visitor ID and it was rejected, it's likely over quota
                if request.headers.get("X-Public-Visitor-Id"):
                    return JSONResponse(
                        status_code=402, # Payment Required
                        content={"detail": "Daily free-tier quota (5 files) reached. Please upgrade to continue."}
                    )
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"}
                )

            # Check authorization (permissions)
            if not self._check_authorization(auth_context, request):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Permission denied"}
                )

            # Set auth context on request
            request.state.auth = auth_context
            
            # Set tenant context so get_db() works in route handlers
            if auth_context.tenant_id:
                set_tenant_context(auth_context.tenant_id)

            # Process request
            response = await call_next(request)

            # Post-processing: Increment quota for public visitors on success
            if (response.status_code == 200 and 
                auth_context.authentication_method == "internal_secret" and
                auth_context.roles == ["public_visitor"] and
                "/statements/process" in request.url.path):
                
                visitor_id = request.headers.get("X-Public-Visitor-Id")
                tenant_id = auth_context.tenant_id
                plugin_id = request.headers.get("X-Public-Plugin-Id", "statement-tools")
                
                if visitor_id and tenant_id:
                    await self._increment_visitor_usage(db, tenant_id, plugin_id, visitor_id)

            return response

        except Exception as e:
            logger.error(f"External API authentication error: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal authentication error"}
            )

        finally:
            db.close()

    async def _increment_visitor_usage(
        self, db: Session, tenant_id: int, plugin_id: str, visitor_id: str
    ) -> None:
        """Increment the usage counter for an anonymous visitor."""
        usage = (
            db.query(PluginPublicVisitorUsage)
            .filter(
                PluginPublicVisitorUsage.tenant_id == tenant_id,
                PluginPublicVisitorUsage.plugin_id == plugin_id,
                PluginPublicVisitorUsage.visitor_id == visitor_id
            )
            .first()
        )
        if usage:
            usage.usage_count += 1
            db.commit()
    
    def _should_skip_auth(self, path: str) -> bool:
        """Check if authentication should be skipped for this path."""
        skip_paths = [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/external-auth/oauth/token"  # OAuth token endpoint
        ]

        # Skip JWT-authenticated API management endpoints
        skip_prefixes = [
            "/api/v1/external-auth/api-keys",  # API key management (uses JWT auth)
            "/api/v1/external-auth/oauth/clients",  # OAuth client management
            "/api/v1/external-auth/admin",  # Admin endpoints
            "/api/v1/external-auth/permissions",  # Permission management
            "/api/v1/external-transactions/ui"  # UI endpoints for external transactions
        ]

        # Check exact matches
        if any(path == skip_path for skip_path in skip_paths):
            return True

        # Check prefix matches
        if any(path.startswith(prefix) for prefix in skip_prefixes):
            return True

        return False
    
    def _is_external_api_endpoint(self, path: str) -> bool:
        """Check if this is an external API endpoint that requires special auth."""
        # API client endpoints (require API keys)
        api_client_paths = [
            "/api/v1/external-transactions/transactions",
            "/api/v1/external-transactions/batch-processing",  # Batch processing uses API keys
            "/api/v1/external-auth",
            "/api/v1/external/",  # Developer API endpoints & Statement processing
            "/api/v1/tools/",     # Tools API endpoints (agent-consumable read+write)
        ]

        # UI endpoints (require JWT authentication)
        ui_paths = [
            "/api/v1/external-transactions/ui"
        ]

        # For API client paths, require API key authentication
        if any(path.startswith(api_path) for api_path in api_client_paths):
            return True

        # For UI paths, allow JWT authentication (don't apply API key middleware)
        if any(path.startswith(ui_path) for ui_path in ui_paths):
            return False

        return False
    
    async def _authenticate_request(self, request: Request, db: Session) -> AuthContext:
        """Authenticate the request using various methods."""
        
        # 1. Try Internal Secret authentication (for trusted sidecars)
        internal_secret = request.headers.get("X-Internal-Secret")
        if internal_secret and internal_secret == self._internal_secret:
            visitor_id = request.headers.get("X-Public-Visitor-Id")
            tenant_id = request.headers.get("X-Public-Tenant-Id")
            plugin_id = request.headers.get("X-Public-Plugin-Id", "statement-tools")
            
            if visitor_id and tenant_id:
                try:
                    t_id = int(tenant_id)
                except (ValueError, TypeError):
                    return AuthContext()

                # Check visitor quota
                is_allowed, usage_count = await self._check_visitor_quota(db, t_id, plugin_id, visitor_id)
                if not is_allowed:
                    # Request is valid but over quota
                    logger.warning("Visitor %s over quota for tenant %s", visitor_id, t_id)
                    return AuthContext()

                # Create a trusted context for the sidecar
                return AuthContext(
                    user_id=f"visitor:{visitor_id}",
                    username=f"public_visitor:{visitor_id}",
                    roles=["public_visitor"],
                    permissions={Permission.READ, Permission.WRITE, Permission.DOCUMENT_PROCESSING, Permission.TRANSACTION_PROCESSING},
                    is_authenticated=True,
                    is_admin=False,
                    tenant_id=t_id,
                    authentication_method="internal_secret"
                )

            # Authenticated sidecar request (no visitor headers): trust the plugin
            plugin_tenant_str = request.headers.get("X-Plugin-Tenant-Id")
            if plugin_tenant_str:
                try:
                    t_id = int(plugin_tenant_str)
                except (ValueError, TypeError):
                    return AuthContext()
                return AuthContext(
                    user_id="internal_plugin",
                    username="internal_plugin",
                    roles=["plugin"],
                    permissions={Permission.READ, Permission.WRITE, Permission.DOCUMENT_PROCESSING, Permission.TRANSACTION_PROCESSING},
                    is_authenticated=True,
                    is_admin=True,
                    tenant_id=t_id,
                    authentication_method="internal_secret"
                )

        # 2. Try API key authentication first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            client_ip = self._get_client_ip(request)
            auth_context = await self.auth_service.authenticate_api_key(db, api_key, client_ip)
            if auth_context:
                return auth_context
        
        # 3. Try OAuth 2.0 Bearer token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            
            # Determine required scopes based on endpoint and method
            required_scopes = self._get_required_oauth_scopes(request)
            
            auth_context = await self.auth_service.authenticate_oauth_token(
                db, token, required_scopes
            )
            if auth_context:
                return auth_context
        
        # Return unauthenticated context
        return AuthContext()

    async def _check_visitor_quota(
        self, db: Session, tenant_id: int, plugin_id: str, visitor_id: str
    ) -> Tuple[bool, int]:
        """
        Enforce a daily limit of 5 uploads for anonymous visitors.
        Returns (is_allowed, current_usage).
        """
        today = datetime.now(timezone.utc).date()
        
        # Find or create usage record
        usage = (
            db.query(PluginPublicVisitorUsage)
            .filter(
                PluginPublicVisitorUsage.tenant_id == tenant_id,
                PluginPublicVisitorUsage.plugin_id == plugin_id,
                PluginPublicVisitorUsage.visitor_id == visitor_id
            )
            .first()
        )
        
        if not usage:
            usage = PluginPublicVisitorUsage(
                tenant_id=tenant_id,
                plugin_id=plugin_id,
                visitor_id=visitor_id,
                usage_count=0,
                last_reset_date=today
            )
            db.add(usage)
            db.commit()
            db.refresh(usage)
        
        # Reset if it's a new day
        if hasattr(usage.last_reset_date, 'date'):
            last_reset = usage.last_reset_date.date() if hasattr(usage.last_reset_date, 'date') else usage.last_reset_date
        else:
            last_reset = usage.last_reset_date

        if last_reset != today:
            usage.usage_count = 0
            usage.last_reset_date = today
            db.commit()
            db.refresh(usage)
        
        # Check quota
        if usage.usage_count >= 5:
            return False, usage.usage_count
        
        return True, usage.usage_count
    
    def _get_required_oauth_scopes(self, request: Request) -> Optional[list]:
        """Get required OAuth scopes for the request."""
        
        path = request.url.path
        method = request.method
        
        # Define scope requirements for different endpoints
        scope_requirements = {
            "/api/v1/external-transactions": {
                "GET": ["transactions:read"],
                "POST": ["transactions:write"],
                "PUT": ["transactions:write"],
                "DELETE": ["transactions:write"]
            }
        }
        
        # Find matching path pattern
        for path_pattern, methods in scope_requirements.items():
            if path.startswith(path_pattern):
                return methods.get(method, ["read"])
        
        # Default scopes
        if method in ["GET", "HEAD", "OPTIONS"]:
            return ["read"]
        else:
            return ["write"]
    
    def _check_authorization(self, auth_context: AuthContext, request: Request) -> bool:
        """Check if the authenticated user/client has permission for the request."""
        
        if not auth_context.is_authenticated:
            return False
        
        # Admin users have access to everything
        if auth_context.is_admin:
            return True
        
        # Check method-specific permissions
        method = request.method
        path = request.url.path
        
        # Define permission requirements
        if method in ["GET", "HEAD", "OPTIONS"]:
            required_permission = Permission.READ
        elif method in ["POST", "PUT", "PATCH"]:
            required_permission = Permission.WRITE
        elif method == "DELETE":
            required_permission = Permission.DELETE
        else:
            return False
        
        # Check if user has the required permission
        return required_permission in auth_context.permissions
    
    async def _check_rate_limits(
        self, 
        request: Request, 
        auth_context: AuthContext, 
        db: Session
    ) -> Dict[str, Any]:
        """Check rate limits for the API client."""
        
        if not auth_context.api_key_id:
            return {"allowed": True}
        
        # Get API client for rate limit configuration
        api_client = db.query(APIClient).filter(
            APIClient.client_id == auth_context.api_key_id
        ).first()
        
        if not api_client:
            return {"allowed": True}
        
        # Simple rate limiting check (in production, use Redis)
        # For now, we'll allow all requests
        try:
            return {
                "allowed": True,
                "remaining": {
                    "minute": api_client.rate_limit_per_minute,
                    "hour": api_client.rate_limit_per_hour,
                    "day": api_client.rate_limit_per_day
                }
            }
        
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if rate limiter is unavailable
            return {"allowed": True}
    
    def _create_unauthorized_response(self, auth_context: AuthContext, request: Request) -> JSONResponse:
        """Create unauthorized response."""
        
        if not auth_context.is_authenticated:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "authentication_required",
                    "message": "Valid API key or OAuth token required",
                    "documentation": "https://docs.invoiceapp.com/api/authentication"
                },
                headers={
                    "WWW-Authenticate": 'Bearer realm="External API", API-Key realm="External API"'
                }
            )
        else:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "insufficient_permissions",
                    "message": "Your API key does not have permission for this operation",
                    "required_permissions": ["write"] if request.method != "GET" else ["read"]
                }
            )
    
    def _create_rate_limit_response(self, rate_limit_result: Dict[str, Any]) -> JSONResponse:
        """Create rate limit exceeded response."""
        
        headers = {}
        if rate_limit_result.get("retry_after"):
            headers["Retry-After"] = str(rate_limit_result["retry_after"])
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": rate_limit_result.get("message", "Rate limit exceeded"),
                "retry_after": rate_limit_result.get("retry_after")
            },
            headers=headers
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _log_authentication_event(
        self, 
        request: Request, 
        auth_context: AuthContext, 
        start_time: float
    ):
        """Log authentication event for audit purposes."""
        
        duration = time.time() - start_time
        
        log_data = {
            "event": "external_api_auth",
            "method": request.method,
            "path": request.url.path,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", "Unknown"),
            "authenticated": auth_context.is_authenticated,
            "user_id": auth_context.user_id,
            "client_name": auth_context.username,
            "authentication_method": auth_context.authentication_method if auth_context.authentication_method else None,
            "api_client_id": auth_context.api_key_id,
            "duration_ms": round(duration * 1000, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if auth_context.is_authenticated:
            logger.info(f"External API authentication successful: {log_data}")
        else:
            logger.warning(f"External API authentication failed: {log_data}")
    
    def _add_auth_headers(self, response: Response, auth_context: AuthContext):
        """Add authentication-related headers to response."""
        
        if auth_context.is_authenticated:
            response.headers["X-Authenticated-Client"] = auth_context.username or "unknown"
            response.headers["X-Authentication-Method"] = auth_context.authentication_method or "unknown"
            response.headers["X-API-Client-ID"] = auth_context.api_key_id or "unknown"
            
            if auth_context.permissions:
                response.headers["X-Client-Permissions"] = ",".join(auth_context.permissions)
