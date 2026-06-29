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
            self.client_id = data["client_id"]

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


def test_post_preview_from_body_returns_html(render_client, render_invoice, render_auth):
    """POST /api/v1/invoices/preview renders the unified template from form data (no save needed)."""
    due_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    r = render_client.post(
        "/api/v1/invoices/preview",
        json={
            "client_id": render_invoice.client_id,
            "number": "PREVIEW-001",
            "currency": "USD",
            "subtotal": 200.0,
            "amount": 200.0,
            "discount_type": "percentage",
            "discount_value": 0.0,
            "due_date": due_date,
            "items": [
                {"description": "Preview Widget", "quantity": 2, "price": 100.0},
            ],
        },
        headers=render_auth,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html"), r.headers["content-type"]
    assert "Render Test Client" in r.text, "Expected client name in rendered HTML"


# ---------------------------------------------------------------------------
# Public share-link renders the unified HTML template
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def shared_invoice_token(render_client: TestClient, render_invoice, render_auth):
    """Create a public share token for the render test invoice."""
    resp = render_client.post(
        "/api/v1/share-tokens/",
        json={
            "record_type": "invoice",
            "record_id": render_invoice.id,
            "access_type": "public",
            "expires_in_hours": 24,
        },
        headers=render_auth,
    )
    assert resp.status_code == 200, f"Share token creation failed: {resp.text}"
    return resp.json()["token"]


def test_public_share_invoice_renders_template(render_client: TestClient, shared_invoice_token: str):
    """GET /api/v1/shared/{token} for an invoice returns 200 HTML with INVOICE keyword."""
    r = render_client.get(f"/api/v1/shared/{shared_invoice_token}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html"), r.headers["content-type"]
    assert "INVOICE" in r.text.upper(), "Expected 'INVOICE' keyword in rendered HTML"


# ---------------------------------------------------------------------------
# POST /invoices/template-preview — settings editor live preview
# ---------------------------------------------------------------------------

def test_template_preview_renders_sample_with_draft_config(render_client, render_auth):
    resp = render_client.post(
        "/api/v1/invoices/template-preview",
        headers=render_auth,
        json={"font_family": "serif", "show_notes": False},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "font-serif" in body                 # draft font applied
    assert "Sample Client LLC" in body          # canned sample data rendered
    assert "Payment due within 15 days" not in body  # notes hidden by draft toggle


def test_template_preview_clamps_bad_enum(render_client, render_auth):
    resp = render_client.post(
        "/api/v1/invoices/template-preview",
        headers=render_auth,
        json={"font_family": "comic-sans"},
    )
    assert resp.status_code == 200
    assert "font-sans" in resp.text             # clamped to default, never raw value
    assert "comic-sans" not in resp.text


def test_template_preview_honors_section_order(render_client, render_auth):
    # Draft section_order must survive the request model and reach the renderer:
    # notes-first must render the notes block before the bill-to block.
    resp = render_client.post(
        "/api/v1/invoices/template-preview",
        headers=render_auth,
        json={"section_order": ["notes", "totals", "items", "custom", "billto"]},
    )
    assert resp.status_code == 200
    body = resp.text
    assert body.index('class="notes"') < body.index('class="billto"')


def test_template_preview_requires_auth(render_client):
    # render_client is module-scoped and shared with render_auth, whose login
    # call leaves an `auth_token` cookie on the client's cookie jar; clear it
    # so this request is actually unauthenticated (get_current_user accepts
    # either the Bearer header or the cookie).
    render_client.cookies.clear()
    resp = render_client.post("/api/v1/invoices/template-preview", json={})
    assert resp.status_code in (401, 403)


def test_template_preview_honors_column_and_layout_keys(render_client, render_auth):
    resp = render_client.post(
        "/api/v1/invoices/template-preview",
        json={"show_col_unit_price": False, "custom_fields_layout": "grid"},
        headers=render_auth,
    )
    assert resp.status_code == 200
    html = resp.text
    assert "<th>Price</th>" not in html          # unit-price column hidden
    assert 'class="custom custom-grid"' in html  # grid layout applied
