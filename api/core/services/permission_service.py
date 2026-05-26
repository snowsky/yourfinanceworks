"""Per-component permission service.

Effective level for a (user, component) pair is `min(user.role, grant)` using the
ordering viewer < user < admin. Grants only restrict — they cannot elevate
above the tenant role. Super admins always have admin on every component.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from core.constants.components import (
    COMPONENTS,
    COMPONENT_KEYS,
    PERMISSION_LEVELS,
    is_valid_component,
    is_valid_level,
    level_rank,
)
from core.models.models_per_tenant import (
    User,
    UserComponentPermission,
    UserPermissionAuditLog,
)


@dataclass(frozen=True)
class EffectivePermission:
    component: str
    role_level: str
    grant_level: Optional[str]
    effective_level: str


def _effective(role: Optional[str], grant: Optional[str]) -> str:
    safe_role = role if role in PERMISSION_LEVELS else "viewer"
    if grant is None:
        return safe_role
    return safe_role if level_rank(safe_role) <= level_rank(grant) else grant


def _ensure_component(component: str) -> None:
    if not is_valid_component(component):
        raise ValueError(f"Unknown component: {component}")


def _ensure_level(level: str) -> None:
    if not is_valid_level(level):
        raise ValueError(f"Unknown permission level: {level}")


def get_effective_permission(
    db: Session, user: User, component: str
) -> EffectivePermission:
    _ensure_component(component)
    grant = (
        db.query(UserComponentPermission)
        .filter(
            UserComponentPermission.user_id == user.id,
            UserComponentPermission.component == component,
        )
        .first()
    )
    grant_level = grant.permission_level if grant else None
    return EffectivePermission(
        component=component,
        role_level=user.role or "viewer",
        grant_level=grant_level,
        effective_level=_effective(user.role, grant_level),
    )


def get_all_effective_permissions(
    db: Session, user: User
) -> List[EffectivePermission]:
    grants = {
        g.component: g.permission_level
        for g in db.query(UserComponentPermission)
        .filter(UserComponentPermission.user_id == user.id)
        .all()
    }
    role = user.role or "viewer"
    return [
        EffectivePermission(
            component=c.key,
            role_level=role,
            grant_level=grants.get(c.key),
            effective_level=_effective(role, grants.get(c.key)),
        )
        for c in COMPONENTS
    ]


def set_user_component_permission(
    db: Session,
    target_user: User,
    component: str,
    level: str,
    actor: User,
) -> UserComponentPermission:
    _ensure_component(component)
    _ensure_level(level)
    existing = (
        db.query(UserComponentPermission)
        .filter(
            UserComponentPermission.user_id == target_user.id,
            UserComponentPermission.component == component,
        )
        .first()
    )
    if existing and existing.permission_level == level:
        return existing

    previous_level = existing.permission_level if existing else None
    if existing:
        existing.permission_level = level
        existing.granted_by_user_id = actor.id
        grant = existing
        action = "update"
    else:
        grant = UserComponentPermission(
            user_id=target_user.id,
            component=component,
            permission_level=level,
            granted_by_user_id=actor.id,
        )
        db.add(grant)
        action = "grant"

    db.add(
        UserPermissionAuditLog(
            user_id=target_user.id,
            actor_user_id=actor.id,
            actor_email=getattr(actor, "email", None),
            component=component,
            action=action,
            previous_level=previous_level,
            new_level=level,
        )
    )
    db.commit()
    db.refresh(grant)
    return grant


def clear_user_component_permission(
    db: Session,
    target_user: User,
    component: str,
    actor: User,
) -> bool:
    """Remove a grant so the user falls back to their role default.

    Returns True if a grant was removed, False if nothing existed.
    """
    _ensure_component(component)
    existing = (
        db.query(UserComponentPermission)
        .filter(
            UserComponentPermission.user_id == target_user.id,
            UserComponentPermission.component == component,
        )
        .first()
    )
    if not existing:
        return False
    previous_level = existing.permission_level
    db.delete(existing)
    db.add(
        UserPermissionAuditLog(
            user_id=target_user.id,
            actor_user_id=actor.id,
            actor_email=getattr(actor, "email", None),
            component=component,
            action="revoke",
            previous_level=previous_level,
            new_level=None,
        )
    )
    db.commit()
    return True


def list_audit_log(
    db: Session,
    user_id: Optional[int] = None,
    limit: int = 100,
) -> List[UserPermissionAuditLog]:
    q = db.query(UserPermissionAuditLog)
    if user_id is not None:
        q = q.filter(UserPermissionAuditLog.user_id == user_id)
    return q.order_by(UserPermissionAuditLog.created_at.desc()).limit(limit).all()


# Exposed for tests only — never use this in routers; routes should use the
# rbac.require_component_permission helper which also short-circuits superusers.
def _effective_level_internal(role: Optional[str], grant: Optional[str]) -> str:
    return _effective(role, grant)


__all__ = [
    "EffectivePermission",
    "COMPONENT_KEYS",
    "PERMISSION_LEVELS",
    "get_effective_permission",
    "get_all_effective_permissions",
    "set_user_component_permission",
    "clear_user_component_permission",
    "list_audit_log",
]
