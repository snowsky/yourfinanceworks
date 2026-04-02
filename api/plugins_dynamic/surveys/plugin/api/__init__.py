"""
YFW plugin entry point.

Called by the YourFinanceWORKS plugin loader at startup:
    register_plugin(app, mcp_registry=..., feature_gate=...)
"""
try:
    from ...shared.database import create_tables
    from ...shared.routers import public_router, surveys_router
except (ImportError, ValueError):
    from shared.database import create_tables
    from shared.routers import public_router, surveys_router

PLUGIN_PREFIX = "/api/v1/surveys"
PUBLIC_PREFIX = "/api/v1/surveys/public"


def register_plugin(app, mcp_registry=None, feature_gate=None):
    """Mount survey routes onto the host YFW FastAPI app."""
    create_tables()

    app.include_router(surveys_router, prefix=PLUGIN_PREFIX, tags=["surveys"])
    app.include_router(public_router, prefix=PUBLIC_PREFIX, tags=["surveys-public"])

    return {
        "name": "surveys",
        "version": "1.0.0",
        "routes": [PLUGIN_PREFIX, PUBLIC_PREFIX],
    }
