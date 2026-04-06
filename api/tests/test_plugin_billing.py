from fastapi.testclient import TestClient

from core.models.models import MasterUser, TenantPluginSettings
from core.routers.auth import get_current_user
from main import app


def _override_admin_user():
    return MasterUser(
        id=100,
        email="admin@example.com",
        hashed_password="hashed",
        tenant_id=1,
        role="admin",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )


def test_plugin_billing_threshold_triggers_public_paywall(client: TestClient, db_session):
    app.dependency_overrides[get_current_user] = _override_admin_user
    try:
        response = client.put(
            "/api/v1/plugins/investments/billing-config",
            json={
                "enabled": True,
                "provider": "stripe",
                "free_endpoint_calls": 2,
                "checkout_url": "https://buy.stripe.com/test-link",
                "price_label": "$19 / month",
                "title": "Unlock premium access",
                "description": "Free usage has been exhausted.",
                "button_label": "Pay with Stripe",
                "payment_completed": False,
                "usage_count": 0,
                "usage_by_endpoint": {},
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["payment_required"] is False

        public_before = client.get("/api/v1/plugins/public-config/investments?tenant_id=1")
        assert public_before.status_code == 200, public_before.text
        assert public_before.json()["billing"]["usage_count"] == 0
        assert public_before.json()["billing"]["payment_required"] is False

        for _ in range(2):
            usage_response = client.post(
                "/api/v1/plugins/public-usage/investments?tenant_id=1",
                json={"endpoint_key": "public_page_view", "quantity": 1},
            )
            assert usage_response.status_code == 200, usage_response.text

        final_public = client.get("/api/v1/plugins/public-config/investments?tenant_id=1")
        assert final_public.status_code == 200, final_public.text
        billing = final_public.json()["billing"]
        assert billing["usage_count"] == 2
        assert billing["usage_by_endpoint"]["public_page_view"] == 2
        assert billing["payment_required"] is True
        assert billing["payment_configured"] is True

        settings_row = db_session.query(TenantPluginSettings).filter(TenantPluginSettings.tenant_id == 1).first()
        assert settings_row is not None
        stored_billing = settings_row.plugin_config["investments"]["billing"]
        assert stored_billing["usage_count"] == 2
        assert stored_billing["checkout_url"] == "https://buy.stripe.com/test-link"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
