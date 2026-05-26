"""Transport-layer retry behavior for InvestmentAPIClient."""

from __future__ import annotations

import os
import stat
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from cli.finance_agent_cli.api_client import (
    APIError,
    InvestmentAPIClient,
    MAX_ATTEMPTS,
    _retry_delay,
)
from cli.finance_agent_cli.config import Profile


def _profile(tmp_path):
    return Profile(
        name="test",
        base_url="http://localhost:8000",
        api_base_url="http://localhost:8000/api/v1",
        auth_type="none",
        email=None,
        password=None,
        token=None,
        yfw_api_key=None,
        llm_provider=None,
        llm_model=None,
        llm_api_key=None,
        llm_base_url=None,
        interval_seconds=300,
        drift_threshold=1.0,
        refresh_prices_on_monitor=False,
        state_path=tmp_path / "state.json",
        token_path=tmp_path / "token.json",
        history_path=tmp_path / "history.jsonl",
        snapshot_dir=tmp_path / "snapshots",
    )


class StubResponse:
    def __init__(self, status_code, *, payload=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload if payload is not None else {}
        self.content = b"{}" if payload is None else b'{"_": "_"}'
        self.text = ""

    def json(self):
        return self._payload


class ScriptedHttpClient:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self.sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("cli.finance_agent_cli.api_client.time.sleep", lambda _: None)


def test_get_retries_on_502_then_succeeds(tmp_path, no_sleep):
    client = InvestmentAPIClient(_profile(tmp_path))
    client._client = ScriptedHttpClient(
        [StubResponse(502), StubResponse(200, payload={"items": []})]
    )

    result = client.list_portfolios()

    assert result == {"items": []}
    assert len(client._client.calls) == 2


def test_get_retries_on_request_error(tmp_path, no_sleep):
    client = InvestmentAPIClient(_profile(tmp_path))
    request = httpx.Request("GET", "http://localhost:8000/api/v1/investments/portfolios")
    client._client = ScriptedHttpClient(
        [
            httpx.ConnectError("connection reset", request=request),
            StubResponse(200, payload={"items": [1]}),
        ]
    )

    result = client.list_portfolios()

    assert result == {"items": [1]}
    assert len(client._client.calls) == 2


def test_get_retries_on_429_with_retry_after_header(tmp_path, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("cli.finance_agent_cli.api_client.time.sleep", sleeps.append)
    client = InvestmentAPIClient(_profile(tmp_path))
    client._client = ScriptedHttpClient(
        [
            StubResponse(429, headers={"Retry-After": "2"}),
            StubResponse(200, payload={"items": []}),
        ]
    )

    client.list_portfolios()

    assert sleeps == [2.0]


def test_post_does_not_retry_on_502(tmp_path, no_sleep):
    client = InvestmentAPIClient(_profile(tmp_path))
    client._client = ScriptedHttpClient([StubResponse(502)])

    with pytest.raises(APIError) as exc_info:
        client.ai_chat("hello")

    assert exc_info.value.status_code == 502
    assert len(client._client.calls) == 1


def test_get_does_not_retry_on_404(tmp_path, no_sleep):
    client = InvestmentAPIClient(_profile(tmp_path))
    client._client = ScriptedHttpClient([StubResponse(404)])

    with pytest.raises(APIError) as exc_info:
        client.list_portfolios()

    assert exc_info.value.status_code == 404
    assert len(client._client.calls) == 1


def test_get_raises_after_max_attempts(tmp_path, no_sleep):
    client = InvestmentAPIClient(_profile(tmp_path))
    client._client = ScriptedHttpClient([StubResponse(503)] * MAX_ATTEMPTS)

    with pytest.raises(APIError) as exc_info:
        client.list_portfolios()

    assert exc_info.value.status_code == 503
    assert len(client._client.calls) == MAX_ATTEMPTS


def test_retry_delay_honors_retry_after_header():
    assert _retry_delay(0, "5") == 5.0


def test_retry_delay_caps_retry_after_at_maximum():
    assert _retry_delay(0, "9999") == 30.0


def test_retry_delay_falls_back_to_exponential_when_header_absent():
    for attempt in range(MAX_ATTEMPTS):
        delay = _retry_delay(attempt, None)
        upper_bound = min(1.0 * (2 ** attempt), 30.0)
        assert 0 < delay <= upper_bound


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only permission semantics")
def test_save_token_to_disk_restricts_permissions(tmp_path):
    profile = _profile(tmp_path)
    client = InvestmentAPIClient(profile)
    client._token = "secret-bearer"
    client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)

    client._save_token_to_disk()

    mode = stat.S_IMODE(os.stat(profile.token_path).st_mode)
    assert mode == 0o600
