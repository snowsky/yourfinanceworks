#!/usr/bin/env python3
"""
Fix OpenRouter configuration by setting the correct API URL
"""
import os
import sys

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import set_tenant_context
from models.models_per_tenant import AIConfig as AIConfigModel
from services.tenant_database_manager import tenant_db_manager
from datetime import datetime, timezone

def fix_openrouter_url():
    """Fix OpenRouter configuration by setting the correct API URL"""
    print("🔧 Fixing OpenRouter configuration...")
    
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
        
        # Find OpenRouter AI config
        ai_config = db.query(AIConfigModel).filter(
            AIConfigModel.provider_name == "openrouter"
        ).first()
        
        if ai_config:
            # Update the provider URL to the correct OpenRouter endpoint
            old_url = ai_config.provider_url
            ai_config.provider_url = "https://openrouter.ai/api/v1"
            ai_config.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            
            print("✅ Fixed OpenRouter configuration:")
            print(f"   Provider: {ai_config.provider_name}")
            print(f"   Model: {ai_config.model_name}")
            print(f"   Old URL: '{old_url}' (empty)")
            print(f"   New URL: {ai_config.provider_url}")
            print(f"   Active: {ai_config.is_active}")
            print(f"   Default: {ai_config.is_default}")
            return True
        else:
            print("❌ No OpenRouter AI config found")
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
    success = fix_openrouter_url()
    if success:
        print("\n🎉 OpenRouter configuration fixed!")
        print("💡 The OCR service should now connect to OpenRouter properly.")
        print("🔄 You may want to restart the OCR worker to pick up the new config:")
        print("   docker-compose restart ocr-worker")
    sys.exit(0 if success else 1)
