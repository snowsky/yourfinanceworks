"""
Tests for Feature Gate System

Tests the feature gate decorator and feature configuration service.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from core.utils.feature_gate import require_feature, feature_enabled, get_enabled_features
from core.services.feature_config_service import FeatureConfigService


class TestFeatureConfigService:
    """Test FeatureConfigService functionality"""
    
    def test_feature_exists(self):
        """Test checking if a feature exists"""
        assert "ai_invoice" in FeatureConfigService.FEATURES
        assert "ai_expense" in FeatureConfigService.FEATURES
        assert "tax_integration" in FeatureConfigService.FEATURES
        assert "batch_processing" in FeatureConfigService.FEATURES
        assert "inventory" in FeatureConfigService.FEATURES
        assert "approvals" in FeatureConfigService.FEATURES
        assert "reporting" in FeatureConfigService.FEATURES
    
    def test_feature_not_exists(self):
        """Test checking non-existent feature"""
        assert FeatureConfigService.is_enabled("nonexistent_feature", check_license=False) is False
    
    def test_get_all_features(self):
        """Test getting all features"""
        features = FeatureConfigService.get_all_features()
        assert len(features) > 0
        assert all('id' in f and 'name' in f and 'category' in f for f in features)
    
    def test_get_features_by_category(self):
        """Test getting features by category"""
        ai_features = FeatureConfigService.get_features_by_category('ai')
        assert len(ai_features) > 0
        assert all(f['category'] == 'ai' for f in ai_features)
        
        integration_features = FeatureConfigService.get_features_by_category('integration')
        assert len(integration_features) > 0
        assert all(f['category'] == 'integration' for f in integration_features)
    
    def test_get_categories(self):
        """Test getting all categories"""
        categories = FeatureConfigService.get_categories()
        assert 'ai' in categories
        assert 'integration' in categories
        assert 'advanced' in categories


class TestFeatureGate:
    """Test feature gate decorator functionality"""
    
    @pytest.mark.asyncio
    async def test_feature_gate_allows_licensed_feature(self):
        """Test that feature gate allows access when feature is licensed"""
        
        @require_feature("ai_invoice")
        async def test_endpoint(db: Session = None):
            return {"success": True}
        
        # Mock the license service to return True
        with patch('utils.feature_gate.LicenseService') as mock_license_service:
            mock_service = Mock()
            mock_service.has_feature.return_value = True
            mock_license_service.return_value = mock_service
            
            mock_db = Mock(spec=Session)
            result = await test_endpoint(db=mock_db)
            assert result == {"success": True}
    
    @pytest.mark.asyncio
    async def test_feature_gate_blocks_unlicensed_feature(self):
        """Test that feature gate blocks access when feature is not licensed"""
        
        @require_feature("ai_invoice")
        async def test_endpoint(db: Session = None):
            return {"success": True}
        
        # Mock the license service to return False
        with patch('utils.feature_gate.LicenseService') as mock_license_service:
            mock_service = Mock()
            mock_service.has_feature.return_value = False
            mock_service.get_trial_status.return_value = {
                "is_trial": True,
                "trial_active": False,
                "in_grace_period": False
            }
            mock_service.get_license_status.return_value = {
                "license_status": "trial",
                "is_licensed": False
            }
            mock_license_service.return_value = mock_service
            
            mock_db = Mock(spec=Session)
            
            with pytest.raises(HTTPException) as exc_info:
                await test_endpoint(db=mock_db)
            
            assert exc_info.value.status_code == 402
            assert "FEATURE_NOT_LICENSED" in str(exc_info.value.detail)
    
    def test_feature_enabled_helper(self):
        """Test feature_enabled helper function"""
        # Mock the license service
        with patch('utils.feature_gate.LicenseService') as mock_license_service:
            mock_service = Mock()
            mock_service.has_feature.return_value = True
            mock_license_service.return_value = mock_service
            
            mock_db = Mock(spec=Session)
            assert feature_enabled("ai_invoice", db=mock_db) is True
    
    def test_get_enabled_features_helper(self):
        """Test get_enabled_features helper function"""
        # Mock the license service
        with patch('utils.feature_gate.LicenseService') as mock_license_service:
            mock_service = Mock()
            mock_service.get_enabled_features.return_value = ["ai_invoice", "ai_expense"]
            mock_license_service.return_value = mock_service
            
            mock_db = Mock(spec=Session)
            features = get_enabled_features(db=mock_db)
            assert "ai_invoice" in features
            assert "ai_expense" in features


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
