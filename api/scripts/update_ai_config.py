#!/usr/bin/env python3
"""
Update AI configuration to use Ollama
"""
import os
import sys

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import get_db
from models.models import AIConfig, Tenant
from datetime import datetime, timezone

def update_ai_config():
    """Update AI configuration to use Ollama"""
    db = next(get_db())
    
    try:
        # Get the default tenant
        tenant = db.query(Tenant).filter(Tenant.name == "Default Tenant").first()
        
        if not tenant:
            print("❌ Default tenant not found")
            return
        
        # Find existing AI config
        ai_config = db.query(AIConfig).filter(
            AIConfig.tenant_id == tenant.id,
            AIConfig.is_default == True
        ).first()
        
        if ai_config:
            # Update to Ollama with available model
            ai_config.provider_name = "ollama"
            ai_config.model_name = "llama3.1:8b"
            ai_config.api_key = None
            ai_config.provider_url = "http://host.docker.internal:11434"
            ai_config.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            
            print(f"✅ Updated AI config to: {ai_config.provider_name}/{ai_config.model_name}")
            print(f"   Provider: {ai_config.provider_name}")
            print(f"   Model: {ai_config.model_name}")
            print(f"   URL: {ai_config.provider_url}")
            print(f"   Active: {ai_config.is_active}")
            print(f"   Default: {ai_config.is_default}")
        else:
            print("❌ No AI config found to update")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_ai_config() 