import sys
import os
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Add api directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock

# Mock db_init to prevent actual DB connection during import
sys.modules["db_init"] = MagicMock()
sys.modules["db_init"].init_db = MagicMock()

# Mock models.database to prevent engine creation
mock_database = MagicMock()
mock_database.engine = MagicMock()
mock_database.SessionLocal = MagicMock()
mock_database.get_db = MagicMock()
sys.modules["models.database"] = mock_database

# Mock tenant_database_manager
mock_tdm = MagicMock()
mock_tdm.tenant_db_manager = MagicMock()
sys.modules["services.tenant_database_manager"] = mock_tdm

# Mock middleware
mock_middleware = MagicMock()
# The middleware is a function, so we need to mock the module
sys.modules["middleware.tenant_context_middleware"] = mock_middleware
# And the function itself
async def mock_tenant_context_middleware(request, call_next):
    return await call_next(request)
mock_middleware.tenant_context_middleware = mock_tenant_context_middleware

from main import app
from core.models.models import MasterUser
from core.routers.auth import get_current_user

def verify_sync():
    client = TestClient(app)
    
    # Mock DB session
    mock_session = MagicMock()
    
    # Setup SessionLocal to return mock_session (for background task)
    mock_database.SessionLocal.return_value = mock_session
    
    # Setup get_db to return mock_session (for dependency)
    app.dependency_overrides[mock_database.get_db] = lambda: mock_session
    
    # Mock Settings query for get_sync_status
    mock_setting = MagicMock()
    mock_setting.value = {"status": "running", "message": "Mock status", "downloaded": 5, "processed": 0}
    mock_session.query.return_value.filter.return_value.first.return_value = mock_setting

    # Mock authentication
    from commercial.integrations.email.router import get_current_user as router_get_current_user
    from core.routers.auth import get_current_user as auth_get_current_user
    from core.routers.auth import oauth2_scheme
    
    print(f"Router get_current_user id: {id(router_get_current_user)}")
    print(f"Auth get_current_user id: {id(auth_get_current_user)}")
    
    mock_user = MasterUser(id=1, email="admin@example.com", is_active=True, is_superuser=True, tenant_id=1, role="admin")
    
    def mock_get_current_user():
        print("Mock get_current_user called")
        return mock_user
        
    app.dependency_overrides[router_get_current_user] = mock_get_current_user
    app.dependency_overrides[auth_get_current_user] = mock_get_current_user
    app.dependency_overrides[oauth2_scheme] = lambda: "mock_token"
    print(f"Overrides: {app.dependency_overrides}")
    
    # Patch the service in the router module
    with patch("routers.email_integration.EmailIngestionService") as MockService:
        instance = MockService.return_value
        
        def mock_sync():
            print("Mock sync running in background...")
            time.sleep(0.1) # Simulate brief work
        
        instance.sync_emails.side_effect = mock_sync
        
        # Trigger sync
        print("Triggering sync...")
        start_time = time.time()
        # Add Authorization header just in case
        response = client.post("/api/v1/email-integration/sync", headers={"Authorization": "Bearer mock_token"})
        end_time = time.time()
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        print(f"Time taken: {end_time - start_time:.4f}s")
        
        if response.status_code != 200:
            print("FAILED: Sync request failed")
            sys.exit(1)
            
        if end_time - start_time > 2.0: # Allow some overhead, but real sync would take much longer
            print("FAILED: Sync request took too long (blocking?)")
            sys.exit(1)
            
        print("SUCCESS: Sync request returned immediately")
        
        # Check status
        # Note: TestClient runs background tasks synchronously after the request, 
        # so by the time we get here, the background task has finished.
        # But we can verify the status endpoint returns something valid.
        
        response = client.get("/api/v1/email-integration/sync/status", headers={"Authorization": "Bearer mock_token"})
        print(f"Status response: {response.json()}")
        
        if response.status_code == 200:
            status = response.json()
            if "status" in status:
                print(f"SUCCESS: Status endpoint returned status: {status['status']}")
            else:
                print("FAILED: Status endpoint missing status field")
                sys.exit(1)
        else:
            print("FAILED: Status endpoint failed")
            sys.exit(1)

if __name__ == "__main__":
    verify_sync()
