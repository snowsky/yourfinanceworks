"""REST client for the investments plugin API."""

from __future__ import annotations

import json
import mimetypes
import os
import random
import time
import uuid
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import Profile
from .logging_config import get_logger


logger = get_logger("api_client")

RETRIABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0


def _retry_delay(attempt: int, retry_after: str | None) -> float:
    """Return the seconds to wait before the next retry attempt."""
    if retry_after:
        try:
            return max(0.0, min(float(retry_after), MAX_BACKOFF_SECONDS))
        except (TypeError, ValueError):
            pass
    base = BASE_BACKOFF_SECONDS * (2 ** attempt)
    jitter = random.uniform(0.5, 1.0)
    return min(base * jitter, MAX_BACKOFF_SECONDS)


class APIError(RuntimeError):
    """Raised when the backend returns a non-success response."""

    def __init__(self, message: str, status_code: int | None = None, payload: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class InvestmentAPIClient:
    """Small synchronous REST client for investment endpoints.

    Pass ``http_client`` to swap in a test fake or a pre-configured
    ``httpx.Client`` (with custom transport, mounts, proxies, etc.). When
    you supply your own client, ``close()`` will leave it open — ownership
    stays with the caller.
    """

    def __init__(
        self,
        profile: Profile,
        timeout: int = 30,
        *,
        http_client: Any | None = None,
    ):
        self.profile = profile
        if http_client is None:
            self._client = httpx.Client(timeout=timeout)
            self._owns_client = True
        else:
            self._client = http_client
            self._owns_client = False
        self._token: str | None = profile.token
        self._token_expires: datetime | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "InvestmentAPIClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def authenticate(self) -> dict[str, Any]:
        """Authenticate now and persist the token for later CLI commands."""
        self._authenticate()
        return {
            "authenticated": bool(self._token),
            "token_path": str(self.profile.token_path),
            "expires": self._token_expires.isoformat() if self._token_expires else None,
        }

    def authenticate_with_device(
        self,
        *,
        open_browser: bool = True,
        timeout_seconds: int = 600,
    ) -> dict[str, Any]:
        """Authenticate through a browser-approved device code flow."""
        start = self._client.post(f"{self.profile.api_base_url}/auth/device/start")
        if start.status_code >= 400:
            raise APIError(
                f"Device login start failed: {start.status_code}",
                status_code=start.status_code,
                payload=_safe_json(start),
            )
        device_payload = start.json()
        verification_url = device_payload["verification_uri_complete"]
        if open_browser:
            webbrowser.open(verification_url)
        return self.poll_device_login(device_payload, timeout_seconds=timeout_seconds)

    def poll_device_login(self, device_payload: dict[str, Any], *, timeout_seconds: int = 600) -> dict[str, Any]:
        """Poll an existing device login until the browser approves it."""
        verification_url = device_payload["verification_uri_complete"]
        deadline = time.monotonic() + min(timeout_seconds, int(device_payload.get("expires_in", timeout_seconds)))
        interval = int(device_payload.get("interval", 5))
        while time.monotonic() < deadline:
            response = self._client.post(
                f"{self.profile.api_base_url}/auth/device/token",
                json={"device_code": device_payload["device_code"]},
            )
            if response.status_code == 428:
                time.sleep(interval)
                continue
            if response.status_code >= 400:
                raise APIError(
                    f"Device login failed: {response.status_code}",
                    status_code=response.status_code,
                    payload=_safe_json(response),
                )
            token_payload = response.json()
            self._save_token_payload(token_payload)
            return {
                "authenticated": True,
                "token_path": str(self.profile.token_path),
                "verification_url": verification_url,
                "expires": self._token_expires.isoformat() if self._token_expires else None,
            }

        raise APIError("Device login timed out before browser approval.")

    def start_device_login(self) -> dict[str, Any]:
        """Start device login without polling; useful for tests and manual flows."""
        response = self._client.post(f"{self.profile.api_base_url}/auth/device/start")
        if response.status_code >= 400:
            raise APIError(
                f"Device login start failed: {response.status_code}",
                status_code=response.status_code,
                payload=_safe_json(response),
            )
        return response.json()

    def _save_token_payload(self, payload: dict[str, Any]) -> None:
        self._token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 25 * 60))
        self._token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        self._save_token_to_disk()

    def auth_status(self) -> dict[str, Any]:
        """Return cached auth status without forcing a new login."""
        has_cached_token = bool(self._token) or self._load_token_from_disk()
        return {
            "auth_type": self.profile.auth_type,
            "authenticated": has_cached_token,
            "token_path": str(self.profile.token_path),
            "expires": self._token_expires.isoformat() if self._token_expires else None,
        }

    def logout(self) -> dict[str, Any]:
        """Clear the cached auth token."""
        removed = False
        try:
            if self.profile.token_path.exists():
                self.profile.token_path.unlink()
                removed = True
        except OSError as exc:
            raise APIError(f"Failed to remove token file: {exc}") from exc
        self._token = None
        self._token_expires = None
        return {"logged_out": True, "token_removed": removed, "token_path": str(self.profile.token_path)}

    def _load_token_from_disk(self) -> bool:
        token_path = self.profile.token_path
        if not token_path.exists():
            return False
        try:
            data = json.loads(token_path.read_text())
            token = data.get("token")
            expires = data.get("expires")
            if not token or not expires:
                return False
            expiry = datetime.fromisoformat(expires)
            if expiry <= datetime.now(timezone.utc):
                return False
            self._token = str(token)
            self._token_expires = expiry
            return True
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return False

    def _save_token_to_disk(self) -> None:
        if not self._token or not self._token_expires:
            return
        self.profile.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile.token_path.write_text(
            json.dumps(
                {
                    "token": self._token,
                    "expires": self._token_expires.isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        _restrict_file_permissions(self.profile.token_path)

    def _authenticate(self) -> None:
        if self.profile.auth_type in {"none", ""}:
            return
        if self.profile.auth_type in {"bearer", "token"}:
            if not self._token:
                raise APIError("Token auth configured but no token is available.")
            return
        if self.profile.auth_type != "password":
            raise APIError(f"Unsupported auth_type: {self.profile.auth_type}")
        if not self.profile.email or not self.profile.password:
            raise APIError("Password auth requires email and password.")

        response = self._client.post(
            f"{self.profile.api_base_url}/auth/login",
            json={"email": self.profile.email, "password": self.profile.password},
        )
        if response.status_code >= 400:
            raise APIError(
                f"Authentication failed: {response.status_code}",
                status_code=response.status_code,
                payload=_safe_json(response),
            )
        payload = response.json()
        self._save_token_payload({**payload, "expires_in": 25 * 60})

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if not self._token:
            self._load_token_from_disk()
        if not self._token and self.profile.auth_type not in {"none", ""}:
            self._authenticate()
        if self._token_expires and self._token_expires <= datetime.now(timezone.utc):
            self._token = None
            if self.profile.auth_type not in {"none", ""}:
                self._authenticate()
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _get_yfw_api_key_headers(self) -> dict[str, str]:
        if not self.profile.yfw_api_key:
            raise APIError("YFW API key is required. Set FINANCE_AGENT_YFW_API_KEY, YFW_API_KEY, or profile.yfw_api_key.")
        return {"Accept": "application/json", "X-API-Key": self.profile.yfw_api_key}

    def _headers_with_idempotency(self, base_headers: dict[str, str]) -> dict[str, str]:
        """Attach a fresh Idempotency-Key unless the caller already supplied one."""
        headers = dict(base_headers)
        headers.setdefault("Idempotency-Key", str(uuid.uuid4()))
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        upper_method = method.upper()
        retriable_method = upper_method == "GET"
        url = f"{self.profile.api_base_url}{path}"
        extra_headers = dict(kwargs.pop("headers", {}))
        if upper_method != "GET" and "Idempotency-Key" not in extra_headers:
            extra_headers["Idempotency-Key"] = str(uuid.uuid4())

        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self._client.request(
                    method=method,
                    url=url,
                    headers={**self._get_headers(), **extra_headers},
                    **kwargs,
                )
            except httpx.RequestError as exc:
                if retriable_method and attempt < MAX_ATTEMPTS - 1:
                    self._sleep_before_retry(
                        attempt,
                        retry_after=None,
                        reason=f"network error: {exc}",
                        method=upper_method,
                        path=path,
                    )
                    continue
                raise APIError(
                    f"API request failed before response: {exc}",
                    payload={
                        "url": str(exc.request.url) if exc.request else url,
                        "attempts": attempt + 1,
                    },
                ) from exc

            status = response.status_code
            if status >= 400:
                if retriable_method and status in RETRIABLE_STATUSES and attempt < MAX_ATTEMPTS - 1:
                    self._sleep_before_retry(
                        attempt,
                        retry_after=response.headers.get("Retry-After"),
                        reason=f"HTTP {status}",
                        method=upper_method,
                        path=path,
                    )
                    continue
                raise APIError(
                    f"API request failed: {status} {path}",
                    status_code=status,
                    payload=_safe_json(response),
                )
            if not response.content:
                return None
            return response.json()

        raise APIError(f"API request failed after {MAX_ATTEMPTS} attempts: {path}")

    def _sleep_before_retry(
        self,
        attempt: int,
        *,
        retry_after: str | None,
        reason: str,
        method: str,
        path: str,
    ) -> None:
        delay = _retry_delay(attempt, retry_after)
        logger.warning(
            "Retrying %s %s in %.2fs (attempt %d/%d): %s",
            method,
            path,
            delay,
            attempt + 2,
            MAX_ATTEMPTS,
            reason,
        )
        time.sleep(delay)

    def list_portfolios(self, *, skip: int = 0, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", "/investments/portfolios", params={"skip": skip, "limit": limit})

    def list_expenses(self, *, skip: int = 0, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", "/expenses/", params={"skip": skip, "limit": limit, "include_total": True})

    def list_invoices(self, *, skip: int = 0, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", "/invoices/", params={"skip": skip, "limit": limit})

    def list_statements(self, *, skip: int = 0, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", "/statements/", params={"skip": skip, "limit": limit})

    def ai_chat(
        self,
        message: str,
        *,
        config_id: int = 0,
        page_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/ai/chat",
            json={
                "message": message,
                "config_id": config_id,
                "page_context": page_context,
            },
        )

    def get_portfolio(self, portfolio_id: int) -> dict[str, Any]:
        return self._request("GET", f"/investments/portfolios/{portfolio_id}")

    def get_holdings(self, portfolio_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/investments/portfolios/{portfolio_id}/holdings")

    def get_transactions(self, portfolio_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/investments/portfolios/{portfolio_id}/transactions")

    def get_performance(self, portfolio_id: int) -> dict[str, Any]:
        return self._request("GET", f"/investments/portfolios/{portfolio_id}/performance")

    def get_allocation(self, portfolio_id: int) -> dict[str, Any]:
        return self._request("GET", f"/investments/portfolios/{portfolio_id}/allocation")

    def get_rebalance(self, portfolio_id: int) -> dict[str, Any] | None:
        try:
            return self._request("GET", f"/investments/portfolios/{portfolio_id}/rebalance")
        except APIError as exc:
            if exc.status_code == 422:
                return None
            raise

    def get_diversification(self, portfolio_id: int) -> dict[str, Any]:
        return self._request("GET", f"/investments/portfolios/{portfolio_id}/diversification")

    def get_community_sentiment(
        self,
        portfolio_id: int,
        *,
        lookback_days: int = 7,
        max_holdings: int = 8,
        max_items_per_source: int = 5,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/investments/portfolios/{portfolio_id}/community-sentiment",
            params={
                "lookback_days": lookback_days,
                "max_holdings": max_holdings,
                "max_items_per_source": max_items_per_source,
            },
        )

    def get_aggregated_analytics(self) -> dict[str, Any]:
        return self._request("GET", "/investments/analytics/aggregated")

    def get_cross_summary(self) -> dict[str, Any]:
        return self._request("GET", "/investments/cross-portfolio/summary")

    def get_overlap(self) -> dict[str, Any]:
        return self._request("GET", "/investments/cross-portfolio/overlap-analysis")

    def get_exposure(self) -> dict[str, Any]:
        return self._request("GET", "/investments/cross-portfolio/exposure-report")

    def get_price_status(self) -> dict[str, Any]:
        return self._request("GET", "/investments/holdings/price-status")

    def refresh_prices(self) -> dict[str, Any]:
        return self._request("POST", "/investments/holdings/update-prices")

    def upload_batch_files(
        self,
        files: list[Path],
        *,
        document_types: list[str] | None = None,
        export_destination_id: int | None = None,
        client_id: int | None = None,
        webhook_url: str | None = None,
        card_type: str = "auto",
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"card_type": card_type}
        if document_types:
            data["document_types"] = ",".join(document_types)
        if export_destination_id is not None:
            data["export_destination_id"] = str(export_destination_id)
        if client_id is not None:
            data["client_id"] = str(client_id)
        if webhook_url:
            data["webhook_url"] = webhook_url

        handles = []
        try:
            multipart = []
            for path in files:
                handle = path.open("rb")
                handles.append(handle)
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                multipart.append(("files", (path.name, handle, content_type)))

            response = self._client.post(
                f"{self.profile.api_base_url}/external-transactions/batch-processing/upload-authenticated",
                headers=self._headers_with_idempotency(self._get_headers()),
                data=data,
                files=multipart,
            )
            if response.status_code >= 400:
                raise APIError(
                    f"Batch upload failed: {response.status_code}",
                    status_code=response.status_code,
                    payload=_safe_json(response),
                )
            return response.json()
        finally:
            for handle in handles:
                handle.close()

    def get_batch_job_status(self, job_id: str) -> dict[str, Any]:
        response = self._client.get(
            f"{self.profile.api_base_url}/external-transactions/batch-processing/jobs/{job_id}",
            headers=self._get_yfw_api_key_headers(),
        )
        if response.status_code >= 400:
            raise APIError(
                f"Batch job status failed: {response.status_code}",
                status_code=response.status_code,
                payload=_safe_json(response),
            )
        return response.json()

    def upload_portfolio_files(self, portfolio_id: int, files: list[Path]) -> list[dict[str, Any]]:
        handles = []
        try:
            multipart = []
            for path in files:
                handle = path.open("rb")
                handles.append(handle)
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                multipart.append(("files", (path.name, handle, content_type)))
            response = self._client.post(
                f"{self.profile.api_base_url}/investments/portfolios/{portfolio_id}/holdings-files",
                headers=self._headers_with_idempotency(self._get_headers()),
                files=multipart,
            )
            if response.status_code >= 400:
                raise APIError(
                    f"Portfolio upload failed: {response.status_code}",
                    status_code=response.status_code,
                    payload=_safe_json(response),
                )
            return response.json()
        finally:
            for handle in handles:
                handle.close()

    def create_tenant(self, tenant_data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/super-admin/tenants", json=tenant_data)

    def get_tenant_info(self) -> dict[str, Any]:
        return self._request("GET", "/tenants/me")

    def list_tenant_users(self, tenant_id: int, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return self._request("GET", f"/super-admin/tenants/{tenant_id}/users", params={"skip": skip, "limit": limit})


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return response.text


def _restrict_file_permissions(path: Path) -> None:
    """Best-effort chmod 0o600. POSIX-only; silently no-op on platforms that reject it."""
    try:
        os.chmod(path, 0o600)
    except (OSError, NotImplementedError) as exc:
        logger.debug("Could not restrict permissions on %s: %s", path, exc)
