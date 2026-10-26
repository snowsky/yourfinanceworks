"""Session compatibility and rejection checks for the PyJWT migration."""

import importlib.util
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
import sys

import pytest
from fastapi import HTTPException

from handler_loader import load_functions


@pytest.fixture
def auth(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "migration-test-secret-at-least-32-bytes")
    path = Path(__file__).resolve().parents[2] / "api/core/utils/auth.py"
    spec = importlib.util.spec_from_file_location("migration_auth", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_accepts_existing_python_jose_session(auth):
    # Created with python-jose 3.5.0, HS256, exp=2100-01-01.
    token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJsZWdhY3lAZXhhbXBsZS50ZXN0IiwidGVuYW50X2lkIjo0MiwiZXhwIjo0MTAyNDQ0ODAwfQ."
        "QFzfrR5TczZGOKjrBBmm8UMijsrCCHk3mGiXtpRldc4"
    )
    payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert auth.validate_staff_claims(payload) == "legacy@example.test"
    assert payload["tenant_id"] == 42


def test_new_session_roundtrip_preserves_tenant(auth):
    token = auth.create_access_token({"sub": "staff@example.test", "tenant_id": 7})
    payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert auth.validate_staff_claims(payload) == "staff@example.test"
    assert payload["tenant_id"] == 7


@pytest.mark.parametrize("kind", ["expired", "wrong-key", "wrong-algorithm", "unsigned", "malformed"])
def test_invalid_sessions_raise_the_caught_exception(auth, kind):
    payload = {"sub": "staff@example.test", "tenant_id": 7}
    if kind == "expired":
        token = auth.create_access_token(payload, expires_delta=timedelta(seconds=-60))
    elif kind == "wrong-key":
        token = auth.jwt.encode(payload, "another-secret-at-least-32-bytes-long", algorithm="HS256")
    elif kind == "wrong-algorithm":
        token = auth.jwt.encode(payload, auth.SECRET_KEY.ljust(48, "_"), algorithm="HS384")
    elif kind == "unsigned":
        token = auth.jwt.encode(payload, "", algorithm="none")
    else:
        token = "not.a.jwt"
    with pytest.raises(auth.JWTError):
        auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])


@pytest.mark.parametrize("tenant_id,expected_status", [(42, None), (99, 403)])
def test_plugin_validator_enforces_signed_tenant(auth, monkeypatch, tenant_id, expected_status):
    monkeypatch.setitem(sys.modules, "core.routers.auth", SimpleNamespace(
        SECRET_KEY=auth.SECRET_KEY, ALGORITHM=auth.ALGORITHM,
    ))
    validate = load_functions("api/commercial/plugin_management/router.py", ["_validate_plugin_user_token"], {
        "HTTPException": HTTPException,
    })["_validate_plugin_user_token"]
    token = auth.create_access_token({"tenant_id": 42, "plugin_user_id": 7})
    if expected_status:
        with pytest.raises(HTTPException) as exc:
            validate(token, tenant_id, 7)
        assert exc.value.status_code == expected_status
    else:
        validate(token, tenant_id, 7)


@pytest.mark.parametrize("kind", ["client", "staff", "expired", "malformed"])
def test_portal_decoder_preserves_session_boundaries(auth, kind):
    decode = load_functions("api/core/services/client_portal_auth.py", ["decode_client_session_token"], {
        "jwt": auth.jwt, "JWTError": auth.JWTError, "SECRET_KEY": auth.SECRET_KEY,
        "ALGORITHM": auth.ALGORITHM, "CLIENT_TOKEN_TYPE": "client", "HTTPException": HTTPException,
    })["decode_client_session_token"]
    payload = {"sub": "client@example.test", "type": "client", "client_id": 7, "tenant_id": 42}
    if kind == "staff":
        payload["type"] = "staff"
    token = auth.create_access_token(payload, expires_delta=timedelta(seconds=-60) if kind == "expired" else None)
    if kind == "malformed":
        token = "not.a.jwt"
    if kind == "client":
        assert decode(token)["tenant_id"] == 42
    else:
        with pytest.raises(HTTPException) as exc:
            decode(token)
        assert exc.value.status_code == 401
