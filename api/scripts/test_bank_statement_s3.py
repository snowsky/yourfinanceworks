#!/usr/bin/env python3
"""
Test bank statement S3 upload functionality.
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

from commercial.cloud_storage.service import CloudStorageService
from commercial.cloud_storage.config import get_cloud_storage_config
from core.models.database import get_db

async def test_bank_statement_s3_upload():
    """Test uploading a bank statement to S3."""
    
    print("🧪 Testing Bank Statement S3 Upload")
    print("=" * 50)
    
    try:
        # Get database session
        db = next(get_db())
        
        # Get cloud storage config
        config = get_cloud_storage_config()
        print(f"✅ Cloud Storage Config: {config.PRIMARY_PROVIDER}")
        print(f"✅ S3 Enabled: {config.AWS_S3_ENABLED}")
        print(f"✅ S3 Bucket: {config.AWS_S3_BUCKET_NAME}")
        
        # Initialize cloud storage service
        cloud_storage_service = CloudStorageService(db, config)
        print("✅ Cloud Storage Service initialized")
        
        # Create test file content
        test_content = b"Test bank statement content for S3 upload"
        
        # Generate file key
        client_id = "test-client"
        filename = "test-statement.pdf"
        file_key = f"bank_statements/api/{client_id}/{uuid.uuid4().hex}_{filename}"
        
        print(f"📁 File Key: {file_key}")
        
        # Test upload
        print("🚀 Uploading to S3...")
        storage_result = await cloud_storage_service.store_file(
            file_key=file_key,
            file_content=test_content,
            tenant_id="test-tenant",
            content_type="application/pdf",
            metadata={
                "original_filename": filename,
                "api_client_id": client_id,
                "api_client_name": "Test Client",
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "file_size": len(test_content),
                "document_type": "bank_statement"
            }
        )
        
        if storage_result.success:
            print(f"✅ Upload successful!")
            print(f"   File URL: {storage_result.file_url}")
            print(f"   Storage Provider: {storage_result.provider}")
        else:
            print(f"❌ Upload failed: {storage_result.error}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_bank_statement_s3_upload())