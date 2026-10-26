"""Exercise the actual public handler without importing app/database startup."""

import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import Depends, HTTPException

from handler_loader import load_functions


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("matches,sent", [(True, True), (True, False), (False, False)])
def test_request_link_response_never_exposes_identity_or_credential(debug, matches, sent):
    tenant = SimpleNamespace(id=3)
    client = SimpleNamespace(id=7) if matches else None
    tenant_db = Mock()
    tenant_db.query.return_value.filter.return_value.first.return_value = client
    manager = Mock()
    manager.get_tenant_session.return_value.return_value = tenant_db
    generic = {"status": "ok", "message": "If that email matches an account, a login link is on its way."}
    namespace = dict(
        Depends=Depends, get_master_db=lambda: None, HTTPException=HTTPException,
        resolve_tenant_by_portal_id=lambda *_: tenant,
        _client_ip=lambda *_: "127.0.0.1", normalize_email=lambda email: email.lower(),
        record_and_check=lambda *a, **k: False, set_tenant_context=Mock(),
        clear_tenant_context=Mock(), tenant_db_manager=manager,
        check_feature=lambda *_: None, _BACKFILLED_TENANTS={3},
        compute_email_hash=lambda *_: "dummy-hash",
        Client=SimpleNamespace(email_hash="dummy-hash"),
        create_login_token=Mock(return_value=SimpleNamespace(token="dummy-secret-login-token")),
        _send_magic_link=Mock(return_value=sent), _DEBUG=debug,
        FRONTEND_URL="https://finance.example.invalid",
        _GENERIC_LINK_RESPONSE=generic, logger=logging.getLogger(__name__),
    )
    load_functions("api/core/routers/client_portal.py", ["request_login_link"], namespace)
    response = namespace["request_login_link"](
        "dummy-portal", SimpleNamespace(email="client@example.invalid"), Mock(), Mock(),
    )
    assert response == generic
    assert "dummy-secret-login-token" not in str(response)
    namespace["clear_tenant_context"].assert_called_once()
    tenant_db.close.assert_called_once()
    if matches:
        namespace["_send_magic_link"].assert_called_once_with(
            tenant_db, tenant, "client@example.invalid", "dummy-secret-login-token",
        )
    else:
        namespace["create_login_token"].assert_not_called()
