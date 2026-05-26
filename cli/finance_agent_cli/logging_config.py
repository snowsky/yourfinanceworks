"""Logging configuration for the finance agent CLI.

Logs go to stderr so machine-readable output on stdout (e.g. --json) is not polluted.
Format defaults to a human-readable line; set FINANCE_AGENT_LOG_FORMAT=json for
structured JSON lines suitable for log aggregators.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


LOGGER_NAME = "finance_agent_cli"

_TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_JSON_RESERVED = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
}


class _JsonFormatter(logging.Formatter):
    """Emit each record as one JSON object on a single line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _JSON_RESERVED or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging(level: str | None = None, fmt: str | None = None) -> logging.Logger:
    """Configure the CLI logger from env vars or explicit overrides.

    Safe to call multiple times; replaces existing handlers on the CLI logger only,
    so it does not interfere with library loggers.
    """
    resolved_level = (level or os.getenv("FINANCE_AGENT_LOG_LEVEL") or "INFO").upper()
    resolved_format = (fmt or os.getenv("FINANCE_AGENT_LOG_FORMAT") or "text").lower()

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(resolved_level)
    logger.propagate = False
    for existing in list(logger.handlers):
        logger.removeHandler(existing)

    handler = logging.StreamHandler(stream=sys.stderr)
    if resolved_format == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT))
    logger.addHandler(handler)
    return logger


def get_logger(suffix: str | None = None) -> logging.Logger:
    """Return a child logger under the CLI logger namespace."""
    if not suffix:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{suffix}")
