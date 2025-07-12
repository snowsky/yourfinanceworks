#!/usr/bin/env python3
"""
Test script for authentication and token validation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.models import User, Tenant
from routers.auth import get_current_user, create_access_token
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
import os

def test_token_creation():
    """Test creating and validating a token"""
    try:
        # Create a test user
        # Use PostgreSQL connection string
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/invoice_app")
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Get the first user from the database
        user = db.query(User).first()
        if not user:
            print("❌ No users found in database")
            return False
        
        print(f"✅ Found user: {user.email}")
        
        # Create a token for this user
        token = create_access_token(data={"sub": user.email})
        print(f"✅ Created token: {token[:20]}...")
        
        # Test token validation
        try:
            payload = jwt.decode(token, os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production"), algorithms=["HS256"])
            email = payload.get("sub")
            print(f"✅ Token payload email: {email}")
            
            # Test getting user from database
            db_user = db.query(User).filter(User.email == email).first()
            if db_user:
                print(f"✅ User found in database: {db_user.email}")
                print(f"✅ User role: {db_user.role}")
                print(f"✅ User tenant_id: {db_user.tenant_id}")
                return True
            else:
                print("❌ User not found in database")
                return False
                
        except Exception as e:
            print(f"❌ Token validation failed: {str(e)}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing authentication: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 Testing authentication...")
    
    if test_token_creation():
        print("\n🎉 Authentication test passed!")
    else:
        print("\n❌ Authentication test failed!")
        sys.exit(1) 