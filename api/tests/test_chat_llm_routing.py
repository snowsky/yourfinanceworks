import pytest
from types import SimpleNamespace

import commercial.ai.routers.chat as chat


@pytest.mark.asyncio
async def test_plan_routes_through_llm_acompletion_with_db(monkeypatch):
    captured = {}

    async def _spy(db, **kwargs):
        captured["db"] = db
        # minimal litellm-shaped response: empty content -> empty plan
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))])

    monkeypatch.setattr(chat, "llm_acompletion", _spy)
    cfg = SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini", api_key="k", provider_url=None)
    sentinel_db = object()
    await chat._plan_mcp_tool_intents(message="hi", page_context_block="", ai_config=cfg, db=sentinel_db)
    assert captured["db"] is sentinel_db   # the connection owner was passed to the helper


@pytest.mark.asyncio
async def test_synthesize_routes_through_llm_acompletion_with_db(monkeypatch):
    captured = {}

    async def _spy(db, **kwargs):
        captured["db"] = db
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    monkeypatch.setattr(chat, "llm_acompletion", _spy)
    cfg = SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini", api_key="k", provider_url=None)
    sentinel_db = object()
    out = await chat._synthesize_tool_results(
        message="hi", planned_results=[("clients", {"data": []})],
        page_context_block="", ai_config=cfg, db=sentinel_db,
    )
    assert captured["db"] is sentinel_db
    assert out == "ok"
