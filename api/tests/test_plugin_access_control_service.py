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
