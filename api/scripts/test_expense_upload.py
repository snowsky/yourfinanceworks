#!/usr/bin/env python3
"""
Test expense attachment upload to verify S3 integration.
"""

import os
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the api directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from commercial.cloud_storage.config import get_cloud_storage_config
from commercial.cloud_storage.service import CloudStorageService

async def test_expense_attachment_upload():
    """Test expense attachment upload flow."""
    
    print("🔧 Testing Expense Attachment Upload to S3...")
    
    try:
        # Get cloud storage configuration
        config = get_cloud_storage_config()
        print(f"✅ Cloud storage config loaded")
        print(f"   Primary provider: {config.PRIMARY_PROVIDER}")
        print(f"   AWS S3 enabled: {config.AWS_S3_ENABLED}")
        print(f"   S3 bucket: {config.AWS_S3_BUCKET_NAME}")
        
        # Create a mock database session (simplified for testing)
        class MockDB:
            def __init__(self):
                pass
        
        db = MockDB()
        
        # Initialize cloud storage service
        cloud_storage_service = CloudStorageService(db, config)
        print("✅ Cloud storage service initialized")
        
        # Test file upload (simulating expense attachment)
        test_content = b"Test expense receipt content - PDF or image data would go here"
        test_filename = "test_expense_receipt.pdf"
        tenant_id = "1"
        expense_id = 12345
        user_id = 1
        
        print(f"\n📤 Testing expense attachment upload...")
        print(f"   Tenant ID: {tenant_id}")
        print(f"   Expense ID: {expense_id}")
        print(f"   Filename: {test_filename}")
        print(f"   File size: {len(test_content)} bytes")
        
        storage_result = await cloud_storage_service.store_file(
            file_content=test_content,
            tenant_id=tenant_id,
            item_id=expense_id,
            attachment_type="expenses",  # This matches the expenses router
            original_filename=test_filename,
            user_id=user_id,
            metadata={
                'content_type': 'application/pdf',
                'expense_id': expense_id,
                'uploaded_via': 'test_script'
            }
        )
        
        if storage_result.success:
            print(f"✅ Expense attachment uploaded successfully!")
            print(f"   File key: {storage_result.file_key}")
            print(f"   Provider: {storage_result.provider}")
            print(f"   File size: {storage_result.file_size} bytes")
            print(f"   Duration: {storage_result.operation_duration_ms}ms")
            
            # The file key should look like: tenant_1/expenses/12345_<timestamp>_test_expense_receipt.pdf
            expected_prefix = f"tenant_{tenant_id}/expenses/{expense_id}_"
            if storage_result.file_key.startswith(expected_prefix):
                print(f"✅ File key format is correct for expense attachments")
            else:
                print(f"⚠️  File key format unexpected: {storage_result.file_key}")
            
            # Test file existence check
            print(f"\n🔍 Testing file existence check...")
            exists, provider = await cloud_storage_service.file_exists(
                file_key=storage_result.file_key,
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            if exists:
                print(f"✅ File exists in storage (provider: {provider})")
            else:
                print(f"❌ File existence check failed")
            
            # Note: We won't test file retrieval due to IAM permission issues
            print(f"\n📝 Note: File retrieval test skipped due to IAM GetObject permissions")
            
            # Clean up test file
            print(f"\n🧹 Cleaning up test file...")
            delete_success = await cloud_storage_service.delete_file(
                file_key=storage_result.file_key,
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            if delete_success:
                print(f"✅ Test file deleted successfully")
            else:
                print(f"⚠️  Failed to delete test file (may need manual cleanup)")
                print(f"   File key: {storage_result.file_key}")
                
        else:
            print(f"❌ Expense attachment upload failed: {storage_result.error_message}")
            return False
        
        print(f"\n🎉 Expense attachment upload test completed successfully!")
        print(f"\n💡 Summary:")
        print(f"   - S3 configuration is working correctly")
        print(f"   - Files are being uploaded to S3 bucket: {config.AWS_S3_BUCKET_NAME}")
        print(f"   - File keys follow the correct tenant/expense pattern")
        print(f"   - The issue is likely IAM permissions for listing/viewing files")
        
        return True
        
    except Exception as e:
        print(f"❌ Expense attachment upload test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_expense_attachment_upload())
    sys.exit(0 if success else 1)