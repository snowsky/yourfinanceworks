import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

@pytest.fixture
def auth_headers(client: TestClient):
    # Create and login user
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

def test_create_client(client: TestClient, auth_headers):
    response = client.post(
        "/api/v1/clients/",
        json={
            "name": "Test Client",
            "email": "client@example.com",
            "phone": "123-456-7890"
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Client"
    assert data["email"] == "client@example.com"

def test_get_clients(client: TestClient, auth_headers):
    # Create a client first
    client.post(
        "/api/v1/clients/",
        json={
            "name": "Test Client",
            "email": "client@example.com"
        },
        headers=auth_headers
    )
    
    response = client.get("/api/v1/clients/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Client"