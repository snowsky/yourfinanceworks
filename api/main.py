from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import logging
from fastapi.staticfiles import StaticFiles
import os

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
    bank_statements
)
from models.database import engine
from models import models

from db_init import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)  # Ensure INFO logs are shown
logger = logging.getLogger(__name__)

# Initialize database (create tables and populate initial data)
try:
    logger.info("Starting database initialization...")
    init_db()
    logger.info("Database initialization completed successfully.")
except Exception as e:
    logger.error(f"Database initialization failed: {str(e)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    # Don't raise the exception to allow the app to start even if DB init fails

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Startup logic can go here if needed
    try:
        yield
    finally:
        # Shutdown: flush Kafka producers
        try:
            from services.ocr_service import flush_all_producers
            flush_all_producers(10.0)
        except Exception:
            pass

app = FastAPI(
    title="Invoice API",
    description="API for the Invoice Management System",
    version="1.0.0",
    lifespan=app_lifespan
)

# CORS Middleware (tightened with env-driven configuration)
# ALLOWED_ORIGINS can be a comma-separated list, e.g. "http://localhost:8080,https://app.example.com"
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
debug_mode = os.getenv("DEBUG", "False").lower() == "true"

if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    # In DEBUG, fall back to permissive wildcard. In production, default to no origins.
    allowed_origins = ["*"] if debug_mode else []

# Credentials cannot be used with wildcard origins per CORS spec
allow_credentials = os.getenv("ALLOW_CORS_CREDENTIALS", "False").lower() == "true"
if allow_credentials and (not allowed_origins or "*" in allowed_origins):
    # Override to safe default when wildcard is used
    allow_credentials = False

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

# Serve static files (e.g., for company logos)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
app.include_router(bank_statements.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Invoice API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Moved shutdown handling to lifespan above to avoid deprecation warnings

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
