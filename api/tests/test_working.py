import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that core modules can be imported"""
    from models.models import User, Client, Invoice
    from schemas.user import UserCreate
    from schemas.client import ClientCreate
    assert User is not None
    assert Client is not None
    assert Invoice is not None
    assert UserCreate is not None
    assert ClientCreate is not None

def test_schema_validation():
    """Test Pydantic schema validation"""
    from schemas.user import UserCreate
    from schemas.client import ClientCreate
    
    # Test valid user creation
    user_data = {
        "email": "test@example.com",
        "password": "testpass123",
        "first_name": "Test",
        "last_name": "User"
    }
    user = UserCreate(**user_data)
    assert user.email == "test@example.com"
    assert user.first_name == "Test"
    assert user.last_name == "User"
    
    # Test valid client creation
    client_data = {
        "name": "Test Client",
        "email": "client@example.com"
    }
    client = ClientCreate(**client_data)
    assert client.name == "Test Client"
    assert client.email == "client@example.com"

def test_password_hashing():
    """Test password hashing utility"""
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password = "testpassword123"
    hashed = pwd_context.hash(password)
    
    assert pwd_context.verify(password, hashed)
    assert not pwd_context.verify("wrongpassword", hashed)