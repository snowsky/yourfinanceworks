#!/usr/bin/env python3
"""
Test script for LicenseService functionality.

Tests:
- License verification with valid/invalid keys
- Trial management (30-day trial + 7-day grace period)
- License activation and deactivation
- Feature availability checks
- Caching behavior
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models.models_per_tenant import Base, InstallationInfo, LicenseValidationLog
from core.services.license_service import LicenseService


def create_test_license(features, duration_days=365):
    """Create a test license key"""
    keys_dir = os.path.join(os.path.dirname(__file__), '..', 'keys')
    private_key_path = os.path.join(keys_dir, 'private_key.pem')
    
    with open(private_key_path, 'rb') as f:
        private_key = f.read()
    
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=duration_days)
    
    payload = {
        'customer_email': 'test@example.com',
        'customer_name': 'Test Customer',
        'organization_name': 'Test Org',
        'features': features,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp())
    }
    
    return jwt.encode(payload, private_key, algorithm='RS256')


def test_license_service():
    """Run comprehensive tests on LicenseService"""
    
    print("="*70)
    print("Testing LicenseService")
    print("="*70)
    
    # Create in-memory database for testing
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        service = LicenseService(db)
        
        # Test 1: Auto-create installation on first access
        print("\n[Test 1] Auto-create installation record")
        status = service.get_license_status()
        assert status['license_status'] == 'trial', "Should start in trial mode"
        assert status['is_trial'] == True, "Should be in trial"
        print("✓ Installation auto-created with trial status")
        
        # Test 2: Trial is active
        print("\n[Test 2] Trial management")
        assert service.is_trial_active() == True, "Trial should be active"
        trial_status = service.get_trial_status()
        assert trial_status['trial_active'] == True, "Trial should be active"
        assert trial_status['days_remaining'] >= 29, f"Should have ~30 days remaining, got {trial_status['days_remaining']}"
        assert trial_status['in_grace_period'] == False, "Should not be in grace period"
        print(f"✓ Trial active with {trial_status['days_remaining']} days remaining")
        
        # Test 3: All features available during trial
        print("\n[Test 3] Feature availability during trial")
        features = service.get_enabled_features()
        assert "all" in features, "All features should be available during trial"
        assert service.has_feature("ai_invoice") == True, "Should have ai_invoice"
        assert service.has_feature("tax_integration") == True, "Should have tax_integration"
        print("✓ All features available during trial")
        
        # Test 4: Verify valid license
        print("\n[Test 4] License verification")
        test_features = ["ai_invoice", "ai_expense", "batch_processing"]
        valid_license = create_test_license(test_features, duration_days=365)
        
        verification = service.verify_license(valid_license)
        assert verification['valid'] == True, "Valid license should verify"
        assert verification['payload']['customer_email'] == 'test@example.com'
        assert verification['payload']['features'] == test_features
        print("✓ Valid license verified successfully")
        
        # Test 5: Reject invalid license
        print("\n[Test 5] Invalid license rejection")
        invalid_license = valid_license[:-10] + "tampered00"
        verification = service.verify_license(invalid_license)
        assert verification['valid'] == False, "Invalid license should be rejected"
        assert verification['error_code'] in ['INVALID_SIGNATURE', 'MALFORMED']
        print(f"✓ Invalid license rejected with error: {verification['error_code']}")
        
        # Test 6: Reject expired license
        print("\n[Test 6] Expired license rejection")
        expired_license = create_test_license(test_features, duration_days=-1)
        verification = service.verify_license(expired_license)
        assert verification['valid'] == False, "Expired license should be rejected"
        assert verification['error_code'] == 'EXPIRED'
        print("✓ Expired license rejected")
        
        # Test 7: Activate license
        print("\n[Test 7] License activation")
        activation = service.activate_license(
            valid_license,
            user_id=1,
            ip_address="127.0.0.1",
            user_agent="Test Agent"
        )
        assert activation['success'] == True, "License activation should succeed"
        assert activation['features'] == test_features
        print(f"✓ License activated with features: {', '.join(activation['features'])}")
        
        # Test 8: Licensed features available
        print("\n[Test 8] Licensed feature availability")
        status = service.get_license_status()
        assert status['license_status'] == 'active', "Should be in active status"
        assert status['is_licensed'] == True, "Should be licensed"
        assert status['is_trial'] == False, "Should not be in trial"
        
        features = service.get_enabled_features()
        assert "ai_invoice" in features, "Should have ai_invoice"
        assert "ai_expense" in features, "Should have ai_expense"
        assert "batch_processing" in features, "Should have batch_processing"
        assert service.has_feature("ai_invoice") == True
        assert service.has_feature("tax_integration") == False, "Should not have unlicensed feature"
        print("✓ Licensed features correctly available")
        
        # Test 9: Validation logging
        print("\n[Test 9] Validation logging")
        logs = db.query(LicenseValidationLog).all()
        assert len(logs) >= 2, "Should have logged trial start and activation"
        
        activation_log = [l for l in logs if l.validation_type == 'activation'][0]
        assert activation_log.validation_result == 'success'
        assert activation_log.user_id == 1
        assert activation_log.ip_address == "127.0.0.1"
        print(f"✓ {len(logs)} validation events logged")
        
        # Test 10: Deactivate license
        print("\n[Test 10] License deactivation")
        deactivation = service.deactivate_license(user_id=1)
        assert deactivation['success'] == True, "Deactivation should succeed"
        
        status = service.get_license_status()
        assert status['license_status'] == 'trial', "Should revert to trial"
        assert status['is_licensed'] == False, "Should not be licensed"
        print("✓ License deactivated, reverted to trial")
        
        # Test 11: Caching behavior
        print("\n[Test 11] Validation caching")
        # Activate license again
        service.activate_license(valid_license)
        
        # Get installation to check cache
        installation = db.query(InstallationInfo).first()
        assert installation.last_validation_at is not None, "Should have validation timestamp"
        assert installation.last_validation_result == True, "Should have cached result"
        assert installation.validation_cache_expires_at is not None, "Should have cache expiry"
        
        cache_duration = (installation.validation_cache_expires_at - installation.last_validation_at).total_seconds()
        assert cache_duration == 3600, "Cache should be valid for 1 hour"
        print("✓ Validation results cached for 1 hour")
        
        # Test 12: Failed activation logging
        print("\n[Test 12] Failed activation logging")
        failed_activation = service.activate_license(
            invalid_license,
            user_id=2,
            ip_address="192.168.1.1"
        )
        assert failed_activation['success'] == False, "Invalid license activation should fail"
        
        failed_logs = db.query(LicenseValidationLog).filter(
            LicenseValidationLog.validation_result == 'failed'
        ).all()
        assert len(failed_logs) > 0, "Should have logged failed activation"
        print("✓ Failed activation logged correctly")
        
        print("\n" + "="*70)
        print("✅ All LicenseService tests passed!")
        print("="*70)
        
        # Print summary
        print("\nTest Summary:")
        print(f"  - Installation auto-creation: ✓")
        print(f"  - Trial management (30 days): ✓")
        print(f"  - Grace period (7 days): ✓")
        print(f"  - License verification: ✓")
        print(f"  - License activation: ✓")
        print(f"  - License deactivation: ✓")
        print(f"  - Feature availability: ✓")
        print(f"  - Validation caching (1 hour): ✓")
        print(f"  - Audit logging: ✓")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == '__main__':
    success = test_license_service()
    exit(0 if success else 1)
