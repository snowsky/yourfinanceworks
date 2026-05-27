"""--json flag consistency and CliInputError exit-code contract."""

from __future__ import annotations

import json

import pytest

from cli.finance_agent_cli.api_client import InvestmentAPIClient
from cli.finance_agent_cli.app import main


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "profiles": {
                    "default": {
                        "base_url": "http://localhost:8000",
                        "auth_type": "none",
                    }
                }
            }
        )
    )
    return path


def _stub_summary():
    return {
        "portfolio_count": 2,
        "total_unique_securities": 10,
        "total_combined_value": 50000.0,
        "total_combined_cost": 45000.0,
        "total_gain_loss": 5000.0,
        "total_gain_loss_pct": 11.11,
        "overlapping_securities_count": 1,
        "overlap_percentage": 5.0,
        "top_holdings": [],
        "concentration_warnings": [],
    }


def test_cross_summary_json_flag_emits_machine_json(config_path, capsys, monkeypatch):
    monkeypatch.setattr(InvestmentAPIClient, "get_cross_summary", lambda self: _stub_summary())

    exit_code = main(["--config", str(config_path), "--json", "portfolio", "cross-summary"])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["portfolio_count"] == 2


def test_cross_summary_default_is_human_readable(config_path, capsys, monkeypatch):
    monkeypatch.setattr(InvestmentAPIClient, "get_cross_summary", lambda self: _stub_summary())

    exit_code = main(["--config", str(config_path), "portfolio", "cross-summary"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Cross-Portfolio Summary" in captured.out
    assert "Portfolios: 2" in captured.out
    # Should not be raw JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.out)


def test_overlap_default_is_human_readable(config_path, capsys, monkeypatch):
    monkeypatch.setattr(
        InvestmentAPIClient,
        "get_overlap",
        lambda self: {
            "portfolio_count": 2,
            "total_unique_securities": 10,
            "overlapping_securities_count": 0,
            "overlap_percentage": 0.0,
            "overlap_details": [],
        },
    )

    exit_code = main(["--config", str(config_path), "portfolio", "overlap"])

    assert exit_code == 0
    assert "Cross-Portfolio Overlap Analysis" in capsys.readouterr().out


def test_exposure_json_flag_emits_machine_json(config_path, capsys, monkeypatch):
    monkeypatch.setattr(
        InvestmentAPIClient,
        "get_exposure",
        lambda self: {
            "total_combined_value": 100.0,
            "securities_count": 1,
            "concentration_warnings_count": 0,
            "concentration_warnings": [],
            "exposures": [],
        },
    )

    exit_code = main(["--config", str(config_path), "--json", "portfolio", "exposure"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["securities_count"] == 1


def test_main_returns_2_on_malformed_page_context(config_path, capsys):
    exit_code = main(
        [
            "--config",
            str(config_path),
            "agent",
            "chat",
            "--page-context",
            "not-json",
            "hello",
        ]
    )

    assert exit_code == 2
    assert "Invalid --page-context JSON" in capsys.readouterr().err


def test_main_returns_2_when_page_context_is_not_an_object(config_path, capsys):
    exit_code = main(
        [
            "--config",
            str(config_path),
            "agent",
            "chat",
            "--page-context",
            "[1, 2, 3]",
            "hello",
        ]
    )

    assert exit_code == 2
    assert "--page-context must be a JSON object." in capsys.readouterr().err
