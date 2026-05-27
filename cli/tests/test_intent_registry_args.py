"""Tests for the args-schema validation layer on IntentRegistry.

Covers ``validate_args`` directly (the pure function) and the registry's
integration of it (validation runs before ``execute``; bad args yield an
error envelope; handlers without ``args_schema`` are untouched). Also pins
the migration of ``expenses`` and ``invoices`` to consume
``ctx.validated_args["limit"]`` instead of poking ``tool_options`` by hand.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


API_DIR = Path(__file__).resolve().parents[2] / "api"


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, API_DIR / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def intent_registry():
    return _load_module(
        "commercial.ai.routers.intent_registry",
        "commercial/ai/routers/intent_registry.py",
    )


@pytest.fixture(scope="module")
def helpers(intent_registry):
    return _load_module(
        "commercial.ai.routers.intents._helpers",
        "commercial/ai/routers/intents/_helpers.py",
    )


@pytest.fixture(scope="module")
def expenses_module(intent_registry, helpers):
    return _load_module(
        "commercial.ai.routers.intents.expenses",
        "commercial/ai/routers/intents/expenses.py",
    )


@pytest.fixture(scope="module")
def invoices_module(intent_registry, helpers):
    return _load_module(
        "commercial.ai.routers.intents.invoices",
        "commercial/ai/routers/intents/invoices.py",
    )


def _ai_config():
    return SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini")


def _ctx(intent_registry, intent, *, tools=None, message="?", tool_options=None):
    return intent_registry.IntentContext(
        intent=intent,
        message=message,
        lower_message=message.lower(),
        tools=tools,
        ai_config=_ai_config(),
        page_context=None,
        db=None,
        tool_options=tool_options,
    )


class _RecordingTools:
    def __init__(self, **results):
        self.calls: list[tuple[str, dict]] = []
        self._results = results

    def __getattr__(self, name):
        async def _impl(**kwargs):
            self.calls.append((name, kwargs))
            return self._results.get(name, {"success": False})
        return _impl


# ---------- validate_args (pure function) ----------


def test_validate_args_returns_defaults_when_options_empty(intent_registry):
    schema = [intent_registry.ArgSpec(name="limit", type=int, default=20)]
    assert intent_registry.validate_args(schema, None) == {"limit": 20}
    assert intent_registry.validate_args(schema, {}) == {"limit": 20}


def test_validate_args_coerces_to_declared_type(intent_registry):
    schema = [intent_registry.ArgSpec(name="limit", type=int, default=20)]
    assert intent_registry.validate_args(schema, {"limit": "7"}) == {"limit": 7}


def test_validate_args_rejects_unknown_keys(intent_registry):
    schema = [intent_registry.ArgSpec(name="limit", type=int, default=20)]
    with pytest.raises(intent_registry.ValidationError, match="Unsupported argument"):
        intent_registry.validate_args(schema, {"limit": 5, "skip": 0})


def test_validate_args_rejects_missing_required(intent_registry):
    schema = [intent_registry.ArgSpec(name="portfolio_id", type=int, required=True)]
    with pytest.raises(intent_registry.ValidationError, match="Missing required"):
        intent_registry.validate_args(schema, {})


def test_validate_args_rejects_type_mismatch(intent_registry):
    schema = [intent_registry.ArgSpec(name="limit", type=int, default=20)]
    with pytest.raises(intent_registry.ValidationError, match="expected int"):
        intent_registry.validate_args(schema, {"limit": "not-a-number"})


def test_validate_args_enforces_min_value(intent_registry):
    schema = [intent_registry.ArgSpec(name="limit", type=int, default=20, min_value=1)]
    with pytest.raises(intent_registry.ValidationError, match="below minimum"):
        intent_registry.validate_args(schema, {"limit": 0})


def test_validate_args_enforces_max_value(intent_registry):
    schema = [intent_registry.ArgSpec(name="limit", type=int, default=20, max_value=100)]
    with pytest.raises(intent_registry.ValidationError, match="above maximum"):
        intent_registry.validate_args(schema, {"limit": 500})


def test_validate_args_enforces_choices(intent_registry):
    schema = [intent_registry.ArgSpec(
        name="period", type=str, default="30d", choices=("7d", "30d", "90d")
    )]
    with pytest.raises(intent_registry.ValidationError, match="not in allowed choices"):
        intent_registry.validate_args(schema, {"period": "14d"})


def test_validate_args_accepts_choice(intent_registry):
    schema = [intent_registry.ArgSpec(
        name="period", type=str, default="30d", choices=("7d", "30d", "90d")
    )]
    assert intent_registry.validate_args(schema, {"period": "7d"}) == {"period": "7d"}


# ---------- registry integration ----------


class _SchemaHandler:
    intent = "demo"
    license_feature = None
    license_denied_message = ""
    args_schema = None  # set per-test

    def __init__(self, args_schema, return_envelope=None):
        self.args_schema = args_schema
        self._return = return_envelope or {"success": True, "data": {"response": "ok"}}
        self.received_args = None

    async def execute(self, ctx):
        self.received_args = dict(ctx.validated_args)
        return self._return


def test_registry_populates_validated_args_before_execute(intent_registry):
    handler = _SchemaHandler(args_schema=[
        intent_registry.ArgSpec(name="limit", type=int, default=20),
    ])
    registry = intent_registry.IntentRegistry().register(handler)

    asyncio.run(registry.dispatch(_ctx(intent_registry, "demo", tool_options={"limit": 7})))

    assert handler.received_args == {"limit": 7}


def test_registry_applies_defaults_when_planner_omits_keys(intent_registry):
    handler = _SchemaHandler(args_schema=[
        intent_registry.ArgSpec(name="limit", type=int, default=20),
    ])
    registry = intent_registry.IntentRegistry().register(handler)

    asyncio.run(registry.dispatch(_ctx(intent_registry, "demo", tool_options=None)))

    assert handler.received_args == {"limit": 20}


def test_registry_returns_error_envelope_on_validation_failure(intent_registry):
    handler = _SchemaHandler(args_schema=[
        intent_registry.ArgSpec(name="limit", type=int, default=20, max_value=100),
    ])
    registry = intent_registry.IntentRegistry().register(handler)

    result = asyncio.run(
        registry.dispatch(_ctx(intent_registry, "demo", tool_options={"limit": 9999}))
    )

    assert result is not None
    assert result["success"] is True
    body = result["data"]["response"]
    assert "invalid arguments" in body
    assert "above maximum" in body
    # Handler must NOT have run.
    assert handler.received_args is None


def test_handler_without_args_schema_is_unaffected(intent_registry):
    """Back-compat: handlers that don't declare args_schema bypass validation entirely."""

    class _NoSchemaHandler:
        intent = "noschema"
        license_feature = None
        license_denied_message = ""
        # Deliberately no args_schema attribute.
        def __init__(self):
            self.calls = 0

        async def execute(self, ctx):
            self.calls += 1
            assert ctx.validated_args == {}  # empty, not populated
            return {"success": True, "data": {"response": "ok"}}

    handler = _NoSchemaHandler()
    registry = intent_registry.IntentRegistry().register(handler)

    result = asyncio.run(
        registry.dispatch(_ctx(intent_registry, "noschema", tool_options={"anything": 1}))
    )

    assert handler.calls == 1
    assert result["data"]["response"] == "ok"


# ---------- expenses migration ----------


def test_expenses_handler_declares_limit_schema(expenses_module):
    schema = expenses_module.ExpensesHandler.args_schema
    assert len(schema) == 1
    spec = schema[0]
    assert spec.name == "limit"
    assert spec.type is int
    assert spec.default == 20
    assert spec.min_value == 1
    assert spec.max_value == 100


def test_expenses_uses_planner_supplied_limit_via_registry(intent_registry, expenses_module):
    tools = _RecordingTools(
        list_expenses={"success": True, "data": [{"id": 1, "amount": 10}]}
    )
    registry = intent_registry.IntentRegistry()
    expenses_module.register(registry)

    asyncio.run(
        registry.dispatch(
            _ctx(
                intent_registry,
                "expenses",
                tools=tools,
                message="show expenses",
                tool_options={"limit": 7},
            )
        )
    )

    assert tools.calls == [("list_expenses", {"limit": 7})]


def test_expenses_falls_back_to_default_limit_when_no_options(intent_registry, expenses_module):
    tools = _RecordingTools(list_expenses={"success": True, "data": [{"id": 1, "amount": 10}]})
    registry = intent_registry.IntentRegistry()
    expenses_module.register(registry)

    asyncio.run(
        registry.dispatch(_ctx(intent_registry, "expenses", tools=tools, message="show expenses"))
    )

    assert tools.calls == [("list_expenses", {"limit": 20})]


def test_expenses_rejects_oversized_limit_with_error_envelope(intent_registry, expenses_module):
    tools = _RecordingTools(list_expenses={"success": True, "data": []})
    registry = intent_registry.IntentRegistry()
    expenses_module.register(registry)

    result = asyncio.run(
        registry.dispatch(
            _ctx(
                intent_registry,
                "expenses",
                tools=tools,
                message="show expenses",
                tool_options={"limit": 500},
            )
        )
    )

    # Tool must not have been called; user gets a clear error.
    assert tools.calls == []
    assert "invalid arguments" in result["data"]["response"]


# ---------- invoices migration (new user) ----------


def test_invoices_now_accepts_planner_supplied_limit(intent_registry, invoices_module):
    """Pre-PR, invoices ignored the planner; now it honors limit on the default list path."""
    tools = _RecordingTools(list_invoices={"success": True, "data": [{"id": 1, "amount": 100}]})
    registry = intent_registry.IntentRegistry()
    invoices_module.register(registry)

    asyncio.run(
        registry.dispatch(
            _ctx(
                intent_registry,
                "invoices",
                tools=tools,
                message="show invoices",
                tool_options={"limit": 50},
            )
        )
    )

    assert tools.calls == [("list_invoices", {"limit": 50})]


def test_invoices_default_limit_is_still_20(intent_registry, invoices_module):
    tools = _RecordingTools(list_invoices={"success": True, "data": [{"id": 1, "amount": 100}]})
    registry = intent_registry.IntentRegistry()
    invoices_module.register(registry)

    asyncio.run(
        registry.dispatch(_ctx(intent_registry, "invoices", tools=tools, message="show invoices"))
    )

    assert tools.calls == [("list_invoices", {"limit": 20})]


def test_invoices_search_fallback_still_hardcoded_to_10(intent_registry, invoices_module):
    """The search-no-query fallback page size is intentionally NOT planner-controlled."""
    tools = _RecordingTools(list_invoices={"success": True, "data": []})
    registry = intent_registry.IntentRegistry()
    invoices_module.register(registry)

    asyncio.run(
        registry.dispatch(
            _ctx(
                intent_registry,
                "invoices",
                tools=tools,
                message="search",
                tool_options={"limit": 99},
            )
        )
    )

    assert tools.calls == [("list_invoices", {"limit": 10})]
