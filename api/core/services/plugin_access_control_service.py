"""
Cross-plugin access control service.

Stores per-tenant, per-user plugin access grants and requests inside
TenantPluginSettings.plugin_config under the `cross_plugin_access` key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4
import copy

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.models.models import TenantPluginSettings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


@dataclass
class PluginAccessDecision:
    granted: bool
    request: Optional[dict[str, Any]] = None
    grant: Optional[dict[str, Any]] = None


class PluginAccessControlService:
    CONFIG_KEY = "cross_plugin_access"

    def __init__(self, db: Session) -> None:
        self.db = db

    def check_or_request_access(
        self,
        *,
        tenant_id: int,
        user_id: int,
        source_plugin: str,
        target_plugin: str,
        access_type: str,
        reason: Optional[str] = None,
        requested_path: Optional[str] = None,
    ) -> PluginAccessDecision:
        if source_plugin == target_plugin:
            return PluginAccessDecision(granted=True, grant={"implicit_self_access": True})

        settings = self._get_or_create_settings(tenant_id)
        config = self._load_config(settings)
        state = config[self.CONFIG_KEY]

        grant = self._find_grant(
            state["grants"],
            source_plugin=source_plugin,
            target_plugin=target_plugin,
            access_type=access_type,
            user_id=user_id,
            requested_path=requested_path,
        )
        if grant:
            return PluginAccessDecision(granted=True, grant=grant)

        pending = self._find_pending_request(
            state["requests"],
            source_plugin=source_plugin,
            target_plugin=target_plugin,
            access_type=access_type,
            user_id=user_id,
        )
        if pending:
            return PluginAccessDecision(granted=False, request=pending)

        request_obj = {
            "id": str(uuid4()),
            "source_plugin": source_plugin,
            "target_plugin": target_plugin,
            "access_type": access_type,
            "status": "pending",
            "requested_by_user_id": user_id,
            "requested_at": _utc_now_iso(),
            "reason": reason,
            "requested_path": requested_path,
        }
        state["requests"].append(request_obj)
        self._save_config(settings, config)

        return PluginAccessDecision(granted=False, request=request_obj)

    def list_requests(
        self,
        *,
        tenant_id: int,
        status_filter: Optional[str] = None,
        requested_by_user_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        settings = self._get_or_create_settings(tenant_id)
        config = self._load_config(settings)
        state = config[self.CONFIG_KEY]

        requests: list[dict[str, Any]] = list(state["requests"])
        if status_filter:
            requests = [r for r in requests if str(r.get("status")) == status_filter]
        if requested_by_user_id is not None:
            requests = [r for r in requests if r.get("requested_by_user_id") == requested_by_user_id]

        requests.sort(key=lambda r: str(r.get("requested_at") or ""), reverse=True)
        return requests

    def list_grants(
        self,
        *,
        tenant_id: int,
        user_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        settings = self._get_or_create_settings(tenant_id)
        config = self._load_config(settings)
        state = config[self.CONFIG_KEY]
        grants: list[dict[str, Any]] = list(state["grants"])
        if user_id is not None:
            grants = [g for g in grants if g.get("granted_to_user_id") == user_id]
        grants.sort(key=lambda g: str(g.get("granted_at") or ""), reverse=True)
        return grants

    def approve_request(
        self,
        *,
        tenant_id: int,
        request_id: str,
        resolver_user_id: int,
        enforce_owner: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        settings = self._get_or_create_settings(tenant_id)
        config = self._load_config(settings)
        state = config[self.CONFIG_KEY]

        request_obj = self._find_request_by_id(state["requests"], request_id)
        if request_obj is None:
            raise ValueError("Request not found")

        if enforce_owner and request_obj.get("requested_by_user_id") != resolver_user_id:
            raise PermissionError("You can only approve your own plugin access requests")

        status = str(request_obj.get("status") or "")
        if status == "approved":
            existing_grant = self._find_grant_by_id(state["grants"], request_obj.get("grant_id"))
            if existing_grant is None:
                raise ValueError("Approved request has no associated grant")
            return request_obj, existing_grant
        if status != "pending":
            raise ValueError(f"Cannot approve a request with status '{status}'")

        grant = self._find_grant(
            state["grants"],
            source_plugin=str(request_obj.get("source_plugin") or ""),
            target_plugin=str(request_obj.get("target_plugin") or ""),
            access_type=str(request_obj.get("access_type") or "read"),
            user_id=int(request_obj.get("requested_by_user_id")),
        )
        if grant is None:
            grant = {
                "id": str(uuid4()),
                "source_plugin": request_obj.get("source_plugin"),
                "target_plugin": request_obj.get("target_plugin"),
                "access_type": request_obj.get("access_type"),
                "granted_to_user_id": request_obj.get("requested_by_user_id"),
                "granted_by_user_id": resolver_user_id,
                "granted_at": _utc_now_iso(),
                "request_id": request_id,
                "allowed_paths": [request_obj.get("requested_path") or "*"],
            }
            state["grants"].append(grant)

        request_obj["status"] = "approved"
        request_obj["resolved_by_user_id"] = resolver_user_id
        request_obj["resolved_at"] = _utc_now_iso()
        request_obj["grant_id"] = grant["id"]
        self._save_config(settings, config)

        return request_obj, grant

    def deny_request(
        self,
        *,
        tenant_id: int,
        request_id: str,
        resolver_user_id: int,
        enforce_owner: bool,
    ) -> dict[str, Any]:
        settings = self._get_or_create_settings(tenant_id)
        config = self._load_config(settings)
        state = config[self.CONFIG_KEY]

        request_obj = self._find_request_by_id(state["requests"], request_id)
        if request_obj is None:
            raise ValueError("Request not found")

        if enforce_owner and request_obj.get("requested_by_user_id") != resolver_user_id:
            raise PermissionError("You can only deny your own plugin access requests")

        status = str(request_obj.get("status") or "")
        if status == "denied":
            return request_obj
        if status != "pending":
            raise ValueError(f"Cannot deny a request with status '{status}'")

        request_obj["status"] = "denied"
        request_obj["resolved_by_user_id"] = resolver_user_id
        request_obj["resolved_at"] = _utc_now_iso()
        self._save_config(settings, config)

        return request_obj

    def revoke_grant(
        self,
        *,
        tenant_id: int,
        grant_id: str,
    ) -> None:
        settings = self._get_or_create_settings(tenant_id)
        config = self._load_config(settings)
        state = config[self.CONFIG_KEY]

        grants = state["grants"]
        grant_index = -1
        request_id = None

        for i, g in enumerate(grants):
            if g.get("id") == grant_id:
                grant_index = i
                request_id = g.get("request_id")
                break

        if grant_index == -1:
            raise ValueError("Grant not found")

        # Remove the grant
        grants.pop(grant_index)

        # Also update the associated request if it exists
        if request_id:
            for r in state["requests"]:
                if r.get("id") == request_id:
                    r["status"] = "revoked"
                    r["resolved_at"] = _utc_now_iso()
                    break

        self._save_config(settings, config)

    def ensure_required_access(
        self,
        *,
        tenant_id: int,
        source_plugin: str,
        required_access: list[dict[str, Any]],
        resolver_user_id: int,
    ) -> None:
        """
        Automatically approve access requests for a list of requirements.
        Useful when enabling a plugin that has declared its needs upfront.
        """
        if not required_access:
            return

        settings = self._get_or_create_settings(tenant_id)
        config = self._load_config(settings)
        state = config[self.CONFIG_KEY]

        any_changed = False
        for req in required_access:
            target_plugin = req.get("target_plugin")
            access_type = req.get("access_type", "read")
            reason = req.get("reason")

            if not target_plugin:
                continue

            # Check if grant already exists for this specific user
            existing = self._find_grant(
                state["grants"],
                source_plugin=source_plugin,
                target_plugin=target_plugin,
                access_type=access_type,
                user_id=resolver_user_id,
            )
            if existing:
                continue

            # Create and approve immediately
            request_id = str(uuid4())
            grant_id = str(uuid4())

            # 1. Add Request
            request_obj = {
                "id": request_id,
                "source_plugin": source_plugin,
                "target_plugin": target_plugin,
                "access_type": access_type,
                "status": "approved",
                "requested_by_user_id": resolver_user_id,
                "requested_at": _utc_now_iso(),
                "reason": reason,
                "resolved_by_user_id": resolver_user_id,
                "resolved_at": _utc_now_iso(),
                "grant_id": grant_id,
            }
            state["requests"].append(request_obj)

            # 2. Add Grant
            grant_obj = {
                "id": grant_id,
                "source_plugin": source_plugin,
                "target_plugin": target_plugin,
                "access_type": access_type,
                "granted_to_user_id": resolver_user_id,
                "granted_by_user_id": resolver_user_id,
                "granted_at": _utc_now_iso(),
                "request_id": request_id,
                "allowed_paths": req.get("allowed_paths", ["*"]),
            }
            state["grants"].append(grant_obj)
            any_changed = True

        if any_changed:
            self._save_config(settings, config)

    def _get_or_create_settings(self, tenant_id: int) -> TenantPluginSettings:
        settings = (
            self.db.query(TenantPluginSettings)
            .filter(TenantPluginSettings.tenant_id == tenant_id)
            .first()
        )
        if settings:
            return settings

        settings = TenantPluginSettings(
            tenant_id=tenant_id,
            enabled_plugins=[],
            plugin_config={},
        )
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def _load_config(self, settings: TenantPluginSettings) -> dict[str, Any]:
        """Load and return a deep copy of the configuration to ensure safe modification."""
        config = copy.deepcopy(settings.plugin_config) or {}

        if self.CONFIG_KEY not in config:
            config[self.CONFIG_KEY] = {"requests": [], "grants": []}
        else:
            state = config[self.CONFIG_KEY]
            if not isinstance(state, dict):
                state = {"requests": [], "grants": []}
                config[self.CONFIG_KEY] = state
            if "requests" not in state or not isinstance(state["requests"], list):
                state["requests"] = []
            if "grants" not in state or not isinstance(state["grants"], list):
                state["grants"] = []

        return config

    def _save_config(self, settings: TenantPluginSettings, config: dict[str, Any]) -> None:
        """Explicitly re-assign the configuration to trigger SQLAlchemy state change."""
        settings.plugin_config = config
        self._persist_settings(settings)

    def _persist_settings(self, settings: TenantPluginSettings) -> None:
        settings.updated_at = _utc_now()
        flag_modified(settings, "plugin_config")
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)

    @staticmethod
    def _find_grant(
        grants: list[dict[str, Any]],
        *,
        source_plugin: str,
        target_plugin: str,
        access_type: str,
        user_id: int,
        requested_path: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        for grant in reversed(grants):
            if grant.get("source_plugin") != source_plugin:
                continue
            if grant.get("target_plugin") != target_plugin:
                continue
            if grant.get("granted_to_user_id") != user_id:
                continue

            grant_access = str(grant.get("access_type") or "")
            if grant_access not in {access_type, "*"}:
                continue

            # Path-level scoping check
            if requested_path:
                allowed_paths = grant.get("allowed_paths", ["*"])
                if not any(PluginAccessControlService._path_matches(requested_path, p) for p in allowed_paths):
                    continue

            return grant
        return None

    @staticmethod
    def _path_matches(requested: str, pattern: str) -> bool:
        """
        Simple path matching with wildcard support.
        - '*' matches everything
        - '/api/v1/*' matches anything starting with /api/v1/
        - exact matches are always supported
        """
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return requested.startswith(prefix)
        return requested == pattern

    @staticmethod
    def _find_pending_request(
        requests: list[dict[str, Any]],
        *,
        source_plugin: str,
        target_plugin: str,
        access_type: str,
        user_id: int,
    ) -> Optional[dict[str, Any]]:
        for request in reversed(requests):
            if request.get("status") != "pending":
                continue
            if request.get("requested_by_user_id") != user_id:
                continue
            if request.get("source_plugin") != source_plugin:
                continue
            if request.get("target_plugin") != target_plugin:
                continue
            if request.get("access_type") != access_type:
                continue
            return request
        return None

    @staticmethod
    def _find_request_by_id(
        requests: list[dict[str, Any]],
        request_id: str,
    ) -> Optional[dict[str, Any]]:
        for request in requests:
            if request.get("id") == request_id:
                return request
        return None

    @staticmethod
    def _find_grant_by_id(
        grants: list[dict[str, Any]],
        grant_id: Any,
    ) -> Optional[dict[str, Any]]:
        if not grant_id:
            return None
        for grant in grants:
            if grant.get("id") == grant_id:
                return grant
        return None
