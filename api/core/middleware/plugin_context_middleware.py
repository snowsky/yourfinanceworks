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
        # This identifies the source plugin for require_plugin_access(), but it
        # should not replace the route owner for DB isolation. A call from
        # docvault to /api/v1/investments/... must execute under investments'
        # table permissions after the access guard approves the caller.
        #
        # The header is attacker-controllable on any unauthenticated reach to
        # the API, so we validate it against the discovered-plugin set before
        # using it as the isolation context. ``require_plugin_access`` does
        # the same check, but only on routes that opt into the dependency —
        # routes without it would otherwise run under an unrecognized context.
        caller_header = request.headers.get("X-Plugin-Caller")
        if caller_header and not plugin_id:
            normalized_caller = caller_header.strip().lower().replace("_", "-")
            if normalized_caller in plugin_loader.get_valid_plugin_ids():
                plugin_id = normalized_caller
            else:
                logger.warning(
                    "Ignoring X-Plugin-Caller='%s' on %s: not a discovered plugin",
                    caller_header, path,
                )

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
