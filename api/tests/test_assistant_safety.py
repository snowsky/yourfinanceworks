"""Isolated assistant regressions; no application startup or live database required.

Run with pytest --noconftest tests/test_assistant_safety.py.
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(monkeypatch, name, path, dependencies):
    for key, values in dependencies.items():
        module = ModuleType(key)
        module.__dict__.update(values)
        monkeypatch.setitem(sys.modules, key, module)
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def actions(monkeypatch):
    return load_module(monkeypatch, 'tested_actions', 'commercial/ai/routers/action_handlers.py', {
        'commercial.ai.routers.llm': {'llm_acompletion': AsyncMock()},
    })


@pytest.mark.asyncio
@pytest.mark.parametrize('message', [
    'How do I create a client named Example with email example@example.com?',
    'Create a client named Example with email example@example.com',
    'Add an expense of 20 USD for travel today',
])
async def test_normal_chat_never_writes_without_confirmation(actions, monkeypatch, message):
    tools = SimpleNamespace(create_client=AsyncMock(return_value={'success': True, 'data': {'id': 1}}), create_expense=AsyncMock(return_value={'success': True, 'data': {'id': 1}}))
    monkeypatch.setattr(actions, '_init_tools', AsyncMock(return_value=tools))
    monkeypatch.setattr(actions, '_extract_onboarding_action', AsyncMock(return_value={
        'action': 'create_client', 'params': {'name': 'Example', 'email': 'example@example.com'},
    }))
    actions.llm_acompletion.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content='{"name":"Example","email":"example@example.com","amount":20,"category":"travel","expense_date":"2026-11-12"}'
    ))])
    result = await actions.handle_early_actions(message, message.lower(), None,
        SimpleNamespace(provider_name='openai', model_name='test', api_key=None), None, None)
    tools.create_client.assert_not_awaited()
    tools.create_expense.assert_not_awaited()
    assert result['data']['type'] == 'proposed_action'


@pytest.mark.asyncio
async def test_normal_chat_confirm_executes_once(actions, monkeypatch):
    tools = SimpleNamespace(create_client=AsyncMock(return_value={'success': True, 'data': {'id': 1}}))
    monkeypatch.setattr(actions, '_init_tools', AsyncMock(return_value=tools))
    result = await actions.handle_early_actions('', '', None, None, None, None,
        confirmed_action={'action': 'create_client', 'params': {'name': 'Example'}})
    assert result['success']
    tools.create_client.assert_awaited_once_with(name='Example', email=None, phone=None)


@pytest.mark.asyncio
async def test_fallback_carries_active_tenant(monkeypatch):
    captured = {}
    class HTTP:
        def __init__(self, **kwargs):
            captured.update(kwargs)
    module = load_module(monkeypatch, 'tested_base', 'commercial/ai/inprocess/base.py', {
        'core.routers.auth': {'create_access_token': lambda **kwargs: 'test-token'},
        'core.models.database': {'get_tenant_context': lambda: 42},
        'commercial.ai.routers.auth_client': {'AuthenticatedAPIClient': HTTP},
        'commercial.ai.inprocess.clients_domain': {'ClientsInProcessMixin': type('Mixin', (), {})},
    })
    client = module.InProcessAPIClient(None, SimpleNamespace(email='test@example.com', tenant_id=1))
    client._get_fallback()
    assert captured['tenant_id'] == 42


@pytest.mark.asyncio
async def test_statement_change_is_a_proposal(actions, monkeypatch):
    tools = SimpleNamespace(reprocess_bank_statement=AsyncMock())
    monkeypatch.setattr(actions, '_init_tools', AsyncMock(return_value=tools))
    monkeypatch.setattr(actions, '_extract_onboarding_action', AsyncMock(return_value={
        'action': 'reprocess_statement', 'params': {'statement_id': 7},
    }))
    result = await actions.handle_early_actions('reprocess this', 'reprocess this',
        {'entity': {'type': 'bank_statement', 'id': 7}}, None, None, None)
    assert result['data']['type'] == 'proposed_action'
    tools.reprocess_bank_statement.assert_not_awaited()


def test_history_is_scoped_retained_and_bounded(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import Column, Integer, String, DateTime, create_engine
    from sqlalchemy.orm import declarative_base, Session
    Base = declarative_base()
    class History(Base):
        __tablename__ = 'history'
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer)
        message = Column(String)
        sender = Column(String)
        created_at = Column(DateTime)
    class Settings(Base):
        __tablename__ = 'settings'
        id = Column(Integer, primary_key=True)
        key = Column(String)
        value = Column(String)
    module = load_module(monkeypatch, 'tested_context', 'commercial/ai/routers/conversation_context.py', {
        'core.models.models_per_tenant': {'AIChatHistory': History, 'Settings': Settings},
    })
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        db.add_all([
            History(user_id=1, sender='user', message='old secret', created_at=now-timedelta(days=8)),
            History(user_id=2, sender='ai', message='other user secret', created_at=now),
            History(user_id=1, sender='ai', message='first answer', created_at=now),
            History(user_id=1, sender='user', message='follow up', created_at=now),
        ])
        db.commit()
        assert module.load_conversation_context(db, 1, 'follow up') == [
            {'role': 'assistant', 'content': 'first answer'}]
        for _ in range(20):
            db.add(History(user_id=1, sender='ai', message='x'*5000, created_at=now))
        db.commit()
        result = module.load_conversation_context(db, 1, 'next')
        assert len(result) <= 12
        assert sum(len(m['content']) for m in result) <= 12000


@pytest.mark.asyncio
async def test_fallback_http_request_has_tenant_header(monkeypatch):
    import httpx
    base = load_module(monkeypatch, 'tested_http_base', 'MCP/_base_client.py', {})
    auth = load_module(monkeypatch, 'tested_http_auth', 'commercial/ai/routers/auth_client.py', {
        'MCP._base_client': {'BaseAPIClient': base.BaseAPIClient},
    })
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[])
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = auth.AuthenticatedAPIClient('http://test', 'token', tenant_id=42, http_client=http)
        await client.list_invoices()
        await client.create_invoice({'client_id': 3, 'amount': 25, 'status': 'draft', 'due_date': '2026-12-01'})
    assert requests[0].headers['x-tenant-id'] == '42'
    assert requests[0].headers['authorization'] == 'Bearer token'
    assert requests[1].method == 'POST'
    assert requests[1].url.path == '/invoices/'
    assert requests[1].headers['x-tenant-id'] == '42'


@pytest.mark.asyncio
async def test_unknown_confirmation_cannot_dispatch(actions, monkeypatch):
    init = AsyncMock()
    monkeypatch.setattr(actions, '_init_tools', init)
    result = await actions.handle_early_actions('', '', None, None, None, None,
        confirmed_action={'action': 'delete_everything', 'params': {}})
    assert not result['success']
    init.assert_not_awaited()


@pytest.mark.asyncio
async def test_extraction_failure_does_not_fall_back_to_a_write(actions, monkeypatch):
    init = AsyncMock()
    monkeypatch.setattr(actions, '_init_tools', init)
    monkeypatch.setattr(actions, '_extract_onboarding_action', AsyncMock(return_value=None))
    result = await actions.handle_early_actions('create a client', 'create a client', None, None, None, None)
    assert result is None
    init.assert_not_awaited()


@pytest.mark.asyncio
async def test_client_intent_cannot_bypass_confirmation(monkeypatch):
    module = load_module(monkeypatch, 'tested_clients_handler', 'commercial/ai/routers/intents/clients.py', {
        'commercial.ai.routers.intent_registry': {'IntentContext': object, 'IntentRegistry': object, 'mcp_envelope': lambda *a: None},
        'commercial.ai.routers.intents._helpers': {'detect_search_intent': lambda text: (False, '')},
    })
    tools = SimpleNamespace(create_client=AsyncMock())
    result = await module.ClientsHandler().execute(SimpleNamespace(lower_message='create client Example', tools=tools))
    assert result is None
    tools.create_client.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_passes_history_to_completion(monkeypatch):
    from unittest.mock import Mock
    cfg = SimpleNamespace(provider_name='openai', model_name='test', api_key=None, provider_url=None)
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = cfg
    history = [{'role': 'assistant', 'content': 'First: A. Second: B.'}]
    load_history = Mock(return_value=history)
    complete = AsyncMock(side_effect=[
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='general'))]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='B explained'))]),
    ])
    class Router:
        def post(self, *args):
            return lambda fn: fn
    module = load_module(monkeypatch, 'tested_chat', 'commercial/ai/routers/chat.py', {
        'fastapi': {'APIRouter': Router, 'Depends': lambda fn: None},
        'core.models.database': {'get_db': lambda: None},
        'core.routers.auth': {'get_current_user': lambda: None},
        'core.models.models': {'MasterUser': object},
        'core.models.models_per_tenant': {'AIConfig': Mock()},
        'core.utils.feature_gate': {'require_feature': lambda feature: lambda fn: fn},
        'commercial.ai.services.ai_config_service': {'AIConfigService': SimpleNamespace(get_model_parameters=lambda *a, **kw: {})},
        'commercial.ai.routers.chat_models': {'ChatRequest': object},
        'commercial.ai.routers.conversation_context': {'load_conversation_context': load_history},
        'commercial.ai.routers.action_handlers': {'handle_early_actions': AsyncMock(return_value=None)},
        'commercial.ai.routers.intent_handlers': {'dispatch_intent': AsyncMock(return_value=None)},
        'commercial.ai.routers.intent_routing': {'TOOL_INTENTS': set(), 'parse_agent_tool_plan': lambda value: []},
        'commercial.ai.routers.llm': {'llm_acompletion': complete, 'materialize_ai_config': lambda value: value},
        'commercial.ai.inprocess.base': {'InProcessAPIClient': lambda **kw: None},
        'MCP.tools': {'InvoiceTools': lambda client: None},
    })
    monkeypatch.setattr(module, '_plan_mcp_tool_intents', AsyncMock(return_value=[]))
    request = SimpleNamespace(message='Explain the second one', config_id=1, page_context=None, mode=None, confirmed_action=None)
    result = await module.ai_chat(request, db, SimpleNamespace(id=7, email='test@example.com'))
    assert result['data']['response'] == 'B explained'
    load_history.assert_called_once_with(db, 7, request.message)
    assert complete.call_args.kwargs['messages'] == [*history, {'role': 'user', 'content': request.message}]


@pytest.mark.asyncio
async def test_confirmed_statement_tools_use_tenant_fallback(actions, monkeypatch):
    http = SimpleNamespace(_make_request=AsyncMock(return_value={'statement': {'labels': [], 'transactions': []}}))
    base = load_module(monkeypatch, 'tested_statement_base', 'commercial/ai/inprocess/base.py', {
        'core.routers.auth': {'create_access_token': lambda **kwargs: 'test-token'},
        'core.models.database': {'get_tenant_context': lambda: 42},
        'commercial.ai.routers.auth_client': {'AuthenticatedAPIClient': lambda **kwargs: http},
        'commercial.ai.inprocess.clients_domain': {'ClientsInProcessMixin': type('Mixin', (), {})},
    })
    bank = load_module(monkeypatch, 'tested_bank_tools', 'MCP/tools/bank_statements.py', {})
    tools = bank.BankStatementToolsMixin()
    tools.api_client = base.InProcessAPIClient(None, SimpleNamespace(email='test@example.com'))
    monkeypatch.setattr(actions, '_init_tools', AsyncMock(return_value=tools))
    for action, params in [
        ('reprocess_statement', {'statement_id': 7}),
        ('update_statement', {'statement_id': 7, 'notes': 'Reviewed', 'add_labels': ['checked']}),
    ]:
        result = await actions.handle_early_actions('', '', None, None, None, None,
            confirmed_action={'action': action, 'params': params})
        assert result['success'], result
    assert http._make_request.await_count == 3
    assert http._make_request.call_args.args == ('PUT', '/statements/7')
    assert http._make_request.call_args.kwargs['json'] == {'notes': 'Reviewed', 'labels': ['checked']}
