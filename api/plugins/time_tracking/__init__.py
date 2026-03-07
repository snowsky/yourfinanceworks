"""
Time Tracking Plugin for YourFinanceWORKS

Self-contained plugin for project management and time tracking.
Follows the same plugin architecture as the investments plugin.

Features:
- Project creation linked to clients
- Task management with hourly rates or fixed costs
- Time entry logging (manual or live timer)
- Expense tagging to projects
- Unbilled items review
- Invoice generation from unbilled items
- Monthly time report export (.xlsx)
"""

from fastapi import APIRouter, Depends


def register_time_tracking_plugin(app, mcp_registry=None, feature_gate=None):
    """
    Register the time tracking plugin with the main application.

    Args:
        app: FastAPI application instance
        mcp_registry: MCP provider registry (optional, not used)
        feature_gate: Feature gate service (optional)

    Returns:
        dict: Plugin metadata
    """
    from .router import projects_router, time_entries_router
    from core.utils.plugin_access_guard import require_plugin_access

    # Register project routes under /api/v1/projects
    app.include_router(
        projects_router,
        prefix="/api/v1/projects",
        tags=["projects"],
        dependencies=[Depends(require_plugin_access("time-tracking"))],
    )

    # Register time entry routes under /api/v1/time-entries
    app.include_router(
        time_entries_router,
        prefix="/api/v1/time-entries",
        tags=["time-entries"],
        dependencies=[Depends(require_plugin_access("time-tracking"))],
    )

    # Register MCP provider for AI assistant (if available)
    if mcp_registry:
        try:
            from .mcp.time_tracking_provider import TimeTrackingMCPProvider
            mcp_registry.register_provider("time_tracking", TimeTrackingMCPProvider())
        except ImportError:
            # MCP provider is optional
            pass

    return {
        "name": "time-tracking",
        "version": "1.0.0",
        "license_tier": "agpl",
        "routes": ["/api/v1/projects", "/api/v1/time-entries"],
        "mcp_providers": ["time_tracking"] if mcp_registry else [],
        "description": "Project management and time tracking",
    }
