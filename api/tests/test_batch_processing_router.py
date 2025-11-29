"""
Test script for batch processing router endpoints.

This script tests the batch processing API endpoints to ensure they work correctly.
"""

import sys
import os

# Add the parent directory to the path so we can import from api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app
from core.models.database import get_db, get_master_db
from core.models.models import MasterUser
from core.models.models_per_tenant import User, ExportDestinationConfig
from sqlalchemy.orm import Session
import io

# Create test client
client = TestClient(app)


def get_test_token():
    """Get a test JWT token for authentication."""
    # First, try to login with test user
    response = client.post(
        "/api/v1/auth/jwt/login",
        data={
            "username": "test@example.com",
            "password": "testpassword123"
        }
    )
    
    if response.status_code == 200:
        return response.json()["access_token"]
    
    # If login fails, try to create a test user
    print("Test user not found, attempting to create...")
    
    # Note: This is a simplified test - in production you'd need proper user creation
    return None


def test_list_jobs_endpoint():
    """Test the GET /api/v1/batch-processing/jobs endpoint."""
    print("\n" + "="*80)
    print("TEST: List Batch Jobs")
    print("="*80)
    
    token = get_test_token()
    if not token:
        print("❌ SKIPPED: Could not get authentication token")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test listing jobs
    response = client.get(
        "/api/v1/batch-processing/jobs",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        print("✅ PASSED: List jobs endpoint works correctly")
        return True
    else:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        return False


def test_list_jobs_with_filters():
    """Test the GET /api/v1/batch-processing/jobs endpoint with filters."""
    print("\n" + "="*80)
    print("TEST: List Batch Jobs with Filters")
    print("="*80)
    
    token = get_test_token()
    if not token:
        print("❌ SKIPPED: Could not get authentication token")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test with status filter
    response = client.get(
        "/api/v1/batch-processing/jobs?status_filter=completed&limit=10&offset=0",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0
        print("✅ PASSED: List jobs with filters works correctly")
        return True
    else:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        return False


def test_get_job_status_not_found():
    """Test the GET /api/v1/batch-processing/jobs/{job_id} endpoint with non-existent job."""
    print("\n" + "="*80)
    print("TEST: Get Job Status (Not Found)")
    print("="*80)
    
    token = get_test_token()
    if not token:
        print("❌ SKIPPED: Could not get authentication token")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test with non-existent job ID
    fake_job_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(
        f"/api/v1/batch-processing/jobs/{fake_job_id}",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 404:
        print("✅ PASSED: Returns 404 for non-existent job")
        return True
    else:
        print(f"❌ FAILED: Expected 404, got {response.status_code}")
        return False


def test_upload_batch_validation():
    """Test the POST /api/v1/batch-processing/upload endpoint validation."""
    print("\n" + "="*80)
    print("TEST: Upload Batch Validation")
    print("="*80)
    
    token = get_test_token()
    if not token:
        print("❌ SKIPPED: Could not get authentication token")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test with no files (should fail)
    response = client.post(
        "/api/v1/batch-processing/upload",
        headers=headers,
        data={
            "export_destination_id": "1"
        },
        files=[]
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 422:  # Validation error
        print("✅ PASSED: Validation works correctly (no files)")
        return True
    else:
        print(f"❌ FAILED: Expected 422, got {response.status_code}")
        return False


def test_router_registration():
    """Test that the batch processing router is properly registered."""
    print("\n" + "="*80)
    print("TEST: Router Registration")
    print("="*80)
    
    # Check if routes are registered
    routes = [route.path for route in app.routes]
    
    expected_routes = [
        "/api/v1/batch-processing/upload",
        "/api/v1/batch-processing/jobs/{job_id}",
        "/api/v1/batch-processing/jobs"
    ]
    
    all_registered = True
    for route in expected_routes:
        if route in routes:
            print(f"✅ Route registered: {route}")
        else:
            print(f"❌ Route NOT registered: {route}")
            all_registered = False
    
    if all_registered:
        print("✅ PASSED: All routes are properly registered")
        return True
    else:
        print("❌ FAILED: Some routes are missing")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("BATCH PROCESSING ROUTER TESTS")
    print("="*80)
    
    tests = [
        ("Router Registration", test_router_registration),
        ("List Jobs", test_list_jobs_endpoint),
        ("List Jobs with Filters", test_list_jobs_with_filters),
        ("Get Job Status (Not Found)", test_get_job_status_not_found),
        ("Upload Batch Validation", test_upload_batch_validation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ ERROR in {test_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

