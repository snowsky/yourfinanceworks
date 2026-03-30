from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

from core.models.models import MasterUser
from core.routers.auth import get_current_user


def test_parse_voice_endpoint_returns_structured_result(client):
    mock_user = MasterUser(
        id=1,
        email="voice@example.com",
        hashed_password="hashed",
        first_name="Voice",
        last_name="User",
        role="admin",
        tenant_id=1,
        is_active=True,
        is_superuser=False,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def override_get_current_user():
        return mock_user

    client.app.dependency_overrides[get_current_user] = override_get_current_user

    with patch(
        "core.routers.expenses.parse_voice_expense",
        new=AsyncMock(return_value={
            "transcript": "spent 24 on uber today",
            "amount": 24.0,
            "currency": "USD",
            "expense_date": date(2026, 3, 30),
            "category": "Transportation",
            "vendor": "Uber",
            "notes": "spent 24 on uber today",
            "confidence": 0.91,
            "parser_used": "ai",
        }),
    ) as mock_parse:
        response = client.post(
            "/api/v1/expenses/parse-voice",
            json={"transcript": "spent 24 on uber today", "currency_hint": "USD"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["amount"] == 24.0
        assert body["category"] == "Transportation"
        assert body["vendor"] == "Uber"
        assert body["parser_used"] == "ai"
        mock_parse.assert_awaited_once()

    client.app.dependency_overrides.pop(get_current_user, None)
