from pathlib import Path

import pytest

from cli.finance_agent_cli.config import _normalize_api_base_url, load_profile


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://demo", "https://demo/api/v1"),
        ("https://demo/", "https://demo/api/v1"),
        ("https://demo/api", "https://demo/api/v1"),
        ("https://demo/api/", "https://demo/api/v1"),
        ("https://demo/api/v1", "https://demo/api/v1"),
        ("https://demo/api/v1/", "https://demo/api/v1"),
        ("http://localhost:8000", "http://localhost:8000/api/v1"),
    ],
)
def test_normalize_api_base_url_canonicalizes_input(raw, expected):
    assert _normalize_api_base_url(raw) == expected


def test_load_profile_normalizes_base_url(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
          "active_profile": "default",
          "profiles": {
            "default": {
              "base_url": "https://demo.yourfinanceworks.com/",
              "auth_type": "none",
              "interval_seconds": 120
            }
          }
        }
        """
    )

    monkeypatch.delenv("INVOICE_API_BASE_URL", raising=False)
    profile = load_profile(config_path=config_path)

    assert profile.base_url == "https://demo.yourfinanceworks.com"
    assert profile.api_base_url == "https://demo.yourfinanceworks.com/api/v1"
    assert profile.interval_seconds == 120


def test_env_overrides_profile(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"profiles": {"default": {"base_url": "https://demo"}}}')
    monkeypatch.setenv("FINANCE_AGENT_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("FINANCE_AGENT_DRIFT_THRESHOLD", "2.5")

    profile = load_profile(config_path=config_path)

    assert profile.api_base_url == "http://localhost:8000/api/v1"
    assert profile.drift_threshold == 2.5


def test_load_profile_reads_yfw_and_llm_settings(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
          "profiles": {
            "default": {
              "base_url": "https://demo",
              "yfw_api_key": "key_123",
              "llm_provider": "openai",
              "llm_model": "gpt-4o-mini"
            }
          }
        }
        """
    )
    monkeypatch.delenv("FINANCE_AGENT_YFW_API_KEY", raising=False)
    monkeypatch.delenv("YFW_API_KEY", raising=False)
    monkeypatch.delenv("INVOICE_API_KEY", raising=False)

    profile = load_profile(config_path=config_path)

    assert profile.yfw_api_key == "key_123"
    assert profile.llm_provider == "openai"
    assert profile.llm_model == "gpt-4o-mini"
