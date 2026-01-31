#!/usr/bin/env python3
"""
Robust script to check AI configuration with proper SQLAlchemy initialization
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, '/app')

def main():
    print("=== AI Configuration Status ===")

    # Import models in the correct order to resolve SQLAlchemy relationships
    try:
        print("Importing models...")
        from core.models.models_per_tenant import User, AIConfig
        from core.models.gamification import UserGamificationProfile

        # Force model registration by referencing them
        _ = User
        _ = UserGamificationProfile
        print("✅ Models imported successfully")

    except Exception as e:
        print(f"❌ Failed to import models: {e}")
        return

    # Now initialize database connection
    try:
        from core.models.database import set_tenant_context, get_db

        print("Setting tenant context...")
        set_tenant_context(1)

        print("Getting database session...")
        db = next(get_db())
        print("✅ Database session established")

    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return

    try:
        # Query AI configurations
        # Query AI configurations
        print("\n=== OpenAI and Anthropic Configurations ===")
        configs = db.query(AIConfig).filter(AIConfig.provider_name.in_(['openai', 'anthropic'])).all()

        for config in configs:
            print(f"ID: {config.id}")
            print(f"  Provider: {config.provider_name}")
            print(f"  Model: {config.model_name}")
            print(f"  OCR Enabled: {config.ocr_enabled}")
            print(f"  Active: {config.is_active}")
            print(f"  Tested: {config.tested}")
            print(f"  Default: {config.is_default}")
            print(f"  Provider URL: {config.provider_url}")
            print(f"  Has API Key: {bool(config.api_key)}")
            print(f"  Usage Count: {config.usage_count}")
            print(f"  Last Used: {config.last_used_at}")
            print()

    except Exception as e:
        print(f"❌ Failed to query configurations: {e}")

    finally:
        try:
            db.close()
            print("✅ Database session closed")
        except:
            pass

if __name__ == '__main__':
    main()
