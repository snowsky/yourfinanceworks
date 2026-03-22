"""
Shared auth dependencies and response types for the Tools API.
Reuses auth from developer_api to avoid duplication.
"""
from typing import Any, Generic, Optional, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from commercial.developer_api.router import (
    _check_domain_access,
    get_api_auth_context,
    get_tenant_db,
)
from core.models.database import get_master_db
from core.services.external_api_auth_service import AuthContext, Permission

__all__ = [
    "get_api_auth_context",
    "get_tenant_db",
    "get_master_db",
    "_check_domain_access",
    "AuthContext",
    "Permission",
    "ToolResponse",
    "require_write",
]

T = TypeVar("T")


class ToolResponse(BaseModel, Generic[T]):
    """Consistent response envelope for all Tools API endpoints."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    count: Optional[int] = None
    message: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


def require_write(auth_context: AuthContext) -> None:
    """Raise 403 if the API key does not have write permission."""
    if Permission.WRITE not in auth_context.permissions and not auth_context.is_admin:
        raise HTTPException(status_code=403, detail="Write permission required")
