"""Tests for api/MCP/_base_client.py — the shared async HTTP client base.

The two production subclasses (``AuthenticatedAPIClient`` for JWT-authed
chat requests, ``InvoiceAPIClient`` for service-account MCP calls) used to
inline this plumbing. The base now owns the ``httpx.AsyncClient``
lifecycle, URL building, header merging, and async context-manager
support; subclasses just declare their auth strategy via
``_get_auth_headers``.

These tests pin the base's contract so subclass refactors stay safe.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import httpx
import pytest


API_DIR = Path(__file__).resolve().parents[2] / "api"
BASE_CLIENT_PATH = API_DIR / "MCP" / "_base_client.py"


@pytest.fixture(scope="module")
def base_client_module():
    spec = importlib.util.spec_from_file_location("mcp_base_client", BASE_CLIENT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["mcp_base_client"] = module
    spec.loader.exec_module(module)
    return module


def _make_subclass(base_client_module, auth_headers=None):
    """Return a concrete subclass that returns the given auth headers."""

    class _TestClient(base_client_module.BaseAPIClient):
        async def _get_auth_headers(self):
            return dict(auth_headers or {"Authorization": "Bearer test-token"})

    return _TestClient


# ---------- abstract method enforcement ----------


def test_base_class_raises_when_auth_headers_not_overridden(base_client_module):
    client = base_client_module.BaseAPIClient("http://example.com")
    with pytest.raises(NotImplementedError, match="_get_auth_headers"):
        asyncio.run(client._execute_request("GET", "/x"))
    asyncio.run(client.close())


# ---------- request execution ----------


def test_execute_request_builds_url_from_base_and_endpoint(base_client_module):
    captured = {}

    class _RecordingHttpClient:
        async def request(self, method, url, headers, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = headers
            return _StubResponse()

        async def aclose(self):
            pass

    Sub = _make_subclass(base_client_module)
    client = Sub("https://api.example.com/v1", http_client=_RecordingHttpClient())

    asyncio.run(client._execute_request("GET", "/clients/"))

    assert captured["method"] == "GET"
    assert captured["url"] == "https://api.example.com/v1/clients/"


def test_execute_request_merges_auth_headers_with_per_request_headers(base_client_module):
    captured = {}

    class _RecordingHttpClient:
        async def request(self, method, url, headers, **kwargs):
            captured["headers"] = headers
            return _StubResponse()

        async def aclose(self):
            pass

    Sub = _make_subclass(base_client_module, auth_headers={"Authorization": "Bearer abc"})
    client = Sub("http://x", http_client=_RecordingHttpClient())

    asyncio.run(
        client._execute_request(
            "POST",
            "/things",
            headers={"X-Trace-Id": "tr1"},
            json={"a": 1},
        )
    )

    assert captured["headers"]["Authorization"] == "Bearer abc"
    assert captured["headers"]["X-Trace-Id"] == "tr1"


def test_execute_request_forwards_remaining_kwargs(base_client_module):
    captured = {}

    class _RecordingHttpClient:
        async def request(self, method, url, headers, **kwargs):
            captured["kwargs"] = kwargs
            return _StubResponse()

        async def aclose(self):
            pass

    Sub = _make_subclass(base_client_module)
    client = Sub("http://x", http_client=_RecordingHttpClient())

    asyncio.run(
        client._execute_request(
            "POST",
            "/upload",
            json={"k": "v"},
            params={"q": "search"},
        )
    )

    assert captured["kwargs"]["json"] == {"k": "v"}
    assert captured["kwargs"]["params"] == {"q": "search"}


# ---------- ownership / close semantics ----------


def test_default_client_is_closed_by_context_manager(base_client_module):
    Sub = _make_subclass(base_client_module)
    client = Sub("http://x")
    real_client = client._client
    assert isinstance(real_client, httpx.AsyncClient)

    async def _use():
        async with client:
            pass

    asyncio.run(_use())
    assert real_client.is_closed


def test_injected_client_is_not_closed(base_client_module):
    closed = []

    class _RecordingHttpClient:
        async def request(self, method, url, **kwargs):
            return _StubResponse()

        async def aclose(self):
            closed.append(True)

    fake = _RecordingHttpClient()
    Sub = _make_subclass(base_client_module)
    client = Sub("http://x", http_client=fake)

    async def _use():
        async with client:
            pass

    asyncio.run(_use())
    assert closed == [], "injected client must outlive context-manager exit"


def test_close_is_idempotent_for_owned_client(base_client_module):
    Sub = _make_subclass(base_client_module)
    client = Sub("http://x")
    asyncio.run(client.close())
    # second close should not raise — httpx.AsyncClient.aclose() is idempotent
    asyncio.run(client.close())


# ---------- timeout passthrough ----------


def test_timeout_is_applied_to_default_client(base_client_module):
    Sub = _make_subclass(base_client_module)
    client = Sub("http://x", timeout=5.0)
    assert client._client.timeout.read == 5.0
    asyncio.run(client.close())


# ---------- helpers ----------


class _StubResponse:
    status_code = 200

    def json(self):
        return {}

    def raise_for_status(self):
        return None
