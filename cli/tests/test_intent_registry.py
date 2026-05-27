"""Unit tests for the AI intent registry + the migrated investments handler.

Backend modules live under ``api/`` and use absolute imports like
``from commercial.ai.routers.intent_registry import ...``. The CLI test runner
does not have ``api/`` on its path, so we use the same ``importlib`` pattern
that the existing ``test_ai_intent_handlers.py`` uses, and pre-register the
loaded modules in ``sys.modules`` under their absolute names so the handler's
absolute imports resolve.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


API_DIR = Path(__file__).resolve().parents[2] / "api"


def _load_module(name: str, relative_path: str):
    """Load a backend module by file path and register it in sys.modules under `name`."""
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
def investments_handler(intent_registry):
    # Loading the handler requires the registry module already in sys.modules.
    return _load_module(
        "commercial.ai.routers.intents.investments",
        "commercial/ai/routers/intents/investments.py",
    )


def _ai_config():
    return SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini")


def _ctx(intent_registry, intent: str, *, tools=None):
    return intent_registry.IntentContext(
        intent=intent,
        message="how am I doing?",
        lower_message="how am i doing?",
        tools=tools,
        ai_config=_ai_config(),
        page_context=None,
        db=None,
        tool_options=None,
    )


# ---------- mcp_envelope ----------


def test_mcp_envelope_includes_provider_and_source(intent_registry):
    ctx = _ctx(intent_registry, intent="any")
    payload = intent_registry.mcp_envelope(ctx, "hello user")
    assert payload == {
        "success": True,
        "data": {
            "response": "hello user",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "source": "mcp_tools",
        },
    }


# ---------- IntentRegistry ----------


class _StubHandler:
    def __init__(
        self,
        intent: str,
        *,
        license_feature: str | None = None,
        return_envelope: dict | None = None,
        raise_exception: Exception | None = None,
    ):
        self.intent = intent
        self.license_feature = license_feature
        self.license_denied_message = f"{intent} disabled"
        self._return = return_envelope
        self._raise = raise_exception
        self.calls = 0

    async def execute(self, ctx):
        self.calls += 1
        if self._raise:
            raise self._raise
        return self._return


def test_registry_dispatches_to_registered_handler(intent_registry):
    envelope = {"success": True, "data": {"response": "done"}}
    handler = _StubHandler("payments", return_envelope=envelope)
    registry = intent_registry.IntentRegistry().register(handler)

    result = asyncio.run(registry.dispatch(_ctx(intent_registry, "payments")))

    assert result is envelope
    assert handler.calls == 1


def test_registry_returns_none_for_unregistered_intent(intent_registry):
    registry = intent_registry.IntentRegistry()

    result = asyncio.run(registry.dispatch(_ctx(intent_registry, "unknown")))

    assert result is None


def test_registry_returns_none_when_handler_raises(intent_registry, caplog):
    handler = _StubHandler("payments", raise_exception=RuntimeError("boom"))
    registry = intent_registry.IntentRegistry().register(handler)

    with caplog.at_level(logging.ERROR, logger="commercial.ai.routers.intent_registry"):
        result = asyncio.run(registry.dispatch(_ctx(intent_registry, "payments")))

    assert result is None
    assert any("raised" in record.message for record in caplog.records)


def test_registry_denies_when_license_feature_disabled(intent_registry, monkeypatch):
    # Stub out the deferred feature_gate import so dispatch sees feature_enabled=False.
    fake_gate = type(sys)("core.utils.feature_gate")
    fake_gate.feature_enabled = lambda feature, db: False  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "core.utils.feature_gate", fake_gate)
    # Also need the parent packages to exist so the import machinery is happy.
    for name in ("core", "core.utils"):
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name) or type(sys)(name))

    handler = _StubHandler(
        "investments",
        license_feature="investments",
        return_envelope={"should": "not be reached"},
    )
    registry = intent_registry.IntentRegistry().register(handler)

    result = asyncio.run(registry.dispatch(_ctx(intent_registry, "investments")))

    assert handler.calls == 0
    assert result["success"] is True
    assert "investments disabled" == result["data"]["response"]


def test_registry_executes_when_license_feature_enabled(intent_registry, monkeypatch):
    fake_gate = type(sys)("core.utils.feature_gate")
    fake_gate.feature_enabled = lambda feature, db: True  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "core.utils.feature_gate", fake_gate)
    for name in ("core", "core.utils"):
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name) or type(sys)(name))

    envelope = {"success": True, "data": {"response": "OK"}}
    handler = _StubHandler(
        "investments",
        license_feature="investments",
        return_envelope=envelope,
    )
    registry = intent_registry.IntentRegistry().register(handler)

    result = asyncio.run(registry.dispatch(_ctx(intent_registry, "investments")))

    assert handler.calls == 1
    assert result is envelope


def test_registry_rejects_duplicate_registration(intent_registry):
    registry = intent_registry.IntentRegistry()
    registry.register(_StubHandler("payments"))

    with pytest.raises(ValueError, match="payments"):
        registry.register(_StubHandler("payments"))


def test_registry_lists_registered_intents(intent_registry):
    registry = intent_registry.IntentRegistry()
    registry.register(_StubHandler("payments"))
    registry.register(_StubHandler("clients"))

    assert registry.registered_intents() == ["clients", "payments"]


# ---------- InvestmentsHandler ----------


class _StubInvestmentTools:
    def __init__(self, result):
        self._result = result
        self.calls = 0

    async def list_portfolios(self):
        self.calls += 1
        return self._result


def test_investments_handler_renders_portfolios(intent_registry, investments_handler):
    tools = _StubInvestmentTools(
        {
            "success": True,
            "data": [
                {
                    "name": "Growth",
                    "type": "TAXABLE",
                    "total_value": 10000.0,
                    "return_percentage": 12.5,
                    "holdings_count": 3,
                },
                {
                    "name": "Retirement",
                    "type": "IRA",
                    "total_value": 25000.0,
                    "return_percentage": -2.0,
                    "holdings_count": 5,
                },
            ],
        }
    )
    handler = investments_handler.InvestmentsHandler()
    ctx = _ctx(intent_registry, "investments", tools=tools)

    result = asyncio.run(handler.execute(ctx))

    assert result["success"] is True
    body = result["data"]["response"]
    assert "Total Portfolios:** 2" in body
    assert "$35,000.00" in body
    assert "+12.50%" in body
    assert "-2.00%" in body


def test_investments_handler_returns_no_portfolios_message(intent_registry, investments_handler):
    tools = _StubInvestmentTools({"success": True, "data": []})
    handler = investments_handler.InvestmentsHandler()
    ctx = _ctx(intent_registry, "investments", tools=tools)

    result = asyncio.run(handler.execute(ctx))

    assert result["data"]["response"] == investments_handler.NO_PORTFOLIOS_MESSAGE


def test_investments_handler_returns_none_on_tool_failure(intent_registry, investments_handler):
    tools = _StubInvestmentTools({"success": False, "error": "db down"})
    handler = investments_handler.InvestmentsHandler()
    ctx = _ctx(intent_registry, "investments", tools=tools)

    result = asyncio.run(handler.execute(ctx))

    assert result is None


def test_investments_handler_declares_license_feature(investments_handler):
    handler = investments_handler.InvestmentsHandler()
    assert handler.intent == "investments"
    assert handler.license_feature == "investments"
    assert "not enabled" in handler.license_denied_message
