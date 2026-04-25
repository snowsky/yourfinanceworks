from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from core.models import EmailNotificationSettings
from core.models.models import MasterUser, Tenant
from core.models.models_per_tenant import Expense, User as TenantUser
from core.services.expense_digest_service import ExpenseDigestService
from core.utils.auth import create_access_token, get_password_hash


class CapturingEmailService:
    def __init__(self):
        self.messages = []
        self.config = type(
            "EmailConfig",
            (),
            {"from_email": "noreply@example.com", "from_name": "YFW"},
        )()

    def send_email(self, message):
        self.messages.append(message)
        return True


@pytest.fixture
def digest_auth_headers(db_session):
    email = f"digest_{uuid4().hex}@example.com"
    hashed_password = get_password_hash("StrongPass123!")

    tenant = db_session.query(Tenant).filter(Tenant.id == 1).first()
    if not tenant:
        tenant = Tenant(id=1, name="Default Tenant", is_active=True)
        db_session.add(tenant)
        db_session.commit()

    master_user = MasterUser(
        email=email,
        hashed_password=hashed_password,
        tenant_id=1,
        is_active=True,
        role="user",
    )
    db_session.add(master_user)
    db_session.commit()
    db_session.refresh(master_user)

    db_session.add(
        TenantUser(
            id=master_user.id,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            role="user",
        )
    )
    db_session.commit()

    token = create_access_token(data={"sub": email})
    return master_user.id, {"Authorization": f"Bearer {token}"}


def test_expense_digest_preferences_default_to_off(client, digest_auth_headers):
    _, headers = digest_auth_headers

    response = client.get("/api/v1/notifications/expense-digest/preferences", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["frequency"] == "weekly"


def test_expense_digest_preferences_update_current_user(client, db_session, digest_auth_headers):
    user_id, headers = digest_auth_headers

    response = client.put(
        "/api/v1/notifications/expense-digest/preferences",
        json={"enabled": True, "frequency": "daily"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["frequency"] == "daily"

    settings = db_session.query(EmailNotificationSettings).filter(
        EmailNotificationSettings.user_id == user_id
    ).one()
    assert settings.expense_digest_enabled is True
    assert settings.expense_digest_frequency == "daily"


def test_expense_digest_preferences_reject_invalid_frequency(client, digest_auth_headers):
    _, headers = digest_auth_headers

    response = client.put(
        "/api/v1/notifications/expense-digest/preferences",
        json={"enabled": True, "frequency": "monthly"},
        headers=headers,
    )

    assert response.status_code == 400


def test_personal_digest_includes_only_user_expenses(db_session, digest_auth_headers):
    user_id, _ = digest_auth_headers
    other_user = TenantUser(
        email=f"other_{uuid4().hex}@example.com",
        hashed_password="hashed",
        is_active=True,
        role="user",
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    db_session.add(
        EmailNotificationSettings(
            user_id=user_id,
            expense_digest_enabled=True,
            expense_digest_frequency="daily",
        )
    )
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            Expense(
                amount=25,
                total_amount=25,
                currency="USD",
                expense_date=now - timedelta(hours=2),
                category="Meals",
                vendor="Cafe",
                created_by_user_id=user_id,
            ),
            Expense(
                amount=100,
                total_amount=100,
                currency="USD",
                expense_date=now - timedelta(hours=2),
                category="Travel",
                vendor="Train",
                created_by_user_id=other_user.id,
            ),
        ]
    )
    db_session.commit()

    email_service = CapturingEmailService()
    result = ExpenseDigestService(db_session, email_service).process_user_digest(
        user_id,
        force=True,
    )

    assert result["status"] == "sent"
    assert result["expenses_count"] == 1
    assert len(email_service.messages) == 1
    assert "Meals" in email_service.messages[0].html_body
    assert "Travel" not in email_service.messages[0].html_body
