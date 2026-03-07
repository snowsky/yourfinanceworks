"""
Investment Management Plugin for YourFinanceWORKS

This plugin provides comprehensive investment portfolio tracking, performance analytics,
and tax reporting capabilities. It's designed as a self-contained commercial feature
that integrates with the existing multi-tenant architecture.

Features:
- Portfolio management (TAXABLE, RETIREMENT, BUSINESS)
- Holdings tracking with cost basis
- Transaction recording (BUY, SELL, DIVIDEND, etc.)
- Performance analytics (inception-to-date)
- Asset allocation analysis
- Dividend tracking
- Tax data export
- MCP assistant integration

License: Commercial tier required
"""

from fastapi import APIRouter, Depends
from core.utils.feature_gate import require_feature

def require_investments_or_any_license():
    """
    Allow investments plugin access if:
    - Any commercial license is active, OR
    - Specific 'investments' feature is present in the license

    This allows all paying customers to access investment features,
    not just those with the specific 'investments' feature flag.
    """
    from core.utils.license_service import get_license_service

    try:
        license_service = get_license_service()

        # Check if any commercial license is active
        if license_service.is_license_active():
            # Any active commercial license grants access
            return True
    except Exception:
        # If license service fails, fall back to feature check
        pass

    # Otherwise require specific investments feature
    return require_feature("investments", tier="commercial")

def register_investment_plugin(app, mcp_registry=None, feature_gate=None):
    """
    Register the investment management plugin with the main application.
    This is a COMMERCIAL feature requiring a commercial license.

    Args:
        app: FastAPI application instance
        mcp_registry: MCP provider registry (optional)
        feature_gate: Feature gate service (optional)

    Returns:
        dict: Plugin metadata
    """
    from .router import investment_router
    from .error_handlers import create_investment_exception_handler
    from .exceptions import InvestmentError
    from core.utils.plugin_access_guard import require_plugin_access

    # Register exception handler
    app.add_exception_handler(InvestmentError, create_investment_exception_handler())

    # Register API routes under /api/v1/investments
    # All routes protected by commercial license requirement
    if feature_gate:
        # Use custom dependency that allows any commercial license
        app.include_router(
            investment_router,
            prefix="/api/v1/investments",
            tags=["investments"],
            dependencies=[
                Depends(require_plugin_access("investments")),
                Depends(require_investments_or_any_license),
            ],
        )
    else:
        # For development/testing without feature gate
        app.include_router(
            investment_router,
            prefix="/api/v1/investments",
            tags=["investments"],
            dependencies=[Depends(require_plugin_access("investments"))],
        )

    # Register MCP provider for AI assistant (if available)
    if mcp_registry:
        try:
            from .mcp.investment_provider import InvestmentMCPProvider
            mcp_registry.register_provider("investments", InvestmentMCPProvider())
        except ImportError:
            # MCP provider is optional
            pass

    return {
        "name": "investment-management",
        "version": "1.0.0",
        "license_tier": "commercial",
        "routes": ["/api/v1/investments"],
        "mcp_providers": ["investments"] if mcp_registry else [],
        "description": "Investment portfolio tracking and analytics"
    }

# Standard alias for the PluginLoader (preferred convention)
register_plugin = register_investment_plugin
