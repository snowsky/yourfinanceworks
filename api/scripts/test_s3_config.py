#!/usr/bin/env python3
"""
Test script to verify S3 configuration and connectivity.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the api directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from commercial.cloud_storage.config import get_cloud_storage_config
from commercial.cloud_storage.service import CloudStorageService
from core.models.database import get_db

async def test_s3_configuration():
    """Test S3 configuration and basic operations."""
    
    print("🔧 Testing S3 Configuration...")
    
    try:
        # Get cloud storage configuration
        config = get_cloud_storage_config()
        print(f"✅ Cloud storage config loaded")
        print(f"   Primary provider: {config.PRIMARY_PROVIDER}")
        print(f"   AWS S3 enabled: {config.AWS_S3_ENABLED}")
        print(f"   S3 bucket: {config.AWS_S3_BUCKET_NAME}")
        print(f"   S3 region: {config.AWS_S3_REGION}")
        
        # Validate configuration
        config.validate()
        print("✅ Configuration validation passed")
        
        # Test database connection
        db = next(get_db())
        print("✅ Database connection established")
        
        # Initialize cloud storage service
        cloud_storage_service = CloudStorageService(db, config)
        print("✅ Cloud storage service initialized")
        
        # Test provider health
        health_status = await cloud_storage_service.health_check_all_providers(force_check=True)
        print("🏥 Provider health check results:")
        for provider, health in health_status.items():
            status = "✅ Healthy" if health.healthy else f"❌ Unhealthy: {health.error_message}"
            print(f"   {provider.value}: {status}")
        
        # Test file upload
        test_content = b"Test file content for S3 upload verification"
        test_filename = "test_s3_upload.txt"
        
        print(f"\n📤 Testing file upload...")
        storage_result = await cloud_storage_service.store_file(
            file_content=test_content,
            tenant_id="1",
            item_id=999999,
            attachment_type="test",
            original_filename=test_filename,
            user_id=1,
            metadata={
                'test': True,
                'purpose': 'configuration_verification'
            }
        )
        
        if storage_result.success:
            print(f"✅ File uploaded successfully!")
            print(f"   File key: {storage_result.file_key}")
            print(f"   Provider: {storage_result.provider}")
            print(f"   File size: {storage_result.file_size} bytes")
            
            # Test file retrieval
            print(f"\n📥 Testing file retrieval...")
            retrieve_result = await cloud_storage_service.retrieve_file(
                file_key=storage_result.file_key,
                tenant_id="1",
                user_id=1,
                generate_url=True
            )
            
            if retrieve_result.success:
                print(f"✅ File retrieved successfully!")
                if retrieve_result.file_url:
                    print(f"   Generated URL: {retrieve_result.file_url[:100]}...")
                print(f"   Provider: {retrieve_result.provider}")
            else:
                print(f"❌ File retrieval failed: {retrieve_result.error_message}")
            
            # Clean up test file
            print(f"\n🧹 Cleaning up test file...")
            delete_success = await cloud_storage_service.delete_file(
                file_key=storage_result.file_key,
                tenant_id="1",
                user_id=1
            )
            
            if delete_success:
                print(f"✅ Test file deleted successfully")
            else:
                print(f"⚠️  Failed to delete test file (may need manual cleanup)")
                
        else:
            print(f"❌ File upload failed: {storage_result.error_message}")
            return False
        
        print(f"\n🎉 S3 configuration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ S3 configuration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_s3_configuration())
    sys.exit(0 if success else 1)