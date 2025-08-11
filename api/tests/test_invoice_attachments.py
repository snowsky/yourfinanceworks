import pytest
import os
from uuid import uuid4
from fastapi.testclient import TestClient

# Avoid running these resource-intensive tests by default to prevent exhausting DB connections
if os.getenv("RUN_ATTACHMENT_TESTS", "0") != "1":
    pytest.skip("Skipping attachment tests by default to avoid DB load; set RUN_ATTACHMENT_TESTS=1 to enable.", allow_module_level=True)


def register_and_login(client: TestClient):
    email = f"test_{uuid4().hex}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpass123",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_client_and_invoice(client: TestClient, headers):
    # create client
    r = client.post(
        "/api/v1/clients/",
        json={"name": "Attach Client", "email": f"{uuid4().hex[:8]}@example.com"},
        headers=headers,
    )
    client_id = r.json()["id"]
    # create invoice
    r2 = client.post(
        "/api/v1/invoices/",
        json={
            "client_id": client_id,
            "amount": 12.34,
            "description": "Attachment Test",
            "status": "draft",
        },
        headers=headers,
    )
    invoice_id = r2.json()["id"]
    return invoice_id


@pytest.fixture
def auth_headers(client: TestClient):
    return register_and_login(client)


def test_upload_and_preview_invoice_attachment(client: TestClient, auth_headers):
    invoice_id = create_client_and_invoice(client, auth_headers)

    # minimal valid PDF bytes start with %PDF
    pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"

    # Upload
    up = client.post(
        f"/api/v1/invoices/{invoice_id}/upload-attachment",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert up.status_code == 200, up.text
    up_data = up.json()
    assert up_data.get("attachment_filename")

    # Info
    info = client.get(
        f"/api/v1/invoices/{invoice_id}/attachment-info", headers=auth_headers
    )
    assert info.status_code == 200, info.text
    info_data = info.json()
    assert info_data["has_attachment"] is True
    assert info_data["filename"].endswith(".pdf")
    assert info_data["content_type"] == "application/pdf"

    # Preview
    prev = client.get(
        f"/api/v1/invoices/{invoice_id}/preview-attachment", headers=auth_headers
    )
    assert prev.status_code == 200
    assert prev.headers.get("content-disposition", "").startswith("inline;")
    assert prev.headers.get("content-type") == "application/pdf"

    # Download
    dl = client.get(
        f"/api/v1/invoices/{invoice_id}/download-attachment", headers=auth_headers
    )
    assert dl.status_code == 200
    # download uses generic octet-stream
    assert dl.headers.get("content-type") == "application/octet-stream"


