"""Configuration loading for the finance agent CLI."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(".finance-agent/config.json")
DEFAULT_STATE_PATH = Path(".finance-agent/state.json")
DEFAULT_TOKEN_PATH = Path(".finance-agent/token.json")
DEFAULT_HISTORY_PATH = Path(".finance-agent/monitor-history.jsonl")
DEFAULT_SNAPSHOT_DIR = Path(".finance-agent/snapshots")


def _normalize_api_base_url(raw_base_url: str) -> str:
    base = raw_base_url.rstrip("/")
    if base.endswith("/api/v1"):
        return base
    if base.endswith("/api"):
        return f"{base}/v1"
    return f"{base}/api/v1"


@dataclass(frozen=True)
class Profile:
    """Runtime profile used by the CLI."""

    name: str
    base_url: str
    api_base_url: str
    auth_type: str
    email: str | None
    password: str | None
    token: str | None
    interval_seconds: int
    drift_threshold: float
    refresh_prices_on_monitor: bool
    state_path: Path
    token_path: Path
    history_path: Path
    snapshot_dir: Path


def load_profile(
    config_path: Path = DEFAULT_CONFIG_PATH,
    profile_name: str | None = None,
) -> Profile:
    """Load configuration from disk and environment variables."""
    raw_data: dict[str, object] = {}
    if config_path.exists():
        raw_data = json.loads(config_path.read_text())

    active_profile = (
        profile_name
        or os.getenv("FINANCE_AGENT_PROFILE")
        or raw_data.get("active_profile")
        or "default"
    )

    profiles = raw_data.get("profiles", {})
    file_profile = profiles.get(active_profile, {}) if isinstance(profiles, dict) else {}

    base_url = str(
        os.getenv("FINANCE_AGENT_BASE_URL")
        or os.getenv("INVOICE_API_BASE_URL")
        or file_profile.get("base_url")
        or "http://localhost:8000"
    ).rstrip("/")

    auth_type = str(
        os.getenv("FINANCE_AGENT_AUTH_TYPE")
        or file_profile.get("auth_type")
        or ("password" if os.getenv("INVOICE_API_EMAIL") and os.getenv("INVOICE_API_PASSWORD") else "none")
    ).lower()

    email = os.getenv("FINANCE_AGENT_EMAIL") or os.getenv("INVOICE_API_EMAIL") or file_profile.get("email")
    password = os.getenv("FINANCE_AGENT_PASSWORD") or os.getenv("INVOICE_API_PASSWORD") or file_profile.get("password")
    token = os.getenv("FINANCE_AGENT_TOKEN") or file_profile.get("token")

    interval_seconds = int(os.getenv("FINANCE_AGENT_INTERVAL", file_profile.get("interval_seconds", 300)))
    drift_threshold = float(os.getenv("FINANCE_AGENT_DRIFT_THRESHOLD", file_profile.get("drift_threshold", 1.0)))
    refresh_prices = str(
        os.getenv(
            "FINANCE_AGENT_REFRESH_PRICES",
            file_profile.get("refresh_prices_on_monitor", False),
        )
    ).lower() in {"1", "true", "yes", "on"}

    state_path = Path(os.getenv("FINANCE_AGENT_STATE_PATH", str(DEFAULT_STATE_PATH)))
    token_path = Path(os.getenv("FINANCE_AGENT_TOKEN_PATH", str(DEFAULT_TOKEN_PATH)))
    history_path = Path(os.getenv("FINANCE_AGENT_HISTORY_PATH", str(DEFAULT_HISTORY_PATH)))
    snapshot_dir = Path(os.getenv("FINANCE_AGENT_SNAPSHOT_DIR", str(DEFAULT_SNAPSHOT_DIR)))

    return Profile(
        name=str(active_profile),
        base_url=base_url,
        api_base_url=_normalize_api_base_url(base_url),
        auth_type=auth_type,
        email=str(email) if email else None,
        password=str(password) if password else None,
        token=str(token) if token else None,
        interval_seconds=interval_seconds,
        drift_threshold=drift_threshold,
        refresh_prices_on_monitor=refresh_prices,
        state_path=state_path,
        token_path=token_path,
        history_path=history_path,
        snapshot_dir=snapshot_dir,
    )
