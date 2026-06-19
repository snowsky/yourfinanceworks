# api/tests/test_llm_release.py
import pytest
from types import SimpleNamespace

import commercial.ai.routers.llm as llm


def test_materialize_ai_config_copies_four_fields():
    src = SimpleNamespace(provider_name="openai", model_name="gpt-4o-mini",
                          api_key="k", provider_url="u", is_default=True, id=5)
    out = llm.materialize_ai_config(src)
    assert (out.provider_name, out.model_name, out.api_key, out.provider_url) == \
        ("openai", "gpt-4o-mini", "k", "u")
    assert not hasattr(out, "id")  # only the four fields carry over


def test_materialize_tolerates_missing_optional_fields():
    src = SimpleNamespace(provider_name="ollama", model_name="llama3")
    out = llm.materialize_ai_config(src)
    assert out.api_key is None and out.provider_url is None


@pytest.mark.asyncio
async def test_llm_acompletion_releases_connection_before_call(monkeypatch):
    order = []

    class _DB:
        def rollback(self):
            order.append("rollback")

    async def _fake_acompletion(**kwargs):
        order.append("acompletion")
        return {"ok": True, "kwargs": kwargs}

    monkeypatch.setattr(llm, "acompletion", _fake_acompletion, raising=False)
    result = await llm.llm_acompletion(_DB(), model="m", messages=[])
    assert order == ["rollback", "acompletion"]   # released BEFORE the LLM call
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_llm_acompletion_tolerates_none_db(monkeypatch):
    async def _fake_acompletion(**kwargs):
        return {"ok": True}
    monkeypatch.setattr(llm, "acompletion", _fake_acompletion, raising=False)
    result = await llm.llm_acompletion(None, model="m", messages=[])
    assert result["ok"] is True
