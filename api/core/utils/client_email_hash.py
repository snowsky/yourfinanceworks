"""Searchable hash for client-email lookup (client portal).

``Client.email`` is encrypted at rest (per-tenant AES) and therefore cannot be
queried directly. We additionally store an HMAC of the normalised email so the
client portal can look a client up by email *without* decrypting or storing
plaintext. The hash is salted with the tenant id, so the same email in two
tenants produces different hashes (no cross-tenant correlation).
"""

import hashlib
import hmac
from typing import Optional

from config import config


def normalize_email(email: str) -> str:
    """Lowercase + trim so lookups are case/whitespace-insensitive."""
    return email.strip().lower()


def compute_email_hash(email: Optional[str], tenant_id: Optional[int]) -> Optional[str]:
    """HMAC-SHA256 of ``"{tenant_id}:{normalized_email}"``.

    Returns None when there is no email or no tenant context (e.g. a client
    record without an email) so the column is simply left NULL.
    """
    if not email or tenant_id is None:
        return None
    normalized = normalize_email(str(email))
    if not normalized:
        return None
    key = str(config.SECRET_KEY).encode("utf-8")
    msg = f"{tenant_id}:{normalized}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()
