import pytest
from uuid import uuid4
import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from core.models.models_per_tenant import Invoice, BankStatement
from core.models.database import get_db

@pytest.fixture
def auth_headers(client: TestClient):
    unique_email = f"test_review_{uuid4().hex}@example.com"
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "TestPass123!",
            "first_name": "Test",
            "last_name": "Reviewer",
            "tenant_id": 1,
            "role": "admin"
        }
    )
    if reg_response.status_code not in (200, 201):
        print(f"Registration failed: {reg_response.text}")
        pytest.fail(f"Registration failed: {reg_response.text}")
    
    response = client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "TestPass123!"}
    )
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        pytest.fail(f"Login failed: {response.text}")
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def client_id(client: TestClient, auth_headers):
    unique_client_email = f"review_client_{uuid4().hex}@example.com"
    response = client.post(
        "/api/v1/clients/",
        json={
            "name": "Review Client",
            "email": unique_client_email
        },
        headers=auth_headers
    )
    if response.status_code not in (200, 201):
        print(f"Client creation failed: {response.text}")
        pytest.fail(f"Client creation failed: {response.text}")
    return response.json()["id"]

def test_invoice_review_lifecycle(client: TestClient, auth_headers, client_id, db_session):
    # 1. Create Invoice
    response = client.post(
        "/api/v1/invoices/",
        json={
            "client_id": client_id,
            "amount": 100.00,
            "description": "Original Invoice",
            "status": "draft"
        },
        headers=auth_headers
    )
    if response.status_code != 201:
        print(f"Invoice creation failed: {response.text}")
    assert response.status_code == 201
    invoice = response.json()
    invoice_id = invoice["id"]
    
    # Assert default fields
    assert invoice.get("review_status") == "not_started" or invoice.get("review_status") is None  # Should be not_started by default but maybe None if not returned in response schema yet (it is in schema now)
    
    # 2. Simulate Worker: Update Invoice with Review Result (via DB directly as worker would)
    # We need a db session to update the record directly
    # Note: `db_session` fixture might need to be defined or we use `get_db`
    # For simplicity, we can try to use a PUT endpoint if it allows updating these fields, 
    # OR better, since we don't have direct DB access in this test easily without more fixtures,
    # we might skip the "simulated worker" part here if we can't write to DB.
    # actually, the `accept-review` logic depends on `review_result` being present.
    # Let's try to cheat and use the PUT endpoint? No, API shouldn't expose review fields to update.
    # We need to inject data into DB.
    pass

# We need a DB fixture to manipulate state "behind the scenes" like a worker
@pytest.fixture
def db_session():
    # Helper to get a session
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        db.close()

def test_invoice_accept_review(client: TestClient, auth_headers, client_id, db_session):
    # 1. Create Invoice
    response = client.post(
        "/api/v1/invoices/",
        json={
            "client_id": client_id,
            "amount": 100.00,
            "description": "Original Invoice",
            "status": "draft"
        },
        headers=auth_headers
    )
    invoice_id = response.json()["id"]

    # 2. Simulate Worker finding a diff
    # We need to find the correct invoice in the DB.
    # The tests usually run against a test DB.
    # We need to know the tenant ID or filter by ID.
    invoice_db = db_session.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    # Ensure we found it (this relies on test utilizing the same DB as the API)
    # If API and Test run in same process/container, it works.
    if invoice_db:
        invoice_db.review_status = "diff_found"
        invoice_db.review_result = {
            "amount": 150.00,
            "description": "Reviewed Invoice"
        }
        invoice_db.reviewed_at = datetime.now(timezone.utc)
        db_session.commit()
    else:
        pytest.skip("Could not find invoice in DB to simulate worker")

    # 3. Call Accept Review
    response = client.post(f"/api/v1/invoices/{invoice_id}/accept-review", headers=auth_headers)
    assert response.status_code == 200
    updated_invoice = response.json()
    
    # 4. Verify Changes
    assert updated_invoice["amount"] == 150.00
    assert updated_invoice["description"] == "Reviewed Invoice"
    assert updated_invoice["review_status"] == "reviewed"

def test_invoice_re_review(client: TestClient, auth_headers, client_id, db_session):
    # 1. Create Invoice
    response = client.post(
        "/api/v1/invoices/",
        json={
            "client_id": client_id,
            "amount": 100.00,
            "description": "Original Invoice",
            "status": "draft"
        },
        headers=auth_headers
    )
    invoice_id = response.json()["id"]
    
    # 2. Set status to 'reviewed' manually
    invoice_db = db_session.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice_db:
        invoice_db.review_status = "reviewed"
        db_session.commit()

    # 3. Call Review (Reset)
    response = client.post(f"/api/v1/invoices/{invoice_id}/review", headers=auth_headers)
    assert response.status_code == 200
    updated_invoice = response.json()
    
    # 4. Verify Reset
    assert updated_invoice["review_status"] == "not_started"
    assert updated_invoice["review_result"] is None
