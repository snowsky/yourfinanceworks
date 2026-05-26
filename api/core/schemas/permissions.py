"""Pydantic schemas for the per-user, per-component permission API."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Mirrors core.constants.components.PERMISSION_LEVELS.
PermissionLevel = Literal["viewer", "user", "admin"]


class ComponentDescriptor(BaseModel):
    key: str
    label: str
    category: str
    description: str


class ComponentCatalogResponse(BaseModel):
    components: List[ComponentDescriptor]
    levels: List[PermissionLevel]


class EffectivePermissionResponse(BaseModel):
    component: str
    role_level: PermissionLevel
    grant_level: Optional[PermissionLevel] = None
    effective_level: PermissionLevel


class UserPermissionsResponse(BaseModel):
    user_id: int
    role: PermissionLevel
    is_superuser: bool
    permissions: List[EffectivePermissionResponse]


class SetPermissionRequest(BaseModel):
    level: PermissionLevel = Field(
        ...,
        description="Permission level. Grants only restrict; they cannot elevate above the user's role.",
    )


class PermissionAuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    actor_user_id: Optional[int]
    actor_email: Optional[str]
    component: str
    action: Literal["grant", "update", "revoke"]
    previous_level: Optional[PermissionLevel]
    new_level: Optional[PermissionLevel]
    created_at: datetime


class PermissionAuditResponse(BaseModel):
    entries: List[PermissionAuditEntry]
