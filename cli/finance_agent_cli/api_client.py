"""REST client for the investments plugin API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import Profile


class APIError(RuntimeError):
    """Raised when the backend returns a non-success response."""

    def __init__(self, message: str, status_code: int | None = None, payload: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class InvestmentAPIClient:
    """Small synchronous REST client for investment endpoints."""

    def __init__(self, profile: Profile, timeout: int = 30):
        self.profile = profile
        self._client = httpx.Client(timeout=timeout)
        self._token: str | None = profile.token
        self._token_expires: datetime | None = None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "InvestmentAPIClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

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
        self._token = payload["access_token"]
        self._token_expires = datetime.now(timezone.utc) + timedelta(minutes=25)
        self._save_token_to_disk()

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.profile.auth_type in {"none", ""}:
            return headers
        if not self._token and not self._load_token_from_disk():
            self._authenticate()
        if self._token_expires and self._token_expires <= datetime.now(timezone.utc):
            self._authenticate()
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(
            method=method,
            url=f"{self.profile.api_base_url}{path}",
            headers={**self._get_headers(), **kwargs.pop("headers", {})},
            **kwargs,
        )
        if response.status_code >= 400:
            raise APIError(
                f"API request failed: {response.status_code} {path}",
                status_code=response.status_code,
                payload=_safe_json(response),
            )
        if not response.content:
            return None
        return response.json()

    def list_portfolios(self, *, skip: int = 0, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", "/investments/portfolios", params={"skip": skip, "limit": limit})

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


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return response.text
