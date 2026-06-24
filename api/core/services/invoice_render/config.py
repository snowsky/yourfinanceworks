# api/core/services/invoice_render/config.py
"""Invoice template layout config, read from the extended invoice_branding settings row."""
import re
from dataclasses import dataclass, field
from typing import Dict

_DEFAULT_SHOW = {"logo": True, "notes": True, "custom_fields": True, "footer": True}

ALLOWED_FONTS = ("sans", "serif", "mono")
ALLOWED_LOGO_PLACEMENTS = ("left", "center", "right")
ALLOWED_LOGO_SIZES = ("small", "medium", "large")

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_DEFAULT_BRAND = "#1e3a8a"
_DEFAULT_ACCENT = "#3b82f6"


@dataclass
class InvoiceTemplateConfig:
    brand_color: str = _DEFAULT_BRAND
    accent_color: str = _DEFAULT_ACCENT
    footer_text: str = ""
    show: Dict[str, bool] = field(default_factory=lambda: dict(_DEFAULT_SHOW))
    font_family: str = "sans"
    logo_placement: str = "left"
    logo_size: str = "medium"


def _clamp(value, allowed, default):
    return value if value in allowed else default


def _clamp_color(value, default):
    return value if isinstance(value, str) and _HEX_RE.match(value) else default


def build_config(branding: Dict) -> "InvoiceTemplateConfig":
    """Build a config from a flat invoice_branding dict, clamping every value.

    Pure (no DB). Out-of-range or missing values fall back to defaults so a bad
    value — from the stored row or a posted draft — can never reach the renderer.
    """
    b = branding or {}
    show = dict(_DEFAULT_SHOW)
    show["logo"] = bool(b.get("show_logo", True))
    for key in ("notes", "custom_fields", "footer"):
        if f"show_{key}" in b:
            show[key] = bool(b[f"show_{key}"])
    return InvoiceTemplateConfig(
        brand_color=_clamp_color(b.get("brand_color"), _DEFAULT_BRAND),
        accent_color=_clamp_color(b.get("accent_color"), _DEFAULT_ACCENT),
        footer_text=(b.get("footer_text") or ""),
        show=show,
        font_family=_clamp(b.get("font_family"), ALLOWED_FONTS, "sans"),
        logo_placement=_clamp(b.get("logo_placement"), ALLOWED_LOGO_PLACEMENTS, "left"),
        logo_size=_clamp(b.get("logo_size"), ALLOWED_LOGO_SIZES, "medium"),
    )


def load_template_config(db) -> "InvoiceTemplateConfig":
    """Build the config from the tenant's invoice_branding settings row."""
    from core.services.invoice_branding import get_invoice_branding
    return build_config(get_invoice_branding(db))
