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

        if "," in s and "." in s:
            s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")

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
