"""
Simple verification test for batch processing router.

This script verifies that the batch processing router is properly integrated
without requiring authentication.
"""

import sys
import os

# Add the parent directory to the path so we can import from api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from commercial.batch_processing import router as batch_processing


def test_router_exists():
    """Test that the batch_processing router module exists and is imported."""
    print("\n" + "="*80)
    print("TEST: Router Module Import")
    print("="*80)
    
    try:
        assert batch_processing is not None
        assert hasattr(batch_processing, 'router')
        print("✅ PASSED: batch_processing router module imported successfully")
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False


def test_router_has_endpoints():
    """Test that the router has the expected endpoints."""
    print("\n" + "="*80)
    print("TEST: Router Endpoints")
    print("="*80)
    
    try:
        router = batch_processing.router
        routes = [route.path for route in router.routes]
        
        expected_endpoints = [
            "/upload",
            "/jobs/{job_id}",
            "/jobs"
        ]
        
        all_found = True
        for endpoint in expected_endpoints:
            if endpoint in routes:
                print(f"✅ Endpoint found: {endpoint}")
            else:
                print(f"❌ Endpoint NOT found: {endpoint}")
                all_found = False
        
        if all_found:
            print("✅ PASSED: All expected endpoints are defined")
            return True
        else:
            print("❌ FAILED: Some endpoints are missing")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_app_routes_registered():
    """Test that routes are registered in the FastAPI app."""
    print("\n" + "="*80)
    print("TEST: App Routes Registration")
    print("="*80)
    
    try:
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
            print("✅ PASSED: All routes are properly registered in app")
            return True
        else:
            print("❌ FAILED: Some routes are not registered")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_endpoint_methods():
    """Test that endpoints have the correct HTTP methods."""
    print("\n" + "="*80)
    print("TEST: Endpoint HTTP Methods")
    print("="*80)
    
    try:
        routes_dict = {}
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                routes_dict[route.path] = list(route.methods)
        
        expected_methods = {
            "/api/v1/batch-processing/upload": ["POST"],
            "/api/v1/batch-processing/jobs/{job_id}": ["GET"],
            "/api/v1/batch-processing/jobs": ["GET"]
        }
        
        all_correct = True
        for path, expected in expected_methods.items():
            if path in routes_dict:
                actual = routes_dict[path]
                if set(expected).issubset(set(actual)):
                    print(f"✅ {path}: {expected} ✓")
                else:
                    print(f"❌ {path}: Expected {expected}, got {actual}")
                    all_correct = False
            else:
                print(f"❌ {path}: Route not found")
                all_correct = False
        
        if all_correct:
            print("✅ PASSED: All endpoints have correct HTTP methods")
            return True
        else:
            print("❌ FAILED: Some endpoints have incorrect methods")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_service_dependency():
    """Test that the BatchProcessingService dependency is available."""
    print("\n" + "="*80)
    print("TEST: Service Dependency")
    print("="*80)
    
    try:
        from commercial.batch_processing.service import BatchProcessingService
        assert BatchProcessingService is not None
        print("✅ BatchProcessingService is available")
        
        # Check if the service has required methods
        required_methods = [
            'create_batch_job',
            'enqueue_files_to_kafka',
            'get_job_status',
            'process_file_completion'
        ]
        
        all_methods_exist = True
        for method in required_methods:
            if hasattr(BatchProcessingService, method):
                print(f"✅ Method exists: {method}")
            else:
                print(f"❌ Method missing: {method}")
                all_methods_exist = False
        
        if all_methods_exist:
            print("✅ PASSED: BatchProcessingService has all required methods")
            return True
        else:
            print("❌ FAILED: Some methods are missing")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_models_exist():
    """Test that the required models exist."""
    print("\n" + "="*80)
    print("TEST: Database Models")
    print("="*80)
    
    try:
        from core.models.models_per_tenant import (
            BatchProcessingJob,
            BatchFileProcessing,
            ExportDestinationConfig
        )
        
        models = [
            ("BatchProcessingJob", BatchProcessingJob),
            ("BatchFileProcessing", BatchFileProcessing),
            ("ExportDestinationConfig", ExportDestinationConfig)
        ]
        
        all_exist = True
        for name, model in models:
            if model is not None:
                print(f"✅ Model exists: {name}")
            else:
                print(f"❌ Model missing: {name}")
                all_exist = False
        
        if all_exist:
            print("✅ PASSED: All required models exist")
            return True
        else:
            print("❌ FAILED: Some models are missing")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("\n" + "="*80)
    print("BATCH PROCESSING ROUTER VERIFICATION")
    print("="*80)
    
    tests = [
        ("Router Module Import", test_router_exists),
        ("Router Endpoints", test_router_has_endpoints),
        ("App Routes Registration", test_app_routes_registered),
        ("Endpoint HTTP Methods", test_endpoint_methods),
        ("Service Dependency", test_service_dependency),
        ("Database Models", test_models_exist),
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
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All verification tests passed!")
        print("\nThe batch processing router is properly implemented and integrated.")
        print("\nImplemented endpoints:")
        print("  - POST   /api/v1/batch-processing/upload")
        print("  - GET    /api/v1/batch-processing/jobs/{job_id}")
        print("  - GET    /api/v1/batch-processing/jobs")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

