"""DocVault plugin registration."""


def register_plugin(app, mcp_registry=None, feature_gate=None):
    from .router import router

    app.include_router(router, prefix="/api/v1/docvault", tags=["docvault"])
    return {
        "name": "docvault",
        "version": "1.0.0",
        "routes": ["/api/v1/docvault"],
    }
