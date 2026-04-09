import json
import logging
import hashlib
import os
import time
from typing import Set, Optional
from pathlib import Path
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import status
from core.models.database import (
    set_tenant_context,
    clear_tenant_context,
    get_master_db,
    get_tenant_context,
)
from core.models.models import MasterUser, user_tenant_association
from core.services.tenant_database_manager import tenant_db_manager
from core.services.analytics_service import analytics_service
from jose import jwt, JWTError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# --- Auth context cache (Redis-backed, in-memory fallback) ---
# Caches resolved user+tenant data per JWT token to avoid 4-5 DB queries per request.
# TTL is intentionally short (60s) to limit stale-auth exposure.
_AUTH_CACHE_TTL = 60  # seconds
_auth_cache_local: dict = {}  # fallback: {token_hash: (data, expires_at)}

try:
    import redis as _redis_lib
    _REDIS_URL = os.getenv("REDIS_URL")
    _redis_client = _redis_lib.from_url(_REDIS_URL, decode_responses=True) if _REDIS_URL else None
except Exception:
    _redis_client = None


def _auth_cache_key(token: str) -> str:
    return "auth_ctx:" + hashlib.sha256(token.encode()).hexdigest()


def _get_auth_cache(token: str) -> Optional[dict]:
    key = _auth_cache_key(token)
    try:
        if _redis_client:
            raw = _redis_client.get(key)
            return json.loads(raw) if raw else None
    except Exception:
        pass
    entry = _auth_cache_local.get(key)
    if entry and time.time() < entry[1]:
        return entry[0]
    return None


def _set_auth_cache(token: str, data: dict) -> None:
    key = _auth_cache_key(token)
    try:
        if _redis_client:
            _redis_client.setex(key, _AUTH_CACHE_TTL, json.dumps(data))
            return
    except Exception:
        pass
    _auth_cache_local[key] = (data, time.time() + _AUTH_CACHE_TTL)


def _invalidate_auth_cache(token: str) -> None:
    key = _auth_cache_key(token)
    try:
        if _redis_client:
            _redis_client.delete(key)
    except Exception:
        pass
    _auth_cache_local.pop(key, None)

# SECURITY IMPROVEMENT 1: Better secret key validation
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        logger.warning("WARNING: Using insecure dev key in debug mode!")
        SECRET_KEY = "dev-insecure-key-change-in-production"
    else:
        raise RuntimeError(
            "SECRET_KEY must be set in the environment for production use"
        )

# Validate secret key strength in production
if not DEBUG and len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 characters long for security")

ALGORITHM = "HS256"

# SECURITY IMPROVEMENT 2: Whitelist allowed static file extensions
ALLOWED_STATIC_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

# SECURITY IMPROVEMENT 3: Rate limiting for failed auth attempts
FAILED_AUTH_CACHE = {}  # In production, use Redis
MAX_FAILED_ATTEMPTS = 9999
LOCKOUT_DURATION = 1  # 1 second


def is_client_locked_out(client_ip: str) -> bool:
    """Check if client IP is locked out due to too many failed attempts"""
    if client_ip not in FAILED_AUTH_CACHE:
        return False

    attempts, last_attempt = FAILED_AUTH_CACHE[client_ip]
    if time.time() - last_attempt > LOCKOUT_DURATION:
        # Reset after lockout period
        del FAILED_AUTH_CACHE[client_ip]
        return False

    return attempts >= MAX_FAILED_ATTEMPTS


def record_failed_auth(client_ip: str):
    """Record a failed authentication attempt"""
    current_time = time.time()
    if client_ip in FAILED_AUTH_CACHE:
        attempts, _ = FAILED_AUTH_CACHE[client_ip]
        FAILED_AUTH_CACHE[client_ip] = (attempts + 1, current_time)
    else:
        FAILED_AUTH_CACHE[client_ip] = (1, current_time)


def is_safe_static_file(path: str) -> bool:
    """Validate static file access for security"""
    try:
        # SECURITY IMPROVEMENT 5: Prevent path traversal
        if ".." in path or "//" in path:
            return False

        # Only allow files in logos subdirectory
        if not path.startswith("/static/logos/"):
            return False

        # SECURITY IMPROVEMENT 4: Validate file extension
        # Sanitize path before using Path()
        safe_path = os.path.basename(path)
        file_path = Path(safe_path)
        if file_path.suffix.lower() not in ALLOWED_STATIC_EXTENSIONS:
            return False

        return True
    except Exception:
        return False


def get_client_ip(request: Request) -> str:
    """Safely extract client IP address"""
    # Check X-Forwarded-For header (from load balancer/proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct connection IP
    return request.client.host if request.client else "unknown"


async def tenant_context_middleware(request: Request, call_next):
    clear_tenant_context()

    # SECURITY IMPROVEMENT 6: Reduce sensitive logging
    client_ip = get_client_ip(request)
    logger.info(
        f"Middleware processing: {request.method} {request.url.path} from {client_ip}"
    )

    # SECURITY IMPROVEMENT 7: Rate limiting check
    if is_client_locked_out(client_ip):
        logger.warning(
            f"Client {client_ip} is locked out due to too many failed attempts"
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Too many failed authentication attempts. Please try again later."
            },
        )

    # Skip tenant context for Slack endpoints
    if request.url.path.startswith("/api/v1/slack/"):
        logger.info(f"Skipping tenant context for Slack endpoint: {request.url.path}")
        return await call_next(request)

    # Skip tenant context for super admin endpoints
    if request.url.path.startswith("/api/v1/super-admin/"):
        logger.warning(
            f"⚠️ Skipping tenant context for super admin endpoint: {request.url.path}"
        )
        return await call_next(request)

    # Skip tenant context for public share link endpoints (no auth required)
    if request.url.path.startswith("/api/v1/shared/"):
        return await call_next(request)

    # Skip tenant context for public plugin config endpoints (no auth required)
    if request.url.path.startswith("/api/v1/plugins/public-config/") or \
       "/public-paywall/" in request.url.path:
        return await call_next(request)

    # Skip tenant context for specific endpoints that don't need it or handle it manually
    skip_tenant_paths = [
        "/health",
        "/",
        "/docs",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/check-email-availability",
        "/api/v1/auth/request-password-reset",
        "/api/v1/auth/reset-password",
        "/api/v1/tenants/check-name-availability",
        "/api/v1/auth/change-password",
        # Google OAuth SSO endpoints must be public
        "/api/v1/auth/google/login",
        "/api/v1/auth/google/callback",
        # Azure AD OAuth SSO endpoints must be public
        "/api/v1/auth/azure/login",
        "/api/v1/auth/azure/callback",
        # SSO status endpoint must be public (used by login/signup pages)
        "/api/v1/auth/sso-status",
        # Password requirements endpoint must be public (used by UI for validation)
        "/api/v1/auth/password-requirements",
        # License features endpoint must be public (used by UI to determine available features)
        "/api/v1/license/features",
        # Organization join endpoints must be public (used during signup)
        "/api/v1/organization-join/lookup",
        "/api/v1/organization-join/request",
        # Plugin registry endpoint must be public (used for plugin discovery)
        "/api/v1/plugins/registry",
        # Sync endpoints handle their own authentication (JWT or API key)
        "/api/v1/sync/status",
        "/api/v1/sync/import"
    ]

    # Skip tenant context for external API endpoints (they use API key auth)
    if request.url.path.startswith("/api/v1/external-transactions/") or \
       request.url.path.startswith("/api/v1/external/"):
        logger.info(
            f"Skipping tenant context for external API endpoint: {request.url.path}"
        )
        return await call_next(request)

    # SECURITY IMPROVEMENT 8: Secure static file handling
    if request.url.path.startswith("/static/") or request.url.path.startswith(
        "/api/v1/static/"
    ):
        # Normalize path for validation
        static_path = (
            request.url.path.replace("/api/v1", "")
            if request.url.path.startswith("/api/v1/static/")
            else request.url.path
        )
        if is_safe_static_file(static_path):
            return await call_next(request)
        else:
            logger.warning(
                f"Blocked unsafe static file access: {request.url.path} from {client_ip}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access denied"},
            )

    # SECURITY IMPROVEMENT 9: More restrictive OPTIONS handling
    if request.method == "OPTIONS":
        # Only allow OPTIONS for specific origins/paths
        origin = request.headers.get("Origin")
        if origin and any(
            allowed_origin in origin
            for allowed_origin in [
                "localhost",
                "127.0.0.1",
                os.getenv("FRONTEND_URL", ""),
            ]
        ):
            return await call_next(request)
        else:
            logger.warning(
                f"Blocked OPTIONS request from unauthorized origin: {origin}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CORS not allowed for this origin"},
            )

    if request.url.path in skip_tenant_paths:
        return await call_next(request)

    try:
        # Extract tenant context from authentication token
        try:
            authorization = request.headers.get("Authorization")
            header_tenant_id = request.headers.get("X-Tenant-ID")

            # Extract token from Bearer header or httpOnly cookie
            token = None
            if authorization and authorization.startswith("Bearer "):
                token = authorization.split(" ")[1]
            else:
                token = request.cookies.get("auth_token")

            auth_present = bool(token)
            logger.info(f"Auth token present: {auth_present}")

            if not auth_present:
                logger.info("No valid Bearer token or auth cookie found")
                record_failed_auth(client_ip)
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required. Please log in."},
                )

            logger.info("Processing token")

            # SECURITY IMPROVEMENT 11: Add token validation
            if len(token) < 10:  # Basic sanity check
                logger.warning("Token too short")
                record_failed_auth(client_ip)
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid token format"},
                )

            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")

            # SECURITY IMPROVEMENT 12: Hash email in logs for privacy
            if email:
                email_hash = hashlib.sha256(email.encode()).hexdigest()[:8]
                logger.info(f"Token processed for user hash: {email_hash}")

                # --- Fast path: serve from auth cache to skip 4-5 DB queries ---
                cached = _get_auth_cache(token)
                if cached:
                    resolved_tenant_id = cached["tenant_id"]
                    cached_tenant_ids = cached["user_tenant_ids"]
                    if header_tenant_id:
                        try:
                            requested_tenant_id = int(header_tenant_id)
                            if requested_tenant_id <= 0:
                                raise ValueError("Invalid tenant ID")
                        except (ValueError, TypeError):
                            return JSONResponse(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                content={"detail": "Invalid tenant ID format"},
                            )
                        if requested_tenant_id not in cached_tenant_ids:
                            record_failed_auth(client_ip)
                            return JSONResponse(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                content={"detail": "Access denied to requested organization."},
                            )
                        resolved_tenant_id = requested_tenant_id
                    set_tenant_context(resolved_tenant_id)
                    logger.debug(f"Auth context served from cache for {email_hash}")
                    return await call_next(request)
                # --- End fast path ---

                master_db = next(get_master_db())
                try:
                    from sqlalchemy.orm import joinedload

                    user = (
                        master_db.query(MasterUser)
                        .options(joinedload(MasterUser.tenants))
                        .filter(MasterUser.email == email)
                        .first()
                    )
                    if user and user.tenant_id:
                        # Use header tenant ID if provided and user has access, otherwise use default tenant
                        tenant_id = user.tenant_id

                        # Get tenant IDs from association table - always do this
                        tenant_memberships = master_db.execute(
                            user_tenant_association.select().where(
                                user_tenant_association.c.user_id == user.id
                            )
                        ).fetchall()
                        user_tenant_ids = [
                            membership.tenant_id for membership in tenant_memberships
                        ] + [user.tenant_id]

                        logger.info(
                            f"User {email_hash} has access to {len(user_tenant_ids)} tenants"
                        )

                        if header_tenant_id:
                            # SECURITY IMPROVEMENT 13: Validate tenant ID format
                            try:
                                requested_tenant_id = int(header_tenant_id)
                                if requested_tenant_id <= 0:
                                    raise ValueError("Invalid tenant ID")
                            except (ValueError, TypeError):
                                logger.warning(
                                    f"Invalid tenant ID format: {header_tenant_id}"
                                )
                                return JSONResponse(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    content={"detail": "Invalid tenant ID format"},
                                )

                            # Check if user has access to the requested tenant
                            if requested_tenant_id in user_tenant_ids:
                                tenant_id = requested_tenant_id
                                logger.info(
                                    f"Switching to tenant {tenant_id} for user {email_hash}"
                                )
                            else:
                                logger.warning(
                                    f"User {email_hash} does not have access to tenant {header_tenant_id}"
                                )
                                record_failed_auth(client_ip)
                                return JSONResponse(
                                    status_code=status.HTTP_401_UNAUTHORIZED,
                                    content={
                                        "detail": "Access denied to requested organization."
                                    },
                                )

                        logger.info(
                            f"Using Tenant ID: {tenant_id} for user {email_hash}"
                        )

                        # Check if tenant database exists before setting context
                        # CRITICAL FIX: Do NOT recreate databases during live requests
                        # Database recreation should only happen during startup or admin operations
                        try:
                            # First check if tenant is enabled
                            from core.models.models import Tenant

                            tenant = (
                                master_db.query(Tenant)
                                .filter(Tenant.id == tenant_id)
                                .first()
                            )
                            if not tenant:
                                logger.warning(
                                    f"Tenant {tenant_id} not found for user {email_hash}"
                                )
                                return JSONResponse(
                                    status_code=status.HTTP_401_UNAUTHORIZED,
                                    content={"detail": "Organization not found."},
                                )

                            if not tenant.is_enabled:
                                logger.warning(
                                    f"Tenant {tenant_id} is disabled for user {email_hash}"
                                )
                                return JSONResponse(
                                    status_code=status.HTTP_403_FORBIDDEN,
                                    content={
                                        "detail": "This organization is currently disabled. Please contact your administrator."
                                    },
                                )

                            tenant_session = tenant_db_manager.get_tenant_session(
                                tenant_id
                            )()
                            from sqlalchemy import text

                            tenant_session.execute(text("SELECT 1"))
                            tenant_session.close()

                            set_tenant_context(tenant_id)
                            logger.info(
                                f"✅ Successfully set tenant context to {tenant_id} for user {email_hash}"
                            )

                            # Only sync user if they still have access to this tenant
                            if tenant_id in user_tenant_ids:
                                from core.utils.user_sync import (
                                    sync_user_to_tenant_database,
                                )

                                sync_user_to_tenant_database(user, tenant_id)

                            # Cache resolved auth context for subsequent requests
                            _set_auth_cache(token, {
                                "tenant_id": tenant_id,
                                "user_tenant_ids": user_tenant_ids,
                                "user_id": user.id,
                            })
                        except Exception as e:
                            logger.warning(
                                f"Tenant database for tenant {tenant_id} does not exist or is inaccessible: {e}"
                            )
                            # DO NOT recreate database during live request - this causes data loss
                            # Database creation should be handled by startup scripts or admin endpoints
                            logger.error(
                                f"Tenant database {tenant_id} is missing. Please run database initialization."
                            )
                            return JSONResponse(
                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                content={
                                    "detail": "Database temporarily unavailable. Please try again later."
                                },
                            )
                    else:
                        logger.warning(
                            f"User not found or tenant_id missing for user hash: {email_hash}"
                        )
                        record_failed_auth(client_ip)
                        return JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={
                                "detail": "Invalid or expired token. Please log in again."
                            },
                        )
                finally:
                    master_db.close()
                    logger.debug(f"Master DB session closed.")
            else:
                logger.debug("Email not found in JWT payload.")
                record_failed_auth(client_ip)
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Invalid or expired token. Please log in again."
                    },
                )

        except JWTError as e:
            logger.error(f"Invalid JWT token: {str(e)}")
            record_failed_auth(client_ip)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token. Please log in again."},
            )
        except Exception as e:
            logger.error(f"Error extracting tenant context: {str(e)}")
            # SECURITY IMPROVEMENT 14: Don't expose internal errors
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )

        # Enforce forced password reset if required
        try:
            forced_reset_required = bool(
                user and getattr(user, "must_reset_password", False)
            )
            if forced_reset_required:
                allowed_paths_when_forced = {
                    "/api/v1/auth/change-password",
                    "/api/v1/auth/me",
                    "/api/v1/auth/logout",
                }
                path = request.url.path
                if (path not in skip_tenant_paths) and (
                    path not in allowed_paths_when_forced
                ):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "detail": "Password reset required",
                            "code": "PASSWORD_RESET_REQUIRED",
                        },
                    )
        except Exception as e:
            logger.error(f"Error checking password reset requirement: {str(e)}")

        # Ensure tenant context is set before proceeding
        current_tenant = get_tenant_context()
        logger.info(f"Current tenant context before handler: {current_tenant}")

        logger.info(f"Calling next middleware/handler for {request.url.path}")
        start_time = time.time()
        response = await call_next(request)
        response_time_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Response status: {response.status_code}")

        # Track page view for API endpoints (skip static files and health checks)
        if (
            request.url.path.startswith("/api/v1/")
            and not request.url.path.startswith("/api/v1/auth/")
            and email
            and current_tenant
        ):
            try:
                user_agent = request.headers.get("User-Agent", "")
                analytics_service.track_page_view(
                    user_email=email,
                    tenant_id=current_tenant,
                    path=request.url.path,
                    method=request.method,
                    user_agent=user_agent,
                    ip_address=client_ip,
                    response_time_ms=response_time_ms,
                    status_code=response.status_code,
                )
            except Exception as e:
                logger.debug(f"Analytics tracking failed: {str(e)}")

        return response
    finally:
        # Don't clear tenant context here - let it persist for the request duration
        pass
