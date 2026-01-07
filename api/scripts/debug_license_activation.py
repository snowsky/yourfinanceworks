#!/usr/bin/env python3
"""
Debug script to test license activation with detailed error information.
"""

import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from license_server.license_generator import LicenseGenerator
from core.services.license_service import LicenseService, PUBLIC_KEYS, DEFAULT_KEY_ID
import jwt


def main():
    """Debug license activation"""
    print("=" * 70)
    print("License Activation Debug Tool")
    print("=" * 70)
    print()
    
    try:
        # Step 1: Generate a test license
        print("Step 1: Generating test license...")
        print("-" * 70)
        
        generator = LicenseGenerator()
        
        all_features = [
            "ai_invoice",
            "ai_expense",
            "ai_bank_statement",
            "ai_chat",
            "tax_integration",
            "slack_integration",
            "cloud_storage",
            "sso_authentication",
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
        
        print(f"✓ License generated")
        print(f"  Key (first 50 chars): {license_key[:50]}...")
        print()
        
        # Step 2: Decode the license to see what's in it
        print("Step 2: Decoding license (without verification)...")
        print("-" * 70)
        
        unverified = jwt.decode(license_key, options={"verify_signature": False})
        print(f"✓ License decoded successfully")
        print(f"  Customer: {unverified.get('customer_name')} ({unverified.get('customer_email')})")
        print(f"  Key ID (kid): {unverified.get('kid', 'NOT SET')}")
        print(f"  Features: {len(unverified.get('features', []))} features")
        print()
        
        # Step 3: Check what public keys are loaded
        print("Step 3: Checking loaded public keys...")
        print("-" * 70)
        
        print(f"Default Key ID: {DEFAULT_KEY_ID}")
        print(f"Available key versions: {list(PUBLIC_KEYS.keys())}")
        
        kid = unverified.get("kid", DEFAULT_KEY_ID)
        if kid in PUBLIC_KEYS:
            print(f"✓ Public key '{kid}' is available")
            print(f"  Key (first 50 chars): {PUBLIC_KEYS[kid][:50]}...")
        else:
            print(f"✗ Public key '{kid}' NOT FOUND")
            print(f"  Available keys: {list(PUBLIC_KEYS.keys())}")
        print()
        
        # Step 4: Try to verify the license
        print("Step 4: Verifying license signature...")
        print("-" * 70)
        
        try:
            payload = jwt.decode(
                license_key,
                PUBLIC_KEYS[kid],
                algorithms=["RS256"]
            )
            print(f"✓ License signature verified successfully!")
            print(f"  Payload verified: {list(payload.keys())}")
        except jwt.InvalidSignatureError as e:
            print(f"✗ Invalid signature: {e}")
            print()
            print("TROUBLESHOOTING:")
            print("1. Check that the license was generated with the correct private key")
            print("2. Check that the public key matches the private key used for signing")
            print("3. Verify the keys in api/core/keys/ directory")
            print()
            
            # Try to help diagnose
            print("Diagnostic info:")
            print(f"  - License kid: {kid}")
            print(f"  - Available keys: {list(PUBLIC_KEYS.keys())}")
            print(f"  - License generator key version: {generator.key_version}")
            
            return False
        except Exception as e:
            print(f"✗ Verification error: {e}")
            return False
        
        print()
        print("=" * 70)
        print("✓ All checks passed! License is valid and ready to activate.")
        print("=" * 70)
        print()
        print("License Key (copy this to activate):")
        print("-" * 70)
        print(license_key)
        print("-" * 70)
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
