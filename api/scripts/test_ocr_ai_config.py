#!/usr/bin/env python3
"""
Test script to verify OCR service can access AI configuration from database
"""
import os
import sys

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_db, set_tenant_context
from core.models.models_per_tenant import AIConfig as AIConfigModel
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager
from sqlalchemy.orm import Session

def test_ocr_ai_config():
    """Test if OCR service can properly fetch AI configuration"""
    print("🔍 Testing OCR AI Configuration Access...")
    
    # First get a tenant ID to set context
    try:
        # Get available tenant IDs
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()
        if not tenant_ids:
            print("❌ No tenants found")
            return False
        
        # Use the first tenant
        tenant_id = tenant_ids[0]
        print(f"   Using tenant ID: {tenant_id}")
        
        # Set tenant context
        set_tenant_context(tenant_id)
        
        # Get tenant-specific database session
        SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
        db = SessionLocalTenant()
    except Exception as e:
        print(f"❌ Failed to set up tenant context: {e}")
        return False
    
    try:
        # Test fetching AI config (same logic as OCR service), prioritizing default
        ai_row = db.query(AIConfigModel).filter(
            AIConfigModel.is_active == True,
            AIConfigModel.tested == True
        ).order_by(AIConfigModel.is_default.desc()).first()
        
        if ai_row:
            ai_config = {
                "provider_name": ai_row.provider_name,
                "provider_url": ai_row.provider_url,
                "api_key": ai_row.api_key,
                "model_name": ai_row.model_name,
            }
            
            print("✅ AI Configuration found in database:")
            print(f"   Provider: {ai_config['provider_name']}")
            print(f"   Model: {ai_config['model_name']}")
            print(f"   URL: {ai_config['provider_url']}")
            print(f"   Has API Key: {'Yes' if ai_config['api_key'] else 'No'}")
            
            # Test OCR endpoint construction for Ollama
            if ai_config['provider_name'] == 'ollama':
                base_url = ai_config['provider_url']
                if not base_url.endswith('/api/generate'):
                    ocr_endpoint = f"{base_url}/api/generate"
                else:
                    ocr_endpoint = base_url
                print(f"   OCR Endpoint: {ocr_endpoint}")
                
                # Check if the endpoint is reachable
                try:
                    import requests
                    response = requests.get(ocr_endpoint.replace('/api/generate', '/api/tags'), timeout=5)
                    if response.status_code == 200:
                        print("✅ Ollama endpoint is reachable")
                        models = response.json().get('models', [])
                        model_names = [m.get('name', 'unknown') for m in models]
                        print(f"   Available models: {model_names}")
                        
                        if ai_config['model_name'] in model_names:
                            print(f"✅ Configured model '{ai_config['model_name']}' is available")
                        else:
                            print(f"⚠️  Configured model '{ai_config['model_name']}' not found in available models")
                    else:
                        print(f"⚠️  Ollama endpoint returned status: {response.status_code}")
                except Exception as e:
                    print(f"⚠️  Could not reach Ollama endpoint: {e}")
            
            return True
        else:
            print("⚠️  No active AI configuration found in database")
            print("   OCR service will fall back to environment variables:")
            
            # Check environment variables
            env_vars = {
                'LLM_MODEL_EXPENSES': os.getenv('LLM_MODEL_EXPENSES'),
                'OLLAMA_MODEL': os.getenv('OLLAMA_MODEL'),
                'LLM_API_BASE': os.getenv('LLM_API_BASE'),
                'OLLAMA_API_BASE': os.getenv('OLLAMA_API_BASE'),
                'OLLAMA_OCR_ENDPOINT': os.getenv('OLLAMA_OCR_ENDPOINT'),
            }
            
            for key, value in env_vars.items():
                if value:
                    print(f"   {key}: {value}")
                else:
                    print(f"   {key}: Not set")
            
            return False
            
    except Exception as e:
        print(f"❌ Error testing AI config: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_ocr_ai_config()
    sys.exit(0 if success else 1)
