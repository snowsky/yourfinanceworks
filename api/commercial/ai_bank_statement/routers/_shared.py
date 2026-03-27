"""Shared helpers for the ai_bank_statement router package."""

import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def get_tenant_id() -> int:
    """Extract tenant ID from context, raising 401 if missing."""
    from core.models.database import get_tenant_context

    try:
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")
    return tenant_id
