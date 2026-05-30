"""Shared utilities, logger, and helpers for the OCR service."""

import logging
import os
from typing import Any, Dict, Optional

from core.utils.currency import CURRENCY_SYMBOL_MAP  # noqa: F401 — re-exported for submodules


def _resolve_log_level(name: str) -> int:
    try:
        return getattr(logging, (name or "INFO").upper(), logging.INFO)
    except Exception:
        return logging.INFO


logging.basicConfig(level=_resolve_log_level(os.getenv("LOG_LEVEL", "INFO")))
logger = logging.getLogger("commercial.ai.services.ocr_service")


def parse_number(value: Any) -> Optional[float]:
    """Robust number parsing for OCR results."""
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()

        import re

        is_negative = False
        if s.startswith("(") and s.endswith(")"):
            is_negative = True
        elif s.startswith("-") or s.endswith("-"):
            is_negative = True
        elif re.search(r"[^0-9]-", s) and re.search(r"-[0-9]", s):
            is_negative = True

        s = re.sub(r"[^0-9,.]", "", s)

        # Locale-aware separator handling. The decimal separator is whichever of
        # ',' / '.' appears LAST; the other is a thousands separator. This fixes
        # European-formatted amounts (e.g. "1.234,56" -> 1234.56) which were
        # previously mis-parsed ~1000x too small.
        has_comma = "," in s
        has_dot = "." in s
        if has_comma and has_dot:
            if s.rfind(",") > s.rfind("."):
                # European: dot=thousands, comma=decimal -> "1.234,56" => 1234.56
                s = s.replace(".", "").replace(",", ".")
            else:
                # US/UK: comma=thousands, dot=decimal -> "1,234.56" => 1234.56
                s = s.replace(",", "")
        elif has_comma:
            # Only commas. Distinguish thousands grouping from a decimal comma.
            parts = s.split(",")
            if len(parts) > 2 or (len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) == 3):
                # "1,234,567" or "1,234" -> thousands grouping
                s = s.replace(",", "")
            else:
                # "123,45" / "1234,5" -> comma is the decimal separator
                s = s.replace(",", ".")
        elif has_dot and len(s.split(".")) > 2:
            # Only dots, more than one -> thousands grouping ("1.234.567" => 1234567)
            s = s.replace(".", "")
        # A single dot is left untouched: dot-as-decimal is the dominant default.

        if not s or s == ".":
            return None

        val = float(s)
        return -val if is_negative else val
    except Exception:
        return None


def first_key(d: Dict[str, Any], keys: list[str]) -> Any:
    """Find the first key in a dictionary that exists and has a value."""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _get_ai_config_from_env() -> Optional[Dict[str, Any]]:
    """
    Legacy function for backward compatibility.
    Use AIConfigService.get_ai_config() for new implementations.
    """
    from commercial.ai.services.ai_config_service import AIConfigService

    return AIConfigService._get_env_config("ocr")
