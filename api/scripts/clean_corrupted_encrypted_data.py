#!/usr/bin/env python3
"""
Clean corrupted encrypted data for a tenant.
This script identifies and nullifies encrypted fields that can't be decrypted.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from core.services.encryption_service import EncryptionService
from sqlalchemy import text
import argparse


def clean_corrupted_data(tenant_id: int, dry_run: bool = True):
    """Clean corrupted encrypted data for a tenant."""
    
    print(f"\n{'='*60}")
    print(f"🧹 Cleaning Corrupted Encrypted Data for Tenant {tenant_id}")
    print(f"{'='*60}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will modify data)'}\n")
    
    set_tenant_context(tenant_id)
    encryption_service = EncryptionService()
    
    tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
    tenant_db = tenant_session()
    
    total_corrupted = 0
    total_fixed = 0
    
    try:
        # Check Settings table (has encrypted 'value' column)
        print("📋 Checking 'settings' table...")
        print("-" * 60)
        
        settings = tenant_db.execute(
            text("SELECT id, key, value FROM settings WHERE value IS NOT NULL")
        ).fetchall()
        
        corrupted_settings = []
        for row in settings:
            setting_id, key, value = row
            if value and isinstance(value, str) and len(value) > 20:
                # Try to decrypt
                try:
                    encryption_service.decrypt(value, tenant_id)
                    print(f"✅ Setting {setting_id} ({key}): OK")
                except Exception as e:
                    print(f"❌ Setting {setting_id} ({key}): CORRUPTED - {str(e)[:50]}")
                    corrupted_settings.append((setting_id, key))
                    total_corrupted += 1
        
        if corrupted_settings and not dry_run:
            print(f"\n🔨 Fixing {len(corrupted_settings)} corrupted settings...")
            for setting_id, key in corrupted_settings:
                tenant_db.execute(
                    text("UPDATE settings SET value = NULL WHERE id = :id"),
                    {"id": setting_id}
                )
                print(f"   ✅ Nullified setting {setting_id} ({key})")
                total_fixed += 1
            tenant_db.commit()
        
        # Check AI Configs table (has encrypted 'api_key' column)
        print(f"\n📋 Checking 'ai_configs' table...")
        print("-" * 60)
        
        ai_configs = tenant_db.execute(
            text("SELECT id, provider_name, api_key FROM ai_configs WHERE api_key IS NOT NULL")
        ).fetchall()
        
        corrupted_configs = []
        for row in ai_configs:
            config_id, provider_name, api_key = row
            if api_key:
                # Try to decrypt
                try:
                    encryption_service.decrypt(api_key, tenant_id)
                    print(f"✅ AI Config {config_id} ({provider_name}): OK")
                except Exception as e:
                    print(f"❌ AI Config {config_id} ({provider_name}): CORRUPTED - {str(e)[:50]}")
                    corrupted_configs.append((config_id, provider_name))
                    total_corrupted += 1
        
        if corrupted_configs and not dry_run:
            print(f"\n🔨 Fixing {len(corrupted_configs)} corrupted AI configs...")
            for config_id, provider_name in corrupted_configs:
                tenant_db.execute(
                    text("UPDATE ai_configs SET api_key = NULL WHERE id = :id"),
                    {"id": config_id}
                )
                print(f"   ✅ Nullified AI config {config_id} ({provider_name})")
                total_fixed += 1
            tenant_db.commit()
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 Summary")
        print(f"{'='*60}")
        print(f"Total corrupted fields found: {total_corrupted}")
        if dry_run:
            print(f"⚠️  DRY RUN - No changes made")
            print(f"Run with --live to actually fix the data")
        else:
            print(f"Total fields fixed: {total_fixed}")
            print(f"✅ Data cleaned successfully")
        print(f"{'='*60}\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if not dry_run:
            tenant_db.rollback()
        return False
    finally:
        tenant_db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean corrupted encrypted data")
    parser.add_argument("--tenant-id", type=int, required=True, help="Tenant ID")
    parser.add_argument("--live", action="store_true", help="Actually fix the data (default is dry run)")
    
    args = parser.parse_args()
    
    success = clean_corrupted_data(args.tenant_id, dry_run=not args.live)
    sys.exit(0 if success else 1)
