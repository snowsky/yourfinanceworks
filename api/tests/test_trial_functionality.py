#!/usr/bin/env python3
"""
Comprehensive test suite for trial functionality.

Tests:
- 30-day trial auto-activation on first install
- Grace period after trial expiration
- Feature access during trial
- Feature blocking after trial expires
- Requirements: 1.2
"""

import sys
import os
import pytest
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.services.license_service import LicenseService, TRIAL_DURATION_DAYS, GRACE_PERIOD_DAYS
from core.models.models_per_tenant import Base, InstallationInfo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


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


class TestTrialAutoActivation:
    """Test 30-day trial auto-activation on first install"""
    
    def test_trial_auto_created_on_first_access(self, license_service, db_session):
        """Test that trial is automatically created on first access"""
        # Verify no installation exists
        installation = db_session.query(InstallationInfo).first()
        assert installation is None
        
        # Access license service (should auto-create installation)
        status = license_service.get_license_status()
        
        # Verify installation was created
        installation = db_session.query(InstallationInfo).first()
        assert installation is not None
        assert installation.license_status == 'trial'
        
    def test_trial_has_30_day_duration(self, license_service):
        """Test that trial is created with 30-day duration"""
        status = license_service.get_license_status()
        trial_info = status['trial_info']
        
        assert trial_info['is_trial'] is True
        assert trial_info['trial_active'] is True
        assert trial_info['days_remaining'] >= 29  # Allow for timing
        assert trial_info['days_remaining'] <= 30
        
    def test_trial_start_and_end_dates_set(self, license_service, db_session):
        """Test that trial start and end dates are properly set"""
        license_service.get_license_status()
        
        installation = db_session.query(InstallationInfo).first()
        assert installation.trial_start_date is not None
        assert installation.trial_end_date is not None
        
        # Verify end date is ~30 days after start
        duration = (installation.trial_end_date - installation.trial_start_date).days
        assert duration == TRIAL_DURATION_DAYS
        
    def test_installation_id_generated(self, license_service, db_session):
        """Test that unique installation ID is generated"""
        license_service.get_license_status()
        
        installation = db_session.query(InstallationInfo).first()
        assert installation.installation_id is not None
        assert len(installation.installation_id) > 0
        
    def test_trial_only_created_once(self, license_service, db_session):
        """Test that trial is only created once, not on every access"""
        # First access
        status1 = license_service.get_license_status()
        installation1 = db_session.query(InstallationInfo).first()
        installation_id1 = installation1.installation_id
        trial_start1 = installation1.trial_start_date
        
        # Second access
        status2 = license_service.get_license_status()
        installation2 = db_session.query(InstallationInfo).first()
        
        # Should be the same installation
        assert installation2.installation_id == installation_id1
        assert installation2.trial_start_date == trial_start1


class TestGracePeriod:
    """Test grace period after trial expiration"""
    
    def test_grace_period_after_trial_expires(self, license_service, db_session):
        """Test that grace period is active after trial expires"""
        # Create installation with expired trial
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=35)  # Started 35 days ago
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)  # Ended 5 days ago
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        # Check trial status
        trial_status = license_service.get_trial_status()
        
        assert trial_status['trial_active'] is False
        assert trial_status['in_grace_period'] is True
        assert trial_status['grace_period_end'] is not None
        
    def test_grace_period_duration_is_7_days(self, license_service, db_session):
        """Test that grace period lasts 7 days"""
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=31)
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        trial_status = license_service.get_trial_status()
        grace_end = trial_status['grace_period_end']
        
        # Grace period should end 7 days after trial end
        expected_grace_end = trial_end + timedelta(days=GRACE_PERIOD_DAYS)
        
        # Allow 1 second tolerance for timing
        time_diff = abs((grace_end - expected_grace_end).total_seconds())
        assert time_diff < 1
        
    def test_no_grace_period_during_active_trial(self, license_service):
        """Test that grace period is not active during trial"""
        trial_status = license_service.get_trial_status()
        
        assert trial_status['trial_active'] is True
        assert trial_status['in_grace_period'] is False
        assert trial_status['grace_period_end'] is None
        
    def test_no_grace_period_after_grace_expires(self, license_service, db_session):
        """Test that grace period ends after 7 days"""
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)  # Started 40 days ago
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)  # Ended 10 days ago
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        trial_status = license_service.get_trial_status()
        
        assert trial_status['trial_active'] is False
        assert trial_status['in_grace_period'] is False


class TestFeatureAccessDuringTrial:
    """Test feature access during trial"""
    
    def test_all_features_available_during_trial(self, license_service):
        """Test that all features are available during active trial"""
        features = license_service.get_enabled_features()
        
        assert "all" in features
        
    def test_has_feature_returns_true_during_trial(self, license_service):
        """Test that has_feature returns True for any feature during trial"""
        assert license_service.has_feature("ai_invoice") is True
        assert license_service.has_feature("ai_expense") is True
        assert license_service.has_feature("tax_integration") is True
        assert license_service.has_feature("slack_integration") is True
        assert license_service.has_feature("batch_processing") is True
        assert license_service.has_feature("inventory") is True
        assert license_service.has_feature("approvals") is True
        assert license_service.has_feature("reporting") is True
        
    def test_all_features_available_during_grace_period(self, license_service, db_session):
        """Test that all features remain available during grace period"""
        # Create installation with expired trial (in grace period)
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=35)
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        features = license_service.get_enabled_features()
        
        assert "all" in features
        assert license_service.has_feature("ai_invoice") is True
        
    def test_license_status_shows_trial_info(self, license_service):
        """Test that license status includes trial information"""
        status = license_service.get_license_status()
        
        assert status['is_trial'] is True
        assert status['is_licensed'] is False
        assert status['has_all_features'] is True
        assert 'trial_info' in status
        assert status['trial_info']['trial_active'] is True


class TestFeatureBlockingAfterTrialExpires:
    """Test feature blocking after trial expires"""
    
    def test_no_features_after_grace_period_expires(self, license_service, db_session):
        """Test that no features are available after grace period expires"""
        # Create installation with expired trial and grace period
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        features = license_service.get_enabled_features()
        
        assert features == []
        assert "all" not in features
        
    def test_has_feature_returns_false_after_expiration(self, license_service, db_session):
        """Test that has_feature returns False after trial and grace expire"""
        # Create installation with expired trial and grace period
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        assert license_service.has_feature("ai_invoice") is False
        assert license_service.has_feature("ai_expense") is False
        assert license_service.has_feature("tax_integration") is False
        
    def test_trial_status_shows_expired(self, license_service, db_session):
        """Test that trial status correctly shows as expired"""
        # Create installation with expired trial and grace period
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        trial_status = license_service.get_trial_status()
        
        assert trial_status['trial_active'] is False
        assert trial_status['days_remaining'] == 0
        assert trial_status['in_grace_period'] is False
        
    def test_license_activation_restores_features(self, license_service, db_session):
        """Test that activating a license restores features after trial expires"""
        import jwt
        
        # Create installation with expired trial
        now = datetime.now(timezone.utc)
        trial_start = now - timedelta(days=40)
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
        
        installation = InstallationInfo(
            installation_id="test-123",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            license_status="trial"
        )
        db_session.add(installation)
        db_session.commit()
        
        # Verify no features available
        assert license_service.get_enabled_features() == []
        
        # Create and activate a license
        keys_dir = os.path.join(os.path.dirname(__file__), '..', 'keys')
        private_key_path = os.path.join(keys_dir, 'private_key.pem')
        
        with open(private_key_path, 'rb') as f:
            private_key = f.read()
        
        exp = now + timedelta(days=365)
        payload = {
            'customer_email': 'test@example.com',
            'customer_name': 'Test Customer',
            'features': ['ai_invoice', 'ai_expense'],
            'iat': int(now.timestamp()),
            'exp': int(exp.timestamp())
        }
        
        license_key = jwt.encode(payload, private_key, algorithm='RS256')
        
        result = license_service.activate_license(license_key)
        assert result['success'] is True
        
        # Verify features are now available
        features = license_service.get_enabled_features()
        assert 'ai_invoice' in features
        assert 'ai_expense' in features


class TestTrialExtension:
    """Test trial extension functionality"""
    
    def test_trial_can_be_extended(self, license_service, db_session):
        """Test that trial can be extended beyond 30 days"""
        # Create installation
        license_service.get_license_status()
        
        installation = db_session.query(InstallationInfo).first()
        
        # Extend trial by 30 days
        now = datetime.now(timezone.utc)
        extended_until = now + timedelta(days=60)
        installation.trial_extended_until = extended_until
        db_session.commit()
        
        # Verify trial is still active
        assert license_service.is_trial_active() is True
        
        trial_status = license_service.get_trial_status()
        assert trial_status['trial_active'] is True
        assert trial_status['days_remaining'] >= 59
        
    def test_extended_trial_provides_all_features(self, license_service, db_session):
        """Test that extended trial still provides all features"""
        license_service.get_license_status()
        
        installation = db_session.query(InstallationInfo).first()
        
        # Extend trial
        now = datetime.now(timezone.utc)
        extended_until = now + timedelta(days=60)
        installation.trial_extended_until = extended_until
        db_session.commit()
        
        features = license_service.get_enabled_features()
        assert "all" in features


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
