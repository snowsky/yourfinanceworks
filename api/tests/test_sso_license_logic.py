
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from core.models.models import MasterUser, Tenant
from sqlalchemy import text
from commercial.sso.router import router
from main import app
from core.models.database import get_master_db
import config

client = TestClient(app)

@pytest.fixture
def db_session():
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_superuser_and_license_bypass_logic(db_session: Session):
    """
    Test that is_superuser is global while license bypass is per-organization.
    """
    # 1. Clear existing users and tenants for clean test
    db_session.execute(text("DELETE FROM invites"))
    db_session.execute(text("DELETE FROM user_tenant_memberships"))
    db_session.execute(text("DELETE FROM tenant_keys"))
    db_session.query(MasterUser).delete()
    db_session.query(Tenant).delete()
    db_session.commit()

    # Mock settings
    with patch("commercial.sso.router.config.IGNORE_LICENSE_FOR_FIRST_SSO_USER", True), \
         patch("commercial.sso.router.google_oauth_client") as mock_google, \
         patch("commercial.sso.router.check_feature") as mock_check_feature:
        
        # Mock Google OAuth client
        mock_google.get_access_token = AsyncMock(return_value={"access_token": "fake_token"})
        # Mock get_id_email (tuple of id, email, verified)
        mock_google.get_id_email = AsyncMock(return_value=("google_123", "first@example.com", True))
        
        with patch("commercial.sso.router.OAUTH_STATE_STORE", {"test_state": {"ts": 9999999999, "next": "/dashboard"}}):
            
            # --- PHASE 1: First Global User ---
            response = client.get("/api/v1/auth/google/callback?code=fake_code&state=test_state", follow_redirects=False)
            if response.status_code != 307:
                print(f"FAILED Phase 1: {response.status_code} - {response.text}")
            assert response.status_code == 307
            
            # Verify first user is superuser
            user1 = db_session.query(MasterUser).filter(MasterUser.email == "first@example.com").first()
            assert user1 is not None
            assert user1.is_superuser is True
            assert user1.role == "admin"
            
            # Verify check_feature was NOT called (bypass)
            mock_check_feature.assert_not_called()
            mock_check_feature.reset_mock()

            # --- PHASE 2: Second User (New Organization) ---
            # Reset state store for next request
            with patch("commercial.sso.router.OAUTH_STATE_STORE", {"test_state2": {"ts": 9999999999, "next": "/dashboard"}}):
                mock_google.get_id_email.return_value = ("google_456", "second@example.com", True)

                response = client.get("/api/v1/auth/google/callback?code=fake_code2&state=test_state2", follow_redirects=False)

                # WITH THE NEW GATING: The second user should be REJECTED early
                # because they are NOT the global first user and have no invitation.
                assert response.status_code == 307
                assert "error=sso_license_required" in response.headers["Location"]
                
                # Verify second user was NOT created
                user2 = db_session.query(MasterUser).filter(MasterUser.email == "second@example.com").first()
                assert user2 is None
                
                # Verify check_feature was never called because rejection happened before DB creation
                mock_check_feature.assert_not_called()

            # --- PHASE 3: Third User (Joining second org) ---
            # Simulating joining an org (in reality this would be via invite, but let's test gating for existing tenant)
            # Actually, let's just test that check_feature IS called for a subsequent user in an org.
            # (We'd need to mock the tenant DB count > 0)
            
            with patch("commercial.sso.router.OAUTH_STATE_STORE", {"test_state3": {"ts": 9999999999, "next": "/dashboard"}}), \
                 patch("commercial.sso.router.tenant_db_manager.get_tenant_session") as mock_tenant_session:
                
                # Mock tenant DB session to show user_count > 0
                mock_t_db = MagicMock()
                mock_t_db.query().count.return_value = 1 # Already has 1 user
                mock_tenant_session.return_value = MagicMock(return_value=mock_t_db)
                
                mock_google.get_id_email.return_value = ("google_789", "third@example.com", True)
                
                # Mock a valid invite to join user1's tenant
                with patch("commercial.sso.router.check_user_has_valid_invite") as mock_invite:
                    mock_inv = MagicMock()
                    mock_inv.tenant_id = user1.tenant_id
                    mock_inv.role = "user"
                    mock_invite.return_value = mock_inv

                    response = client.get("/api/v1/auth/google/callback?code=fake_code3&state=test_state3", follow_redirects=False)

                    # Verify check_feature WAS called this time
                    mock_check_feature.assert_called_with("sso", mock_t_db)
                    mock_check_feature.reset_mock()

            # --- PHASE 4: Password Registration Gating (New Check) ---
            # Test that a second user registering via password is gated
            from core.schemas.user import UserCreate
            signup_data = {
                "email": "password_user@example.com",
                "password": "Password123!",
                "first_name": "Password",
                "last_name": "User",
                "tenant_id": user1.tenant_id, # Joining first org
                "organization_name": "My Org"
            }
            
            with patch("core.routers.auth.tenant_db_manager.get_tenant_session") as mock_tenant_session_auth:
                # Mock tenant DB session to show user_count = 1
                mock_t_db_auth = MagicMock()
                mock_t_db_auth.query().count.return_value = 1
                mock_tenant_session_auth.return_value = MagicMock(return_value=mock_t_db_auth)
                
                # We need to mock check_feature in core.routers.auth
                with patch("core.routers.auth.check_feature") as mock_check_feature_auth:
                    # In auth.py, we check is_global_first_user which is False now
                    response = client.post("/api/v1/auth/register", json=signup_data)
                    
                    # Verify check_feature WAS called
                    mock_check_feature_auth.assert_called_with("sso", mock_t_db_auth)

    print("\n✅ Superuser and License Bypass Logic test passed!")

if __name__ == "__main__":
    import sys
    # Create a simple wrapper to run the test
    from core.models.database import SessionLocal
    db = SessionLocal()
    try:
        test_superuser_and_license_bypass_logic(db)
    finally:
        db.close()
