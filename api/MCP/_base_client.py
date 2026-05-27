"""Shared base for async HTTP clients that talk to the YFW API.

Two clients used to inline the same plumbing:

  * ``commercial.ai.routers.auth_client.AuthenticatedAPIClient`` — JWT-based,
    constructed per-request from the chat router with the user's session token.
  * ``MCP.api_client.InvoiceAPIClient`` — long-lived, email/password auth via
    ``InvoiceAPIAuthClient`` (token cached on disk).

The auth flows differ by design (per-request JWT vs cached service-account
token), but the URL building, header merging, ``httpx.AsyncClient`` lifecycle,
and missing context-manager support were duplicated. This base lifts the
shared bits and lets each subclass declare its auth strategy through
``_get_auth_headers``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger(__name__)


class BaseAPIClient:
    """Async HTTP client base: shared plumbing + pluggable auth strategy.

    Subclasses MUST implement ``_get_auth_headers`` (async, returns the
    headers dict to attach to every request — typically an ``Authorization``
    header). They typically also expose their own ``_make_request`` that
    wraps ``_execute_request`` with subclass-specific error handling.

    Use as an async context manager to guarantee the underlying
    ``httpx.AsyncClient`` is closed::

        async with InvoiceAPIClient(...) as client:
            await client.list_clients()
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.base_url = base_url
        if http_client is None:
            self._client = httpx.AsyncClient(timeout=timeout)
            self._owns_client = True
        else:
            self._client = http_client
            self._owns_client = False

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Return the auth headers to merge into every outgoing request.

        Subclasses MUST override.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement _get_auth_headers"
        )

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Build URL + auth headers, fire the request, return the raw response.

        No error handling — subclasses wrap this with their own semantics
        (some want friendly user-facing messages, others want structured
        exceptions).
        """
        headers = await self._get_auth_headers()
        headers.update(kwargs.pop("headers", {}))
        return await self._client.request(
            method=method,
            url=f"{self.base_url}{endpoint}",
            headers=headers,
            **kwargs,
        )

    async def close(self) -> None:
        """Close the underlying httpx client iff we created it ourselves.

        Caller-supplied clients (via ``http_client=`` in __init__) are left
        open — ownership stays with the caller.
        """
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "BaseAPIClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
