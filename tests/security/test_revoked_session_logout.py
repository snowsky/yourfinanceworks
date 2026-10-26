"""A revoked session must still be able to discard its browser cookie."""

import logging
import os
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from jose import JWTError

from handler_loader import load_functions


@pytest.mark.parametrize("locked", [False, True])
def test_expired_or_locked_session_can_logout_through_middleware(locked):
    def expired(*args, **kwargs):
        raise JWTError("expired dummy session")
    namespace = dict(
        clear_tenant_context=Mock(), get_client_ip=lambda *_: "127.0.0.1",
        logger=logging.getLogger(__name__), is_client_locked_out=lambda *_: locked,
        JSONResponse=JSONResponse, status=status, os=os,
        jwt=type("JWT", (), {"decode": staticmethod(expired)}), JWTError=JWTError,
        SECRET_KEY="dummy-key", ALGORITHM="HS256", AUTH_COOKIE_NAME="auth_token",
        record_failed_auth=Mock(),
    )
    load_functions("api/core/middleware/tenant_context_middleware.py", ["tenant_context_middleware"], namespace)
    load_functions("api/core/routers/auth/login_register.py", ["logout"], namespace)
    # Preserve the real Response annotation for FastAPI parameter injection.
    from fastapi import Response
    namespace["logout"].__annotations__ = {"response": Response}
    app = FastAPI()
    app.middleware("http")(namespace["tenant_context_middleware"])
    app.post("/api/v1/auth/logout")(namespace["logout"])
    with TestClient(app) as client:
        client.cookies.set("auth_token", "expired.dummy.token")
        response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert 'auth_token=""' in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    namespace["record_failed_auth"].assert_not_called()


def test_untrusted_origin_still_cannot_call_logout():
    from types import SimpleNamespace
    import asyncio
    namespace = dict(
        _CSRF_SAFE_METHODS={"GET", "HEAD", "OPTIONS"}, _AUTH_COOKIE_NAME="auth_token",
        allowed_origins=["https://app.example.invalid"], JSONResponse=JSONResponse,
        logger=logging.getLogger(__name__),
    )
    load_functions("api/main.py", ["_origin_is_trusted", "csrf_protection"], namespace)
    request = SimpleNamespace(method="POST", cookies={"auth_token": "expired.dummy.token"},
        headers={"origin": "https://untrusted.example.invalid"},
        url=SimpleNamespace(path="/api/v1/auth/logout"))
    async def forbidden(_):
        pytest.fail("untrusted browser origin reached logout")
    assert asyncio.run(namespace["csrf_protection"](request, forbidden)).status_code == 403
