#!/usr/bin/env python3
"""Create a test AI config for testing usage tracking"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from core.models.database import get_master_db, set_tenant_context
from core.models.models_per_tenant import AIConfig
from datetime import datetime, timezone

def create_test_ai_config():
    """Create a test Ollama AI config"""
    print("Creating test AI config...")

    # Set tenant context to 1 (default tenant)
    set_tenant_context(1)

    # Get database session
    db = next(get_master_db())

    try:
        # Check if any AI configs exist
        existing = db.query(AIConfig).all()
        print(f'Existing AI configs: {len(existing)}')

        if not existing:
            # Create a test Ollama config
            ollama_config = AIConfig(
                provider_name='ollama',
                provider_url='http://localhost:11434',
                model_name='llama3.2-vision:11b',
                is_active=True,
                tested=True,
                is_default=True,
                ocr_enabled=True,  # Enable OCR for this config
                max_tokens=4096,
                temperature=0.1,
                usage_count=0
            )
            db.add(ollama_config)
            db.commit()
            db.refresh(ollama_config)
            print(f'✅ Created test Ollama AI config with ID: {ollama_config.id}')
            print(f'   Provider: {ollama_config.provider_name}')
            print(f'   Model: {ollama_config.model_name}')
            print(f'   Usage count: {ollama_config.usage_count}')
        else:
            for config in existing:
                print(f'  {config.provider_name}/{config.model_name}: usage_count={config.usage_count}')

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_ai_config()
