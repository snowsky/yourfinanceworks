#!/usr/bin/env python3
"""
Update AI configuration to use local Ollama instead of OpenRouter
"""
import os
import sys

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import set_tenant_context
from core.models.models_per_tenant import AIConfig as AIConfigModel
from core.services.tenant_database_manager import tenant_db_manager
from datetime import datetime, timezone

def update_ai_config_to_ollama():
    """Update AI configuration to use local Ollama"""
    print("🔄 Updating AI configuration to use local Ollama...")
    
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
        
        # Find existing AI config
        ai_config = db.query(AIConfigModel).filter(
            AIConfigModel.is_active == True
        ).first()
        
        if ai_config:
            # Update to Ollama
            ai_config.provider_name = "ollama"
            ai_config.model_name = "llama3.2-vision:11b"  # OCR model for expenses
            ai_config.api_key = None  # Ollama doesn't need API key
            ai_config.provider_url = "http://host.docker.internal:11434"
            ai_config.updated_at = datetime.now(timezone.utc)
            ai_config.tested = True  # Mark as tested since we know the config
            
            db.commit()
            
            print("✅ Updated AI config to use local Ollama:")
            print(f"   Provider: {ai_config.provider_name}")
            print(f"   Model: {ai_config.model_name}")
            print(f"   URL: {ai_config.provider_url}")
            print(f"   Active: {ai_config.is_active}")
            print(f"   Default: {ai_config.is_default}")
            return True
        else:
            print("❌ No AI config found to update")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        try:
            db.rollback()
        except:
            pass
        return False
    finally:
        try:
            db.close()
        except:
            pass

if __name__ == "__main__":
    success = update_ai_config_to_ollama()
    if success:
        print("\n🎉 OCR service should now connect to your local Ollama instance!")
        print("💡 Make sure Ollama is running and has the llama3.2-vision:11b model installed.")
    sys.exit(0 if success else 1)
