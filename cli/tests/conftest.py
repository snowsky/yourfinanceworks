"""Test-wide fixtures for the finance agent CLI suite."""

from __future__ import annotations

import logging

import pytest


@pytest.fixture(autouse=True)
def _reset_finance_agent_logger():
    """Restore the CLI logger to defaults after each test.

    configure_logging() sets propagate=False and attaches a stderr handler;
    that state would otherwise leak across tests and break pytest's caplog,
    which relies on records propagating to the root logger.
    """
    yield
    logger = logging.getLogger("finance_agent_cli")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.propagate = True
    logger.setLevel(logging.NOTSET)
