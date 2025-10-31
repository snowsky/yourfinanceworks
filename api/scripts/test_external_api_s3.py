#!/usr/bin/env python3
"""
Test the External API S3 upload by simulating the exact flow.
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

async def test_external_api_s3_flow():
    """Test the exact flow used in External API for S3 upload."""
    
    print("🧪 Testing External API S3 Flow")
    print("=" * 50)
    
    try:
        # Step 1: Set up tenant context (simulate API client)
        print("1. Setting up tenant context...")
        from models.database import set_tenant_context
        
        # Use a test tenant ID
        test_tenant_id = "1"  # This should match your actual tenant
        set_tenant_context(test_tenant_id)
        print(f"   ✅ Tenant context set: {test_tenant_id}")
        
        # Step 2: Get database session
        print("2. Getting database session...")
        from models.database import get_db
        db = next(get_db())
        print("   ✅ Database session obtained")
        
        # Step 3: Initialize cloud storage service
        print("3. Initializing cloud storage service...")
        from services.cloud_storage_service import CloudStorageService
        from settings.cloud_storage_config import get_cloud_storage_config
        
        cloud_config = get_cloud_storage_config()
        cloud_storage_service = CloudStorageService(db, cloud_config)
        print("   ✅ Cloud storage service initialized")
        
        # Step 4: Prepare test data
        print("4. Preparing test data...")
        file_content = b"Test bank statement content for S3 upload"
        safe_filename = "test_statement.pdf"
        client_id = "test-client"
        file_key = f"bank_statements/api/{client_id}/{uuid.uuid4().hex}_{safe_filename}"
        
        print(f"   File key: {file_key}")
        print(f"   File size: {len(file_content)} bytes")
        
        # Step 5: Attempt S3 upload
        print("5. Attempting S3 upload...")
        
        storage_result = await cloud_storage_service.store_file(
            file_content=file_content,
            tenant_id=test_tenant_id,
            item_id=0,  # Use 0 for test
            attachment_type="bank_statements",
            original_filename=safe_filename,
            user_id=0,  # Use 0 for test
            metadata={
                "original_filename": safe_filename,
                "api_client_id": client_id,
                "api_client_name": "Test Client",
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "file_size": len(file_content),
                "document_type": "bank_statement",
                "file_key": file_key
            }
        )
        
        if storage_result.success:
            print(f"   ✅ Upload successful!")
            print(f"   File URL: {storage_result.file_url}")
            print(f"   Provider: {storage_result.provider}")
        else:
            print(f"   ❌ Upload failed: {storage_result.error}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_external_api_s3_flow())