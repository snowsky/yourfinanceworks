"""
Currency Rates Plugin — __init__.py
=====================================

Demonstrates the minimal structure required for a YourFinanceWORKS plugin:
  - A `register_plugin(app, ...)` function (the standard entry point)
  - Include the plugin router with a prefix
  - Return a metadata dict

No database models are needed for this plugin.

Third-party service:
  This plugin fetches live exchange rates from https://open.er-api.com (free,
  no API key required). If the request fails the router falls back to a set of
  static hardcoded rates so the plugin always works, even offline.
"""


def register_plugin(app, mcp_registry=None, feature_gate=None):
    """
    Register the currency-rates plugin with the FastAPI application.

    Parameters
    ----------
    app : FastAPI
        The main application instance.
    mcp_registry : optional
        MCP provider registry (not used by this plugin).
    feature_gate : optional
        Feature gate helper (not used by this plugin).

    Returns
    -------
    dict
        Plugin metadata consumed by the loader for logging.
    """
    from .router import router

    app.include_router(router, prefix="/api/v1", tags=["currency-rates"])

    return {
        "name": "currency-rates",
        "version": "1.0.0",
        "routes": ["/api/v1/currency-rates"],
    }
