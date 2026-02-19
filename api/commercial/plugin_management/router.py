"""
Plugin management router for handling plugin settings and configuration.
Commercial feature - requires plugin_management license.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func
from typing import List
from datetime import datetime, timezone

from core.models.models import TenantPluginSettings, Tenant, MasterUser
from core.models.database import get_master_db
from core.routers.auth import get_current_user
from core.services.tenant_database_manager import tenant_db_manager


router = APIRouter(prefix="/plugins", tags=["plugins"])


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

    # Validate plugin IDs format
    valid_plugins = {"investments"}  # Add more plugins as they're created
    invalid_plugins = [p for p in enabled_plugins if p not in valid_plugins]

    if invalid_plugins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plugin IDs: {', '.join(invalid_plugins)}"
        )

    # Get or create settings
    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).first()

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
    valid_plugins = {"investments"}
    if plugin_id not in valid_plugins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plugin ID: {plugin_id}"
        )

    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).first()

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
    ).first()

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
    valid_plugins = {"investments"}
    if plugin_id not in valid_plugins:
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

    # Validate plugin ID
    valid_plugins = {"investments"}
    if plugin_id not in valid_plugins:
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

    # Get or create settings
    settings = db.query(TenantPluginSettings).filter(
        TenantPluginSettings.tenant_id == tenant_id
    ).first()

    if not settings:
        settings = TenantPluginSettings(
            tenant_id=tenant_id,
            enabled_plugins=[],
            plugin_config={plugin_id: config}
        )
        db.add(settings)
    else:
        # Update plugin_config
        current_config = settings.plugin_config or {}
        current_config[plugin_id] = config
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
