import sys
import os
import jwt
from datetime import datetime, timedelta, timezone

# Add api to path
sys.path.insert(0, os.path.join(os.getcwd(), 'api'))

from core.services.license_service import LicenseService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_verification():
    engine = create_engine('sqlite:///:memory:')
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    license_service = LicenseService(db)

    # Load keys
    keys_dir = os.path.join(os.getcwd(), 'api', 'core', 'keys')
    private_key_path = os.path.join(keys_dir, 'private_key.pem')

    with open(private_key_path, 'rb') as f:
        private_key = f.read()

    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=365)

    payload = {
        'customer_email': 'test@example.com',
        'customer_name': 'Test Customer',
        'features': ['ai_invoice'],
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp())
    }

    # Encode with RS256
    token = jwt.encode(payload, private_key, algorithm='RS256')
    print(f"Token: {token[:50]}...")

    # Verify
    result = license_service.verify_license(token)
    print(f"Verification Result: {result}")

if __name__ == '__main__':
    test_verification()
