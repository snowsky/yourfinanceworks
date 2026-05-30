"""Date parsing helpers for transaction ingestion.

The key property: never fabricate a date. Bank-statement transactions previously fell back
to ``datetime.utcnow().date()`` whenever a date failed to parse, silently misdating records
with a plausible-but-wrong value. Callers should instead skip (background worker) or reject
(interactive API) rows whose date cannot be parsed.
"""

from datetime import date, datetime
from typing import Optional


def parse_transaction_date(value: object) -> Optional[date]:
    """Parse a transaction date to a ``date``, or ``None`` if missing/unparseable.

    Accepts ``date``/``datetime`` instances and ISO-8601 strings (matching the previous
    ``datetime.fromisoformat`` behaviour). Returns ``None`` rather than guessing when the
    value is empty or cannot be parsed.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None
