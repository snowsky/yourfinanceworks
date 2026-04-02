from __future__ import annotations

from fastapi import FastAPI
from .routers import surveys, public

def register_plugin(app: FastAPI, **kwargs):
    """
    Register the Surveys plugin with the main FastAPI application.
    """
    # Management API (Authenticated)
    app.include_router(
        surveys.router,
        prefix="/api/v1/surveys",
        tags=["surveys"]
    )

    # Public API (No authentication required)
    app.include_router(
        public.router,
        prefix="/api/v1/surveys/public",
        tags=["surveys-public"]
    )

    return {
        "name": "Surveys",
        "version": "1.0.0",
        "routes": [
            "/api/v1/surveys",
            "/api/v1/surveys/public"
        ]
    }
