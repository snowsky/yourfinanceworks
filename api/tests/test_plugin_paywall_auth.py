"""Tests for the plugin paywall access-token validator.

The three public-paywall endpoints (/checkout, /status, /increment-usage)
previously trusted the ``tenant_id`` and ``plugin_user_id`` from the request
body with no authentication. The ``_validate_plugin_user_token`` helper closes
that hole by verifying a JWT access token before each endpoint reads or
mutates billing state. These tests cover the helper directly.
"""

import pytest
from fastapi import HTTPException
from jose import jwt

from core.routers.auth import SECRET_KEY, ALGORITHM
from commercial.plugin_management.router import _validate_plugin_user_token


def _sign(payload: dict) -> str:
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def test_validate_plugin_user_token_happy_path():
    token = _sign({"plugin_user_id": 7, "tenant_id": 42})
    _validate_plugin_user_token(token, tenant_id=42, plugin_user_id=7)


def test_validate_plugin_user_token_rejects_missing_token():
    with pytest.raises(HTTPException) as exc:
        _validate_plugin_user_token("", tenant_id=1, plugin_user_id=1)
    assert exc.value.status_code == 401


def test_validate_plugin_user_token_rejects_undecodable_token():
    with pytest.raises(HTTPException) as exc:
        _validate_plugin_user_token("not-a-jwt", tenant_id=1, plugin_user_id=1)
    assert exc.value.status_code == 401


def test_validate_plugin_user_token_rejects_token_signed_with_wrong_key():
    bogus = jwt.encode({"plugin_user_id": 7, "tenant_id": 42}, "different-secret", algorithm=ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        _validate_plugin_user_token(bogus, tenant_id=42, plugin_user_id=7)
    assert exc.value.status_code == 401


def test_validate_plugin_user_token_rejects_tenant_id_mismatch():
    token = _sign({"plugin_user_id": 7, "tenant_id": 42})
    with pytest.raises(HTTPException) as exc:
        _validate_plugin_user_token(token, tenant_id=99, plugin_user_id=7)
    assert exc.value.status_code == 403


def test_validate_plugin_user_token_rejects_plugin_user_id_mismatch():
    token = _sign({"plugin_user_id": 7, "tenant_id": 42})
    with pytest.raises(HTTPException) as exc:
        _validate_plugin_user_token(token, tenant_id=42, plugin_user_id=8)
    assert exc.value.status_code == 403


def test_validate_plugin_user_token_rejects_missing_claims():
    # A token signed with the right key but missing the bound claims must
    # still be rejected — otherwise any valid-looking JWT could pass.
    token = _sign({"sub": "anything"})
    with pytest.raises(HTTPException) as exc:
        _validate_plugin_user_token(token, tenant_id=42, plugin_user_id=7)
    assert exc.value.status_code == 403
