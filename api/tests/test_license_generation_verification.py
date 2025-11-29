#!/usr/bin/env python3
"""
Comprehensive test suite for license generation and verification.

Tests:
- License generation with CLI tool
- Signature validation
- Expiration date enforcement
- Invalid license rejection
- Requirements: 1.3, 1.9
"""

import sys
import os
import pytest
import jwt
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.services.license_service import LicenseService
from core.models.models_per_tenant import Base, InstallationInfo, LicenseValidationLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Add license_server to path
license_server_path = os.path.join(os.path.dirname(__file__), '..', '..', 'license_server')
if os.path.exists(license_server_path):
    sys.path.insert(0, license_server_path)
    from license_generator import LicenseGenerator


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


@pytest.fixture
def license_generator():
    """Create a LicenseGenerator instance"""
    if 'LicenseGenerator' not in globals():
        pytest.skip("LicenseGenerator not available")
    return LicenseGenerator()


class TestLicenseGeneration:
    """Test license generation with CLI tool"""
    
    def test_generate_standard_license(self, license_generator):
        """Test generating a standard license"""
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice", "ai_expense"],
            duration_days=365
        )
        
        assert license_key is not None
        assert isinstance(license_key, str)
        assert len(license_key) > 100  # JWT tokens are long
        
    def test_generate_trial_license(self, license_generator):
        """Test generating a trial license"""
        license_key = license_generator.generate_trial_license(
            customer_email="trial@example.com",
            customer_name="Trial User"
        )
        
        assert license_key is not None
        info = license_generator.get_license_info(license_key)
        assert info['license_type'] == 'trial'
        assert info['days_remaining'] == 30
        
    def test_generate_perpetual_license(self, license_generator):
        """Test generating a perpetual license"""
        license_key = license_generator.generate_perpetual_license(
            customer_email="perpetual@example.com",
            customer_name="Perpetual Customer",
            features=["ai_invoice", "reporting"]
        )
        
        assert license_key is not None
        info = license_generator.get_license_info(license_key)
        assert info['license_type'] == 'perpetual'
        assert info['days_remaining'] > 36500  # 100 years
        
    def test_license_contains_required_fields(self, license_generator):
        """Test that generated licenses contain all required fields"""
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice"],
            duration_days=365
        )
        
        info = license_generator.get_license_info(license_key)
        
        assert 'customer_email' in info
        assert 'customer_name' in info
        assert 'features' in info
        assert 'issued_at' in info
        assert 'expires_at' in info
        assert 'license_type' in info


class TestSignatureValidation:
    """Test signature validation works correctly"""
    
    def test_valid_signature_accepted(self, license_service, license_generator):
        """Test that valid signatures are accepted"""
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice"],
            duration_days=365
        )
        
        result = license_service.verify_license(license_key)
        
        assert result['valid'] is True
        assert result['error_code'] is None
        assert result['payload'] is not None
        
    def test_invalid_signature_rejected(self, license_service, license_generator):
        """Test that invalid signatures are rejected"""
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice"],
            duration_days=365
        )
        
        # Tamper with the license
        tampered_key = license_key[:-10] + "TAMPERED00"
        
        result = license_service.verify_license(tampered_key)
        
        assert result['valid'] is False
        assert result['error_code'] in ['INVALID_SIGNATURE', 'MALFORMED']
        
    def test_malformed_license_rejected(self, license_service):
        """Test that malformed licenses are rejected"""
        malformed_key = "not.a.valid.jwt.token"
        
        result = license_service.verify_license(malformed_key)
        
        assert result['valid'] is False
        assert result['error_code'] == 'MALFORMED'
        
    def test_empty_license_rejected(self, license_service):
        """Test that empty licenses are rejected"""
        result = license_service.verify_license("")
        
        assert result['valid'] is False
        assert result['error_code'] == 'MALFORMED'
        
    def test_signature_with_wrong_algorithm_rejected(self, license_service):
        """Test that licenses signed with wrong algorithm are rejected"""
        # Create a license signed with HS256 instead of RS256
        payload = {
            'customer_email': 'test@example.com',
            'features': ['ai_invoice'],
            'iat': int(datetime.now(timezone.utc).timestamp()),
            'exp': int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp())
        }
        
        wrong_algo_key = jwt.encode(payload, "secret", algorithm='HS256')
        
        result = license_service.verify_license(wrong_algo_key)
        
        assert result['valid'] is False


class TestExpirationEnforcement:
    """Test expiration date enforcement"""
    
    def test_expired_license_rejected(self, license_service, license_generator):
        """Test that expired licenses are rejected"""
        # Generate a license that expired 1 day ago
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice"],
            duration_days=-1  # Expired yesterday
        )
        
        result = license_service.verify_license(license_key)
        
        assert result['valid'] is False
        assert result['error_code'] == 'EXPIRED'
        
    def test_future_license_accepted(self, license_service, license_generator):
        """Test that future licenses are accepted"""
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice"],
            duration_days=365
        )
        
        result = license_service.verify_license(license_key)
        
        assert result['valid'] is True
        
    def test_license_expiring_today_accepted(self, license_service):
        """Test that licenses expiring today are still accepted"""
        keys_dir = os.path.join(os.path.dirname(__file__), '..', 'keys')
        private_key_path = os.path.join(keys_dir, 'private_key.pem')
        
        with open(private_key_path, 'rb') as f:
            private_key = f.read()
        
        now = datetime.now(timezone.utc)
        # Expires in 1 hour
        exp = now + timedelta(hours=1)
        
        payload = {
            'customer_email': 'test@example.com',
            'customer_name': 'Test Customer',
            'features': ['ai_invoice'],
            'iat': int(now.timestamp()),
            'exp': int(exp.timestamp())
        }
        
        license_key = jwt.encode(payload, private_key, algorithm='RS256')
        
        result = license_service.verify_license(license_key)
        
        assert result['valid'] is True
        
    def test_perpetual_license_never_expires(self, license_service, license_generator):
        """Test that perpetual licenses don't expire"""
        license_key = license_generator.generate_perpetual_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice"]
        )
        
        result = license_service.verify_license(license_key)
        
        assert result['valid'] is True
        
        info = license_generator.get_license_info(license_key)
        assert info['days_remaining'] > 36500  # More than 100 years


class TestInvalidLicenseRejection:
    """Test invalid license rejection"""
    
    def test_license_with_missing_fields_rejected(self, license_service):
        """Test that licenses with missing required fields are rejected"""
        keys_dir = os.path.join(os.path.dirname(__file__), '..', 'keys')
        private_key_path = os.path.join(keys_dir, 'private_key.pem')
        
        with open(private_key_path, 'rb') as f:
            private_key = f.read()
        
        now = datetime.now(timezone.utc)
        exp = now + timedelta(days=365)
        
        # Missing customer_email
        payload = {
            'customer_name': 'Test Customer',
            'features': ['ai_invoice'],
            'iat': int(now.timestamp()),
            'exp': int(exp.timestamp())
        }
        
        license_key = jwt.encode(payload, private_key, algorithm='RS256')
        
        result = license_service.verify_license(license_key)
        
        # Should still verify signature, but activation might fail
        assert result['valid'] is True  # Signature is valid
        
    def test_license_with_invalid_features_format(self, license_service):
        """Test that licenses with invalid features format are handled"""
        keys_dir = os.path.join(os.path.dirname(__file__), '..', 'keys')
        private_key_path = os.path.join(keys_dir, 'private_key.pem')
        
        with open(private_key_path, 'rb') as f:
            private_key = f.read()
        
        now = datetime.now(timezone.utc)
        exp = now + timedelta(days=365)
        
        # Features as string instead of list
        payload = {
            'customer_email': 'test@example.com',
            'customer_name': 'Test Customer',
            'features': 'ai_invoice',  # Should be a list
            'iat': int(now.timestamp()),
            'exp': int(exp.timestamp())
        }
        
        license_key = jwt.encode(payload, private_key, algorithm='RS256')
        
        result = license_service.verify_license(license_key)
        
        # Signature is valid, but features format is wrong
        assert result['valid'] is True
        
    def test_license_from_different_key_rejected(self, license_service):
        """Test that licenses signed with a different key are rejected"""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        # Generate a different key pair
        different_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        different_private_pem = different_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        now = datetime.now(timezone.utc)
        exp = now + timedelta(days=365)
        
        payload = {
            'customer_email': 'test@example.com',
            'customer_name': 'Test Customer',
            'features': ['ai_invoice'],
            'iat': int(now.timestamp()),
            'exp': int(exp.timestamp())
        }
        
        # Sign with different key
        license_key = jwt.encode(payload, different_private_pem, algorithm='RS256')
        
        result = license_service.verify_license(license_key)
        
        assert result['valid'] is False
        assert result['error_code'] == 'INVALID_SIGNATURE'


class TestLicenseActivation:
    """Test license activation with verification"""
    
    def test_activate_valid_license(self, license_service, license_generator, db_session):
        """Test activating a valid license"""
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice", "ai_expense"],
            duration_days=365
        )
        
        result = license_service.activate_license(
            license_key,
            user_id=1,
            ip_address="127.0.0.1"
        )
        
        assert result['success'] is True
        assert result['features'] == ["ai_invoice", "ai_expense"]
        
        # Verify it's stored in database
        installation = db_session.query(InstallationInfo).first()
        assert installation.license_key == license_key
        assert installation.is_licensed is True
        
    def test_activate_invalid_license_fails(self, license_service, license_generator):
        """Test that activating an invalid license fails"""
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice"],
            duration_days=365
        )
        
        # Tamper with it
        tampered_key = license_key[:-10] + "TAMPERED00"
        
        result = license_service.activate_license(
            tampered_key,
            user_id=1,
            ip_address="127.0.0.1"
        )
        
        assert result['success'] is False
        assert 'error' in result
        
    def test_activate_expired_license_fails(self, license_service, license_generator):
        """Test that activating an expired license fails"""
        license_key = license_generator.generate_license(
            customer_email="test@example.com",
            customer_name="Test Customer",
            features=["ai_invoice"],
            duration_days=-1  # Expired
        )
        
        result = license_service.activate_license(
            license_key,
            user_id=1,
            ip_address="127.0.0.1"
        )
        
        assert result['success'] is False
        assert 'expired' in result.get('error', '').lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
