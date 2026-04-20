from pathlib import Path

from cli.finance_agent_cli.config import load_profile


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
