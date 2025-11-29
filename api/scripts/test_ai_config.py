#!/usr/bin/env python3
"""
Test script for AI Configuration functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.models import AIConfig
from core.models.database import get_db
import os

def test_ai_config_creation():
    """Test creating an AI configuration"""
    try:
        # Create a test AI config
        test_config = AIConfig(
            tenant_id=1,  # Assuming tenant 1 exists
            provider_name="openai",
            provider_url="https://api.openai.com/v1",
            api_key="test-key",
            model_name="gpt-4",
            is_active=True,
            is_default=True
        )
        
        # Get database session
        engine = create_engine("sqlite:///./data/invoice_app.db")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Add the test config
        db.add(test_config)
        db.commit()
        db.refresh(test_config)
        
        print(f"✅ Successfully created AI config with ID: {test_config.id}")
        
        # Test querying
        configs = db.query(AIConfig).filter(AIConfig.tenant_id == 1).all()
        print(f"✅ Found {len(configs)} AI configs for tenant 1")
        
        # Clean up
        db.delete(test_config)
        db.commit()
        print("✅ Successfully deleted test AI config")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error testing AI config: {str(e)}")
        return False

def test_litellm_import():
    """Test if litellm can be imported"""
    try:
        from litellm import completion
        print("✅ LiteLLM imported successfully")
        return True
    except ImportError as e:
        print(f"❌ LiteLLM import failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 Testing AI Configuration functionality...")
    
    # Test litellm import
    litellm_ok = test_litellm_import()
    
    # Test AI config creation
    config_ok = test_ai_config_creation()
    
    if litellm_ok and config_ok:
        print("\n🎉 All AI configuration tests passed!")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        sys.exit(1) 