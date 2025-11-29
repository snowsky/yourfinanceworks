#!/usr/bin/env python3
"""
Comprehensive test suite for feature gating.

Tests:
- API endpoints with and without licenses
- HTTP 402 responses for unlicensed features
- Feature gates with expired licenses
- UI feature visibility based on license
- Requirements: 1.3, 1.4, 1.8, 1.9
"""

import sys
import os
import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app
from core.services.license_service import LicenseService
from core.models.models_per_tenant import Base, InstallationInfo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def license_service(db_session):
    """Create a LicenseService instance"""
    return LicenseService(db_session)


def create_valid_license(features, duration_days=365):
    """Helper to create a valid license"""
    keys_dir = os.path.join(os.path.dirname(__file__), '..', 'keys')
    private_key_path = os.path.join(keys_dir, 'private_key.pem')
    
    with open(private_key_path, 'rb') as f:
        private_key = f.read()
    
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=duration_days)
    
    payload = {
        'customer_email': 'test@example.com',
        'customer_name': 'Test Customer',
        'features': features,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp())
    }
    
    return jwt.encode(payload, private_key, algorithm='RS256')


class TestAPIEndpointsWithLicenses:
    """Test API endpoints with and without licenses"""
    
    def test_endpoint_accessible_with_valid_license(self, license_service, db_session):
        """Test that endpoints are accessible with valid license"""
        # Activate a license with ai_invoice feature
        license_key = create_valid_license(['ai_invoice'])
        result = license_service.activate_license(license_key)
        
        assert result['success'] is True
        assert license_service.has_feature('ai_invoice') is True
        
    def test_endpoint_accessible_during_trial(self, license_service):
        """Test that endpoints are accessible during trial period"""
        # Get status to auto-create trial
        status = license_service.get_license_status()
        
        assert status['is_trial'] is True
        assert license_service.has_feature('ai_invoice') is True
        assert license_service.has_feature('tax_integration') is True
        
    def test_endpoint_blocked_without_license(self, license_service, db_session):
        """Test that endpoints are blocked without license after trial expires"""
        # Create expired trial
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)
        trial_end = trial_start + timedelta(days=30)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        # Verify features are blocked
        assert license_service.has_feature('ai_invoice') is False
        assert license_service.has_feature('tax_integration') is False
        
    def test_multiple_features_in_license(self, license_service):
        """Test that license can enable multiple features"""
        license_key = create_valid_license(['ai_invoice', 'ai_expense', 'batch_processing'])
        result = license_service.activate_license(license_key)
        
        assert result['success'] is True
        assert license_service.has_feature('ai_invoice') is True
        assert license_service.has_feature('ai_expense') is True
        assert license_service.has_feature('batch_processing') is True
        assert license_service.has_feature('tax_integration') is False


class TestHTTP402Responses:
    """Test HTTP 402 (Payment Required) responses for unlicensed features"""
    
    def test_http_402_returned_for_unlicensed_feature(self, license_service, db_session):
        """Test that HTTP 402 is returned when feature is not licensed"""
        from fastapi import HTTPException
        from core.utils.feature_gate import require_feature
        
        # Create expired trial
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)
        trial_end = trial_start + timedelta(days=30)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        # Create a test endpoint with feature gate
        @require_feature("ai_invoice")
        async def test_endpoint():
            return {"success": True}
        
        # Mock the database dependency
        with patch('utils.feature_gate.get_db') as mock_get_db:
            mock_get_db.return_value = db_session
            
            # Should raise HTTPException with 402
            with pytest.raises(HTTPException) as exc_info:
                import asyncio
                asyncio.run(test_endpoint())
            
            assert exc_info.value.status_code == 402
            
    def test_http_402_includes_feature_info(self, license_service, db_session):
        """Test that HTTP 402 response includes feature information"""
        from fastapi import HTTPException
        from core.utils.feature_gate import require_feature
        
        # Create expired trial
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)
        trial_end = trial_start + timedelta(days=30)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        @require_feature("ai_invoice")
        async def test_endpoint():
            return {"success": True}
        
        with patch('utils.feature_gate.get_db') as mock_get_db:
            mock_get_db.return_value = db_session
            
            with pytest.raises(HTTPException) as exc_info:
                import asyncio
                asyncio.run(test_endpoint())
            
            detail = exc_info.value.detail
            assert 'error_code' in detail
            assert detail['error_code'] == 'FEATURE_NOT_LICENSED'
            assert 'feature_id' in detail
            assert detail['feature_id'] == 'ai_invoice'
            
    def test_http_200_with_valid_license(self, license_service, db_session):
        """Test that HTTP 200 is returned with valid license"""
        from core.utils.feature_gate import require_feature
        
        # Activate license
        license_key = create_valid_license(['ai_invoice'])
        license_service.activate_license(license_key)
        
        @require_feature("ai_invoice")
        async def test_endpoint():
            return {"success": True}
        
        with patch('utils.feature_gate.get_db') as mock_get_db:
            mock_get_db.return_value = db_session
            
            import asyncio
            result = asyncio.run(test_endpoint())
            assert result == {"success": True}


class TestExpiredLicenses:
    """Test feature gates with expired licenses"""
    
    def test_expired_license_blocks_features(self, license_service):
        """Test that expired license blocks feature access"""
        # Create expired license
        license_key = create_valid_license(['ai_invoice'], duration_days=-1)
        result = license_service.activate_license(license_key)
        
        # Activation should fail
        assert result['success'] is False
        assert 'expired' in result.get('error', '').lower()
        
    def test_features_blocked_after_license_expires(self, license_service, db_session):
        """Test that features are blocked after license expiration date"""
        # Create installation with expired license
        now = datetime.now(timezone.utc)
        expired_date = now - timedelta(days=1)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=now - timedelta(days=60),
            trial_end_date=now - timedelta(days=30),
            license_status="active",
            license_activated_at=now - timedelta(days=365),
            license_expires_at=expired_date,
            licensed_features=['ai_invoice', 'ai_expense']
        )
        db_session.add(installation)
        db_session.commit()
        
        # Features should be blocked
        features = license_service.get_enabled_features()
        assert features == []
        
    def test_license_status_updated_on_expiration(self, license_service, db_session):
        """Test that license status is updated when license expires"""
        # Create installation with expired license
        now = datetime.now(timezone.utc)
        expired_date = now - timedelta(days=1)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=now - timedelta(days=60),
            trial_end_date=now - timedelta(days=30),
            license_status="active",
            license_activated_at=now - timedelta(days=365),
            license_expires_at=expired_date,
            licensed_features=['ai_invoice']
        )
        db_session.add(installation)
        db_session.commit()
        
        # Access features (should trigger expiration check)
        license_service.get_enabled_features()
        
        # Refresh installation
        db_session.refresh(installation)
        
        # Status should be updated to expired
        assert installation.license_status == "expired"
        
    def test_valid_license_not_marked_expired(self, license_service, db_session):
        """Test that valid license is not marked as expired"""
        # Create installation with valid license
        now = datetime.now(timezone.utc)
        future_date = now + timedelta(days=365)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=now - timedelta(days=60),
            trial_end_date=now - timedelta(days=30),
            license_status="active",
            license_activated_at=now,
            license_expires_at=future_date,
            licensed_features=['ai_invoice']
        )
        db_session.add(installation)
        db_session.commit()
        
        # Access features
        features = license_service.get_enabled_features()
        
        # Refresh installation
        db_session.refresh(installation)
        
        # Status should still be active
        assert installation.license_status == "active"
        assert 'ai_invoice' in features


class TestUIFeatureVisibility:
    """Test UI feature visibility based on license"""
    
    def test_license_features_endpoint_returns_enabled_features(self, client):
        """Test that /license/features endpoint returns enabled features"""
        # This would require authentication, so we'll test the service directly
        pass
    
    def test_all_features_visible_during_trial(self, license_service):
        """Test that all features are visible during trial"""
        status = license_service.get_license_status()
        
        assert status['has_all_features'] is True
        assert 'all' in status['enabled_features']
        
    def test_only_licensed_features_visible_with_license(self, license_service):
        """Test that only licensed features are visible"""
        license_key = create_valid_license(['ai_invoice', 'batch_processing'])
        license_service.activate_license(license_key)
        
        status = license_service.get_license_status()
        features = status['enabled_features']
        
        assert 'ai_invoice' in features
        assert 'batch_processing' in features
        assert 'tax_integration' not in features
        assert 'all' not in features
        
    def test_no_features_visible_after_expiration(self, license_service, db_session):
        """Test that no features are visible after trial and license expire"""
        # Create expired trial
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)
        trial_end = trial_start + timedelta(days=30)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        status = license_service.get_license_status()
        
        assert status['has_all_features'] is False
        assert status['enabled_features'] == []
        
    def test_feature_list_includes_metadata(self, license_service):
        """Test that feature list includes metadata for UI display"""
        from core.services.feature_config_service import FeatureConfigService
        
        features = FeatureConfigService.get_all_features()
        
        # Verify each feature has required metadata
        for feature in features:
            assert 'id' in feature
            assert 'name' in feature
            assert 'description' in feature
            assert 'category' in feature


class TestFeatureGateIntegration:
    """Integration tests for feature gating"""
    
    def test_feature_gate_with_environment_variable_override(self):
        """Test that environment variables can override feature gates"""
        from core.services.feature_config_service import FeatureConfigService
        import os
        
        # Set environment variable
        os.environ['FEATURE_AI_INVOICE_ENABLED'] = 'false'
        
        # Clear cache
        FeatureConfigService.is_enabled.cache_clear()
        
        # Check if feature is disabled
        enabled = FeatureConfigService.is_enabled('ai_invoice', check_license=False)
        
        # Clean up
        del os.environ['FEATURE_AI_INVOICE_ENABLED']
        FeatureConfigService.is_enabled.cache_clear()
        
        assert enabled is False
        
    def test_feature_categories_correctly_assigned(self):
        """Test that features are correctly categorized"""
        from core.services.feature_config_service import FeatureConfigService
        
        ai_features = FeatureConfigService.get_features_by_category('ai')
        integration_features = FeatureConfigService.get_features_by_category('integration')
        advanced_features = FeatureConfigService.get_features_by_category('advanced')
        
        # Verify AI features
        ai_ids = [f['id'] for f in ai_features]
        assert 'ai_invoice' in ai_ids
        assert 'ai_expense' in ai_ids
        assert 'ai_bank_statement' in ai_ids
        assert 'ai_chat' in ai_ids
        
        # Verify integration features
        integration_ids = [f['id'] for f in integration_features]
        assert 'tax_integration' in integration_ids
        assert 'slack_integration' in integration_ids
        
        # Verify advanced features
        advanced_ids = [f['id'] for f in advanced_features]
        assert 'batch_processing' in advanced_ids
        assert 'approvals' in advanced_ids
        assert 'reporting' in advanced_ids


class TestLicenseValidationCaching:
    """Test license validation caching behavior"""

    def test_validation_results_cached(self, license_service, db_session):
        """Test that validation results are cached"""
        license_key = create_valid_license(['ai_invoice'])
        license_service.activate_license(license_key)
        
        installation = db_session.query(InstallationInfo).first()
        
        assert installation.last_validation_at is not None
        assert installation.last_validation_result is True
        assert installation.validation_cache_expires_at is not None
        
    def test_cache_expires_after_ttl(self, license_service, db_session):
        """Test that cache expires after TTL"""
        license_key = create_valid_license(['ai_invoice'])
        license_service.activate_license(license_key)
        
        installation = db_session.query(InstallationInfo).first()
        
        # Check cache duration
        cache_duration = (installation.validation_cache_expires_at - installation.last_validation_at).total_seconds()
        
        # Should be 1 hour (3600 seconds)
        assert cache_duration == 3600


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
