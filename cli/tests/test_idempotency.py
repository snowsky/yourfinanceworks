"""Idempotency-Key header injection for non-GET requests."""

from __future__ import annotations

import uuid

from cli.finance_agent_cli.api_client import InvestmentAPIClient
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


class FakeResponse:
    status_code = 200
    content = b"{}"

    def json(self):
        return {}


class FakeHttpClient:
    def __init__(self):
        self.request_calls = []
        self.post_calls = []

    def request(self, method, url, **kwargs):
        self.request_calls.append((method, url, kwargs))
        return FakeResponse()

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse()

    def close(self):
        pass


def test_post_request_includes_generated_idempotency_key(tmp_path):
    client = InvestmentAPIClient(_profile(tmp_path))
    fake = FakeHttpClient()
    client._client = fake

    client.ai_chat("hello")

    _method, _url, kwargs = fake.request_calls[0]
    key = kwargs["headers"]["Idempotency-Key"]
    uuid.UUID(key)  # raises if not a valid UUID


def test_get_request_does_not_include_idempotency_key(tmp_path):
    client = InvestmentAPIClient(_profile(tmp_path))
    fake = FakeHttpClient()
    client._client = fake

    client.list_portfolios()

    _method, _url, kwargs = fake.request_calls[0]
    assert "Idempotency-Key" not in kwargs["headers"]


def test_caller_supplied_idempotency_key_is_preserved(tmp_path):
    client = InvestmentAPIClient(_profile(tmp_path))
    fake = FakeHttpClient()
    client._client = fake

    client._request("POST", "/some/path", headers={"Idempotency-Key": "user-supplied"})

    _method, _url, kwargs = fake.request_calls[0]
    assert kwargs["headers"]["Idempotency-Key"] == "user-supplied"


def test_batch_upload_includes_idempotency_key(tmp_path):
    file_path = tmp_path / "receipt.pdf"
    file_path.write_bytes(b"receipt")
    client = InvestmentAPIClient(_profile(tmp_path))
    fake = FakeHttpClient()
    client._client = fake

    client.upload_batch_files([file_path], document_types=["expense"])

    _url, kwargs = fake.post_calls[0]
    key = kwargs["headers"]["Idempotency-Key"]
    uuid.UUID(key)


def test_portfolio_upload_includes_idempotency_key(tmp_path):
    file_path = tmp_path / "holdings.csv"
    file_path.write_text("symbol,quantity\nAAPL,10\n")
    client = InvestmentAPIClient(_profile(tmp_path))
    fake = FakeHttpClient()
    client._client = fake

    client.upload_portfolio_files(1, [file_path])

    _url, kwargs = fake.post_calls[0]
    key = kwargs["headers"]["Idempotency-Key"]
    uuid.UUID(key)


def test_idempotency_key_stable_within_single_logical_call(tmp_path):
    """When POST retries land (today: only on GET), the key must not change between attempts."""
    client = InvestmentAPIClient(_profile(tmp_path))
    fake = FakeHttpClient()
    client._client = fake

    client.ai_chat("first")
    client.ai_chat("second")

    keys = [call[2]["headers"]["Idempotency-Key"] for call in fake.request_calls]
    assert keys[0] != keys[1], "different logical calls must get distinct keys"
