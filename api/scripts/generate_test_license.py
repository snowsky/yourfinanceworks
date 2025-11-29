#!/usr/bin/env python3
"""
Generate a test license for local development and testing.

This script generates a valid license key using the current keys in api/core/keys/
"""

import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from license_server.license_generator import LicenseGenerator


def main():
    """Generate a test license"""
    print("=" * 70)
    print("Test License Generator")
    print("=" * 70)
    print()
    
    try:
        # Initialize generator with current keys
        generator = LicenseGenerator()
        
        # Generate a test license with all licensed features
        all_features = [
            "ai_invoice",
            "ai_expense",
            "ai_bank_statement",
            "ai_chat",
            "tax_integration",
            "slack_integration",
            "cloud_storage",
            "sso",
            "email_integration",
            "batch_processing",
            "api_keys",
            "approvals",
            "reporting",
            "advanced_search",
        ]
        
        license_key = generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test User",
            features=all_features,
            duration_days=365,
            organization_name="Test Organization",
        )
        
        print("✓ License generated successfully!")
        print()
        print("License Key:")
        print("-" * 70)
        print(license_key)
        print("-" * 70)
        print()
        
        # Get license info
        info = generator.get_license_info(license_key)
        print("License Information:")
        print(f"  Customer: {info['customer_name']} ({info['customer_email']})")
        print(f"  Organization: {info.get('organization_name', 'N/A')}")
        print(f"  Features: {len(info['features'])} features")
        print(f"  Issued: {info['issued_at']}")
        print(f"  Expires: {info['expires_at']}")
        print(f"  Days Remaining: {info['days_remaining']}")
        print()
        print("To activate this license:")
        print("1. Copy the license key above")
        print("2. Go to the License Management page in the UI")
        print("3. Paste the license key and click 'Activate'")
        print()
        
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        print()
        print("To generate keys, run:")
        print("  python api/scripts/generate_license_keys.py")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
