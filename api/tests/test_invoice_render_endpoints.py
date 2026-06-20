"""Integration tests for the unified-renderer PDF + HTML preview endpoints.

Runs in-container with the conftest real-DB fixtures (needs postgres-master).
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Auth + seed fixtures — module-scoped so a single user/tenant handles all 4
# tests without hitting the license tenant-count limit.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def render_client():
    """Dedicated TestClient for this module, with DB overrides applied."""
    from core.models.database import get_db, get_master_db
    from main import app
    from tests.conftest import override_get_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_master_db] = override_get_db
    return TestClient(app)


@pytest.fixture(scope="module")
def render_auth(render_client: TestClient):
    """Register once, return auth headers for the whole module."""
    unique_email = f"render_{uuid4().hex}@example.com"
    reg = render_client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert reg.status_code in (200, 201), f"Registration failed: {reg.text}"
    login = render_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "Password123!"},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def render_invoice(render_client: TestClient, render_auth):
    """Create one client + invoice, reused across module tests."""
    # Create client
    cr = render_client.post(
        "/api/v1/clients/",
        json={"name": "Render Test Client", "email": "renderclient@example.com"},
        headers=render_auth,
    )
    assert cr.status_code == 201, cr.text
    client_id = cr.json()["id"]

    # Create invoice
    due_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    ir = render_client.post(
        "/api/v1/invoices/",
        json={
            "client_id": client_id,
            "amount": 0,
            "currency": "USD",
            "description": "Render test invoice",
            "status": "draft",
            "due_date": due_date,
            "items": [
                {"description": "Widget A", "quantity": 2, "price": 50},
            ],
        },
        headers=render_auth,
    )
    assert ir.status_code == 201, ir.text

    class _Invoice:
        def __init__(self, data):
            self.id = data["id"]
            self.number = data["number"]

    return _Invoice(ir.json())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_preview_returns_html(render_client, render_invoice, render_auth):
    r = render_client.get(
        f"/api/v1/invoices/{render_invoice.id}/preview",
        headers=render_auth,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert render_invoice.number in r.text


def test_pdf_returns_pdf(render_client, render_invoice, render_auth):
    r = render_client.get(
        f"/api/v1/invoices/{render_invoice.id}/pdf",
        headers=render_auth,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_preview_404_for_unknown_invoice(render_client, render_auth):
    r = render_client.get("/api/v1/invoices/9999999/preview", headers=render_auth)
    assert r.status_code == 404


def test_pdf_404_for_unknown_invoice(render_client, render_auth):
    r = render_client.get("/api/v1/invoices/9999999/pdf", headers=render_auth)
    assert r.status_code == 404
