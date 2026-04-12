from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import logging

from core.utils.plugin_context import set_current_plugin_id, reset_current_plugin_id
from plugins.loader import plugin_loader

logger = logging.getLogger(__name__)

class PluginContextMiddleware(BaseHTTPMiddleware):
    """
    Automatic context enforcement for plugin routes.

    This middleware detects if a request is targeting a specific plugin
    (based on the URL prefix) and automatically sets the plugin context
    with 'Lockdown Mode' enabled.
    """
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        plugin_id = None

        # 1. Broad prefix detection
        # e.g. /api/v1/investments/... -> investments
        route_map = plugin_loader.get_plugin_route_map()
        for prefix, p_id in route_map.items():
            if path.startswith(prefix):
                plugin_id = p_id
                break

        # 2. X-Plugin-Caller Header detection
        # (This is for cross-plugin internal calls)
        caller_header = request.headers.get("X-Plugin-Caller")
        if caller_header:
            plugin_id = caller_header.strip().lower().replace("_", "-")

        if plugin_id:
            # Set the context and LOCK it.
            # This prevents the plugin code from spoofing its identity later.
            token = set_current_plugin_id(plugin_id, lock=True)
            try:
                logger.debug("Routing request to plugin '%s' (Lockdown Mode ON)", plugin_id)
                response = await call_next(request)
                return response
            finally:
                reset_current_plugin_id(token)
        else:
            # No plugin context (Core request)
            return await call_next(request)
