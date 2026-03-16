# Copyright (c) 2026 YourFinanceWORKS
# This file is part of YourFinanceWORKS, which uses a split-licensing model.
# Core components are licensed under GNU AGPLv3.
# Commercial components are licensed under the YourFinanceWORKS Commercial License.
# See LICENSE-AGPLv3.txt and LICENSE-COMMERCIAL.txt for details.

import os
import shutil
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import logging
from fastapi.staticfiles import StaticFiles

# Auto-copy .env.example.full to .env if .env doesn't exist
def ensure_env_file():
    """Copy .env.example.full to .env if .env doesn't exist"""
    api_dir = Path(__file__).parent
    env_file = api_dir / ".env"
    env_example_file = api_dir / ".env.example.full"

    if not env_file.exists() and env_example_file.exists():
        try:
            shutil.copy2(env_example_file, env_file)
            print(f"✅ Created .env from .env.example.full")
        except Exception as e:
            print(f"⚠️  Failed to copy .env.example.full to .env: {e}")
    elif not env_file.exists():
        print("⚠️  .env file doesn't exist and .env.example.full not found")

# Ensure .env file exists before proceeding
ensure_env_file()

from core.routers import (
    auth,
    clients,
    invoices,
    payments,
    expenses,
    currency,
    settings,
    tenant,
    discount_rules,
    crm,
    email,
    audit_log,  # Add the audit log router
    super_admin,  # Add the super admin router
    inventory,
    inventory_attachments,
    organization_join,
    reminders,
    files,
    attachments,
    license,
    analytics, # Add the new analytics router
    notifications,  # Add the notifications router
    gamification,  # Add the gamification router
    social_features,  # Add the social features router
    user_preference_controls,  # Add the user preference controls router
    sync,  # Add the synchronization router
    timeline  # Add the client timeline router
)

# Configure logging early so we can use it in imports
logging.basicConfig(level=logging.INFO)  # Ensure INFO logs are shown
logger = logging.getLogger(__name__)

# Import Commercial Modules (Conditional)
try:
    from commercial.cloud_storage.router import router as cloud_storage
    from commercial.accounting_export.router import router as accounting_export
    from commercial.integrations.slack.router import router as slack_simplified
    from commercial.integrations.email.router import router as email_integration
    from commercial.api_access.router import router as external_api_auth
    from commercial.workflows.approvals.router import router as approvals
    from commercial.routers import approval_reports
    from commercial.batch_processing.router import router as batch_processing
    from commercial.ai.router import router as ai
    from commercial.ai.config_router import router as ai_config
    from commercial.ai.pdf_processor import router as pdf_processor
    from commercial.export.router import router as export_router
    from commercial.sso.router import router as sso_router
    from commercial.ai_bank_statement.router import router as statements
    from commercial.reporting.router import router as reports
    from commercial.advanced_search.router import router as search
    from commercial.prompt_management.router import router as prompts
    from commercial.ai_bank_statement.external_router import router as external_api
    from commercial.external_transactions.router import router as external_transactions
    from commercial.plugin_management.router import router as plugin_management
    COMMERCIAL_MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import commercial modules: {str(e)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    cloud_storage = None
    accounting_export = None
    slack_simplified = None
    email_integration = None
    external_api_auth = None
    plugin_management = None
    approvals = None
    approval_reports = None
    batch_processing = None
    ai = None
    ai_config = None
    pdf_processor = None
    export_router = None
    sso_router = None
    statements = None
    reports = None
    search = None
    prompts = None
    external_api = None
    external_transactions = None
    COMMERCIAL_MODULES_AVAILABLE = False
from core.models.database import engine
from core.models import models

from db_init import init_db
from core.services.search_indexer import search_indexer

# Auto-discover plugins and import their models BEFORE init_db()
# so create_all() includes plugin tables for new tenant databases.
from plugins.loader import plugin_loader
plugin_loader.import_models()

# Initialize database (create tables and populate initial data)
try:
    logger.info("Starting database initialization...")
    init_db()
    logger.info("Database initialization completed successfully.")
except Exception as e:
    logger.error(f"Database initialization failed: {str(e)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    # Don't raise the exception to allow the app to start even if DB init fails
    # (Tables may not exist yet, they will be created by migrations if needed)


async def auto_activate_license():
    """
    Automatically activate a license if provided via environment variables.
    Used for cloud deployments where the license is injected into the container.
    """
    # Support aliases for environment variables
    installation_id = os.getenv("INSTALLATION_ID")
    license_key = os.getenv("LICENSE_KEY") or os.getenv("LICENSE")
    private_key_pem = os.getenv("DEPLOYMENT_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")

    # Default to True if license_key is provided
    auto_activate_str = os.getenv("AUTO_ACTIVATE_LICENSE")
    if auto_activate_str is None and license_key:
        auto_activate = True
    else:
        auto_activate = str(auto_activate_str).lower() == "true"

    if not (installation_id or license_key or private_key_pem):
        return

    logger.info("Checking for injected license data for auto-activation...")
    if installation_id:
        logger.info(f"  - Installation ID: {installation_id}")
    if license_key:
        logger.info(f"  - License Key: [PROVIDED] (Auto-activate: {auto_activate})")
    if private_key_pem:
        logger.info(f"  - Private Key: [PROVIDED]")

    from core.models.database import get_master_db
    from core.services.license_service import LicenseService, KEYS_DIR, DEFAULT_KEY_ID, PUBLIC_KEYS
    from core.models.models import GlobalInstallationInfo

    db_gen = get_master_db()
    db = next(db_gen)

    try:
        service = LicenseService(db, master_db=db)

        # 1. Load private key from env var into memory — derive public key without disk writes
        if private_key_pem:
            try:
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.backends import default_backend

                pk = serialization.load_pem_private_key(
                    private_key_pem.encode(),
                    password=None,
                    backend=default_backend()
                )
                pub_pem = pk.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ).decode("utf-8")

                # Update in-memory public key — no filesystem write needed
                PUBLIC_KEYS[DEFAULT_KEY_ID] = pub_pem
                logger.info("Loaded private key from env var; derived public key held in memory (not written to disk)")
            except Exception as pk_err:
                logger.warning(f"Could not load private key from env var: {pk_err}")

        # 2. Sync Installation ID if provided
        if installation_id:
            global_info = db.query(GlobalInstallationInfo).first()
            if not global_info:
                global_info = GlobalInstallationInfo(
                    installation_id=installation_id,
                    license_status="invalid"
                )
                db.add(global_info)
                logger.info(f"Initialized global installation with injected ID: {installation_id}")
            elif global_info.installation_id != installation_id:
                old_id = global_info.installation_id
                global_info.installation_id = installation_id
                logger.info(f"Synchronized global installation ID from {old_id} to {installation_id}")
            db.commit()

        # 3. Auto-activate license if requested
        if license_key and auto_activate:
            # Check if already licensed
            global_info = db.query(GlobalInstallationInfo).first()
            if global_info and global_info.is_licensed and global_info.license_key == license_key:
                logger.info("License already active and matches injected key.")
            else:
                result = service.activate_global_license(license_key)
                if result.get("success"):
                    logger.info("✅ Successfully auto-activated injected license.")
                else:
                    logger.warning(f"❌ Failed to auto-activate injected license: {result.get('message')}")
    except Exception as e:
        logger.error(f"Error during license auto-activation: {str(e)}")
    finally:
        db.close()

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Startup logic
    try:
        # Start reminder background service
        try:
            from core.services.reminder_background_service import start_reminder_background_service
            await start_reminder_background_service()
            logger.info("Reminder background service started successfully")
        except Exception as e:
            logger.warning(f"Failed to start reminder background service: {str(e)}")

        # Initialize processing lock system with crash recovery
        # Note: Processing locks are tenant-specific, so we run recovery per tenant
        try:
            from core.models.processing_lock import ProcessingLock
            from core.services.tenant_database_manager import tenant_db_manager
            from core.models.database import set_tenant_context

            # Get all tenant IDs
            tenant_ids = tenant_db_manager.get_existing_tenant_ids()

            if tenant_ids:
                logger.info(f"🔄 Running processing lock crash recovery for {len(tenant_ids)} tenants...")

                total_expired = 0
                total_stuck = 0
                total_active = 0

                for tenant_id in tenant_ids:
                    try:
                        set_tenant_context(tenant_id)
                        SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
                        db = SessionLocalTenant()

                        try:
                            recovery_result = ProcessingLock.startup_lock_recovery(db, older_than_minutes=30)
                            total_expired += recovery_result['expired_locks_cleaned']
                            total_stuck += recovery_result['stuck_locks_recovered']
                            total_active += recovery_result['remaining_active_locks']

                            if recovery_result['stuck_locks_recovered'] > 0:
                                logger.warning(f"⚠️  Tenant {tenant_id}: Recovered {recovery_result['stuck_locks_recovered']} stuck locks")
                        except Exception as e:
                            # If table doesn't exist yet, skip gracefully
                            if "does not exist" in str(e).lower():
                                logger.debug(f"Processing locks table not yet created for tenant {tenant_id}")
                            else:
                                logger.error(f"❌ Tenant {tenant_id}: Processing lock recovery failed: {str(e)}")
                        finally:
                            db.close()
                    except Exception as e:
                        logger.debug(f"Skipping tenant {tenant_id}: {str(e)}")

                logger.info(f"📊 Processing Lock Recovery Summary (all tenants):")
                logger.info(f"   - Expired locks cleaned: {total_expired}")
                logger.info(f"   - Stuck locks recovered: {total_stuck}")
                logger.info(f"   - Remaining active locks: {total_active}")

                if total_stuck > 0:
                    logger.warning("⚠️  Found and recovered locks that may have been left by crashed services!")
                else:
                    logger.info("✅ No stuck locks found - processing lock system is healthy")
            else:
                logger.info("No tenants found, skipping processing lock recovery")

        except Exception as e:
            logger.warning(f"Failed to initialize processing lock recovery: {str(e)}")

        # Auto-activate license if injected via environment variables
        try:
            await auto_activate_license()
        except Exception as e:
            logger.error(f"Failed to auto-activate license on startup: {str(e)}")

        # Sync default prompts to DB for all tenants
        # This ensures changes to default_prompts.py are picked up on restart
        try:
            from commercial.prompt_management.services.prompt_service import PromptService
            from core.services.tenant_database_manager import tenant_db_manager
            from core.models.database import set_tenant_context

            tenant_ids = tenant_db_manager.get_existing_tenant_ids()
            if tenant_ids:
                logger.info(f"🔄 Syncing default prompts for {len(tenant_ids)} tenants...")
                for tenant_id in tenant_ids:
                    try:
                        set_tenant_context(tenant_id)
                        SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
                        db = SessionLocalTenant()
                        try:
                            result = PromptService(db).sync_default_prompts()
                            if result["updated"] > 0 or result["inserted"] > 0:
                                logger.info(
                                    f"✅ Tenant {tenant_id}: prompts synced "
                                    f"({result['inserted']} inserted, {result['updated']} updated)"
                                )
                        finally:
                            db.close()
                    except Exception as e:
                        logger.warning(f"Failed to sync prompts for tenant {tenant_id}: {e}")
            else:
                logger.info("No tenants found, skipping prompt sync")
        except ImportError:
            logger.info("Prompt management (Commercial) not available, skipping prompt sync")
        except Exception as e:
            logger.warning(f"Failed to sync default prompts on startup: {e}")

        yield
    finally:
        # Stop reminder background service
        try:
            from core.services.reminder_background_service import stop_reminder_background_service
            await stop_reminder_background_service()
        except Exception:
            logger.warning("Failed to stop reminder background service on shutdown", exc_info=True)

        # Shutdown: flush Kafka producers
        try:
            from commercial.ai.services.ocr_service import flush_all_producers
            flush_all_producers(10.0)
        except Exception:
            logger.warning("Failed to flush Kafka producers on shutdown", exc_info=True)

app = FastAPI(
    title="Invoice API",
    description="API for the YourFinanceWORKS",
    version="1.0.0",
    lifespan=app_lifespan,
    redirect_slashes=False  # Disable automatic trailing slash redirects
)

# Add exception handler for Pydantic validation errors
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

def serialize_validation_errors(errors):
    """Convert Pydantic validation errors to JSON-serializable format"""
    serialized_errors = []
    for error in errors:
        error_copy = error.copy()
        # Convert any non-serializable objects to strings
        if 'ctx' in error_copy and 'error' in error_copy['ctx']:
            error_copy['ctx']['error'] = str(error_copy['ctx']['error'])
        serialized_errors.append(error_copy)
    return serialized_errors

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error on {request.method} {request.url.path}")
    logger.error(f"Validation errors: {exc.errors()}")
    try:
        body = await request.body()
        logger.error(f"Request body: {body}")
    except Exception:
        body = b"Unable to read request body"
        logger.error("Could not read request body")

    errors = serialize_validation_errors(exc.errors())

    return JSONResponse(
        status_code=400,
        content={"detail": errors}
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    logger.error(f"Pydantic validation error on {request.method} {request.url.path}")
    logger.error(f"Validation errors: {exc.errors()}")

    errors = serialize_validation_errors(exc.errors())

    return JSONResponse(
        status_code=400,
        content={"detail": errors}
    )

# Serve static files (e.g., for company logos)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/api/v1/static", StaticFiles(directory=static_dir), name="api_static")

# CORS Middleware (permissive for development)
# Check multiple environment indicators for debug mode
debug_env = os.getenv("DEBUG", "False").lower()
dev_env = os.getenv("ENVIRONMENT", "development").lower()
debug_mode = debug_env == "true" or dev_env in ["development", "dev"]
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()

if debug_mode:
    # In debug mode, allow all origins
    allowed_origins = ["*"]
    allow_credentials = False  # Cannot use credentials with wildcard
else:
    # In production, use specific origins
    if allowed_origins_env:
        allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
    else:
        allowed_origins = [
            "http://localhost:8080", "http://localhost:3000"
        ]

    # Add license key request URL to allowed origins if specified
    license_key_site = os.getenv("LICENSE_KEY_REQUEST_URL")
    if license_key_site:
        if license_key_site not in allowed_origins:
            allowed_origins.append(license_key_site)

    allow_credentials = os.getenv("ALLOW_CORS_CREDENTIALS", "True").lower() == "true"

# Log CORS configuration for debugging
logger.info(f"CORS Configuration:")
logger.info(f"  Debug mode: {debug_mode}")
logger.info(f"  Allowed origins: {allowed_origins}")
logger.info(f"  Allow credentials: {allow_credentials}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_AUTH_COOKIE_NAME = "auth_token"

def _origin_is_trusted(origin: str, allowed: list) -> bool:
    origin = origin.rstrip("/")
    return any(origin == ao.rstrip("/") for ao in allowed)

@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    """Validate Origin/Referer on state-changing cookie-authenticated requests.

    Rules:
    - Safe methods (GET/HEAD/OPTIONS) are always allowed.
    - In debug mode (wildcard CORS) the check is skipped.
    - Requests using Bearer token auth are inherently CSRF-safe; skip check.
    - For cookie-authenticated requests, the Origin header must match an
      allowed origin. If Origin is absent, the Referer is checked instead.
      Requests with neither header are allowed (non-browser API clients).
    """
    if request.method in _CSRF_SAFE_METHODS or debug_mode:
        return await call_next(request)

    # Bearer token ⇒ CSRF-safe by design
    if request.headers.get("authorization", "").startswith("Bearer "):
        return await call_next(request)

    # Only enforce for requests that carry the session cookie
    if not request.cookies.get(_AUTH_COOKIE_NAME):
        return await call_next(request)

    origin = request.headers.get("origin")
    if origin:
        if not _origin_is_trusted(origin, allowed_origins):
            logger.warning(f"CSRF check failed: untrusted Origin '{origin}' on {request.method} {request.url.path}")
            return JSONResponse(status_code=403, content={"detail": "CSRF check failed: untrusted origin"})
    else:
        referer = request.headers.get("referer", "")
        if referer:
            from urllib.parse import urlparse as _urlparse
            p = _urlparse(referer)
            ref_origin = f"{p.scheme}://{p.netloc}"
            if not _origin_is_trusted(ref_origin, allowed_origins):
                logger.warning(f"CSRF check failed: untrusted Referer '{referer}' on {request.method} {request.url.path}")
                return JSONResponse(status_code=403, content={"detail": "CSRF check failed: untrusted referer"})
        # No Origin and no Referer ⇒ non-browser client; allow

    return await call_next(request)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # Content-Security-Policy is context-dependent; set a conservative default for API responses
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
    return response

# Add error handling middleware
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled exception on {request.method} {request.url}")
        logger.error(f"Exception: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}" if isinstance(str(e), str) else "Internal server error"}
        )

# Add tenant context middleware (function-based)
from core.middleware.tenant_context_middleware import tenant_context_middleware
app.middleware('http')(tenant_context_middleware)

# Add external API authentication middleware
from core.middleware.external_api_auth_middleware import ExternalAPIAuthMiddleware
app.add_middleware(ExternalAPIAuthMiddleware)

# ==============================================================================
# ROUTER REGISTRATION
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. Core Routers (AGPLv3)
# These features are available in all versions of the application.
# ------------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tenant.router, prefix="/api/v1")
app.include_router(super_admin.router, prefix="/api/v1")  # Add super admin router
app.include_router(clients.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(expenses.router, prefix="/api/v1")
app.include_router(currency.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(discount_rules.router, prefix="/api/v1")
app.include_router(email.router, prefix="/api/v1")
app.include_router(crm.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")  # Add the new inventory router
app.include_router(inventory_attachments.router, prefix="/api/v1")  # Add the inventory attachments router
app.include_router(organization_join.router, prefix="/api/v1")  # Add the new organization join router
app.include_router(reminders.router, prefix="/api/v1/reminders", tags=["reminders"])  # Add the new reminders router
app.include_router(files.router, prefix="/api/v1")  # Add the new files router
app.include_router(notifications.router, prefix="/api/v1")  # Add the new notifications router
app.include_router(attachments.router, prefix="/api/v1")  # Add the new attachments router
app.include_router(license.router, prefix="/api/v1")  # Add the license management router
app.include_router(user_preference_controls.router, prefix="/api/v1")  # Add the user preference controls router
app.include_router(gamification.router, prefix="/api/v1")  # Add the gamification router
app.include_router(social_features.router, prefix="/api/v1")  # Add the social features router
app.include_router(analytics.router, prefix="/api/v1")       # Add the new analytics router
app.include_router(audit_log.router, prefix="/api/v1")       # Add the new audit log router
app.include_router(sync.router, prefix="/api/v1")            # Add the sync router
app.include_router(timeline.router, prefix="/api/v1")        # Add the client timeline router


# ------------------------------------------------------------------------------
# 2. Commercial Routers (Proprietary)
# These features are only available with a valid commercial license.
# Note: Some commercial features are temporarily in core import list but should be moved.
# ------------------------------------------------------------------------------

# --- Auto-register all discovered plugins ---
# plugin_loader was already used above to import models; now register routes.
plugin_loader.register_all(app)


if sso_router:
    app.include_router(sso_router, prefix="/api/v1")

if ai:
    app.include_router(ai, prefix="/api/v1")
if ai_config:
    app.include_router(ai_config, prefix="/api/v1")
if pdf_processor:
    app.include_router(pdf_processor, prefix="/api/v1")

if accounting_export:
    app.include_router(accounting_export, prefix="/api/v1")
if email_integration:
    app.include_router(email_integration, prefix="/api/v1")
if slack_simplified:
    app.include_router(slack_simplified, prefix="/api/v1")

if cloud_storage:
    app.include_router(cloud_storage, prefix="/api/v1")
if export_router:
    app.include_router(export_router, prefix="/api/v1")
if batch_processing:
    app.include_router(batch_processing, prefix="/api/v1")

if external_api_auth:
    app.include_router(external_api_auth, prefix="/api/v1")

if approvals:
    app.include_router(approvals, prefix="/api/v1")
if approval_reports:
    app.include_router(approval_reports.router, prefix="/api/v1")

if statements:
    app.include_router(statements, prefix="/api/v1")

if reports:
    app.include_router(reports, prefix="/api/v1")

if search:
    logger.info("Registering advanced_search router")
    app.include_router(search, prefix="/api/v1")
else:
    logger.warning("advanced_search router is None - not registering")

if prompts:
    logger.info("Registering prompt_management router")
    app.include_router(prompts, prefix="/api/v1")
else:
    logger.warning("prompt_management router is None - not registering")

if external_api:
    logger.info("Registering external_api router")
    app.include_router(external_api, prefix="/api/v1")
else:
    logger.warning("external_api router is None - not registering")

if external_transactions:
    logger.info("Registering external_transactions router")
    app.include_router(external_transactions, prefix="/api/v1")
else:
    logger.warning("external_transactions router is None - not registering")

if plugin_management:
    logger.info("Registering plugin_management router")
    app.include_router(plugin_management, prefix="/api/v1")
else:
    logger.warning("plugin_management router is None - not registering")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Invoice API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Moved shutdown handling to lifespan above to avoid deprecation warnings

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
