"""Cached credentials must stay with the profile and API that issued them."""

import json
from types import SimpleNamespace

import pytest

from cli.finance_agent_cli.api_client import APIError, InvestmentAPIClient


def profile(tmp_path, **changes):
    fields = dict(
        name="personal",
        api_base_url="https://finance.example.invalid/api/v1",
        email="owner@example.invalid",
        auth_type="none",
        token=None,
        token_path=tmp_path / "token.json",
    )
    return SimpleNamespace(**(fields | changes))


def saved_client(tmp_path):
    client = InvestmentAPIClient(profile(tmp_path), http_client=object())
    client._save_token_payload({"access_token": "dummy-cached-token", "expires_in": 3600})
    return client


@pytest.mark.parametrize("changes", [
    {"api_base_url": "https://other.example.invalid/api/v1"},
    {"api_base_url": "https://finance.example.invalid/other/api/v1"},
    {"name": "work"},
    {"email": "other@example.invalid"},
])
def test_cache_does_not_cross_server_profile_or_account(tmp_path, changes):
    saved_client(tmp_path)
    other = InvestmentAPIClient(profile(tmp_path, **changes), http_client=object())
    assert "Authorization" not in other._get_headers()
    assert not other.auth_status()["authenticated"]


def test_valid_cache_remains_available_without_password_auth(tmp_path):
    saved_client(tmp_path)
    same = InvestmentAPIClient(profile(tmp_path), http_client=object())
    assert same._get_headers()["Authorization"] == "Bearer dummy-cached-token"


def test_legacy_unbound_cache_requires_login(tmp_path):
    current = profile(tmp_path)
    current.token_path.write_text(json.dumps({
        "token": "legacy-token", "expires": "2999-01-01T00:00:00+00:00",
    }))
    client = InvestmentAPIClient(current, http_client=object())
    assert "Authorization" not in client._get_headers()


def test_equivalent_url_and_email_normalization_preserves_cache(tmp_path):
    saved_client(tmp_path)
    current = profile(
        tmp_path,
        api_base_url="https://FINANCE.example.invalid/api/v1/",
        email="OWNER@example.invalid",
    )
    client = InvestmentAPIClient(current, http_client=object())
    assert client._get_headers()["Authorization"] == "Bearer dummy-cached-token"


def device_client(tmp_path, approved_email):
    payload = {"access_token": "dummy-device-token", "expires_in": 3600}
    if approved_email is not None:
        payload["user"] = {"email": approved_email}
    response = SimpleNamespace(status_code=200, json=lambda: payload)
    http = SimpleNamespace(post=lambda *args, **kwargs: response)
    return InvestmentAPIClient(profile(tmp_path), http_client=http)


@pytest.mark.parametrize("approved_email", ["other@example.invalid", None])
def test_device_approval_must_identify_the_configured_account(tmp_path, approved_email):
    client = device_client(tmp_path, approved_email)
    with pytest.raises(APIError):
        client.poll_device_login({"verification_uri_complete": "https://finance.example.invalid/verify",
            "device_code": "dummy-code", "expires_in": 30})
    assert not client.profile.token_path.exists()
    assert client._token is None


def test_device_cache_persists_verified_account(tmp_path):
    client = device_client(tmp_path, "OWNER@example.invalid")
    client.poll_device_login({"verification_uri_complete": "https://finance.example.invalid/verify",
        "device_code": "dummy-code", "expires_in": 30})
    payload = json.loads(client.profile.token_path.read_text())
    assert payload["account_email"] == "owner@example.invalid"


def test_device_profile_without_email_keeps_the_approved_account(tmp_path):
    client = device_client(tmp_path, "browser@example.invalid")
    client.profile.email = None
    client.poll_device_login({"verification_uri_complete": "https://finance.example.invalid/verify",
        "device_code": "dummy-code", "expires_in": 30})
    payload = json.loads(client.profile.token_path.read_text())
    assert payload["account_email"] == "browser@example.invalid"
    cached = InvestmentAPIClient(profile(tmp_path, email=None), http_client=object())
    assert cached._get_headers()["Authorization"] == "Bearer dummy-device-token"
    assert cached._token_account == "browser@example.invalid"
