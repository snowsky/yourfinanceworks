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

INVOICE_BRANDING_KEY = "invoice_branding"

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

MAX_FOOTER_LEN = 500

DEFAULT_INVOICE_BRANDING: Dict[str, Any] = {
    "brand_color": "#1e3a8a",
    "accent_color": "#3b82f6",
    "show_logo": True,
    "footer_text": "",
}


def get_invoice_branding(db: Session) -> Dict[str, Any]:
    """Return the tenant's invoice branding merged over the defaults."""
    from core.models.models_per_tenant import Settings

    record = db.query(Settings).filter(Settings.key == INVOICE_BRANDING_KEY).first()
    if record and record.value:
        return {**DEFAULT_INVOICE_BRANDING, **record.value}
    return dict(DEFAULT_INVOICE_BRANDING)


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

    return cleaned
