import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

@pytest.fixture
def auth_headers(client: TestClient):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "test@example.com",
            "password": "testpass123",
            "full_name": "Test User"
        }
    )
    
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "testpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def test_client_id(client: TestClient, auth_headers):
    response = client.post(
        "/api/v1/clients/",
        json={
            "name": "Test Client",
            "email": "client@example.com"
        },
        headers=auth_headers
    )
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
    assert len(data) >= 1