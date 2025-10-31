#!/usr/bin/env python3
"""
Debug bank statement upload process to see where S3 upload fails.
"""

import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the API directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def debug_cloud_storage_service():
    """Debug the cloud storage service initialization."""
    
    print("🔍 Debugging Cloud Storage Service Initialization")
    print("=" * 60)
    
    try:
        # Test 1: Import cloud storage service
        print("1. Testing imports...")
        from services.cloud_storage_service import CloudStorageService
        from settings.cloud_storage_config import get_cloud_storage_config
        print("   ✅ Imports successful")
        
        # Test 2: Get configuration
        print("2. Testing configuration...")
        config = get_cloud_storage_config()
        print(f"   ✅ Config loaded: {config.PRIMARY_PROVIDER}")
        print(f"   ✅ S3 Enabled: {config.AWS_S3_ENABLED}")
        print(f"   ✅ S3 Bucket: {config.AWS_S3_BUCKET_NAME}")
        
        # Test 3: Try to initialize service (this is where it might fail)
        print("3. Testing service initialization...")
        
        # We need a database session, but let's try without tenant context first
        try:
            from models.database import get_db
            db = next(get_db())
            print("   ❌ Database requires tenant context")
        except Exception as e:
            print(f"   ❌ Database error (expected): {e}")
        
        # Test 4: Try to initialize service with mock database
        print("4. Testing with mock database...")
        
        # Create a simple mock database session
        class MockDB:
            def query(self, *args):
                return self
            def filter(self, *args):
                return self
            def first(self):
                return None
            def commit(self):
                pass
            def rollback(self):
                pass
        
        mock_db = MockDB()
        
        try:
            service = CloudStorageService(mock_db, config)
            print("   ✅ Service initialized with mock DB")
            
            # Test service status
            status = service.get_service_status()
            print(f"   ✅ Service status: {status}")
            
        except Exception as e:
            print(f"   ❌ Service initialization failed: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

def debug_external_api_flow():
    """Debug the external API flow that should upload to S3."""
    
    print("\n🔍 Debugging External API Flow")
    print("=" * 60)
    
    try:
        # Simulate the external API flow
        print("1. Simulating external API bank statement upload...")
        
        # Test file content
        file_content = b"Test bank statement content for debugging"
        safe_filename = "test_statement.pdf"
        
        print(f"   File size: {len(file_content)} bytes")
        print(f"   Filename: {safe_filename}")
        
        # Test cloud storage import and config
        print("2. Testing cloud storage imports...")
        try:
            from services.cloud_storage_service import CloudStorageService
            from settings.cloud_storage_config import get_cloud_storage_config
            
            cloud_config = get_cloud_storage_config()
            print("   ✅ Cloud storage imports successful")
            print(f"   ✅ Primary provider: {cloud_config.PRIMARY_PROVIDER}")
            
        except ImportError as e:
            print(f"   ❌ Import failed: {e}")
            return
        
        # Test file key generation
        print("3. Testing file key generation...")
        client_id = "test-client"
        file_key = f"bank_statements/api/{client_id}/{uuid.uuid4().hex}_{safe_filename}"
        print(f"   ✅ Generated file key: {file_key}")
        
        # Test metadata creation
        print("4. Testing metadata creation...")
        metadata = {
            "original_filename": safe_filename,
            "api_client_id": client_id,
            "api_client_name": "Test Client",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "file_size": len(file_content),
            "document_type": "bank_statement"
        }
        print(f"   ✅ Metadata created: {len(metadata)} fields")
        
        print("\n💡 The issue is likely in the CloudStorageService initialization")
        print("   which requires proper tenant context and database session.")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main debug function."""
    debug_cloud_storage_service()
    debug_external_api_flow()
    
    print("\n" + "=" * 60)
    print("🎯 LIKELY ISSUE:")
    print("The External API's CloudStorageService initialization fails")
    print("due to tenant context requirements, causing it to fall back")
    print("to local storage instead of uploading to S3.")
    print("\n💡 SOLUTION:")
    print("The External API needs to handle the tenant context properly")
    print("when initializing the CloudStorageService for bank statements.")

if __name__ == "__main__":
    main()