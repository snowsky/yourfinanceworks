"""Size guardrails on chat messages."""

from __future__ import annotations

import json
import logging

import pytest

from cli.finance_agent_cli.api_client import InvestmentAPIClient
from cli.finance_agent_cli.app import (
    CHAT_PASTE_WARNING_BYTES,
    MAX_CHAT_MESSAGE_BYTES,
    CliInputError,
    _validate_chat_message,
    main,
)


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


def test_message_under_warning_threshold_is_silent(caplog):
    with caplog.at_level(logging.WARNING, logger="finance_agent_cli.app"):
        _validate_chat_message("hi")
    assert caplog.records == []


def test_message_over_paste_threshold_logs_warning(caplog):
    payload = "x" * (CHAT_PASTE_WARNING_BYTES + 1)
    with caplog.at_level(logging.WARNING, logger="finance_agent_cli.app"):
        _validate_chat_message(payload)
    assert any("paste-warning threshold" in record.message for record in caplog.records)


def test_message_over_hard_limit_raises_cli_input_error():
    payload = "x" * (MAX_CHAT_MESSAGE_BYTES + 1)
    with pytest.raises(CliInputError) as exc_info:
        _validate_chat_message(payload)
    assert "max is" in str(exc_info.value)


def test_main_returns_2_for_oversized_chat_message(config_path, capsys):
    huge = "x" * (MAX_CHAT_MESSAGE_BYTES + 1)
    exit_code = main(
        [
            "--config",
            str(config_path),
            "agent",
            "chat",
            huge,
        ]
    )

    assert exit_code == 2
    assert "max is" in capsys.readouterr().err


def test_size_check_counts_utf8_bytes_not_codepoints():
    """A 5000-character string of 4-byte UTF-8 emoji should exceed the 8 KB limit."""
    emoji = "🚀"  # 4 bytes in UTF-8
    payload = emoji * 2049  # 8196 bytes, just over 8 KB
    with pytest.raises(CliInputError):
        _validate_chat_message(payload)
