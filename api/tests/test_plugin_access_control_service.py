import pytest
from sqlalchemy.exc import IntegrityError
from unittest.mock import patch

from core.services.plugin_access_control_service import PluginAccessControlService


def test_check_creates_pending_request_and_reuses_it(db_session):
    service = PluginAccessControlService(db_session)

    first = service.check_or_request_access(
        tenant_id=1,
        user_id=101,
        source_plugin="time-tracking",
        target_plugin="investments",
        access_type="read",
        reason="Load portfolio summaries",
        requested_path="/api/v1/investments/portfolios",
    )
    assert first.granted is False
    assert first.request is not None
    assert first.request["status"] == "pending"

    second = service.check_or_request_access(
        tenant_id=1,
        user_id=101,
        source_plugin="time-tracking",
        target_plugin="investments",
        access_type="read",
        reason="Load portfolio summaries",
        requested_path="/api/v1/investments/portfolios",
    )
    assert second.granted is False
    assert second.request is not None
    assert second.request["id"] == first.request["id"]


def test_approve_request_grants_access(db_session):
    service = PluginAccessControlService(db_session)

    decision = service.check_or_request_access(
        tenant_id=1,
        user_id=200,
        source_plugin="time-tracking",
        target_plugin="investments",
        access_type="read",
    )
    request_id = decision.request["id"]

    request_obj, grant_obj = service.approve_request(
        tenant_id=1,
        request_id=request_id,
        resolver_user_id=200,
        enforce_owner=True,
    )

    assert request_obj["status"] == "approved"
    assert grant_obj["source_plugin"] == "time-tracking"
    assert grant_obj["target_plugin"] == "investments"
    assert grant_obj["granted_to_user_id"] == 200

    check_after_approval = service.check_or_request_access(
        tenant_id=1,
        user_id=200,
        source_plugin="time-tracking",
        target_plugin="investments",
        access_type="read",
    )
    assert check_after_approval.granted is True
    assert check_after_approval.grant is not None


def test_owner_enforcement_for_approval_and_denial(db_session):
    service = PluginAccessControlService(db_session)

    decision = service.check_or_request_access(
        tenant_id=1,
        user_id=300,
        source_plugin="time-tracking",
        target_plugin="investments",
        access_type="write",
    )
    request_id = decision.request["id"]

    try:
        service.approve_request(
            tenant_id=1,
            request_id=request_id,
            resolver_user_id=999,
            enforce_owner=True,
        )
        assert False, "Expected PermissionError when non-owner approves request"
    except PermissionError:
        pass

    try:
        service.deny_request(
            tenant_id=1,
            request_id=request_id,
            resolver_user_id=998,
            enforce_owner=True,
        )
        assert False, "Expected PermissionError when non-owner denies request"
    except PermissionError:
        pass


def test_get_or_create_settings_recovers_from_concurrent_insert(db_session):
    """Two concurrent ``check_or_request_access`` calls for the same tenant
    used to race into ``UNIQUE(tenant_id)`` IntegrityError because both saw no
    row on SELECT and both ran INSERT. The fix catches the IntegrityError,
    rolls back, and re-reads the winner under ``with_for_update``."""
    service = PluginAccessControlService(db_session)

    real_commit = db_session.commit
    commit_calls = {"n": 0}

    def commit_then_raise_once():
        commit_calls["n"] += 1
        if commit_calls["n"] == 1:
            # Simulate the other transaction having committed between our
            # SELECT and INSERT — surface the unique violation our commit
            # would have raised in production.
            real_commit()
            raise IntegrityError("simulated", params=None, orig=Exception("unique"))
        return real_commit()

    with patch.object(db_session, "commit", side_effect=commit_then_raise_once):
        # First call: SELECT returns nothing → INSERT → patched commit raises
        # IntegrityError. The recovery path re-reads the row. The patched
        # commit re-uses ``real_commit`` for the first call, so the row DID
        # land — the recovery query finds it.
        settings = service._get_or_create_settings(tenant_id=4242)

    assert settings is not None
    assert settings.tenant_id == 4242
