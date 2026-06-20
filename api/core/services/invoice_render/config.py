# api/core/services/invoice_render/config.py
"""Invoice template layout config, read from the extended invoice_branding settings row."""
from dataclasses import dataclass, field
from typing import Dict

_DEFAULT_SHOW = {"logo": True, "notes": True, "custom_fields": True, "footer": True}


@dataclass
class InvoiceTemplateConfig:
    brand_color: str = "#1e3a8a"
    accent_color: str = "#3b82f6"
    footer_text: str = ""
    show: Dict[str, bool] = field(default_factory=lambda: dict(_DEFAULT_SHOW))


def load_template_config(db) -> "InvoiceTemplateConfig":
    """Build the config from the tenant's invoice_branding settings row."""
    from core.services.invoice_branding import get_invoice_branding
    b = get_invoice_branding(db)  # dict: brand_color, accent_color, show_logo, footer_text
    show = dict(_DEFAULT_SHOW)
    show["logo"] = bool(b.get("show_logo", True))
    # New per-tenant section toggles (added to the branding row; default on if absent)
    for key in ("notes", "custom_fields", "footer"):
        if f"show_{key}" in b:
            show[key] = bool(b[f"show_{key}"])
    return InvoiceTemplateConfig(
        brand_color=b.get("brand_color", "#1e3a8a"),
        accent_color=b.get("accent_color", "#3b82f6"),
        footer_text=b.get("footer_text", "") or "",
        show=show,
    )
