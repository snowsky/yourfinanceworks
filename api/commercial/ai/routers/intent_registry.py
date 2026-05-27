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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised by validate_args when planner-supplied args fail schema checks."""


@dataclass(frozen=True)
class ArgSpec:
    """Declarative description of one argument a handler accepts from the planner.

    Used by ``IntentRegistry.dispatch`` to coerce, range-check, and reject
    invalid ``tool_options`` *before* the handler runs. Lifts logic that
    individual handlers used to inline.
    """

    name: str
    type: Callable[[Any], Any] = str
    required: bool = False
    default: Any = None
    choices: Optional[tuple] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""


def validate_args(
    schema: list[ArgSpec],
    tool_options: Optional[dict],
) -> dict[str, Any]:
    """Coerce and validate planner-supplied args against a handler's schema.

    Strict on unknown keys: any key in ``tool_options`` not declared in
    ``schema`` raises ``ValidationError``. The planner shouldn't be sending
    arguments the handler can't consume — surfacing it early beats silently
    ignoring it and letting drift creep in.
    """
    options = tool_options or {}
    known = {spec.name for spec in schema}
    unknown = set(options) - known
    if unknown:
        raise ValidationError(
            f"Unsupported argument(s) {sorted(unknown)}. "
            f"Supported: {sorted(known) or 'none'}"
        )

    result: dict[str, Any] = {}
    for spec in schema:
        raw = options.get(spec.name)
        if raw is None:
            if spec.required:
                raise ValidationError(f"Missing required argument: {spec.name!r}")
            result[spec.name] = spec.default
            continue
        try:
            value = spec.type(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"Argument {spec.name!r} expected {spec.type.__name__}; got {raw!r}"
            ) from exc
        if spec.choices is not None and value not in spec.choices:
            raise ValidationError(
                f"Argument {spec.name!r}={value!r} not in allowed choices "
                f"{list(spec.choices)}"
            )
        if spec.min_value is not None and value < spec.min_value:
            raise ValidationError(
                f"Argument {spec.name!r}={value} below minimum {spec.min_value}"
            )
        if spec.max_value is not None and value > spec.max_value:
            raise ValidationError(
                f"Argument {spec.name!r}={value} above maximum {spec.max_value}"
            )
        result[spec.name] = value
    return result


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
    validated_args: dict[str, Any] = field(default_factory=dict)


class IntentHandler(Protocol):
    """Pluggable handler for a single AI-classified intent.

    Implementations declare:

      * ``intent`` — the canonical name routed via ``IntentRegistry.dispatch``
      * ``license_feature`` (optional) — gates execution behind
        ``feature_enabled(...)``; deny path returns the denial envelope
        without calling ``execute``
      * ``args_schema`` (optional) — list of ``ArgSpec`` declarations the
        registry uses to coerce/validate ``ctx.tool_options``. Validated
        values land in ``ctx.validated_args``. Bad input yields a user-
        facing error envelope; the handler is not called.
      * ``execute(ctx)`` — coroutine returning the MCP envelope dict or
        ``None`` to fall back to plain-LLM.
    """

    intent: str
    license_feature: Optional[str]
    license_denied_message: str
    args_schema: Optional[list[ArgSpec]]

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

        schema = getattr(handler, "args_schema", None)
        if schema:
            try:
                ctx.validated_args = validate_args(schema, ctx.tool_options)
            except ValidationError as exc:
                logger.warning(
                    "intent_registry: arg validation failed for %s: %s",
                    ctx.intent,
                    exc,
                )
                return mcp_envelope(
                    ctx,
                    f"I couldn't run the {ctx.intent} request — invalid arguments: {exc}",
                )

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
