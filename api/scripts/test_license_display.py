#!/usr/bin/env python3
"""
Test script to check license activation and display dates
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from core.models.database import SessionLocal
from core.services.license_service import LicenseService

def test_license_dates():
    """Test license activation and date display"""
    db = SessionLocal()
    
    try:
        license_service = LicenseService(db)
        
        # Get current license status
        status = license_service.get_license_status()
        
        print("=" * 70)
        print("LICENSE STATUS TEST")
        print("=" * 70)
        print(f"\nInstallation ID: {status['installation_id']}")
        print(f"License Status: {status['license_status']}")
        print(f"Usage Type: {status['usage_type']}")
        print(f"Is Licensed: {status['is_licensed']}")
        
        if status.get('license_info'):
            license_info = status['license_info']
            print("\n--- LICENSE INFO ---")
            print(f"Activated At: {license_info.get('activated_at')}")
            print(f"Expires At: {license_info.get('expires_at')}")
            print(f"Customer: {license_info.get('customer_name')}")
            print(f"Email: {license_info.get('customer_email')}")
            
            # Check if dates are datetime objects or strings
            expires_at = license_info.get('expires_at')
            if expires_at:
                print(f"\nExpires At Type: {type(expires_at)}")
                if isinstance(expires_at, datetime):
                    print(f"Expires At (ISO): {expires_at.isoformat()}")
                    now = datetime.now(timezone.utc)
                    days_remaining = (expires_at - now).days
                    print(f"Days Remaining: {days_remaining}")
                else:
                    print(f"Expires At (String): {expires_at}")
        
        if status.get('trial_info'):
            trial_info = status['trial_info']
            print("\n--- TRIAL INFO ---")
            print(f"Is Trial: {trial_info.get('is_trial')}")
            print(f"Trial Active: {trial_info.get('trial_active')}")
            print(f"Days Remaining: {trial_info.get('days_remaining')}")
        
        print("\n--- ENABLED FEATURES ---")
        print(f"Features: {status['enabled_features']}")
        print(f"Has All Features: {status['has_all_features']}")
        
        print("\n" + "=" * 70)
        
    finally:
        db.close()

if __name__ == "__main__":
    test_license_dates()
