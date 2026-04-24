import pytest
from fastapi import HTTPException

from core.models.models import MasterUser, Settings as MasterSettings, Tenant, user_tenant_association
from core.services.expense_mobile_service import save_expense_mobile_config
from core.utils.auth import get_password_hash


def seed_mobile_binding(db_session, *, enabled=True, app_id="yfw-expense-demo", signup_enabled=True, default_role="user"):
    setting = MasterSettings(
        tenant_id=1,
        key="expense_mobile_app",
        value={
            "enabled": enabled,
            "app_id": app_id,
            "signup_enabled": signup_enabled,
            "default_role": default_role,
            "allowed_auth_methods": {
                "password": True,
                "google": False,
                "microsoft": False,
            },
            "branding": {
                "title": "Bound Expenses",
                "subtitle": "Bound to org 1",
                "accent_color": "#10b981",
                "logo_url": "",
            },
        },
    )
    db_session.add(setting)
    db_session.commit()
    return setting


def test_mobile_expense_config_returns_bound_org_settings(client, db_session):
    seed_mobile_binding(db_session)

    response = client.get("/api/v1/mobile/expenses/config", params={"app_id": "yfw-expense-demo"})

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["app_id"] == "yfw-expense-demo"
    assert body["branding"]["title"] == "Bound Expenses"
    assert body["allowed_auth_methods"]["password"] is True


def test_mobile_expense_signup_creates_user_in_bound_org_and_me_returns_bound_session(client, db_session):
    seed_mobile_binding(db_session, default_role="viewer")

    signup_response = client.post(
        "/api/v1/mobile/expenses/auth/signup",
        json={
            "app_id": "yfw-expense-demo",
            "email": "mobile-user@example.com",
            "password": "StrongPass123!",
            "first_name": "Mobile",
            "last_name": "User",
        },
    )

    assert signup_response.status_code == 201
    signup_body = signup_response.json()
    assert signup_body["user"]["tenant_id"] == 1
    assert signup_body["user"]["role"] == "viewer"
    assert signup_body["user"]["email"] == "mobile-user@example.com"

    me_response = client.get(
        "/api/v1/mobile/expenses/auth/me",
        params={"app_id": "yfw-expense-demo"},
        headers={"Authorization": f"Bearer {signup_body['access_token']}"},
    )

    assert me_response.status_code == 200
    me_body = me_response.json()
    assert me_body["tenant_id"] == 1
    assert me_body["role"] == "viewer"
    assert me_body["email"] == "mobile-user@example.com"


def test_mobile_expense_signup_existing_user_adds_membership_without_changing_primary_tenant(client, db_session):
    db_session.add(Tenant(id=2, name="Primary Tenant", is_active=True, is_enabled=True))
    existing_user = MasterUser(
        email="existing-mobile-user@example.com",
        hashed_password=get_password_hash("StrongPass123!"),
        tenant_id=2,
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db_session.add(existing_user)
    db_session.commit()
    db_session.refresh(existing_user)
    seed_mobile_binding(db_session, default_role="viewer")

    signup_response = client.post(
        "/api/v1/mobile/expenses/auth/signup",
        json={
            "app_id": "yfw-expense-demo",
            "email": "existing-mobile-user@example.com",
            "password": "StrongPass123!",
            "first_name": "Existing",
            "last_name": "User",
        },
    )

    assert signup_response.status_code == 201
    db_session.refresh(existing_user)
    assert existing_user.tenant_id == 2
    membership = db_session.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == existing_user.id,
            user_tenant_association.c.tenant_id == 1,
        )
    ).first()
    assert membership is not None
    assert membership.role == "viewer"
    assert signup_response.json()["user"]["tenant_id"] == 1
    assert signup_response.json()["user"]["role"] == "viewer"


def test_expense_mobile_app_id_must_be_unique_across_enabled_orgs(db_session):
    db_session.add(Tenant(id=2, name="Other Tenant", is_active=True, is_enabled=True))
    seed_mobile_binding(db_session, app_id="duplicate-app")
    other_tenant = db_session.query(Tenant).filter(Tenant.id == 2).one()

    with pytest.raises(HTTPException) as exc_info:
        save_expense_mobile_config(
            db_session,
            other_tenant,
            {
                "enabled": True,
                "app_id": "duplicate-app",
                "signup_enabled": True,
                "default_role": "user",
            },
        )

    assert exc_info.value.status_code == 409
