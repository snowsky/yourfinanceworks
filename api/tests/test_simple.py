import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """Test basic health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200

def test_docs_endpoint(client: TestClient):
    """Test API docs endpoint"""
    response = client.get("/docs")
    assert response.status_code == 200