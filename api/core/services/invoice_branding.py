"""Per-tenant invoice branding settings.

Stored as a single tenant-DB ``Settings`` row under the ``invoice_branding`` key.
Shared by the authenticated settings router (read/write) and the public share
endpoint (read, to brand the unauthenticated invoice view). Company name, logo
and contact details live on the master ``Tenant`` record — only the colours and
footer copy are stored here.
"""

import re
from typing import Any, Dict

from sqlalchemy.orm import Session

from core.services.invoice_render.config import (
    ALLOWED_FONTS, ALLOWED_LOGO_PLACEMENTS, ALLOWED_LOGO_SIZES, ALLOWED_SECTIONS)

INVOICE_BRANDING_KEY = "invoice_branding"

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

MAX_FOOTER_LEN = 500

DEFAULT_INVOICE_BRANDING: Dict[str, Any] = {
    "brand_color": "#1e3a8a",
    "accent_color": "#3b82f6",
    "show_logo": True,
    "footer_text": "",
    "font_family": "sans",
    "logo_placement": "left",
    "logo_size": "medium",
    "show_notes": True,
    "show_custom_fields": True,
    "show_footer": True,
}


def get_invoice_branding(db: Session) -> Dict[str, Any]:
    """Return the tenant's invoice branding merged over the defaults.

    Colours are re-validated at read time: they are interpolated into CSS
    contexts (``style="..."``/``<style>``) that HTML autoescaping does not
    protect, so a non-hex value reaching the DB through any path (a future
    writer, a migration, a manual edit) falls back to the default rather than
    being rendered. Defence-in-depth on top of :func:`validate_invoice_branding`.
    """
    from core.models.models_per_tenant import Settings

    record = db.query(Settings).filter(Settings.key == INVOICE_BRANDING_KEY).first()
    merged = dict(DEFAULT_INVOICE_BRANDING)
    if record and record.value:
        merged.update(record.value)

    for key in ("brand_color", "accent_color"):
        if not HEX_COLOR_RE.match(str(merged.get(key, ""))):
            merged[key] = DEFAULT_INVOICE_BRANDING[key]

    return merged


def validate_invoice_branding(value: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize an incoming branding payload.

    Only known keys are kept (unknown keys are dropped). Colours must be 6-digit
    hex. Raises ``ValueError`` on invalid input.
    """
    if not isinstance(value, dict):
        raise ValueError("invoice_branding must be an object")

    cleaned: Dict[str, Any] = {}

    for key in ("brand_color", "accent_color"):
        if value.get(key) is not None:
            color = str(value[key]).strip()
            if not HEX_COLOR_RE.match(color):
                raise ValueError(f"{key} must be a 6-digit hex colour like #1e3a8a")
            cleaned[key] = color.lower()

    if value.get("show_logo") is not None:
        cleaned["show_logo"] = bool(value["show_logo"])

    if value.get("footer_text") is not None:
        footer = str(value["footer_text"]).strip()
        if len(footer) > MAX_FOOTER_LEN:
            raise ValueError(f"footer_text must be at most {MAX_FOOTER_LEN} characters")
        cleaned["footer_text"] = footer

    for key, allowed in (
        ("font_family", ALLOWED_FONTS),
        ("logo_placement", ALLOWED_LOGO_PLACEMENTS),
        ("logo_size", ALLOWED_LOGO_SIZES),
    ):
        if value.get(key) is not None:
            v = str(value[key]).strip().lower()
            if v not in allowed:
                raise ValueError(f"{key} must be one of: {', '.join(allowed)}")
            cleaned[key] = v

    for key in ("show_notes", "show_custom_fields", "show_footer"):
        if value.get(key) is not None:
            cleaned[key] = bool(value[key])

    if value.get("section_order") is not None:
        order = value["section_order"]
        if not isinstance(order, list) or any(
            not isinstance(sid, str) or sid not in ALLOWED_SECTIONS for sid in order
        ):
            raise ValueError(
                f"section_order must be a list of: {', '.join(ALLOWED_SECTIONS)}"
            )
        cleaned["section_order"] = list(order)

    return cleaned
