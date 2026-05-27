# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.
"""Registry pattern for AI chat intent handlers.

Replaces the long ``dispatch_intent`` if/elif chain. Each handler declares
its intent name, optional feature-license gate, and an ``execute`` coroutine
that returns the MCP response envelope (or ``None`` to fall back to the LLM).

Migration is incremental: legacy intents stay in ``intent_handlers.py`` until
they are ported here one at a time. ``dispatch_intent`` consults the registry
first; if no handler is registered for the intent, it falls through to the
legacy branches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Protocol

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


@dataclass
class IntentContext:
    """Everything an intent handler needs to do its work.

    Constructed by ``dispatch_intent`` for each chat turn and passed verbatim
    to the registered handler. Centralizing this struct means new fields can
    be added later (request_id, tenant_id, feature_flags...) without changing
    every handler signature.
    """

    intent: str
    message: str
    lower_message: str
    tools: Any
    ai_config: Any
    page_context: Optional[dict]
    db: "Session"
    tool_options: Optional[dict] = None


class IntentHandler(Protocol):
    """Pluggable handler for a single AI-classified intent.

    Implementations declare ``intent`` (the canonical name routed via
    ``IntentRegistry.dispatch``), optionally a ``license_feature`` string
    that gates execution behind ``feature_enabled(...)``, and a coroutine
    ``execute(ctx)`` that returns an MCP envelope dict or ``None``.
    """

    intent: str
    license_feature: Optional[str]
    license_denied_message: str

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        ...


class IntentRegistry:
    """Maps intent strings to ``IntentHandler`` implementations.

    The registry is responsible for:
      * applying the feature-license gate before calling ``execute``
      * trapping handler exceptions and returning ``None`` (legacy behavior:
        an exception falls back to plain-LLM, never bubbles to the user)
      * emitting structured logs so dispatch decisions are observable
    """

    def __init__(self) -> None:
        self._handlers: dict[str, IntentHandler] = {}

    def register(self, handler: IntentHandler) -> "IntentRegistry":
        if handler.intent in self._handlers:
            raise ValueError(f"intent {handler.intent!r} already registered")
        self._handlers[handler.intent] = handler
        return self

    def is_registered(self, intent: str) -> bool:
        return intent in self._handlers

    def registered_intents(self) -> list[str]:
        return sorted(self._handlers.keys())

    async def dispatch(self, ctx: IntentContext) -> Optional[dict]:
        handler = self._handlers.get(ctx.intent)
        if handler is None:
            return None

        logger.info("intent_registry: dispatching intent=%s", ctx.intent)

        license_feature = getattr(handler, "license_feature", None)
        if license_feature:
            from core.utils.feature_gate import feature_enabled  # deferred — keeps import light at test time

            if not feature_enabled(license_feature, ctx.db):
                logger.info(
                    "intent_registry: feature %s disabled; returning denial envelope",
                    license_feature,
                )
                return mcp_envelope(ctx, handler.license_denied_message)

        try:
            return await handler.execute(ctx)
        except Exception:
            logger.exception(
                "intent_registry: handler for %s raised; falling back to LLM",
                ctx.intent,
            )
            return None


def mcp_envelope(ctx: IntentContext, response_text: str) -> dict:
    """Build the standard MCP success envelope used by every handler."""
    return {
        "success": True,
        "data": {
            "response": response_text,
            "provider": ctx.ai_config.provider_name,
            "model": ctx.ai_config.model_name,
            "source": "mcp_tools",
        },
    }


default_registry = IntentRegistry()
"""Module-level registry populated by ``intents/__init__.py`` at import time."""
