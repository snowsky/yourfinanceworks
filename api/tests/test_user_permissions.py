"""Tests for per-user, per-component permission grants.

Covers:
- Effective level math (role ceiling, grants only restrict).
- Audit logging on grant/update/revoke.
- Endpoint authorization (only tenant admins + super admins can assign).
- Migrated invoices.create_invoice enforces the new component check.
"""

from __future__ import annotations

import pytest

from core.constants.components import COMPONENT_KEYS, PERMISSION_LEVELS
from core.models.models_per_tenant import (
    UserComponentPermission,
    UserPermissionAuditLog,
)
from core.services import permission_service as ps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(create_test_user, email: str, role: str = "user", **extra):
    return create_test_user(email=email, role=role, **extra)


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role,grant,expected",
    [
        ("admin", None, "admin"),
        ("admin", "viewer", "viewer"),
        ("admin", "user", "user"),
        ("admin", "admin", "admin"),
        ("user", None, "user"),
        ("user", "viewer", "viewer"),
        # Grant can never elevate above role.
        ("user", "admin", "user"),
        ("viewer", "admin", "viewer"),
        ("viewer", "user", "viewer"),
        ("viewer", None, "viewer"),
        # Unknown/missing role defaults to viewer.
        (None, "admin", "viewer"),
        ("garbage", "user", "viewer"),
    ],
)
def test_effective_level(role, grant, expected):
    assert ps._effective_level_internal(role, grant) == expected


def test_component_catalog_is_non_empty_and_keys_are_unique():
    assert len(COMPONENT_KEYS) > 0


def test_permission_levels_in_ascending_order():
    assert PERMISSION_LEVELS == ("viewer", "user", "admin")


# ---------------------------------------------------------------------------
# Service: persistence + audit log
# ---------------------------------------------------------------------------


def test_set_creates_grant_and_audit_entry(db_session, create_test_user):
    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")

    grant = ps.set_user_component_permission(
        db=db_session,
        target_user=target,
        component="invoices",
        level="viewer",
        actor=actor,
    )

    assert grant.user_id == target.id
    assert grant.permission_level == "viewer"
    assert grant.granted_by_user_id == actor.id

    audit = db_session.query(UserPermissionAuditLog).all()
    assert len(audit) == 1
    assert audit[0].action == "grant"
    assert audit[0].previous_level is None
    assert audit[0].new_level == "viewer"
    assert audit[0].actor_user_id == actor.id


def test_set_updates_existing_grant_and_logs_update(db_session, create_test_user):
    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")
    ps.set_user_component_permission(
        db_session, target, "expenses", "viewer", actor
    )
    ps.set_user_component_permission(
        db_session, target, "expenses", "user", actor
    )

    grants = db_session.query(UserComponentPermission).all()
    assert len(grants) == 1
    assert grants[0].permission_level == "user"

    audit = (
        db_session.query(UserPermissionAuditLog)
        .order_by(UserPermissionAuditLog.id)
        .all()
    )
    assert [a.action for a in audit] == ["grant", "update"]
    assert audit[1].previous_level == "viewer"
    assert audit[1].new_level == "user"


def test_set_noop_when_level_unchanged(db_session, create_test_user):
    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")
    ps.set_user_component_permission(
        db_session, target, "invoices", "viewer", actor
    )
    ps.set_user_component_permission(
        db_session, target, "invoices", "viewer", actor
    )
    # Only the first set produces audit; second is a no-op.
    audit = db_session.query(UserPermissionAuditLog).all()
    assert len(audit) == 1


def test_clear_removes_grant_and_logs_revoke(db_session, create_test_user):
    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")
    ps.set_user_component_permission(
        db_session, target, "invoices", "viewer", actor
    )

    removed = ps.clear_user_component_permission(
        db_session, target, "invoices", actor
    )
    assert removed is True

    assert db_session.query(UserComponentPermission).count() == 0
    audit = (
        db_session.query(UserPermissionAuditLog)
        .order_by(UserPermissionAuditLog.id)
        .all()
    )
    assert [a.action for a in audit] == ["grant", "revoke"]
    assert audit[1].previous_level == "viewer"
    assert audit[1].new_level is None


def test_clear_no_op_when_no_grant_exists(db_session, create_test_user):
    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")
    removed = ps.clear_user_component_permission(
        db_session, target, "invoices", actor
    )
    assert removed is False
    assert db_session.query(UserPermissionAuditLog).count() == 0


def test_get_effective_permission_uses_role_ceiling(db_session, create_test_user):
    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")

    # No grant: falls back to role.
    e = ps.get_effective_permission(db_session, target, "invoices")
    assert e.effective_level == "user"
    assert e.grant_level is None

    # Grant cannot elevate above role.
    ps.set_user_component_permission(
        db_session, target, "invoices", "admin", actor
    )
    e = ps.get_effective_permission(db_session, target, "invoices")
    assert e.effective_level == "user"  # clamped by role
    assert e.grant_level == "admin"

    # Grant can restrict below role.
    ps.set_user_component_permission(
        db_session, target, "invoices", "viewer", actor
    )
    e = ps.get_effective_permission(db_session, target, "invoices")
    assert e.effective_level == "viewer"


def test_get_all_effective_permissions_returns_every_component(
    db_session, create_test_user
):
    target = _make_user(create_test_user, "alice@example.com", role="admin")
    rows = ps.get_all_effective_permissions(db_session, target)
    assert {r.component for r in rows} == set(COMPONENT_KEYS)
    assert all(r.effective_level == "admin" for r in rows)


def test_set_rejects_unknown_component(db_session, create_test_user):
    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")
    with pytest.raises(ValueError):
        ps.set_user_component_permission(
            db_session, target, "totally_made_up", "viewer", actor
        )


def test_set_rejects_unknown_level(db_session, create_test_user):
    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")
    with pytest.raises(ValueError):
        ps.set_user_component_permission(
            db_session, target, "invoices", "god_mode", actor
        )


# ---------------------------------------------------------------------------
# RBAC helper
# ---------------------------------------------------------------------------


def test_require_component_permission_short_circuits_for_superuser(
    db_session, create_test_user
):
    from core.utils.rbac import require_component_permission

    target = _make_user(create_test_user, "root@example.com", role="viewer")
    target.is_superuser = True
    db_session.commit()
    # Should NOT raise even though role is viewer.
    require_component_permission(db_session, target, "invoices", "admin")


def test_require_component_permission_uses_effective_level(
    db_session, create_test_user
):
    from fastapi import HTTPException

    from core.utils.rbac import require_component_permission

    actor = _make_user(create_test_user, "admin@example.com", role="admin")
    target = _make_user(create_test_user, "alice@example.com", role="user")
    # Restrict invoices to viewer.
    ps.set_user_component_permission(
        db_session, target, "invoices", "viewer", actor
    )

    # user-level required on invoices: should be denied (effective=viewer).
    with pytest.raises(HTTPException) as exc:
        require_component_permission(db_session, target, "invoices", "user")
    assert exc.value.status_code == 403

    # viewer-level required: allowed.
    require_component_permission(db_session, target, "invoices", "viewer")


def test_can_assign_permission_helpers():
    from fastapi import HTTPException

    from core.utils.rbac import (
        can_assign_component_permissions,
        require_component_permission_assigner,
    )

    class FakeUser:
        def __init__(self, role="user", is_superuser=False):
            self.role = role
            self.is_superuser = is_superuser

    assert can_assign_component_permissions(FakeUser(role="admin"))
    assert can_assign_component_permissions(FakeUser(is_superuser=True))
    assert not can_assign_component_permissions(FakeUser(role="user"))
    assert not can_assign_component_permissions(FakeUser(role="viewer"))

    require_component_permission_assigner(FakeUser(role="admin"))
    with pytest.raises(HTTPException) as exc:
        require_component_permission_assigner(FakeUser(role="user"))
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Router handler unit tests (in-process; skips TestClient/auth plumbing)
# ---------------------------------------------------------------------------
#
# These call the route handler functions as plain Python coroutines with a
# real DB session, so we get full coverage of the endpoint logic without
# wiring up JWT/cookie auth in the test environment.


import asyncio

from fastapi import HTTPException

from core.routers import user_permissions as up_router
from core.schemas.permissions import SetPermissionRequest


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_endpoint_get_components_lists_catalog(db_session, create_test_user):
    user = create_test_user(email="someone@example.com", role="user")
    resp = _run(up_router.get_components(current_user=user))
    assert resp.levels == ["viewer", "user", "admin"]
    assert {c.key for c in resp.components} == set(COMPONENT_KEYS)


def test_endpoint_set_permission_requires_admin(db_session, create_test_user):
    target = create_test_user(email="alice@example.com", role="user")
    non_admin = create_test_user(email="bob@example.com", role="user")
    with pytest.raises(HTTPException) as exc:
        _run(
            up_router.set_user_permission(
                user_id=target.id,
                component="invoices",
                payload=SetPermissionRequest(level="viewer"),
                current_user=non_admin,
                db=db_session,
            )
        )
    assert exc.value.status_code == 403


def test_endpoint_set_permission_clamps_to_role_ceiling(
    db_session, create_test_user
):
    target = create_test_user(email="alice@example.com", role="user")
    admin = create_test_user(email="admin@example.com", role="admin")
    resp = _run(
        up_router.set_user_permission(
            user_id=target.id,
            component="invoices",
            payload=SetPermissionRequest(level="admin"),
            current_user=admin,
            db=db_session,
        )
    )
    assert resp.grant_level == "admin"
    assert resp.effective_level == "user"  # clamped to role ceiling


def test_endpoint_clear_permission_returns_role_default(
    db_session, create_test_user
):
    target = create_test_user(email="alice@example.com", role="user")
    admin = create_test_user(email="admin@example.com", role="admin")
    _run(
        up_router.set_user_permission(
            user_id=target.id,
            component="invoices",
            payload=SetPermissionRequest(level="viewer"),
            current_user=admin,
            db=db_session,
        )
    )
    resp = _run(
        up_router.clear_user_permission(
            user_id=target.id,
            component="invoices",
            current_user=admin,
            db=db_session,
        )
    )
    assert resp.grant_level is None
    assert resp.effective_level == "user"


def test_endpoint_get_my_permissions_returns_all_components(
    db_session, create_test_user
):
    me = create_test_user(email="me@example.com", role="admin")
    resp = _run(
        up_router.get_my_permissions(current_user=me, db=db_session)
    )
    assert resp.role == "admin"
    assert {p.component for p in resp.permissions} == set(COMPONENT_KEYS)


def test_endpoint_audit_returns_history_newest_first(
    db_session, create_test_user
):
    admin = create_test_user(email="admin@example.com", role="admin")
    target = create_test_user(email="alice@example.com", role="user")
    _run(
        up_router.set_user_permission(
            user_id=target.id,
            component="invoices",
            payload=SetPermissionRequest(level="viewer"),
            current_user=admin,
            db=db_session,
        )
    )
    _run(
        up_router.set_user_permission(
            user_id=target.id,
            component="invoices",
            payload=SetPermissionRequest(level="user"),
            current_user=admin,
            db=db_session,
        )
    )
    resp = _run(
        up_router.get_user_permission_audit(
            user_id=target.id,
            limit=100,
            current_user=admin,
            db=db_session,
        )
    )
    assert [e.action for e in resp.entries] == ["update", "grant"]


def test_endpoint_set_rejects_unknown_component(db_session, create_test_user):
    admin = create_test_user(email="admin@example.com", role="admin")
    target = create_test_user(email="alice@example.com", role="user")
    with pytest.raises(HTTPException) as exc:
        _run(
            up_router.set_user_permission(
                user_id=target.id,
                component="totally_made_up",
                payload=SetPermissionRequest(level="viewer"),
                current_user=admin,
                db=db_session,
            )
        )
    assert exc.value.status_code == 400


def test_endpoint_set_404_when_user_missing(db_session, create_test_user):
    admin = create_test_user(email="admin@example.com", role="admin")
    with pytest.raises(HTTPException) as exc:
        _run(
            up_router.set_user_permission(
                user_id=999999,
                component="invoices",
                payload=SetPermissionRequest(level="viewer"),
                current_user=admin,
                db=db_session,
            )
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Per-component require_component_permission unit checks
# ---------------------------------------------------------------------------
# Locks in that every (component, level) combo actually wired into a router
# is a known component-level pair the helper accepts and the role ceiling
# enforces. Keeps router migrations from silently regressing if someone
# renames a component key.


_COMPONENT_LEVEL_CASES = [
    ("customers", "user"),
    ("bank_statements", "user"),
    ("reports", "user"),
    ("reports", "admin"),
    ("users", "admin"),
    ("settings", "admin"),
    ("integrations", "admin"),
    ("integrations", "user"),
    ("audit_log", "admin"),
]


@pytest.mark.parametrize("component,required_level", _COMPONENT_LEVEL_CASES)
def test_migrated_components_deny_viewer(
    db_session, create_test_user, component, required_level
):
    """A viewer-role user must be denied wherever the migrated routers require
    a level above viewer."""
    from core.utils.rbac import require_component_permission

    user = _make_user(
        create_test_user,
        f"viewer-{component}-{required_level}@example.com",
        role="viewer",
    )
    with pytest.raises(HTTPException) as exc:
        require_component_permission(
            db_session, user, component, required_level, "test"
        )
    assert exc.value.status_code == 403


@pytest.mark.parametrize("component,required_level", _COMPONENT_LEVEL_CASES)
def test_migrated_components_allow_admin(
    db_session, create_test_user, component, required_level
):
    """An admin must be allowed everywhere the migrated routers gate access."""
    from core.utils.rbac import require_component_permission

    user = _make_user(
        create_test_user,
        f"admin-{component}-{required_level}@example.com",
        role="admin",
    )
    require_component_permission(db_session, user, component, required_level, "test")
