import pytest
from uuid import uuid4
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

@pytest.fixture
def auth_headers(db_session):
    from core.models.models import MasterUser, Tenant
    from core.models.models_per_tenant import User as TenantUser
    from core.utils.auth import get_password_hash, create_access_token
    from uuid import uuid4

    unique_email = f"test_{uuid4().hex}@example.com"
    hashed_password = get_password_hash("TestPass123!")

    # Ensure tenant exists
    tenant = db_session.query(Tenant).filter(Tenant.id == 1).first()
    if not tenant:
        tenant = Tenant(id=1, name="Test Tenant", is_active=True)
        db_session.add(tenant)
        db_session.commit()

    # Create master user
    master_user = MasterUser(
        email=unique_email,
        hashed_password=hashed_password,
        tenant_id=1,
        is_active=True,
        role="admin"
    )
    db_session.add(master_user)
    db_session.commit()
    db_session.refresh(master_user)
    
    # Create tenant user
    tenant_user = TenantUser(
        id=master_user.id,
        email=unique_email,
        hashed_password=hashed_password,
        is_active=True,
        role="admin"
    )
    db_session.add(tenant_user)
    db_session.commit()

    token = create_access_token(data={"sub": unique_email})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def test_client_id(client: TestClient, auth_headers):
    response = client.post(
        "/api/v1/clients/",
        json={
            "name": "Test Client",
            "email": f"client_{uuid4().hex}@example.com"
        },
        headers=auth_headers
    )
    if response.status_code != 201:
        raise Exception(f"Client creation failed. Status: {response.status_code}")

    return response.json()["id"]

def test_create_invoice(client: TestClient, auth_headers, test_client_id):
    response = client.post(
        "/api/v1/invoices/",
        json={
            "client_id": test_client_id,
            "amount": 100.00,
            "description": "Test Invoice",
            "status": "draft"
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 100.00
    assert data["description"] == "Test Invoice"
    assert data["status"] == "draft"

def test_get_invoices(client: TestClient, auth_headers, test_client_id):
    # Create an invoice first
    client.post(
        "/api/v1/invoices/",
        json={
            "client_id": test_client_id,
            "amount": 100.00,
            "description": "Test Invoice"
        },
        headers=auth_headers
    )
    
    response = client.get("/api/v1/invoices/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1

def test_invoice_payer_default(client: TestClient, auth_headers, test_client_id):
    response = client.post(
        "/api/v1/invoices/",
        json={
            "client_id": test_client_id,
            "amount": 150.00,
            "description": "Payer Default Test"
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["payer"] == "Client"

def test_payment_sync(client: TestClient, auth_headers, test_client_id):
    # 1. Create an invoice
    invoice_resp = client.post(
        "/api/v1/invoices/",
        json={
            "client_id": test_client_id,
            "amount": 200.00,
            "description": "Payment Sync Test",
            "status": "pending"
        },
        headers=auth_headers
    )
    assert invoice_resp.status_code == 201
    invoice_id = invoice_resp.json()["id"]

    # 2. Create a partial payment
    payment_resp = client.post(
        "/api/v1/payments/",
        json={
            "invoice_id": invoice_id,
            "amount": 50.00,
            "payment_method": "cash"
        },
        headers=auth_headers
    )
    assert payment_resp.status_code == 200

    # 3. Verify invoice status and paid_amount
    invoice_resp = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth_headers)
    assert invoice_resp.status_code == 200
    data = invoice_resp.json()
    assert data["status"] == "partially_paid"
    assert data["paid_amount"] == 50.00

    # 4. Create another payment to complete it
    client.post(
        "/api/v1/payments/",
        json={
            "invoice_id": invoice_id,
            "amount": 150.00,
            "payment_method": "bank_transfer"
        },
        headers=auth_headers
    )

    # 5. Verify status is "paid" and paid_amount is full
    invoice_resp = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth_headers)
    assert invoice_resp.status_code == 200
    data = invoice_resp.json()
    assert data["status"] == "paid"
    assert data["paid_amount"] == 200.00

def test_update_invoice_paid_amount_sets_status_paid(client: TestClient, auth_headers, test_client_id):
    # Editing an invoice's paid_amount (the "mark as paid" flow in the edit UI)
    # must derive invoice status the same way recording a payment does.
    invoice_resp = client.post(
        "/api/v1/invoices/",
        json={
            "client_id": test_client_id,
            "amount": 200.00,
            "description": "Edit Paid Amount Test",
            "status": "pending"
        },
        headers=auth_headers
    )
    assert invoice_resp.status_code == 201
    invoice_id = invoice_resp.json()["id"]

    # Partial payment via edit form
    update_resp = client.put(
        f"/api/v1/invoices/{invoice_id}",
        json={"paid_amount": 50.00},
        headers=auth_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "partially_paid"

    # Full payment via edit form
    update_resp = client.put(
        f"/api/v1/invoices/{invoice_id}",
        json={"paid_amount": 200.00},
        headers=auth_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "paid"

    invoice_resp = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth_headers)
    assert invoice_resp.status_code == 200
    data = invoice_resp.json()
    assert data["status"] == "paid"
    assert data["paid_amount"] == 200.00

