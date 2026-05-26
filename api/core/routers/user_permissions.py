"""Endpoints for per-user, per-component permission management.

Authorization:
- GET catalog + GET /me/permissions: any authenticated user
- All admin endpoints: tenant role=admin or is_superuser
  (see `require_component_permission_assigner`)
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.constants.components import COMPONENTS, PERMISSION_LEVELS, is_valid_component
from core.models.database import get_db
from core.models.models_per_tenant import User
from core.routers.auth import get_current_user
from core.schemas.permissions import (
    ComponentCatalogResponse,
    ComponentDescriptor,
    EffectivePermissionResponse,
    PermissionAuditEntry,
    PermissionAuditResponse,
    SetPermissionRequest,
    UserPermissionsResponse,
)
from core.services.permission_service import (
    clear_user_component_permission,
    get_all_effective_permissions,
    list_audit_log,
    set_user_component_permission,
)
from core.utils.rbac import require_component_permission_assigner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permissions", tags=["permissions"])


def _effective_to_schema(rows) -> List[EffectivePermissionResponse]:
    return [
        EffectivePermissionResponse(
            component=p.component,
            role_level=p.role_level,
            grant_level=p.grant_level,
            effective_level=p.effective_level,
        )
        for p in rows
    ]


def _user_payload(user: User, rows) -> UserPermissionsResponse:
    return UserPermissionsResponse(
        user_id=user.id,
        role=user.role or "viewer",
        is_superuser=bool(getattr(user, "is_superuser", False)),
        permissions=_effective_to_schema(rows),
    )


def _load_target(db: Session, user_id: int) -> User:
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return target


@router.get("/components", response_model=ComponentCatalogResponse)
async def get_components(current_user: User = Depends(get_current_user)):
    """List every component eligible for per-user permission grants."""
    return ComponentCatalogResponse(
        components=[
            ComponentDescriptor(
                key=c.key, label=c.label, category=c.category, description=c.description
            )
            for c in COMPONENTS
        ],
        levels=list(PERMISSION_LEVELS),
    )


@router.get("/me", response_model=UserPermissionsResponse)
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's effective permissions for every component."""
    rows = get_all_effective_permissions(db, current_user)
    # For super admins the rows still show role="admin" effective everywhere,
    # but the explicit flag makes the UI logic trivial.
    return _user_payload(current_user, rows)


@router.get("/users/{user_id}", response_model=UserPermissionsResponse)
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_component_permission_assigner(current_user)
    target = _load_target(db, user_id)
    rows = get_all_effective_permissions(db, target)
    return _user_payload(target, rows)


@router.put(
    "/users/{user_id}/components/{component}",
    response_model=EffectivePermissionResponse,
)
async def set_user_permission(
    user_id: int,
    component: str,
    payload: SetPermissionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_component_permission_assigner(current_user)
    if not is_valid_component(component):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown component: {component}",
        )
    target = _load_target(db, user_id)
    set_user_component_permission(
        db=db,
        target_user=target,
        component=component,
        level=payload.level,
        actor=current_user,
    )
    # Recompute effective level so we honor the role ceiling in the response.
    from core.services.permission_service import get_effective_permission

    effective = get_effective_permission(db, target, component)
    return EffectivePermissionResponse(
        component=effective.component,
        role_level=effective.role_level,
        grant_level=effective.grant_level,
        effective_level=effective.effective_level,
    )


@router.delete(
    "/users/{user_id}/components/{component}",
    response_model=EffectivePermissionResponse,
)
async def clear_user_permission(
    user_id: int,
    component: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_component_permission_assigner(current_user)
    if not is_valid_component(component):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown component: {component}",
        )
    target = _load_target(db, user_id)
    clear_user_component_permission(
        db=db, target_user=target, component=component, actor=current_user
    )
    from core.services.permission_service import get_effective_permission

    effective = get_effective_permission(db, target, component)
    return EffectivePermissionResponse(
        component=effective.component,
        role_level=effective.role_level,
        grant_level=effective.grant_level,
        effective_level=effective.effective_level,
    )


@router.get(
    "/users/{user_id}/audit",
    response_model=PermissionAuditResponse,
)
async def get_user_permission_audit(
    user_id: int,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_component_permission_assigner(current_user)
    target = _load_target(db, user_id)
    entries = list_audit_log(db, user_id=target.id, limit=limit)
    return PermissionAuditResponse(
        entries=[PermissionAuditEntry.model_validate(e) for e in entries]
    )
