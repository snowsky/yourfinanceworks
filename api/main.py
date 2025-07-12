from fastapi import FastAPI, Request, HTTPException
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import logging

from routers import (
    auth,
    clients,
    invoices,
    payments,
    currency,
    settings,
    tenant,
    discount_rules,
    crm,
    email,
    ai, # Add the new AI router
    ai_config # Add the new AI config router
)
from models.database import engine
from models import models
from cors_middleware import CustomCORSMiddleware
from db_init import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
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

app = FastAPI(
    title="Invoice API",
    description="API for the Invoice Management System",
    version="1.0.0"
)

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

# Add our custom CORS middleware
app.add_middleware(CustomCORSMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers with v1 API versioning
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tenant.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(email.router, prefix="/api/v1")
app.include_router(currency.router, prefix="/api/v1")
app.include_router(crm.router, prefix="/api/v1")
app.include_router(discount_rules.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1") # Include the new AI router
app.include_router(ai_config.router, prefix="/api/v1") # Include the new AI config router

@app.get("/")
def read_root():
    return {"message": "Welcome to the Invoice API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
