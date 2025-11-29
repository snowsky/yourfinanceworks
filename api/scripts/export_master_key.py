#!/usr/bin/env python3
"""
Export Master Key for Environment Variable

This script exports the current master key as a base64-encoded string
that can be used as the MASTER_KEY environment variable.

Usage:
    python scripts/export_master_key.py
"""

import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services.key_management_service import get_key_management_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Export the current master key for environment variable use."""
    try:
        logger.info("Exporting current master key...")
        
        # Get the key management service
        kms = get_key_management_service()
        
        # Export the master key
        master_key_b64 = kms.export_master_key_for_env()
        
        print("\n" + "="*60)
        print("MASTER KEY EXPORT")
        print("="*60)
        print(f"Add this to your environment variables:")
        print(f"MASTER_KEY={master_key_b64}")
        print("\nOr add to your docker-compose.yml:")
        print(f"  - MASTER_KEY={master_key_b64}")
        print("\nOr add to your .env file:")
        print(f"MASTER_KEY={master_key_b64}")
        print("="*60)
        print("⚠️  SECURITY WARNING: Keep this key secure and never commit it to version control!")
        print("="*60)
        
        logger.info("Master key exported successfully")
        
    except Exception as e:
        logger.error(f"Failed to export master key: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()