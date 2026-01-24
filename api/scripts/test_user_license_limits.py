#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models.models import Base, MasterUser, Tenant, GlobalInstallationInfo
from core.services.license_service import LicenseService

def create_test_license(max_users, features=["all"]):
    """Create a test license key"""
    private_key_path = '/app/core/keys/private_key.pem'
    if not os.path.exists(private_key_path):
        # Fallback for local run
        keys_dir = os.path.join(os.path.dirname(__file__), '..', 'core', 'keys')
        private_key_path = os.path.join(keys_dir, 'private_key.pem')
    
    with open(private_key_path, 'rb') as f:
        private_key = f.read()
    
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=365)
    
    payload = {
        'customer_email': 'test@example.com',
        'customer_name': 'Test Customer',
        'organization_name': 'Test Org',
        'features': features,
        'max_users': max_users,
        'installation_id': 'test-installation-id',
        'license_scope': 'global',
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp())
    }
    
    return jwt.encode(payload, private_key, algorithm='RS256')

def test_user_license_limits():
    """Test user level license limits and exemptions"""
    print("="*70)
    print("Testing User-Level License Limits")
    print("="*70)
    
    # Create in-memory database
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Setup Service
        service = LicenseService(db, master_db=db)
        
        # 2. Activate Global License with max_users=2
        print("\n[Step 1] Activating global license with max_users=2")
        
        # Ensure installation ID matches
        global_info = db.query(GlobalInstallationInfo).first()
        if not global_info:
            global_info = GlobalInstallationInfo(installation_id='test-installation-id')
            db.add(global_info)
        else:
            global_info.installation_id = 'test-installation-id'
        db.commit()
        
        license_key = create_test_license(max_users=2)
        activation = service.activate_global_license(license_key)
        if not activation.get('success'):
            print(f"Activation failure: {activation}")
        assert activation['success'] == True
        
        status = service.get_license_status()
        assert status['user_licensing_info']['max_users'] == 2
        print("✓ License activated with limit: 2 users")
        
        # 3. Create users and check counts
        print("\n[Step 2] Creating users")
        def create_user(email, id):
            user = MasterUser(
                id=id,
                email=email,
                hashed_password="hash",
                first_name="Test",
                last_name=str(id),
                role="user",
                tenant_id=1,
                is_verified=True
            )
            db.add(user)
            db.commit()
            return user

        u1 = create_user("u1@test.com", 1)
        u2 = create_user("u2@test.com", 2)
        
        count = service.get_current_user_count()
        print(f"Current user count: {count}")
        assert count == 2
        print("✓ Created 2 users, count is 2")
        
        # 4. Verify limit enforcement Simulation
        # (We simulation the router check here since we are testing the service layer + logic)
        print("\n[Step 3] Verifying limit check logic")
        status = service.get_license_status()
        info = status['user_licensing_info']
        can_add = info['current_users_count'] < info['max_users']
        print(f"Can add more users? {can_add}")
        assert can_add == False
        print("✓ Limit correctly detected")
        
        # 5. Exempt a user
        print("\n[Step 4] Exempting a user")
        success = service.update_user_capacity_control(u1.id, False)
        assert success == True
        
        count = service.get_current_user_count()
        print(f"Current user count after exemption: {count}")
        assert count == 1
        print("✓ User 1 exempted, count is now 1")
        
        # 6. Verify we can add another user now
        print("\n[Step 5] Re-verifying limit check logic")
        status = service.get_license_status()
        info = status['user_licensing_info']
        can_add = info['current_users_count'] < info['max_users']
        print(f"Can add more users? {can_add}")
        assert can_add == True
        print("✓ Can add more users after exemption")
        
        print("\n" + "="*70)
        print("✅ User-Level License Limit tests passed!")
        print("="*70)
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == '__main__':
    success = test_user_license_limits()
    exit(0 if success else 1)
