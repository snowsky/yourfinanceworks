#!/usr/bin/env python3
"""
Simple verification test for core feature access.
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

def test_core_features():
    """Test that core features are accessible"""
    
    # Create in-memory database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    print("=" * 80)
    print("Testing Core Feature Access")
    print("=" * 80)
    
    # Test 1: Fresh install - core features via defaults
    print("\n📋 Test 1: Fresh Install (Invalid Status)")
    print("-" * 80)
    db = SessionLocal()
    
    installation = InstallationInfo(
        installation_id="test-fresh",
        license_status="invalid",
        usage_type=None
    )
    db.add(installation)
    db.commit()
    
    # Core features with default=True should be accessible
    reporting_enabled = FeatureConfigService.is_enabled("reporting", db)
    advanced_search_enabled = FeatureConfigService.is_enabled("advanced_search", db)
    
    print(f"✓ reporting (core, default=True): {reporting_enabled}")
    print(f"✓ advanced_search (core, default=True): {advanced_search_enabled}")
    
    assert reporting_enabled, "Core features with default=True should be enabled"
    assert advanced_search_enabled, "Core features with default=True should be enabled"
    
    # Commercial features should NOT be accessible
    ai_invoice_enabled = FeatureConfigService.is_enabled("ai_invoice", db)
    print(f"✓ ai_invoice (commercial, default=False): {ai_invoice_enabled}")
    assert not ai_invoice_enabled, "Commercial features should NOT be enabled"
    
    db.close()
    print("✅ Test 1 PASSED")
    
    # Test 2: Personal license
    print("\n📋 Test 2: Personal License")
    print("-" * 80)
    db = SessionLocal()
    
    db.query(InstallationInfo).delete()
    installation = InstallationInfo(
        installation_id="test-personal",
        license_status="personal",
        usage_type="personal"
    )
    db.add(installation)
    db.commit()
    
    reporting_enabled = FeatureConfigService.is_enabled("reporting", db)
    ai_invoice_enabled = FeatureConfigService.is_enabled("ai_invoice", db)
    
    print(f"✓ reporting (core): {reporting_enabled}")
    print(f"✓ ai_invoice (commercial): {ai_invoice_enabled}")
    
    assert reporting_enabled, "Core features should be enabled for personal"
    assert not ai_invoice_enabled, "Commercial features should NOT be enabled for personal"
    
    db.close()
    print("✅ Test 2 PASSED")
    
    print("\n" + "=" * 80)
    print("✅ ALL CORE FEATURE TESTS PASSED!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_core_features()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
