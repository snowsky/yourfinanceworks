import asyncio
import logging
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException, Depends, status
from jwt import InvalidTokenError as JWTError
from handler_loader import load_functions


def claims():
    return load_functions('api/core/utils/auth.py', ['validate_staff_claims'], {'JWTError': JWTError})['validate_staff_claims']


@pytest.mark.parametrize('kind', ['client', 'plugin', 'plugin_public', 'mfa', 'reset'])
def test_nonstaff_claims_rejected(kind):
    with pytest.raises(JWTError):
        claims()({'sub': 'staff@example.test', 'type': kind})


@pytest.mark.parametrize('payload', [{'sub': 'staff@example.test'}, {'sub': 'staff@example.test', 'type': 'staff'}])
def test_legacy_and_staff_claims_allowed(payload):
    assert claims()(payload) == 'staff@example.test'


def test_public_registration_cannot_select_existing_tenant():
    ns = load_functions('api/core/routers/auth/login_register.py', ['register'], {
        'Depends': Depends, 'get_master_db': lambda: None, 'logging': logging,
        'HTTPException': HTTPException, 'status': status,
    })
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ns['register'](NS(tenant_id=42, email='x@example.test'), NS()))
    assert exc.value.status_code == 403


def test_existing_mfa_account_cannot_issue_token_or_create_org_via_signup(monkeypatch):
    import sys
    from unittest.mock import Mock
    module = NS(LicenseService=lambda *a, **k: NS(get_license_status=lambda: {}))
    monkeypatch.setitem(sys.modules, 'core.services.license_service', module)
    db = Mock()
    db.query.return_value.count.return_value = 2
    db.query.return_value.filter.return_value.first.return_value = NS(
        hashed_password='dummy-hash', is_active=True, mfa_chain_enabled=True,
    )
    ns = load_functions('api/core/routers/auth/login_register.py', ['_register_user'], {
        'HTTPException': HTTPException, 'status': status, 'logging': logging,
        'MasterUser': NS(email=Field()), 'verify_password': lambda *args: True,
        'create_access_token': lambda **kwargs: pytest.fail('issued token before MFA'),
    })
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ns['_register_user'](NS(
            tenant_id=None, email='staff@example.test', password='dummy-password',
        ), db))
    assert exc.value.status_code == 403
    db.add.assert_not_called()
    db.commit.assert_not_called()


class Field:
    def __eq__(self, value):
        return True


class DB:
    def __init__(self, *rows):
        self.rows = iter(rows)
    def query(self, *args):
        return self
    def filter(self, *args):
        return self
    def first(self):
        return next(self.rows)


def device_namespace(session, user):
    from datetime import datetime, timezone
    from threading import Lock
    from fastapi.responses import HTMLResponse
    from html import escape
    import secrets
    from urllib.parse import quote
    return load_functions('api/core/routers/auth/device.py', ['verify_device_login', 'approve_device_login', 'exchange_device_token'], {
        'Depends': Depends, 'get_master_db': lambda: None, 'HTTPException': HTTPException,
        'status': status, 'HTMLResponse': HTMLResponse, 'datetime': datetime,
        'timezone': timezone, 'escape': escape, 'secrets': secrets, 'quote': quote,
        '_device_lock': Lock(), '_device_sessions': {'device': session},
        '_prune_expired_sessions': lambda: None, '_current_browser_user': lambda request, db: user,
        'Tenant': NS(id=Field()), 'MasterUser': NS(email=Field()),
    })


def test_device_get_requires_explicit_post_approval():
    user = NS(id=3, email='staff@example.test', is_active=True, tenant_id=1)
    session = {'user_code': 'ABCD-1234', 'approved_email': None}
    ns = device_namespace(session, user)
    response = asyncio.run(ns['verify_device_login'](NS(), 'ABCD-1234', DB(NS(is_active=True, is_enabled=True))))
    assert session['approved_email'] is None
    assert b'method="post"' in response.body
    assert session['approval_nonce']


@pytest.mark.parametrize('nonce,user_id,enabled', [('wrong', 3, True), ('nonce', 9, True), ('nonce', 3, False)])
def test_device_post_rejects_invalid_binding_or_disabled_tenant(nonce, user_id, enabled):
    session = {'user_code': 'ABCD-1234', 'approval_nonce': 'nonce', 'approval_user_id': 3}
    ns = device_namespace(session, NS(id=user_id, is_active=True, tenant_id=1))
    async def form():
        return {'user_code': 'ABCD-1234', 'csrf_token': nonce}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ns['approve_device_login'](NS(form=form), DB(NS(is_active=True, is_enabled=enabled))))
    assert exc.value.status_code == 403
    assert not session.get('approved_email')


def test_device_post_approves_once():
    session = {'user_code': 'ABCD-1234', 'approval_nonce': 'nonce', 'approval_user_id': 3}
    ns = device_namespace(session, NS(id=3, email='staff@example.test', is_active=True, tenant_id=1))
    async def form():
        return {'user_code': 'ABCD-1234', 'csrf_token': 'nonce'}
    assert asyncio.run(ns['approve_device_login'](NS(form=form), DB(NS(is_active=True, is_enabled=True)))).status_code == 200
    with pytest.raises(HTTPException):
        asyncio.run(ns['approve_device_login'](NS(form=form), DB(NS(is_active=True, is_enabled=True))))


def test_device_exchange_identifies_the_same_account_as_the_issued_token():
    from datetime import timedelta
    user = NS(id=3, email='staff@example.test', is_active=True, tenant_id=1)
    session = {'user_code': 'ABCD-1234', 'approved_email': user.email, 'approved_tenant_id': 1}
    ns = device_namespace(session, user)
    issued = []
    def issue(**kwargs):
        issued.append(kwargs['data']['sub'])
        return 'dummy-device-token'
    ns.update(timedelta=timedelta, ACCESS_TOKEN_EXPIRE_MINUTES=60, create_access_token=issue)
    result = asyncio.run(ns['exchange_device_token'](
        NS(device_code='device'), DB(user, NS(is_active=True, is_enabled=True)),
    ))
    assert issued == [result['user']['email']] == [user.email]
    assert result['access_token'] == 'dummy-device-token'


def test_mobile_login_returns_mfa_challenge_without_staff_token():
    user = NS(email='staff@example.test', hashed_password='hash', is_active=True)
    ns = load_functions('api/core/routers/mobile_expense.py', ['login_mobile_expense_user'], {
        'Depends': Depends, 'get_master_db': lambda: None, 'HTTPException': HTTPException,
        'status': status, 'MasterUser': NS(email=Field()), 'verify_password': lambda *args: True,
        'resolve_expense_mobile_binding': lambda *args: (NS(id=1), {'allowed_auth_methods': {'password': True}}),
        '_get_user_role_for_tenant': lambda *args: 'user',
        '_maybe_require_mfa_for_user': lambda user: {'session_id': 'challenge', 'current_factor_id': 'totp', 'current_factor_label': 'Authenticator'},
        'create_access_token': lambda **kwargs: pytest.fail('issued token before MFA'),
    })
    result = asyncio.run(ns['login_mobile_expense_user'](NS(app_id='app', email=user.email, password='pw'), DB(user)))
    assert result['mfa_required'] is True
    assert 'access_token' not in result


def test_staff_dependency_rejects_disabled_account():
    ns = load_functions('api/core/routers/auth/_shared.py', ['get_current_user'], {
        'Depends': Depends, 'security': None, 'get_master_db': lambda: None,
        'HTTPException': HTTPException, 'status': status, 'INVALID_CREDENTIALS': 'invalid',
        'AUTH_COOKIE_NAME': 'auth_token', 'JWTError': JWTError, 'SECRET_KEY': 'test', 'ALGORITHM': 'HS256',
        'jwt': NS(decode=lambda *args, **kwargs: {'sub': 'staff@example.test'}),
        'validate_staff_claims': claims(), 'logger': logging.getLogger('test'),
        'MasterUser': NS(email=Field()),
    })
    with pytest.raises(HTTPException) as exc:
        ns['get_current_user'](NS(cookies={'auth_token': 'token'}), None, DB(NS(is_active=False)))
    assert exc.value.status_code == 401
