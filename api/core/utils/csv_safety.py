"""Helpers for producing CSV output that is safe against spreadsheet formula injection.

When a CSV cell begins with one of `= + - @ \\t \\r`, spreadsheet applications (Excel,
LibreOffice, Google Sheets) may interpret it as a formula. Since bank-statement exports
embed LLM-extracted text from arbitrary uploaded documents, an attacker can smuggle a
formula (e.g. ``=HYPERLINK(...)`` or DDE payloads) into a description and have it execute
on the machine of whoever opens the export. See OWASP "CSV Injection".
"""

from typing import Any

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def escape_csv_formula(value: Any) -> str:
    """Return ``value`` as a string safe to write into a CSV cell.

    Values that begin with a formula-trigger character are prefixed with a single quote
    so spreadsheet apps treat them as literal text. Plain numbers (including legitimate
    negatives like ``-45.67``) are left untouched so numeric columns stay numeric.
    """
    if value is None:
        return ""
    text = str(value)
    if not text:
        return text
    if text[0] in _FORMULA_PREFIXES and not _is_number(text):
        return "'" + text
    return text
