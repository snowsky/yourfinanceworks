import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add api directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock dependencies before importing modules that might trigger DB connections
sys.modules['models.database'] = MagicMock()
sys.modules['models.models_per_tenant'] = MagicMock()
sys.modules['services.license_service'] = MagicMock()

# Now import the modules we want to test
# We need to reload them if they were already imported, but this is a fresh script
from core.services.feature_config_service import FeatureConfigService
from core.utils.feature_gate import require_feature
from fastapi import HTTPException

# Mock LicenseService for our specific test cases
class MockLicenseService:
    def __init__(self, db):
        self.db = db
        
    def has_feature(self, feature_id):
        return False
        
    def get_license_status(self):
        return {
            "license_status": "invalid",
            "is_licensed": False,
            "is_trial": False,
            "is_personal": False,
            "trial_info": {
                "trial_active": False,
                "in_grace_period": False
            }
        }
        
    def get_trial_status(self):
        return {
            "is_trial": False,
            "trial_active": False,
            "in_grace_period": False
        }

async def test_feature_enabled_invalid_license():
    print("Testing FeatureConfigService.is_enabled with invalid license...")
    mock_db = MagicMock()
    
    with patch('services.feature_config_service.LicenseService', MockLicenseService):
        # 'reporting' is default enabled
        is_enabled = FeatureConfigService.is_enabled('reporting', mock_db, check_license=True)
        print(f"Reporting enabled: {is_enabled}")
        assert is_enabled is True, "Reporting should be enabled by default even with invalid license"
        
        # 'approvals' is default disabled
        is_enabled = FeatureConfigService.is_enabled('approvals', mock_db, check_license=True)
        print(f"Approvals enabled: {is_enabled}")
        assert is_enabled is False, "Approvals should be disabled by default"
        
    print("✅ FeatureConfigService test passed")

async def test_require_feature_decorator():
    print("\nTesting require_feature decorator with invalid license...")
    mock_db = MagicMock()
    
    # Define a dummy endpoint
    @require_feature("reporting")
    async def reporting_endpoint(db=None):
        return "success"
        
    # Mock LicenseService in feature_gate
    # We need to patch where it's imported in feature_gate.py
    with patch('utils.feature_gate.LicenseService', MockLicenseService):
        # Should succeed because reporting is default enabled
        try:
            result = await reporting_endpoint(db=mock_db)
            print(f"Endpoint result: {result}")
            assert result == "success", "Endpoint should return success"
        except HTTPException as e:
            print(f"❌ Endpoint raised exception: {e.detail}")
            raise
            
    print("✅ require_feature decorator test passed")

async def test_require_feature_decorator_blocks_disabled():
    print("\nTesting require_feature decorator blocks disabled features...")
    mock_db = MagicMock()
    
    # Define a dummy endpoint for a disabled feature
    @require_feature("approvals")
    async def approvals_endpoint(db=None):
        return "success"
        
    # Mock LicenseService in feature_gate
    with patch('utils.feature_gate.LicenseService', MockLicenseService):
        # Should raise 402 because approvals is default disabled
        try:
            await approvals_endpoint(db=mock_db)
            print("❌ Endpoint did not raise exception")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            print(f"Caught expected exception: {e.status_code}")
            assert e.status_code == 402, f"Expected 402, got {e.status_code}"
            
    print("✅ require_feature blocking test passed")

async def main():
    try:
        await test_feature_enabled_invalid_license()
        await test_require_feature_decorator()
        await test_require_feature_decorator_blocks_disabled()
        print("\n🎉 All verification tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
