"""Cached credentials must stay with the profile and API that issued them."""

import json
from types import SimpleNamespace

import pytest

from cli.finance_agent_cli.api_client import InvestmentAPIClient


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
