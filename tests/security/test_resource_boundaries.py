import asyncio
import logging
import mimetypes
import os
import types
import urllib.parse
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from handler_loader import load_functions


def validator():
    return load_functions('api/core/utils/file_validation.py', ['validate_file_path'], {'os': os})['validate_file_path']


def files(tmp_path, monkeypatch, tenant=1):
    monkeypatch.setitem(__import__('sys').modules, 'core.models.database', NS(get_tenant_context=lambda: tenant))
    source = Path('api/core/routers/files.py').read_text()
    names = ['serve_file', 'get_file_info']
    if 'def _resolve_tenant_file' in source:
        names.append('_resolve_tenant_file')
    return load_functions('api/core/routers/files.py', names, dict(
        Path=Path, urllib=urllib, mimetypes=mimetypes, HTTPException=HTTPException,
        status=status, Depends=Depends, Query=Query, get_db=lambda: None,
        get_current_user=lambda: None, app_config=NS(UPLOAD_PATH=str(tmp_path)),
        validate_file_path=validator(), FileResponse=FileResponse, logger=logging.getLogger('test')))


def call(ns, name, key):
    kw = dict(encoded_file_key=key, db=None, current_user=NS(id=9))
    if name == 'serve_file':
        kw['inline'] = False
    return asyncio.run(ns[name](**kw))


@pytest.mark.parametrize('endpoint', ['serve_file', 'get_file_info'])
def test_valid_file_and_legacy_fallback(tmp_path, monkeypatch, endpoint):
    root = tmp_path / 'tenant_1'
    root.mkdir()
    (root / 'receipt.txt').write_text('receipt')
    ns = files(tmp_path, monkeypatch)
    for key in ['tenant_1/receipt.txt', 'tenant_1/old/receipt.txt']:
        result = call(ns, endpoint, key)
        assert result['size'] == 7 if endpoint == 'get_file_info' else Path(result.path).read_text() == 'receipt'


@pytest.mark.parametrize('endpoint', ['serve_file', 'get_file_info'])
@pytest.mark.parametrize('key,tenant,code', [
    ('tenant_2/secret.txt', 1, 403), ('tenant_1/secret.txt', None, 403),
    ('tenant_1/../tenant_2/secret.txt', 1, 400), ('/tenant_1/secret.txt', 1, 400),
    ('tenant_1/dir\\secret.txt', 1, 400), ('tenant_1/a\x00.txt', 1, 400),
    ('tenant_1/missing.txt', 1, 404),
])
def test_rejected_file_keys(tmp_path, monkeypatch, endpoint, key, tenant, code):
    (tmp_path / 'tenant_1').mkdir()
    (tmp_path / 'tenant_1' / 'secret.txt').write_text('own')
    (tmp_path / 'tenant_2').mkdir()
    (tmp_path / 'tenant_2' / 'secret.txt').write_text('foreign')
    with pytest.raises(HTTPException) as exc:
        call(files(tmp_path, monkeypatch, tenant), endpoint, key)
    assert exc.value.status_code == code
    assert str(tmp_path) not in exc.value.detail


@pytest.mark.parametrize('endpoint', ['serve_file', 'get_file_info'])
@pytest.mark.parametrize('fallback', [False, True])
def test_symlink_escape(tmp_path, monkeypatch, endpoint, fallback):
    root = tmp_path / 'tenant_1'
    root.mkdir()
    outside = tmp_path / 'outside.txt'
    outside.write_text('private')
    (root / 'link.txt').symlink_to(outside)
    with pytest.raises(HTTPException) as exc:
        call(files(tmp_path, monkeypatch), endpoint, 'tenant_1/' + ('old/' if fallback else '') + 'link.txt')
    assert exc.value.status_code == 400


def test_generic_validation_resolves_symlinks_for_write_destinations(tmp_path):
    root = tmp_path / 'safe'
    root.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (root / 'link').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        validator()(str(root / 'link' / 'new.txt'), must_exist=False, base_dir=str(root))
    assert validator()(str(root / 'new.txt'), must_exist=False, base_dir=str(root)) == str(root / 'new.txt')


class Field:
    def __eq__(self, other):
        return True


class DB:
    def __init__(self, record):
        self.record = record
        self.closed = False
    def query(self, model):
        return self
    def filter(self, *args):
        return self
    def first(self):
        return self.record
    def close(self):
        self.closed = True


@pytest.mark.parametrize('state', ['enabled', 'disabled', 'inactive', 'archived', 'missing', 'open_error'])
def test_portal_master_tenant_lifecycle(state):
    tenant = NS(is_active=state != 'inactive', is_enabled=state != 'disabled', archived_at='date' if state == 'archived' else None)
    master = DB(None if state == 'missing' else tenant)
    db = DB(NS(id=3))
    events = []
    def session(tenant_id):
        events.append('open')
        if state == 'open_error':
            raise RuntimeError('unavailable')
        return lambda: db
    ns = load_functions('api/core/services/client_portal_auth.py', ['get_current_client'], dict(
        Header=Header, Depends=Depends, HTTPException=HTTPException,
        get_master_db=lambda: master, decode_client_session_token=lambda token: dict(tenant_id=1, client_id=3),
        set_tenant_context=lambda tid: events.append('set'), clear_tenant_context=lambda: events.append('clear'),
        tenant_db_manager=NS(get_tenant_session=session), Tenant=NS(id=Field()), Client=NS(id=Field()),
        ClientContext=lambda **kwargs: NS(**kwargs)))
    import inspect
    kwargs = {'master_db': master} if 'master_db' in inspect.signature(ns['get_current_client']).parameters else {}
    gen = ns['get_current_client']('Bearer dummy', **kwargs)
    if state == 'enabled':
        assert next(gen).client.id == 3
        gen.close()
        assert db.closed
    elif state == 'open_error':
        with pytest.raises(RuntimeError):
            next(gen)
    else:
        with pytest.raises(HTTPException) as exc:
            next(gen)
        assert exc.value.status_code == 401
        assert 'open' not in events
    assert events[-1] == 'clear'


@pytest.mark.parametrize('tenant', ['1', '01', 1])
@pytest.mark.parametrize('endpoint', ['serve_file', 'get_file_info'])
def test_normalized_tenant_ids(tmp_path, monkeypatch, tenant, endpoint):
    root = tmp_path / 'tenant_1'
    root.mkdir()
    (root / 'receipt.txt').write_text('receipt')
    result = call(files(tmp_path, monkeypatch, tenant), endpoint, 'tenant_01/receipt.txt')
    assert result['size'] == 7 if endpoint == 'get_file_info' else Path(result.path).read_text() == 'receipt'


@pytest.mark.parametrize('endpoint', ['serve_file', 'get_file_info'])
def test_tenant_root_symlink_cannot_redirect_to_other_tenant(tmp_path, monkeypatch, endpoint):
    foreign = tmp_path / 'tenant_2'
    foreign.mkdir()
    (foreign / 'secret.txt').write_text('foreign')
    (tmp_path / 'tenant_1').symlink_to(foreign, target_is_directory=True)
    with pytest.raises(HTTPException) as exc:
        call(files(tmp_path, monkeypatch), endpoint, 'tenant_1/secret.txt')
    assert exc.value.status_code == 400


def test_generic_validation_preserves_missing_file_semantics(tmp_path):
    missing = tmp_path / 'new.txt'
    with pytest.raises(ValueError):
        validator()(str(missing), base_dir=str(tmp_path))
    assert validator()(str(missing), must_exist=False, base_dir=str(tmp_path)) == str(missing)
