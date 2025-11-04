from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import logging
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from routers import (
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
    ai, # Add the new AI router
    ai_config, # Add the new AI config router
    super_admin, # Add the new super admin router
    audit_log, # Add the new audit log router
    slack_simplified, # Add the new simplified Slack router
    notifications, # Add the new notifications router
    analytics, # Add the new analytics router
    pdf_processor, # Add the new PDF processor router
    statements,
    tax_integration,  # Add the new tax integration router
    reports,  # Add the new reports router
    attachments,  # Add the new attachments router
    search,
    external_api_auth,  # Add the new external API auth router
    external_transactions,  # Add the new external transactions router
    external_api,  # Add the new external API router
    inventory,  # Add the new inventory router
    inventory_attachments,  # Add the inventory attachments router
    approvals,  # Add the new approvals router
    approval_reports,  # Add the new approval reports router
    organization_join,  # Add the new organization join router
    reminders,  # Add the new reminders router
    files,  # Add the new files router
    cloud_storage  # Add the new cloud storage router
)
from models.database import engine
from models import models

from db_init import init_db
from services.search_indexer import search_indexer

# Configure logging
logging.basicConfig(level=logging.INFO)  # Ensure INFO logs are shown
logger = logging.getLogger(__name__)

# Initialize database (create tables and populate initial data)
try:
    logger.info("Starting database initialization...")
    init_db(skip_migrations=True)  # Skip migrations to avoid hanging during startup
    logger.info("Database initialization completed successfully.")
except Exception as e:
    logger.error(f"Database initialization failed: {str(e)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    # Don't raise the exception to allow the app to start even if DB init fails

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Startup logic
    try:
        # Initialize tax integration service
        try:
            from config import config
            from services.tax_integration_service import initialize_tax_integration_service

            if config.TAX_SERVICE_ENABLED and config.TAX_SERVICE_API_KEY:
                tax_config = config.tax_service_config
                initialize_tax_integration_service(tax_config)
                logger.info("Tax integration service initialized successfully")
            else:
                logger.info("Tax integration service not enabled or not configured")

        except Exception as e:
            logger.warning(f"Failed to initialize tax integration service: {str(e)}")

        # Start reminder background service
        try:
            from services.reminder_background_service import start_reminder_background_service
            await start_reminder_background_service()
            logger.info("Reminder background service started successfully")
        except Exception as e:
            logger.warning(f"Failed to start reminder background service: {str(e)}")

        yield
    finally:
        # Stop reminder background service
        try:
            from services.reminder_background_service import stop_reminder_background_service
            await stop_reminder_background_service()
        except Exception:
            pass

        # Shutdown: flush Kafka producers
        try:
            from services.ocr_service import flush_all_producers
            flush_all_producers(10.0)
        except Exception:
            pass

        # Cleanup tax integration service
        try:
            from services.tax_integration_service import cleanup_tax_integration_service
            await cleanup_tax_integration_service()
        except Exception:
            pass

app = FastAPI(
    title="Invoice API",
    description="API for the Invoice Management System",
    version="1.0.0",
    lifespan=app_lifespan,
    redirect_slashes=False  # Disable automatic trailing slash redirects
)

# Serve static files (e.g., for company logos)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/api/v1/static", StaticFiles(directory=static_dir), name="api_static")

# CORS Middleware (permissive for development)
# Check multiple environment indicators for debug mode
debug_env = os.getenv("DEBUG", "True").lower()
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
            content={"detail": f"Internal server error: {str(e)}"}
        )

# Add tenant context middleware (function-based)
from middleware.tenant_context_middleware import tenant_context_middleware
app.middleware('http')(tenant_context_middleware)

# Add external API authentication middleware
from middleware.external_api_auth_middleware import ExternalAPIAuthMiddleware
app.add_middleware(ExternalAPIAuthMiddleware)

# Include routers with v1 API versioning
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tenant.router, prefix="/api/v1")
app.include_router(super_admin.router, prefix="/api/v1")  # Add super admin router
app.include_router(clients.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(expenses.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(email.router, prefix="/api/v1")
app.include_router(currency.router, prefix="/api/v1")
app.include_router(crm.router, prefix="/api/v1")
app.include_router(discount_rules.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1") # Include the new AI router
app.include_router(ai_config.router, prefix="/api/v1") # Include the new AI config router
app.include_router(audit_log.router, prefix="/api/v1") # Include the new audit log router
app.include_router(slack_simplified.router, prefix="/api/v1") # Include the new simplified Slack router
app.include_router(notifications.router, prefix="/api/v1") # Include the new notifications router
app.include_router(analytics.router, prefix="/api/v1") # Include the new analytics router
app.include_router(pdf_processor.router, prefix="/api/v1") # Include the new PDF processor router
app.include_router(statements.router, prefix="/api/v1")
app.include_router(tax_integration.router, prefix="/api/v1") # Include the new tax integration router
app.include_router(reports.router, prefix="/api/v1") # Include the new reports router
app.include_router(attachments.router, prefix="/api/v1") # Include the new attachments router
app.include_router(search.router, prefix="/api/v1") # Include the new search router
app.include_router(external_api_auth.router, prefix="/api/v1") # Include the new external API auth router
app.include_router(external_transactions.router, prefix="/api/v1") # Include the new external transactions router
app.include_router(external_api.router) # Include the new external API router (no prefix as it has its own)
app.include_router(inventory.router, prefix="/api/v1") # Include the new inventory router
app.include_router(inventory_attachments.router, prefix="/api/v1") # Include the inventory attachments router
app.include_router(approvals.router, prefix="/api/v1") # Include the new approvals router
app.include_router(approval_reports.router, prefix="/api/v1") # Include the new approval reports router
app.include_router(organization_join.router, prefix="/api/v1") # Include the new organization join router
app.include_router(reminders.router, prefix="/api/v1/reminders", tags=["reminders"]) # Include the new reminders router
app.include_router(files.router, prefix="/api/v1") # Include the new files router
app.include_router(cloud_storage.router, prefix="/api/v1") # Include the new cloud storage router

@app.get("/")
def read_root():
    return {"message": "Welcome to the Invoice API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Moved shutdown handling to lifespan above to avoid deprecation warnings

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
