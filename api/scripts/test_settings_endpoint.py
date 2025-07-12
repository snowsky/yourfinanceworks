#!/usr/bin/env python3
"""
Test script for settings endpoint
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.models import User, Tenant
from routers.auth import create_access_token
import requests
import os

def test_settings_endpoint():
    """Test the settings endpoint"""
    try:
        # Connect to database
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/invoice_app")
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Get the first user
        user = db.query(User).first()
        if not user:
            print("❌ No users found in database")
            return False
        
        print(f"✅ Found user: {user.email} (role: {user.role})")
        
        # Create a token for this user
        token = create_access_token(data={"sub": user.email})
        print(f"✅ Created token: {token[:20]}...")
        
        # Test the settings endpoint
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get("http://localhost:8000/api/v1/settings/", headers=headers)
        
        print(f"✅ Response status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Settings retrieved successfully")
            print(f"   - Company name: {data.get('company_info', {}).get('name', 'N/A')}")
            print(f"   - AI Assistant enabled: {data.get('enable_ai_assistant', False)}")
            return True
        else:
            print(f"❌ Settings endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing settings endpoint: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 Testing settings endpoint...")
    
    if test_settings_endpoint():
        print("\n🎉 Settings endpoint test passed!")
    else:
        print("\n❌ Settings endpoint test failed!")
        sys.exit(1) 