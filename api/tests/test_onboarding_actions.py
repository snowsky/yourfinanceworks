import pytest
from types import SimpleNamespace

import commercial.ai.routers.action_handlers as ah


class _FakeTools:
    def __init__(self):
        self.calls = []

    async def create_client(self, name, email=None, phone=None, address=None):
        self.calls.append(("create_client", {"name": name, "email": email, "phone": phone}))
        return {"success": True, "data": {"id": 1, "name": name}}

    async def set_branding(self, brand_color=None, accent_color=None):
        self.calls.append(("set_branding", {"brand_color": brand_color, "accent_color": accent_color}))
        return {"success": True, "data": {"accent_color": accent_color}}


class _Cfg:
    provider_name = "openai"
    model_name = "gpt-4o-mini"


_USER = SimpleNamespace(id=1, email="u@x.com", tenant_id=1, role="admin", is_superuser=True)


@pytest.fixture
def patch_tools(monkeypatch):
    fake = _FakeTools()

    async def _fake_init(db, current_user):
        return fake

    monkeypatch.setattr(ah, "_init_tools", _fake_init)
    return fake


@pytest.mark.asyncio
async def test_onboarding_confirmed_action_executes_tool(patch_tools):
    result = await ah.handle_early_actions(
        message="", lower_message="", page_context=None, ai_config=_Cfg(), db=None,
        current_user=_USER, mode="onboarding",
        confirmed_action={"action": "create_client", "params": {"name": "Acme", "email": "ap@acme.com"}},
    )
    assert result["success"] is True
    assert result["data"]["executed_action"] == "create_client"
    assert patch_tools.calls == [("create_client", {"name": "Acme", "email": "ap@acme.com", "phone": None})]


@pytest.mark.asyncio
async def test_onboarding_proposes_without_executing(monkeypatch, patch_tools):
    async def _fake_extract(message, ai_config, db):
        return {"action": "create_client", "params": {"name": "Acme", "email": "ap@acme.com"}}

    monkeypatch.setattr(ah, "_extract_onboarding_action", _fake_extract)
    result = await ah.handle_early_actions(
        message="add a client called Acme ap@acme.com", lower_message="add a client called acme ap@acme.com",
        page_context=None, ai_config=_Cfg(), db=None, current_user=_USER, mode="onboarding",
    )
    assert result["data"]["type"] == "proposed_action"
    assert result["data"]["action"] == "create_client"
    assert patch_tools.calls == []  # nothing executed


@pytest.mark.asyncio
async def test_onboarding_rejects_non_whitelisted_action(patch_tools):
    result = await ah.handle_early_actions(
        message="", lower_message="", page_context=None, ai_config=_Cfg(), db=None,
        current_user=_USER, mode="onboarding",
        confirmed_action={"action": "delete_everything", "params": {}},
    )
    assert result["success"] is False
    assert patch_tools.calls == []


@pytest.mark.asyncio
async def test_onboarding_no_action_falls_through(monkeypatch):
    async def _none(message, ai_config, db):
        return None

    monkeypatch.setattr(ah, "_extract_onboarding_action", _none)
    result = await ah.handle_early_actions(
        message="what is an invoice?", lower_message="what is an invoice?", page_context=None,
        ai_config=_Cfg(), db=None, current_user=_USER, mode="onboarding",
    )
    assert result is None  # falls through to normal chat answer


def test_clean_onboarding_name_strips_leading_filler():
    assert ah._clean_onboarding_name("with john doe") == "john doe"
    assert ah._clean_onboarding_name("named Acme Co") == "Acme Co"
    assert ah._clean_onboarding_name("called  Globex") == "Globex"
    assert ah._clean_onboarding_name("with the John") == "John"  # iterates


def test_clean_onboarding_name_leaves_real_names_untouched():
    assert ah._clean_onboarding_name("John Doe") == "John Doe"
    assert ah._clean_onboarding_name("Acme Corp") == "Acme Corp"
    assert ah._clean_onboarding_name(None) is None


@pytest.mark.asyncio
async def test_extract_applies_name_cleaning(monkeypatch):
    import commercial.ai.routers.llm as llm_mod

    async def _fake_acompletion(**kwargs):
        return {
            "choices": [
                {"message": {"content": '{"action":"create_client","params":{"name":"with john doe","email":"jd@x.com"}}'}}
            ]
        }

    monkeypatch.setattr(llm_mod, "acompletion", _fake_acompletion, raising=False)
    out = await ah._extract_onboarding_action("create a client with john doe email jd@x.com", _Cfg(), None)
    assert out["action"] == "create_client"
    assert out["params"]["name"] == "john doe"  # 'with ' stripped
