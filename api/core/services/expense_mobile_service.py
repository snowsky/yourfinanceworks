from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.models.models import Settings as MasterSettings, Tenant


EXPENSE_MOBILE_SETTINGS_KEY = "expense_mobile_app"
DEFAULT_EXPENSE_MOBILE_SUBTITLE = "Capture receipts and voice expenses in seconds."
DEFAULT_EXPENSE_MOBILE_ACCENT = "#10b981"
ALLOWED_DEFAULT_ROLES = {"user", "viewer"}


def normalize_expense_mobile_config(raw_value: dict[str, Any] | None, tenant: Tenant) -> dict[str, Any]:
    raw_value = raw_value or {}
    branding = raw_value.get("branding") or {}
    auth_methods = raw_value.get("allowed_auth_methods") or {}

    default_role = str(raw_value.get("default_role") or "user")
    if default_role not in ALLOWED_DEFAULT_ROLES:
        default_role = "user"

    return {
        "enabled": bool(raw_value.get("enabled", False)),
        "app_id": str(raw_value.get("app_id") or "").strip(),
        "signup_enabled": bool(raw_value.get("signup_enabled", True)),
        "default_role": default_role,
        "allowed_auth_methods": {
            "password": bool(auth_methods.get("password", True)),
            "google": bool(auth_methods.get("google", False)),
            "microsoft": bool(auth_methods.get("microsoft", False)),
        },
        "branding": {
            "title": str(branding.get("title") or tenant.name),
            "subtitle": str(branding.get("subtitle") or DEFAULT_EXPENSE_MOBILE_SUBTITLE),
            "accent_color": str(branding.get("accent_color") or DEFAULT_EXPENSE_MOBILE_ACCENT),
            "logo_url": branding.get("logo_url") or tenant.company_logo_url or "",
        },
    }


def get_expense_mobile_setting(db: Session, tenant_id: int) -> MasterSettings | None:
    return (
        db.query(MasterSettings)
        .filter(
            MasterSettings.tenant_id == tenant_id,
            MasterSettings.key == EXPENSE_MOBILE_SETTINGS_KEY,
        )
        .first()
    )


def get_expense_mobile_config(db: Session, tenant: Tenant) -> dict[str, Any]:
    setting = get_expense_mobile_setting(db, tenant.id)
    return normalize_expense_mobile_config(setting.value if setting else None, tenant)


def save_expense_mobile_config(db: Session, tenant: Tenant, raw_value: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_expense_mobile_config(raw_value, tenant)
    app_id = normalized["app_id"]
    if normalized["enabled"] and not app_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mobile App ID is required when the mobile expense service is enabled.",
        )

    if app_id:
        settings_rows = (
            db.query(MasterSettings)
            .filter(MasterSettings.key == EXPENSE_MOBILE_SETTINGS_KEY)
            .all()
        )
        for settings_row in settings_rows:
            if settings_row.tenant_id == tenant.id:
                continue
            other_tenant = db.query(Tenant).filter(Tenant.id == settings_row.tenant_id).first()
            if not other_tenant or not other_tenant.is_active or not other_tenant.is_enabled:
                continue
            other_config = normalize_expense_mobile_config(settings_row.value, other_tenant)
            if other_config["enabled"] and other_config["app_id"] == app_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Mobile App ID is already configured for another organization.",
                )

    setting = get_expense_mobile_setting(db, tenant.id)

    if setting:
        setting.value = normalized
    else:
        setting = MasterSettings(
            tenant_id=tenant.id,
            key=EXPENSE_MOBILE_SETTINGS_KEY,
            value=normalized,
        )
        db.add(setting)

    db.flush()
    return normalized


def resolve_expense_mobile_binding(db: Session, app_id: str) -> tuple[Tenant, dict[str, Any]]:
    normalized_app_id = (app_id or "").strip()
    if not normalized_app_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="app_id is required",
        )

    settings_rows = (
        db.query(MasterSettings)
        .filter(MasterSettings.key == EXPENSE_MOBILE_SETTINGS_KEY)
        .all()
    )

    for setting in settings_rows:
        tenant = db.query(Tenant).filter(Tenant.id == setting.tenant_id).first()
        if not tenant or not tenant.is_active or not tenant.is_enabled:
            continue

        config = normalize_expense_mobile_config(setting.value if setting else None, tenant)
        if config["enabled"] and config["app_id"] == normalized_app_id:
            return tenant, config

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Expense mobile service is not configured for this app.",
    )
