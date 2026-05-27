# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""Shared utilities for intent handlers."""

from __future__ import annotations

import re
from typing import Any, Optional


_SEARCH_RE = re.compile(r"""(?:search|find)\s+(?:for\s+)?["']?([^"']+)["']?""")


def detect_search_intent(lower_message: str) -> tuple[bool, Optional[str]]:
    """Inspect a chat message for an explicit search request.

    Returns (is_search_request, captured_query_or_None). The two-tuple lets
    the caller distinguish three cases that have different defaults in the
    legacy handlers:

      * search request with a captured query  -> call the search tool
      * search request, no query captured     -> fall back to a small list
      * no search request                     -> list with the default page
    """
    if "search" not in lower_message and "find" not in lower_message:
        return (False, None)
    match = _SEARCH_RE.search(lower_message)
    return (True, match.group(1) if match else None)


def _requested_limit_from_options(
    tool_options: Optional[dict[str, Any]],
    *,
    default: int,
    maximum: int = 100,
) -> int:
    """Read planned result limits from the agent tool plan.

    Originally lived in intent_handlers.py; relocated here so it can be reused
    by any registry-resident handler. The leading underscore is kept for
    backwards-compatibility with tests that already import this exact name.
    """
    if not tool_options or tool_options.get("limit") is None:
        return default
    try:
        return max(1, min(maximum, int(tool_options["limit"])))
    except (TypeError, ValueError):
        return default
