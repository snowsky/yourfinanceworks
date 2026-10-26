import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from handler_loader import load_functions

ROOT = Path(__file__).resolve().parents[2]

def load_method(name, namespace):
    tree = ast.parse((ROOT / 'api/core/services/external_api_auth_service.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ExternalAPIAuthService')
    method = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), method], type_ignores=[])), '<method>', 'exec'), namespace)
    return namespace[name]

@pytest.mark.parametrize('role', ['viewer', 'user'])
def test_tool_write_checks_owner_component(role):
    calls = []
    def check(db, user, component, level, action):
        calls.append(component)
        if user.role == 'viewer':
            raise HTTPException(403)
    ns = load_functions('api/commercial/tools_api/deps.py', ['require_write'], dict(HTTPException=HTTPException, Permission=NS(WRITE='write'), require_component_permission=check))
    context = NS(permissions={'write'}, is_admin=True, user=NS(role=role))
    if role == 'viewer':
        with pytest.raises(HTTPException): ns['require_write'](context, object(), 'customers')
    else:
        ns['require_write'](context, object(), 'customers')
        assert calls == ['customers']

@pytest.mark.parametrize('path,name,component,level', [
 ('api/core/routers/clients.py','delete_client','customers','user'),
 ('api/core/routers/invoices/crud.py','delete_invoice','invoices','user'),
 ('api/core/routers/payments.py','create_payment','invoices','user'),
 ('api/core/routers/payments.py','update_payment','invoices','user'),
 ('api/core/routers/payments.py','delete_payment','invoices','admin'),
])
def test_ordinary_mutations_deny_before_query(path,name,component,level):
    calls = []
    def deny(db,user,c,l,action):
        calls.append((c,l))
        raise HTTPException(403)
    ns = load_functions(path,[name],dict(Depends=lambda x: None,get_db=None,get_current_user=None,require_component_permission=deny))
    kwargs = dict(db=NS(), current_user=NS(role='viewer'))
    if name != 'create_payment': kwargs['client_id' if name == 'delete_client' else 'invoice_id' if name == 'delete_invoice' else 'payment_id'] = 1
    if name in ('create_payment','update_payment'): kwargs['payment'] = NS()
    with pytest.raises(HTTPException) as exc: asyncio.run(ns[name](**kwargs))
    assert exc.value.status_code == 403
    assert calls == [(component,level)]

class Column:
    def __eq__(self, value): return self

class Query:
    def __init__(self, row): self.row = row
    def filter(self, *args): return self
    def first(self): return self.row

@pytest.mark.parametrize('tenant_id,membership,active,enabled,archived,allowed,role', [
 (1,None,True,True,None,True,'admin'),
 (2,NS(is_active=True,role='viewer'),True,True,None,True,'viewer'),
 (2,NS(is_active=True,role='user'),True,True,None,True,'user'),
 (2,None,True,True,None,False,None),
 (2,NS(is_active=False,role='admin'),True,True,None,False,None),
 (1,NS(is_active=False,role='admin'),True,True,None,False,None),
 (2,NS(is_active=True,role='user'),False,True,None,False,None),
 (2,NS(is_active=True,role='user'),True,False,None,False,None),
 (2,NS(is_active=True,role='user'),True,True,'archived',False,None),
])
def test_selected_tenant_authority(tenant_id,membership,active,enabled,archived,allowed,role):
    owner = NS(id=5,tenant_id=1,role='admin',is_active=True)
    tenant = NS(is_active=active,is_enabled=enabled,archived_at=archived)
    tenant_model = NS(id=Column())
    association = NS(c=NS(user_id=Column(),tenant_id=Column()))
    model = NS(__table__=NS(columns=[NS(key=k) for k in vars(owner)]))
    db = NS(query=lambda m: Query(tenant if m is tenant_model else membership))
    method = load_method('_selected_tenant_user',dict(Tenant=tenant_model,MasterUser=model,user_tenant_association=association,SimpleNamespace=NS))
    result = method(None,db,owner,tenant_id)
    assert (result is not None) == allowed
    if allowed:
        assert result.tenant_id == tenant_id
        assert result.role == role
    assert owner.tenant_id == 1 and owner.role == 'admin'

@pytest.mark.parametrize('component', ['customers','invoices','expenses','bank_statements'])
def test_tool_component_restriction_cannot_be_elevated(component):
    def deny(db,user,c,level,action):
        assert db == 'tenant-db' and c == component
        raise HTTPException(403)
    ns = load_functions('api/commercial/tools_api/deps.py',['require_write'],dict(HTTPException=HTTPException,Permission=NS(WRITE='write'),require_component_permission=deny))
    with pytest.raises(HTTPException):
        ns['require_write'](NS(permissions={'write'},is_admin=True,user=NS(role='admin')), 'tenant-db', component)

def test_all_tool_mutations_execute_permission_guard_with_tenant_db():
    import inspect
    components = dict(clients='customers',invoices='invoices',expenses='expenses',payments='invoices',bank_statements='bank_statements')
    checked = []
    for filename,component in components.items():
        path = f'api/commercial/tools_api/{filename}.py'
        tree = ast.parse((ROOT / path).read_text())
        for node in tree.body:
            if not isinstance(node,ast.AsyncFunctionDef): continue
            mutations = any(isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in ('post','put','patch','delete') for d in node.decorator_list)
            if mutations:
                tenant_db = object()
                context = object()
                def deny(auth, db, actual_component):
                    assert auth is context and db is tenant_db
                    assert actual_component == component
                    checked.append((filename, node.name))
                    raise HTTPException(403, 'permission denied')
                namespace = dict(
                    Depends=lambda *_: None, get_tenant_db=None, get_api_auth_context=None,
                    get_master_db=None, require_write=deny, HTTPException=HTTPException,
                    _check_domain_access=lambda *args: None, DOMAIN='dummy',
                )
                handler = load_functions(path, [node.name], namespace)[node.name]
                kwargs = {name: NS() for name in inspect.signature(handler).parameters}
                kwargs.update(tenant_db=tenant_db, auth_context=context)
                with pytest.raises(HTTPException) as exc:
                    asyncio.run(handler(**kwargs))
                assert exc.value.status_code == 403
    assert len(checked) == 11

def test_api_key_uses_persisted_tenant_not_primary():
    from datetime import datetime, timezone
    key_model = NS(api_key_hash=Column(),is_active=Column())
    user_model = NS(id=Column())
    owner = NS(id=9,tenant_id=1,is_active=True,role='admin',is_superuser=False,email='dummy@example.test')
    selected = NS(**vars(owner)); selected.tenant_id=2; selected.role='viewer'
    client = NS(user_id=9,tenant_id=2,allowed_ip_addresses=[],total_requests=0,client_name='dummy',client_id='test-key',is_sandbox=False,allowed_document_types=['invoice'],custom_quotas={},api_key_prefix='test')
    class Context:
        def __init__(self,**kw): self.__dict__.update(kw)
    db = NS(query=lambda model: Query(client if model is key_model else owner),commit=lambda:None)
    selected_calls=[]
    def resolve(db,user,tenant):
        selected_calls.append(tenant)
        return selected
    service=NS(hash_api_key=lambda key:'hash',_selected_tenant_user=resolve,_get_api_client_permissions=lambda client:{'write'})
    method=load_method('authenticate_api_key',dict(Permission=NS(READ='read',INVOICE_READ='invoice_read',EXPENSE_READ='expense_read'),APIClient=key_model,MasterUser=user_model,datetime=datetime,timezone=timezone,AuthContext=Context,AuthenticationMethod=NS(API_KEY='api_key')))
    result=asyncio.run(method(service,db,'dummy','127.0.0.1'))
    assert selected_calls == [2]
    assert result.tenant_id == result.user.tenant_id == 2
    assert result.user.role == 'viewer' and not result.is_admin
    assert 'write' not in result.permissions
    assert owner.tenant_id == 1 and owner.role == 'admin'
