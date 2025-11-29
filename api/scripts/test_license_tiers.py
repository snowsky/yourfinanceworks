#!/usr/bin/env python3
"""
Test script to verify license tier validation logic.

This script tests:
1. Personal license only enables core features
2. Trial/grace period enables all features
3. Commercial license enables commercial + core features
4. FeatureConfigService correctly uses tier information
"""

import sys
import os
from pathlib import Path

# Add the api directory to the path
api_dir = Path(__file__).parent.parent
sys.path.insert(0, str(api_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.models_per_tenant import Base, InstallationInfo
from core.services.license_service import LicenseService
from core.services.feature_config_service import FeatureConfigService
from datetime import datetime, timedelta, timezone


def test_license_tiers():
    """Test license tier validation logic"""
    
    # Create in-memory database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    print("=" * 80)
    print("Testing License Tier Validation Logic")
    print("=" * 80)
    
    # Test 1: Personal License (Core Only)
    print("\n📋 Test 1: Personal License (Core Features Only)")
    print("-" * 80)
    db = SessionLocal()
    
    # Create personal installation
    installation = InstallationInfo(
        installation_id="test-personal",
        license_status="personal",
        usage_type="personal"
    )
    db.add(installation)
    db.commit()
    
    license_service = LicenseService(db)
    enabled_features = license_service.get_enabled_features()
    
    print(f"✓ Enabled features: {enabled_features}")
    assert enabled_features == ["core"], f"Expected ['core'], got {enabled_features}"
    
    # Test core feature
    has_reporting = license_service.has_feature("reporting", tier="core")
    print(f"✓ Has 'reporting' (core): {has_reporting}")
    assert has_reporting, "Core features should be enabled for personal license"
    
    # Test commercial feature
    has_ai_invoice = license_service.has_feature("ai_invoice", tier="commercial")
    print(f"✓ Has 'ai_invoice' (commercial): {has_ai_invoice}")
    assert not has_ai_invoice, "Commercial features should NOT be enabled for personal license"
    
    # Test FeatureConfigService integration
    reporting_enabled = FeatureConfigService.is_enabled("reporting", db)
    ai_invoice_enabled = FeatureConfigService.is_enabled("ai_invoice", db)
    
    print(f"✓ FeatureConfigService - reporting (core): {reporting_enabled}")
    print(f"✓ FeatureConfigService - ai_invoice (commercial): {ai_invoice_enabled}")
    
    assert reporting_enabled, "Core features should be enabled via FeatureConfigService"
    assert not ai_invoice_enabled, "Commercial features should NOT be enabled via FeatureConfigService"
    
    db.close()
    print("✅ Test 1 PASSED: Personal license correctly enables only core features")
    
    # Test 2: Trial License (All Features)
    print("\n📋 Test 2: Trial License (All Features)")
    print("-" * 80)
    db = SessionLocal()
    
    # Clear previous installation
    db.query(InstallationInfo).delete()
    
    # Create trial installation
    now = datetime.now(timezone.utc)
    installation = InstallationInfo(
        installation_id="test-trial",
        license_status="trial",
        usage_type="business",
        trial_start_date=now,
        trial_end_date=now + timedelta(days=30)
    )
    db.add(installation)
    db.commit()
    
    license_service = LicenseService(db)
    enabled_features = license_service.get_enabled_features()
    
    print(f"✓ Enabled features: {enabled_features}")
    assert enabled_features == ["all"], f"Expected ['all'], got {enabled_features}"
    
    # Test core feature
    has_reporting = license_service.has_feature("reporting", tier="core")
    print(f"✓ Has 'reporting' (core): {has_reporting}")
    assert has_reporting, "Core features should be enabled during trial"
    
    # Test commercial feature
    has_ai_invoice = license_service.has_feature("ai_invoice", tier="commercial")
    print(f"✓ Has 'ai_invoice' (commercial): {has_ai_invoice}")
    assert has_ai_invoice, "Commercial features should be enabled during trial"
    
    # Test FeatureConfigService integration
    reporting_enabled = FeatureConfigService.is_enabled("reporting", db)
    ai_invoice_enabled = FeatureConfigService.is_enabled("ai_invoice", db)
    
    print(f"✓ FeatureConfigService - reporting (core): {reporting_enabled}")
    print(f"✓ FeatureConfigService - ai_invoice (commercial): {ai_invoice_enabled}")
    
    assert reporting_enabled, "Core features should be enabled via FeatureConfigService during trial"
    assert ai_invoice_enabled, "Commercial features should be enabled via FeatureConfigService during trial"
    
    db.close()
    print("✅ Test 2 PASSED: Trial license correctly enables all features")
    
    # Test 3: Active Commercial License (Commercial + Core)
    print("\n📋 Test 3: Active Commercial License (Commercial + Core)")
    print("-" * 80)
    db = SessionLocal()
    
    # Clear previous installation
    db.query(InstallationInfo).delete()
    
    # Create active license installation (without license_key to avoid verification)
    installation = InstallationInfo(
        installation_id="test-active",
        license_status="active",
        usage_type="business",
        licensed_features=["ai_invoice", "ai_expense", "cloud_storage"],
        license_activated_at=datetime.now(timezone.utc),
        license_expires_at=datetime.now(timezone.utc) + timedelta(days=365)
    )
    db.add(installation)
    db.commit()
    
    license_service = LicenseService(db)
    enabled_features = license_service.get_enabled_features()
    
    print(f"✓ Enabled features: {enabled_features}")
    assert "core" in enabled_features, "Core should be in enabled features"
    assert "ai_invoice" in enabled_features, "Licensed commercial features should be enabled"
    
    # Test core feature
    has_reporting = license_service.has_feature("reporting", tier="core")
    print(f"✓ Has 'reporting' (core): {has_reporting}")
    assert has_reporting, "Core features should be enabled with active license"
    
    # Test licensed commercial feature
    has_ai_invoice = license_service.has_feature("ai_invoice", tier="commercial")
    print(f"✓ Has 'ai_invoice' (commercial, licensed): {has_ai_invoice}")
    assert has_ai_invoice, "Licensed commercial features should be enabled"
    
    # Test unlicensed commercial feature
    has_tax = license_service.has_feature("tax_integration", tier="commercial")
    print(f"✓ Has 'tax_integration' (commercial, not licensed): {has_tax}")
    assert not has_tax, "Unlicensed commercial features should NOT be enabled"
    
    db.close()
    print("✅ Test 3 PASSED: Active license correctly enables commercial + core features")
    
    # Test 4: Expired License (Core Only)
    print("\n📋 Test 4: Expired License (Core Only)")
    print("-" * 80)
    db = SessionLocal()
    
    # Clear previous installation
    db.query(InstallationInfo).delete()
    
    # Create expired license installation
    installation = InstallationInfo(
        installation_id="test-expired",
        license_status="active",
        usage_type="business",
        licensed_features=["ai_invoice", "ai_expense"],
        license_key="test-key",
        license_activated_at=datetime.now(timezone.utc) - timedelta(days=400),
        license_expires_at=datetime.now(timezone.utc) - timedelta(days=35)  # Expired 35 days ago
    )
    db.add(installation)
    db.commit()
    
    license_service = LicenseService(db)
    enabled_features = license_service.get_enabled_features()
    
    print(f"✓ Enabled features: {enabled_features}")
    assert enabled_features == ["core"], f"Expected ['core'] for expired license, got {enabled_features}"
    
    # Verify status was updated to expired
    db.refresh(installation)
    print(f"✓ License status updated to: {installation.license_status}")
    assert installation.license_status == "expired", "License status should be updated to expired"
    
    db.close()
    print("✅ Test 4 PASSED: Expired license correctly falls back to core features")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print("\nSummary:")
    print("  ✓ Personal license: Core features only")
    print("  ✓ Trial license: All features")
    print("  ✓ Active commercial license: Licensed commercial + core features")
    print("  ✓ Expired license: Falls back to core features")
    print("  ✓ FeatureConfigService correctly integrates with license tiers")


if __name__ == "__main__":
    try:
        test_license_tiers()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
