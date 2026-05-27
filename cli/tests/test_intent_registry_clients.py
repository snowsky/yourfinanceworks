"""Tests for the clients handler — create / search / list with regex extraction.

Covers the routing decision, the regex extraction edge cases, count detection,
the friendly-error envelope on list/search failure, and the create-path
behavior change (the legacy branch silently swallowed the create-success
message; this handler returns it).
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
def clients(intent_registry, helpers):
    return _load_module(
        "commercial.ai.routers.intents.clients",
        "commercial/ai/routers/intents/clients.py",
    )


def _ai_config():
    return SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini")


def _ctx(intent_registry, *, tools, message):
    return intent_registry.IntentContext(
        intent="clients",
        message=message,
        lower_message=message.lower(),
        tools=tools,
        ai_config=_ai_config(),
        page_context=None,
        db=None,
        tool_options=None,
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


# ---------- keyword detection ----------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("create a client named Acme", True),
        ("add new client", True),
        ("new client called foo", True),
        ("list clients", False),
        ("search clients", False),
    ],
)
def test_is_create_intent(clients, message, expected):
    assert clients.is_create_intent(message.lower()) is expected


@pytest.mark.parametrize(
    "message,expected",
    [
        ("how many clients do I have", True),
        ("count my clients", True),
        ("total number of clients", True),
        ("number of clients", True),
        ("list my clients", False),
        ("create a new client", False),
    ],
)
def test_is_count_intent(clients, message, expected):
    assert clients.is_count_intent(message.lower()) is expected


# ---------- regex extraction ----------


def test_extract_name_with_named_keyword(clients):
    # The handler always passes the lowercased message; mirror that here.
    name, email, phone = clients.extract_create_client_args(
        "create a client named acme corp"
    )
    assert name == "acme corp"
    assert email is None
    assert phone is None


def test_extract_name_quoted(clients):
    name, _, _ = clients.extract_create_client_args(
        "create client 'my client' with details"
    )
    assert name == "my client"


def test_extract_name_with_email_and_phone(clients):
    name, email, phone = clients.extract_create_client_args(
        "create client acme with email foo@bar.com phone 555-1212"
    )
    # The first regex captures everything up to a comma; here it grabs the name.
    assert "acme" in (name or "")
    assert email == "foo@bar.com"
    assert phone == "555-1212"


def test_extract_no_name_returns_none(clients):
    name, _, _ = clients.extract_create_client_args("create something else entirely")
    assert name is None


def test_extract_email_only_when_email_keyword_present(clients):
    _, email, _ = clients.extract_create_client_args(
        "add client foo@bar.com"
    )
    assert email is None  # no "email" keyword preceding the address


# ---------- create path ----------


def test_create_success_returns_confirmation_envelope(intent_registry, clients):
    """Behavior change vs. legacy: the create-success envelope now actually reaches the user."""
    tools = _RecordingTools(
        create_client={
            "success": True,
            "data": {"id": 42, "name": "Acme", "email": "a@b.com"},
        }
    )
    handler = clients.ClientsHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="create a client named Acme"))
    )
    body = result["data"]["response"]

    assert tools.calls == [("create_client", {"name": "acme", "email": None, "phone": None})]
    assert "Client Created Successfully" in body
    assert "ID:** 42" in body


def test_create_failure_returns_error_envelope(intent_registry, clients):
    tools = _RecordingTools(
        create_client={"success": False, "error": "duplicate name"}
    )
    handler = clients.ClientsHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="create a client named Acme"))
    )

    assert "Failed to create client: duplicate name" in result["data"]["response"]


def test_create_without_extractable_name_returns_help_envelope(intent_registry, clients):
    tools = _RecordingTools()
    handler = clients.ClientsHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="create something"))
    )

    # No tool call should have been made
    assert tools.calls == []
    assert result["data"]["response"] == clients.NAME_REQUIRED_MESSAGE


# ---------- search path ----------


def test_search_with_captured_query_calls_search_tool(intent_registry, clients):
    tools = _RecordingTools(
        search_clients={
            "success": True,
            "data": [{"id": 1, "name": "Acme", "outstanding_balance": 100}],
        }
    )
    handler = clients.ClientsHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="search for acme"))
    )["data"]["response"]

    assert tools.calls == [("search_clients", {"query": "acme"})]
    assert "Client Management Dashboard" in body
    assert "Acme" in body


def test_search_keyword_without_query_defaults_to_list_with_limit_10(intent_registry, clients):
    tools = _RecordingTools(list_clients={"success": True, "data": []})
    handler = clients.ClientsHandler()
    asyncio.run(handler.execute(_ctx(intent_registry, tools=tools, message="search")))
    assert tools.calls == [("list_clients", {"limit": 10})]


# ---------- list path ----------


def test_list_default_uses_limit_20(intent_registry, clients):
    tools = _RecordingTools(list_clients={"success": True, "data": []})
    handler = clients.ClientsHandler()
    asyncio.run(handler.execute(_ctx(intent_registry, tools=tools, message="show me my clients")))
    assert tools.calls == [("list_clients", {"limit": 20})]


def test_count_request_uses_limit_1000_and_short_message(intent_registry, clients):
    tools = _RecordingTools(
        list_clients={"success": True, "data": [{"id": i, "name": f"c{i}"} for i in range(7)]}
    )
    handler = clients.ClientsHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="how many clients do I have"))
    )

    assert tools.calls == [("list_clients", {"limit": 1000})]
    assert result["data"]["response"] == clients.format_count_response(7)
    assert "7 clients" in result["data"]["response"]


def test_count_request_singular_grammar(intent_registry, clients):
    tools = _RecordingTools(
        list_clients={"success": True, "data": [{"id": 1, "name": "only"}]}
    )
    handler = clients.ClientsHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="how many clients"))
    )
    response = result["data"]["response"]
    assert "**1 client**" in response  # singular
    assert "**1 clients**" not in response


def test_list_failure_returns_friendly_error_envelope(intent_registry, clients):
    """Legacy clients-specific behavior preserved: list failures don't fall back to LLM."""
    tools = _RecordingTools(list_clients={"success": False, "error": "db locked"})
    handler = clients.ClientsHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="show clients"))
    )
    assert result["data"]["response"] == "Error retrieving clients: db locked"


def test_list_empty_returns_no_clients_message(intent_registry, clients):
    tools = _RecordingTools(list_clients={"success": True, "data": []})
    handler = clients.ClientsHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="show clients"))
    )
    assert result["data"]["response"] == clients.NO_CLIENTS_MESSAGE


def test_list_renders_aggregate_balances(intent_registry, clients):
    tools = _RecordingTools(
        list_clients={
            "success": True,
            "data": [
                {"id": 1, "name": "A", "email": "a@x.com", "outstanding_balance": 100},
                {"id": 2, "name": "B", "phone": "555", "outstanding_balance": 250},
                {"id": 3, "name": "C"},  # no email/phone/balance
            ],
        }
    )
    handler = clients.ClientsHandler()
    body = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=tools, message="show clients"))
    )["data"]["response"]

    assert "Total Clients:** 3" in body
    assert "Total Outstanding Balance:** $350.00" in body
    assert "Average Balance per Client:** $116.67" in body


def test_list_tool_raises_is_wrapped_into_error_envelope(intent_registry, clients):
    """Legacy try/except around list_clients preserved; raised exceptions become friendly errors."""

    class _ExplodingTools:
        async def list_clients(self, **_kwargs):
            raise RuntimeError("network down")

    handler = clients.ClientsHandler()
    result = asyncio.run(
        handler.execute(_ctx(intent_registry, tools=_ExplodingTools(), message="show clients"))
    )
    assert "Error retrieving clients: network down" in result["data"]["response"]


# ---------- dispatch_intent shim ----------


def test_dispatch_intent_is_now_a_registry_shim():
    """intent_handlers.py no longer carries any legacy if/elif branches."""
    src = (API_DIR / "commercial" / "ai" / "routers" / "intent_handlers.py").read_text()
    assert 'if intent == "' not in src
    assert "elif intent ==" not in src
    # The shim still exposes dispatch_intent for the chat router to call.
    assert "async def dispatch_intent" in src
