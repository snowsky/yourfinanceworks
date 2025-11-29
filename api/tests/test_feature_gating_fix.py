import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from core.services.feature_config_service import FeatureConfigService
from core.utils.feature_gate import require_feature

# Mock LicenseService
class MockLicenseService:
    def __init__(self, db):
        self.db = db
        
    def has_feature(self, feature_id):
        return False
        
    def get_license_status(self):
        return {"license_status": "invalid"}
        
    def get_trial_status(self):
        return {
            "is_trial": False,
            "trial_active": False,
            "in_grace_period": False
        }

@pytest.mark.asyncio
async def test_feature_enabled_invalid_license():
    """Test that feature is enabled when license is invalid but default is True"""
    
    # Mock dependencies
    mock_db = MagicMock()
    
    with patch('services.feature_config_service.LicenseService', MockLicenseService):
        # Test FeatureConfigService directly
        # 'reporting' is default enabled
        assert FeatureConfigService.is_enabled('reporting', mock_db, check_license=True) is True
        
        # 'approvals' is default disabled
        assert FeatureConfigService.is_enabled('approvals', mock_db, check_license=True) is False

@pytest.mark.asyncio
async def test_require_feature_decorator_invalid_license():
    """Test that decorator allows access when license is invalid but default is True"""
    
    mock_db = MagicMock()
    
    # Define a dummy endpoint
    @require_feature("reporting")
    async def reporting_endpoint(db=None):
        return "success"
        
    # Mock LicenseService in feature_gate
    with patch('utils.feature_gate.LicenseService', MockLicenseService):
        # Should succeed because reporting is default enabled
        result = await reporting_endpoint(db=mock_db)
        assert result == "success"

@pytest.mark.asyncio
async def test_require_feature_decorator_blocks_disabled():
    """Test that decorator blocks access when license is invalid and default is False"""
    
    mock_db = MagicMock()
    
    # Define a dummy endpoint for a disabled feature
    @require_feature("approvals")
    async def approvals_endpoint(db=None):
        return "success"
        
    # Mock LicenseService in feature_gate
    with patch('utils.feature_gate.LicenseService', MockLicenseService):
        # Should raise 402 because approvals is default disabled
        with pytest.raises(HTTPException) as excinfo:
            await approvals_endpoint(db=mock_db)
        
        assert excinfo.value.status_code == 402
