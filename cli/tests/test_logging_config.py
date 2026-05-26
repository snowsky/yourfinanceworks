"""Logging configuration: format selection, level, stderr destination."""

from __future__ import annotations

import json
import logging

import pytest

from cli.finance_agent_cli.logging_config import LOGGER_NAME, configure_logging


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)


def test_default_format_is_human_readable(monkeypatch, capsys):
    monkeypatch.delenv("FINANCE_AGENT_LOG_FORMAT", raising=False)
    monkeypatch.delenv("FINANCE_AGENT_LOG_LEVEL", raising=False)

    logger = configure_logging()
    logger.info("hello")

    captured = capsys.readouterr()
    assert "hello" in captured.err
    assert captured.out == ""
    # Text format includes level name; not raw JSON.
    assert "INFO" in captured.err
    assert not captured.err.strip().startswith("{")


def test_json_format_emits_structured_lines(monkeypatch, capsys):
    monkeypatch.setenv("FINANCE_AGENT_LOG_FORMAT", "json")

    logger = configure_logging()
    logger.warning("disk-full")

    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["message"] == "disk-full"
    assert payload["level"] == "WARNING"
    assert payload["logger"] == LOGGER_NAME


def test_log_level_env_var_suppresses_lower_levels(monkeypatch, capsys):
    monkeypatch.setenv("FINANCE_AGENT_LOG_LEVEL", "WARNING")

    logger = configure_logging()
    logger.info("noisy-info")
    logger.warning("important")

    captured = capsys.readouterr()
    assert "noisy-info" not in captured.err
    assert "important" in captured.err


def test_configure_logging_is_idempotent(monkeypatch):
    monkeypatch.delenv("FINANCE_AGENT_LOG_FORMAT", raising=False)

    configure_logging()
    configure_logging()

    logger = logging.getLogger(LOGGER_NAME)
    assert len(logger.handlers) == 1
