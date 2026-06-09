"""Security tests for client-portal session tokens (type segregation)."""

import pytest
from fastapi import HTTPException

from core.services.client_portal_auth import (
    CLIENT_TOKEN_TYPE,
    mint_client_session_token,
    decode_client_session_token,
)
from core.utils.auth import create_access_token


def test_mint_decode_roundtrip():
    token = mint_client_session_token(client_id=7, tenant_id=3, email_hash="abc")
    claims = decode_client_session_token(token)
    assert claims["type"] == CLIENT_TOKEN_TYPE
    assert claims["client_id"] == 7
    assert claims["tenant_id"] == 3
    assert claims["sub"] == "abc"


def test_decode_rejects_staff_token():
    # A staff token (no type=client) must never satisfy the client decoder.
    staff = create_access_token({"sub": "admin@example.com"})
    with pytest.raises(HTTPException) as exc:
        decode_client_session_token(staff)
    assert exc.value.status_code == 401


def test_decode_rejects_garbage():
    with pytest.raises(HTTPException):
        decode_client_session_token("not.a.jwt")


def test_decode_rejects_missing_ids():
    bad = create_access_token({"sub": "abc", "type": "client"})  # no client_id/tenant_id
    with pytest.raises(HTTPException):
        decode_client_session_token(bad)


def test_decode_rejects_wrong_type():
    other = create_access_token({"sub": "abc", "type": "staff", "client_id": 1, "tenant_id": 1})
    with pytest.raises(HTTPException):
        decode_client_session_token(other)
