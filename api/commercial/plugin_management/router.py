"""
Plugin management router for handling plugin settings and configuration.
Commercial feature - requires plugin_management license.
"""
import os
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional
from datetime import datetime, timezone

from core.models.models import TenantPluginSettings, MasterUser
from core.models.database import get_master_db
from core.routers.auth import get_current_user
from core.services.plugin_access_control_service import PluginAccessControlService
from core.services.tenant_database_manager import tenant_db_manager
from core.models.models_per_tenant import Settings as TenantSetting
from plugins.loader import plugin_loader
from commercial.plugin_management.services.git_installer import (
    start_install,
    run_install,
    get_job,
    get_install_meta,
    uninstall_plugin,
)


router = APIRouter(prefix="/plugins", tags=["plugins"])


def _valid_plugins() -> set[str]:
    """Return the set of valid plugin IDs discovered on disk."""
    return plugin_loader.get_valid_plugin_ids()


def _normalize_plugin_id(plugin_id: str) -> str:
    return plugin_id.strip().lower().replace("_", "-")


def _is_admin(user: MasterUser) -> bool:
    return user.role in {"admin", "superuser"}


def _validate_plugin_id(plugin_id: str, field_name: str = "plugin_id") -> str:
    normalized = _normalize_plugin_id(plugin_id)
    if normalized not in _valid_plugins():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: {plugin_id}",
        )
    return normalized


@router.get("/registry")
async def get_plugin_registry():
    """
    Return metadata for all plugins discovered on disk.
    This is public metadata — no authentication required.
    Used by the frontend to populate the plugin list dynamically.
    """
    return {"plugins": plugin_loader.get_registry()}


@router.post("/access/check")
async def check_cross_plugin_access(
    payload: dict,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Check whether the current user already approved cross-plugin access.
    If not approved, a pending request is created and returned.
    """
    source_plugin = _validate_plugin_id(payload.get("source_plugin", ""), "source_plugin")
    target_plugin = _validate_plugin_id(payload.get("target_plugin", ""), "target_plugin")
    access_type = str(payload.get("access_type", "read")).lower()
    if access_type not in {"read", "write"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="access_type must be either 'read' or 'write'",
        )

    access_service = PluginAccessControlService(db)
    decision = access_service.check_or_request_access(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        source_plugin=source_plugin,
        target_plugin=target_plugin,
        access_type=access_type,
        reason=payload.get("reason"),
        requested_path=payload.get("requested_path"),
    )

    return {
        "granted": decision.granted,
        "requires_approval": not decision.granted,
        "grant": decision.grant,
        "request": decision.request,
    }


@router.get("/access-requests")
async def list_access_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    mine_only: bool = Query(True),
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    List cross-plugin access requests for this tenant.
    Non-admin users can only list their own requests.
    """
    if not mine_only and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list all access requests",
        )

    requested_by_user_id = current_user.id if mine_only or not _is_admin(current_user) else None
    access_service = PluginAccessControlService(db)
    requests = access_service.list_requests(
        tenant_id=current_user.tenant_id,
        status_filter=status_filter,
        requested_by_user_id=requested_by_user_id,
    )
    return {"requests": requests}


@router.get("/access-grants")
async def list_access_grants(
    mine_only: bool = Query(True),
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    List cross-plugin access grants for this tenant.
    Non-admin users can only list their own grants.
    """
    if not mine_only and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list all access grants",
        )

    granted_user_id = current_user.id if mine_only or not _is_admin(current_user) else None
    access_service = PluginAccessControlService(db)
    grants = access_service.list_grants(
        tenant_id=current_user.tenant_id,
        user_id=granted_user_id,
    )
    return {"grants": grants}


@router.delete("/access-grants/{grant_id}")
async def revoke_access_grant(
    grant_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Revoke an active cross-plugin access grant.
    Only administrators can revoke grants.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can revoke access grants",
        )

    access_service = PluginAccessControlService(db)
    try:
        access_service.revoke_grant(
            tenant_id=current_user.tenant_id,
            grant_id=grant_id,
        )
        return {"message": "Access grant revoked successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/access-requests/{request_id}/approve")
async def approve_access_request(
    request_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Approve a pending cross-plugin access request.
    Admin users can approve any request; others can approve their own.
    """
    access_service = PluginAccessControlService(db)
    try:
        request_obj, grant = access_service.approve_request(
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            resolver_user_id=current_user.id,
            enforce_owner=not _is_admin(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {
        "message": "Access request approved",
        "request": request_obj,
        "grant": grant,
    }


@router.post("/access-requests/{request_id}/deny")
async def deny_access_request(
    request_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Deny a pending cross-plugin access request.
    Admin users can deny any request; others can deny their own.
    """
    access_service = PluginAccessControlService(db)
    try:
        request_obj = access_service.deny_request(
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            resolver_user_id=current_user.id,
            enforce_owner=not _is_admin(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {
        "message": "Access request denied",
        "request": request_obj,
    }


@router.get("/settings")
async def get_plugin_settings(
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get enabled plugins for the current tenant.
    Returns list of enabled plugin IDs.
    """
    tenant_id = current_user.tenant_id

    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).first()

    if not settings:
        # Create default settings if they don't exist
        settings = TenantPluginSettings(
            tenant_id=tenant_id,
            enabled_plugins=[]
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return {
        "tenant_id": tenant_id,
        "enabled_plugins": settings.enabled_plugins or [],
        "updated_at": settings.updated_at
    }


@router.post("/settings")
async def update_plugin_settings(
    payload: dict,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Update enabled plugins for the current tenant.
    Requires admin role.

    Payload:
    {
        "enabled_plugins": ["investments", "reports"]
    }
    """
    tenant_id = current_user.tenant_id

    # Check if user is admin in the tenant
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage plugin settings"
        )

    enabled_plugins = payload.get("enabled_plugins", [])

    # Validate that enabled_plugins is a list
    if not isinstance(enabled_plugins, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="enabled_plugins must be a list of plugin IDs"
        )

    # Validate plugin IDs against discovered plugins
    valid = _valid_plugins()
    invalid_plugins = [p for p in enabled_plugins if p not in valid]

    if invalid_plugins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plugin IDs: {', '.join(invalid_plugins)}"
        )

    # Get or create settings with row lock to prevent race conditions
    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).with_for_update().first()

    if not settings:
        settings = TenantPluginSettings(
            tenant_id=tenant_id,
            enabled_plugins=enabled_plugins
        )
        db.add(settings)
    else:
        settings.enabled_plugins = enabled_plugins
        settings.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(settings)

    # Trigger schema migration to ensure tables exist for enabled plugins
    if enabled_plugins:
        try:
            tenant_db_manager.migrate_tenant_schema(tenant_id)
        except Exception as e:
            # Log but don't fail the request - tables might already exist or migration might be partial
            import logging
            logging.getLogger(__name__).error(f"Failed to migrate schema for tenant {tenant_id} on plugin enablement: {e}")

    return {
        "tenant_id": tenant_id,
        "enabled_plugins": settings.enabled_plugins,
        "updated_at": settings.updated_at,
        "message": "Plugin settings updated successfully"
    }


@router.post("/settings/{plugin_id}/enable")
async def enable_plugin(
    plugin_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Enable a specific plugin for the current tenant.
    Requires admin role.
    """
    tenant_id = current_user.tenant_id

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage plugin settings"
        )

    # Validate plugin ID
    if plugin_id not in _valid_plugins():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plugin ID: {plugin_id}"
        )

    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).with_for_update().first()

    if not settings:
        settings = TenantPluginSettings(
            tenant_id=tenant_id,
            enabled_plugins=[plugin_id]
        )
        db.add(settings)
    else:
        if plugin_id not in settings.enabled_plugins:
            # Create a new list to ensure SQLAlchemy detects the change
            settings.enabled_plugins = list(settings.enabled_plugins) + [plugin_id]
            settings.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(settings)

    # Automatically grant any required access defined in the plugin manifest
    manifest = next((p for p in plugin_loader.get_registry() if p.get("name") == plugin_id), None)
    if manifest and "required_access" in manifest:
        access_service = PluginAccessControlService(db)
        access_service.ensure_required_access(
            tenant_id=tenant_id,
            source_plugin=plugin_id,
            required_access=manifest["required_access"],
            resolver_user_id=current_user.id
        )

    # Trigger schema migration to ensure tables exist for the enabled plugin
    try:
        tenant_db_manager.migrate_tenant_schema(tenant_id)
    except Exception as e:
        # Log but don't fail the request
        import logging
        logging.getLogger(__name__).error(f"Failed to migrate schema for tenant {tenant_id} on plugin '{plugin_id}' enable: {e}")

    return {
        "tenant_id": tenant_id,
        "enabled_plugins": settings.enabled_plugins,
        "message": f"Plugin '{plugin_id}' enabled successfully"
    }


@router.post("/settings/{plugin_id}/disable")
async def disable_plugin(
    plugin_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Disable a specific plugin for the current tenant.
    Requires admin role.
    """
    tenant_id = current_user.tenant_id

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage plugin settings"
        )

    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).with_for_update().first()

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plugin settings not found for this tenant"
        )

    if plugin_id in settings.enabled_plugins:
        # Create a new list to ensure SQLAlchemy detects the change
        settings.enabled_plugins = [p for p in settings.enabled_plugins if p != plugin_id]
        settings.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(settings)

    return {
        "tenant_id": tenant_id,
        "enabled_plugins": settings.enabled_plugins,
        "message": f"Plugin '{plugin_id}' disabled successfully"
    }


@router.get("/settings/{plugin_id}/config")
async def get_plugin_config(
    plugin_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get configuration for a specific plugin.
    Returns the plugin-specific configuration object.
    """
    tenant_id = current_user.tenant_id

    # Validate plugin ID
    if plugin_id not in _valid_plugins():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plugin ID: {plugin_id}"
        )

    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).first()

    if not settings:
        # Return empty config if settings don't exist
        return {
            "plugin_id": plugin_id,
            "config": {}
        }

    plugin_config = settings.plugin_config or {}
    return {
        "plugin_id": plugin_id,
        "config": plugin_config.get(plugin_id, {})
    }


@router.put("/settings/{plugin_id}/config")
async def update_plugin_config(
    plugin_id: str,
    payload: dict,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Update configuration for a specific plugin.
    Requires admin role.

    Payload:
    {
        "config": {
            "enable_ai_import": true,  // Enable AI-powered import of holdings + transactions
            ...
        }
    }
    """

    tenant_id = current_user.tenant_id

    # Check if user is admin
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage plugin settings"
        )

    if plugin_id not in _valid_plugins():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plugin ID: {plugin_id}"
        )

    config = payload.get("config", {})
    if not isinstance(config, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="config must be a dictionary"
        )

    # Get or create settings with a lock for update to prevent concurrent modification races
    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).with_for_update().first()

    if not settings:
        settings = TenantPluginSettings(
            tenant_id=tenant_id,
            enabled_plugins=[],
            plugin_config={plugin_id: config}
        )
        db.add(settings)
    else:
        # Update plugin_config safely
        current_config = settings.plugin_config or {}
        existing_plugin_cfg = current_config.get(plugin_id, {})
        
        # Merge the new config, but preserve public_access which is managed separately
        new_plugin_cfg = dict(config)
        if _PUBLIC_ACCESS_KEY in existing_plugin_cfg:
            new_plugin_cfg[_PUBLIC_ACCESS_KEY] = existing_plugin_cfg[_PUBLIC_ACCESS_KEY]
            
        current_config[plugin_id] = new_plugin_cfg
        settings.plugin_config = current_config
        # Mark the column as modified so SQLAlchemy detects the change
        flag_modified(settings, 'plugin_config')
        settings.updated_at = datetime.now(timezone.utc)


    db.commit()
    db.refresh(settings)

    return {
        "plugin_id": plugin_id,
        "config": config,
        "message": f"Configuration for plugin '{plugin_id}' updated successfully"
    }


# ---------------------------------------------------------------------------
# Plugin public access configuration
# ---------------------------------------------------------------------------

_PUBLIC_ACCESS_KEY = "public_access"
_PUBLIC_ACCESS_DEFAULTS = {"enabled": False, "require_login": True}
_BILLING_KEY = "billing"
_BILLING_DEFAULTS = {
    "enabled": False,
    "provider": "stripe",
    "free_endpoint_calls": 0,
    "usage_count": 0,
    "usage_by_endpoint": {},
    "checkout_url": "",
    "stripe_price_id": "",
    "price_label": "",
    "title": "",
    "description": "",
    "button_label": "",
    "payment_completed": False,
}
_PAYMENT_SETTINGS_KEY = "plugin_payment_settings"


def _get_public_access_config(plugin_config: dict | None, plugin_id: str) -> dict:
    """Extract public_access settings for a plugin, returning safe defaults."""
    cfg = (plugin_config or {}).get(plugin_id, {})
    pa = cfg.get(_PUBLIC_ACCESS_KEY, {})
    return {
        "enabled": bool(pa.get("enabled", False)),
        "require_login": bool(pa.get("require_login", True)),
    }


def _get_plugin_settings_row(db: Session, tenant_id: int, for_update: bool = False) -> Optional[TenantPluginSettings]:
    query = db.query(TenantPluginSettings).filter(TenantPluginSettings.tenant_id == tenant_id)
    return query.with_for_update().first() if for_update else query.first()


def _get_plugin_config_blob(plugin_config: dict | None, plugin_id: str) -> dict:
    return dict((plugin_config or {}).get(plugin_id, {}) or {})


def _save_plugin_config_blob(
    settings: Optional[TenantPluginSettings],
    *,
    db: Session,
    tenant_id: int,
    plugin_id: str,
    plugin_cfg: dict,
) -> TenantPluginSettings:
    if not settings:
        settings = TenantPluginSettings(
            tenant_id=tenant_id,
            enabled_plugins=[],
            plugin_config={plugin_id: plugin_cfg},
        )
        db.add(settings)
    else:
        cfg = settings.plugin_config or {}
        cfg[plugin_id] = plugin_cfg
        settings.plugin_config = cfg
        flag_modified(settings, "plugin_config")
        settings.updated_at = datetime.now(timezone.utc)
    return settings


def _coerce_non_negative_int(value: object, default: int = 0) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _coerce_usage_limit(value: object, default: int = -1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return -1 if parsed < 0 else parsed


def _normalize_billing_config(plugin_config: dict | None, plugin_id: str) -> dict:
    cfg = _get_plugin_config_blob(plugin_config, plugin_id)
    raw = dict(cfg.get(_BILLING_KEY, {}) or {})
    usage_by_endpoint = raw.get("usage_by_endpoint", {})
    if not isinstance(usage_by_endpoint, dict):
        usage_by_endpoint = {}

    billing = {
        "enabled": bool(raw.get("enabled", _BILLING_DEFAULTS["enabled"])),
        "provider": str(raw.get("provider", _BILLING_DEFAULTS["provider"]) or "stripe"),
        "free_endpoint_calls": _coerce_usage_limit(raw.get("free_endpoint_calls", -1)),
        "usage_count": _coerce_non_negative_int(raw.get("usage_count", 0)),
        "usage_by_endpoint": {
            str(key): _coerce_non_negative_int(value)
            for key, value in usage_by_endpoint.items()
        },
        "checkout_url": str(raw.get("checkout_url", "") or "").strip(),
        "stripe_price_id": str(raw.get("stripe_price_id", "") or "").strip(),
        "price_label": str(raw.get("price_label", "") or "").strip(),
        "title": str(raw.get("title", "") or "").strip(),
        "description": str(raw.get("description", "") or "").strip(),
        "button_label": str(raw.get("button_label", "") or "").strip(),
        "payment_completed": bool(raw.get("payment_completed", False)),
    }
    return billing


def _billing_response_payload(plugin_id: str, billing: dict) -> dict:
    free_calls = billing["free_endpoint_calls"]
    usage_count = billing["usage_count"]
    usage_limited = free_calls >= 0
    payment_required = billing["enabled"] and usage_limited and usage_count >= free_calls and not billing["payment_completed"]
    payment_configured = bool(billing["checkout_url"])

    return {
        "plugin_id": plugin_id,
        "enabled": billing["enabled"],
        "provider": billing["provider"],
        "free_endpoint_calls": free_calls,
        "usage_count": usage_count,
        "usage_by_endpoint": billing["usage_by_endpoint"],
        "checkout_url": billing["checkout_url"] or None,
        "stripe_price_id": billing["stripe_price_id"] or None,
        "price_label": billing["price_label"] or None,
        "title": billing["title"] or None,
        "description": billing["description"] or None,
        "button_label": billing["button_label"] or None,
        "payment_completed": billing["payment_completed"],
        "payment_required": payment_required,
        "payment_configured": payment_configured,
        "remaining_free_calls": max(free_calls - usage_count, 0) if usage_limited else None,
    }


def _resolve_public_tenant_id(request: Request, db: Session, tenant_id: Optional[int]) -> Optional[int]:
    from core.models.models import Tenant

    if tenant_id is not None:
        return tenant_id

    host = request.headers.get("host", "").split(":")[0]
    subdomain = host.split(".")[0] if "." in host else None
    if subdomain and subdomain != "localhost":
        tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain).first()
        if tenant:
            return tenant.id
    return None


def _get_tenant_payment_settings(tenant_id: int) -> dict:
    tenant_session_factory = tenant_db_manager.get_tenant_session(tenant_id)
    tenant_db = tenant_session_factory()
    try:
        row = tenant_db.query(TenantSetting).filter(TenantSetting.key == _PAYMENT_SETTINGS_KEY).first()
        value = row.value if row and isinstance(row.value, dict) else {}
        return {
            "provider": str(value.get("provider", "stripe") or "stripe"),
            "stripe_secret_key": str(value.get("stripe_secret_key", "") or "").strip(),
            "stripe_publishable_key": str(value.get("stripe_publishable_key", "") or "").strip(),
            "stripe_webhook_secret": str(value.get("stripe_webhook_secret", "") or "").strip(),
            "checkout_success_url": str(value.get("checkout_success_url", "") or "").strip(),
            "checkout_cancel_url": str(value.get("checkout_cancel_url", "") or "").strip(),
        }
    finally:
        tenant_db.close()


@router.get("/{plugin_id}/public-access")
async def get_plugin_public_access(
    plugin_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Get the public-access configuration for a plugin.
    Returns whether the plugin's public page is enabled and whether login is required.
    Admin-only.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    plugin_id = _normalize_plugin_id(plugin_id)
    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == current_user.tenant_id
    ).first()

    pa = _get_public_access_config(settings.plugin_config if settings else None, plugin_id)

    # Include manifest public_page metadata so the UI knows the target path/label
    manifest = next((p for p in plugin_loader.get_registry() if p.get("name") == plugin_id), {})
    return {
        "plugin_id": plugin_id,
        "enabled": pa["enabled"],
        "require_login": pa["require_login"],
        "public_page": manifest.get("public_page"),
    }


@router.get("/{plugin_id}/billing-config")
async def get_plugin_billing_config(
    plugin_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Get billing/paywall configuration for a plugin.
    Admin-only.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    plugin_id = _normalize_plugin_id(plugin_id)
    settings = _get_plugin_settings_row(db, current_user.tenant_id)
    billing = _normalize_billing_config(settings.plugin_config if settings else None, plugin_id)
    return _billing_response_payload(plugin_id, billing)


@router.put("/{plugin_id}/billing-config")
async def update_plugin_billing_config(
    plugin_id: str,
    payload: dict,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Update billing/paywall configuration for a plugin.
    Admin-only.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    plugin_id = _normalize_plugin_id(plugin_id)
    settings = _get_plugin_settings_row(db, current_user.tenant_id, for_update=True)
    plugin_cfg = _get_plugin_config_blob(settings.plugin_config if settings else None, plugin_id)
    billing = _normalize_billing_config(settings.plugin_config if settings else None, plugin_id)

    billing["enabled"] = bool(payload.get("enabled", billing["enabled"]))
    billing["provider"] = str(payload.get("provider", billing["provider"]) or "stripe")
    billing["free_endpoint_calls"] = _coerce_usage_limit(
        payload.get("free_endpoint_calls", billing["free_endpoint_calls"])
    )
    billing["checkout_url"] = str(payload.get("checkout_url", billing["checkout_url"]) or "").strip()
    billing["stripe_price_id"] = str(payload.get("stripe_price_id", billing["stripe_price_id"]) or "").strip()
    billing["price_label"] = str(payload.get("price_label", billing["price_label"]) or "").strip()
    billing["title"] = str(payload.get("title", billing["title"]) or "").strip()
    billing["description"] = str(payload.get("description", billing["description"]) or "").strip()
    billing["button_label"] = str(payload.get("button_label", billing["button_label"]) or "").strip()
    billing["payment_completed"] = bool(payload.get("payment_completed", billing["payment_completed"]))

    if "usage_count" in payload:
        billing["usage_count"] = _coerce_non_negative_int(payload.get("usage_count", billing["usage_count"]))
    if "usage_by_endpoint" in payload and isinstance(payload.get("usage_by_endpoint"), dict):
        billing["usage_by_endpoint"] = {
            str(key): _coerce_non_negative_int(value)
            for key, value in payload["usage_by_endpoint"].items()
        }

    plugin_cfg[_BILLING_KEY] = billing
    _save_plugin_config_blob(
        settings,
        db=db,
        tenant_id=current_user.tenant_id,
        plugin_id=plugin_id,
        plugin_cfg=plugin_cfg,
    )
    db.commit()

    response = _billing_response_payload(plugin_id, billing)
    response["message"] = f"Billing config for plugin '{plugin_id}' updated"
    return response


@router.put("/{plugin_id}/public-access")
async def update_plugin_public_access(
    plugin_id: str,
    payload: dict,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Update the public-access configuration for a plugin.
    Payload: {"enabled": bool, "require_login": bool}
    Admin-only.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    plugin_id = _normalize_plugin_id(plugin_id)

    enabled = bool(payload.get("enabled", False))
    require_login = bool(payload.get("require_login", True))

    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == current_user.tenant_id
    ).with_for_update().first()

    if not settings:
        settings = TenantPluginSettings(
            tenant_id=current_user.tenant_id,
            enabled_plugins=[],
            plugin_config={plugin_id: {_PUBLIC_ACCESS_KEY: {"enabled": enabled, "require_login": require_login}}},
        )
        db.add(settings)
    else:
        cfg = settings.plugin_config or {}
        plugin_cfg = cfg.get(plugin_id, {})
        plugin_cfg[_PUBLIC_ACCESS_KEY] = {"enabled": enabled, "require_login": require_login}
        cfg[plugin_id] = plugin_cfg
        settings.plugin_config = cfg
        flag_modified(settings, "plugin_config")
        settings.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {
        "plugin_id": plugin_id,
        "enabled": enabled,
        "require_login": require_login,
        "message": f"Public access for plugin '{plugin_id}' updated",
    }


@router.get("/public-config/{plugin_id}")
async def get_plugin_public_config(
    request: Request,
    plugin_id: str,
    tenant_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_master_db),
):
    """
    Return the public-access config for a plugin + tenant.
    No authentication required — used by the frontend to decide whether to render
    the public plugin page and whether to enforce login.

    tenant_id is optional: when omitted the tenant is resolved from the Host header
    subdomain (e.g. demo.yourfinanceworks.com → subdomain 'demo').
    """
    # Normalize without validating against discovered plugins —
    # the plugin may be a sidecar not fully registered yet.
    plugin_id = plugin_id.strip().lower().replace("_", "-")
    resolved_tenant_id = _resolve_public_tenant_id(request, db, tenant_id)

    if resolved_tenant_id is None:
        return {
            "plugin_id": plugin_id,
            "enabled": False,
            "require_login": True,
            "public_page": None,
            "billing": _billing_response_payload(plugin_id, _normalize_billing_config(None, plugin_id)),
        }

    settings = _get_plugin_settings_row(db, resolved_tenant_id)

    pa = _get_public_access_config(settings.plugin_config if settings else None, plugin_id)
    billing = _normalize_billing_config(settings.plugin_config if settings else None, plugin_id)

    manifest = next((p for p in plugin_loader.get_registry() if p.get("name") == plugin_id), {})
    return {
        "plugin_id": plugin_id,
        "enabled": pa["enabled"],
        "require_login": pa["require_login"],
        "public_page": manifest.get("public_page"),
        "billing": _billing_response_payload(plugin_id, billing),
    }


@router.post("/public-usage/{plugin_id}")
async def record_plugin_public_usage(
    request: Request,
    plugin_id: str,
    payload: dict,
    tenant_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_master_db),
):
    """
    Increment public-plugin usage counters so a public page can switch to
    a paywall after the free threshold has been consumed.
    No authentication required.
    """
    plugin_id = _normalize_plugin_id(plugin_id)
    resolved_tenant_id = _resolve_public_tenant_id(request, db, tenant_id)

    if resolved_tenant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to resolve tenant")

    settings = _get_plugin_settings_row(db, resolved_tenant_id, for_update=True)
    plugin_cfg = _get_plugin_config_blob(settings.plugin_config if settings else None, plugin_id)
    billing = _normalize_billing_config(settings.plugin_config if settings else None, plugin_id)

    if billing["enabled"]:
        quantity = min(_coerce_non_negative_int(payload.get("quantity", 1), default=1), 1000)
        endpoint_key = str(payload.get("endpoint_key", "public_page_view") or "public_page_view").strip()[:120]
        if quantity > 0:
            billing["usage_count"] += quantity
            billing["usage_by_endpoint"][endpoint_key] = (
                _coerce_non_negative_int(billing["usage_by_endpoint"].get(endpoint_key, 0)) + quantity
            )
            plugin_cfg[_BILLING_KEY] = billing
            _save_plugin_config_blob(
                settings,
                db=db,
                tenant_id=resolved_tenant_id,
                plugin_id=plugin_id,
                plugin_cfg=plugin_cfg,
            )
            db.commit()

    return _billing_response_payload(plugin_id, billing)


@router.post("/public-checkout/{plugin_id}")
async def create_plugin_public_checkout_session(
    request: Request,
    plugin_id: str,
    payload: dict,
    tenant_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_master_db),
):
    """
    Create a Stripe Checkout session for a public plugin paywall.
    No authentication required.
    """
    plugin_id = _normalize_plugin_id(plugin_id)
    resolved_tenant_id = _resolve_public_tenant_id(request, db, tenant_id)
    if resolved_tenant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to resolve tenant")

    settings = _get_plugin_settings_row(db, resolved_tenant_id)
    billing = _normalize_billing_config(settings.plugin_config if settings else None, plugin_id)
    billing_payload = _billing_response_payload(plugin_id, billing)

    if not billing_payload["payment_required"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment is not currently required")

    if billing["provider"] != "stripe":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported billing provider")

    payment_settings = _get_tenant_payment_settings(resolved_tenant_id)
    stripe_secret_key = payment_settings["stripe_secret_key"] or os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not stripe_secret_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe secret key is not configured")

    stripe_price_id = billing["stripe_price_id"]
    if not stripe_price_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe price ID is not configured for this plugin")

    current_url = str(payload.get("current_url", "") or "").strip()
    success_url = payment_settings["checkout_success_url"] or current_url
    cancel_url = payment_settings["checkout_cancel_url"] or current_url
    if not success_url or not cancel_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Checkout success and cancel URLs are not configured")

    try:
        import stripe

        stripe.api_key = stripe_secret_key
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(resolved_tenant_id),
                "plugin_id": plugin_id,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe checkout session failed: {exc}") from exc

    return {
        "plugin_id": plugin_id,
        "tenant_id": resolved_tenant_id,
        "checkout_url": getattr(session, "url", None),
        "session_id": getattr(session, "id", None),
    }


@router.post("/stripe/webhook")
async def handle_plugin_stripe_webhook(
    request: Request,
    db: Session = Depends(get_master_db),
):
    """
    Stripe webhook endpoint for plugin billing checkout completion.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        import stripe
        candidate_secrets = []
        env_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
        if env_secret:
            candidate_secrets.append(env_secret)

        for tenant_id in tenant_db_manager.get_existing_tenant_ids():
            tenant_secret = _get_tenant_payment_settings(tenant_id).get("stripe_webhook_secret", "")
            if tenant_secret and tenant_secret not in candidate_secrets:
                candidate_secrets.append(tenant_secret)

        if not candidate_secrets:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe webhook secret is not configured")

        event = None
        last_error: Optional[Exception] = None
        for candidate_secret in candidate_secrets:
            try:
                event = stripe.Webhook.construct_event(payload=payload, sig_header=signature, secret=candidate_secret)
                break
            except Exception as exc:
                last_error = exc

        if event is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid Stripe webhook: {last_error}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid Stripe webhook: {exc}") from exc

    if event.get("type") != "checkout.session.completed":
        return {"received": True}

    session_object = event["data"]["object"]
    metadata = session_object.get("metadata", {})
    try:
        resolved_tenant_id = int(metadata.get("tenant_id"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing tenant metadata") from exc
    plugin_id = _normalize_plugin_id(str(metadata.get("plugin_id", "") or ""))
    if not plugin_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing plugin metadata")

    settings = _get_plugin_settings_row(db, resolved_tenant_id, for_update=True)
    plugin_cfg = _get_plugin_config_blob(settings.plugin_config if settings else None, plugin_id)
    billing = _normalize_billing_config(settings.plugin_config if settings else None, plugin_id)
    billing["payment_completed"] = True
    plugin_cfg[_BILLING_KEY] = billing
    _save_plugin_config_blob(
        settings,
        db=db,
        tenant_id=resolved_tenant_id,
        plugin_id=plugin_id,
        plugin_cfg=plugin_cfg,
    )
    db.commit()

    return {"received": True, "plugin_id": plugin_id, "tenant_id": resolved_tenant_id}


# ---------------------------------------------------------------------------
# Git-based plugin installation
# ---------------------------------------------------------------------------

@router.post("/install", status_code=status.HTTP_202_ACCEPTED)
async def install_plugin_from_git(
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Start a background job that clones a git repository and installs it as a plugin.
    A server restart (and frontend rebuild if the plugin includes UI) is required
    after installation to activate the plugin.

    Payload:
    {
        "git_url": "https://github.com/org/my-plugin",
        "ref": "main"          // branch, tag, or commit (default: "main")
    }
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can install plugins",
        )

    git_url = str(payload.get("git_url", "")).strip()
    ref = str(payload.get("ref", "main")).strip() or "main"
    github_token = str(payload["github_token"]).strip() if payload.get("github_token") else None

    if not git_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="git_url is required",
        )

    try:
        job = start_install(git_url=git_url, ref=ref, github_token=github_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    background_tasks.add_task(run_install, job.job_id)

    return {
        "job_id": job.job_id,
        "message": "Installation started",
        "status_url": f"/api/v1/plugins/install/status/{job.job_id}",
    }


@router.get("/install/status/{job_id}")
async def get_install_status(
    job_id: str,
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Poll the status of a plugin installation job.
    Returns step-by-step progress and final result.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view installation status",
        )

    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Install job '{job_id}' not found",
        )

    return job.to_dict()


@router.post("/{plugin_id}/reinstall", status_code=status.HTTP_202_ACCEPTED)
async def reinstall_plugin_endpoint(
    plugin_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Re-install an externally installed plugin from its original git source.
    Requires admin role. Uses the URL and ref recorded at install time.
    A server restart is required after reinstallation.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reinstall plugins",
        )

    normalized = _normalize_plugin_id(plugin_id)

    if not plugin_loader.is_dynamic_plugin(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only externally installed plugins can be reinstalled",
        )

    # Prefer stored metadata; fall back to URL supplied in the request body
    # (needed for plugins installed before metadata tracking was added).
    meta = get_install_meta(normalized)
    git_url = (meta or {}).get("git_url") or str(payload.get("git_url", "")).strip()
    ref = (meta or {}).get("ref") or str(payload.get("ref", "main")).strip() or "main"

    if not git_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="git_url is required — install metadata not found for this plugin.",
        )

    github_token = str(payload["github_token"]).strip() if payload.get("github_token") else None

    try:
        job = start_install(git_url=git_url, ref=ref, github_token=github_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    background_tasks.add_task(run_install, job.job_id)

    return {
        "job_id": job.job_id,
        "message": "Reinstallation started",
        "status_url": f"/api/v1/plugins/install/status/{job.job_id}",
    }


@router.delete("/{plugin_id}/uninstall", status_code=status.HTTP_200_OK)
async def uninstall_plugin_endpoint(
    plugin_id: str,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Remove a plugin from disk and disable it for all tenants.
    Requires admin role. A server restart is required after uninstallation.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can uninstall plugins",
        )

    normalized = _normalize_plugin_id(plugin_id)

    # Disable the plugin for this tenant if it is enabled
    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == current_user.tenant_id
    ).first()
    if settings and normalized in (settings.enabled_plugins or []):
        settings.enabled_plugins = [p for p in settings.enabled_plugins if p != normalized]
        settings.updated_at = datetime.now(timezone.utc)
        db.commit()

    try:
        uninstall_plugin(normalized)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Uninstall failed: {exc}",
        )

    return {
        "plugin_id": normalized,
        "message": f"Plugin '{normalized}' uninstalled. A server restart is required.",
        "restart_required": True,
    }
