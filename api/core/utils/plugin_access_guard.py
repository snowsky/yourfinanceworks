"""
Dependency helpers for cross-plugin access enforcement.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.models.database import get_master_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.services.plugin_access_control_service import PluginAccessControlService
from core.utils.plugin_context import set_current_plugin_id
from plugins.loader import plugin_loader


def _normalize_plugin_id(plugin_id: str) -> str:
    return plugin_id.strip().lower().replace("_", "-")


def _access_type_from_method(method: str) -> str:
    return "read" if method.upper() in {"GET", "HEAD", "OPTIONS"} else "write"


def require_plugin_access(target_plugin_id: str):
    """
    Require per-user approval when one plugin calls another plugin's API.

    Enforcement is activated only when the request includes `X-Plugin-Caller`.
    Direct user requests without this header are unaffected.
    """
    normalized_target = _normalize_plugin_id(target_plugin_id)

    async def _dependency(
        request: Request,
        master_db: Session = Depends(get_master_db),
        current_user: MasterUser = Depends(get_current_user),
    ) -> None:
        source_header = request.headers.get("X-Plugin-Caller")
        if not source_header:
            return

        source_plugin = _normalize_plugin_id(source_header)
        if source_plugin == normalized_target:
            return

        valid_plugins = plugin_loader.get_valid_plugin_ids()
        if source_plugin not in valid_plugins:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_PLUGIN_CALLER",
                    "message": f"Unknown plugin caller '{source_plugin}'",
                },
            )

        if normalized_target not in valid_plugins:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "PLUGIN_GUARD_CONFIGURATION_ERROR",
                    "message": f"Target plugin '{normalized_target}' is not registered",
                },
            )

        access_service = PluginAccessControlService(master_db)
        decision = access_service.check_or_request_access(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            source_plugin=source_plugin,
            target_plugin=normalized_target,
            access_type=_access_type_from_method(request.method),
            reason=f"{request.method} {request.url.path}",
            requested_path=request.url.path,
        )

        if decision.granted:
            # Set the persistent context for database isolation
            set_current_plugin_id(source_plugin)
            return

        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail={
                "error_code": "PLUGIN_ACCESS_APPROVAL_REQUIRED",
                "message": (
                    f"Plugin '{source_plugin}' needs your approval to access "
                    f"'{normalized_target}' plugin data."
                ),
                "request": decision.request,
            },
        )

    return _dependency
