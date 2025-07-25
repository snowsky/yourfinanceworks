import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Simple test setup without complex database fixtures
@pytest.fixture(scope="function")
def client():
    from main import app
    return TestClient(app)