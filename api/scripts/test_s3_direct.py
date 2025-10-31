#!/usr/bin/env python3
"""
Test S3 upload directly without database dependencies.
"""

import os
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_s3_direct():
    """Test S3 upload directly."""
    
    print("🧪 Testing Direct S3 Upload")
    print("=" * 40)
    
    # Get S3 configuration
    bucket_name = os.getenv('AWS_S3_BUCKET_NAME')
    access_key = os.getenv('AWS_S3_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_S3_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_S3_REGION', 'us-east-1')
    
    print(f"Bucket: {bucket_name}")
    print(f"Region: {region}")
    print(f"Access Key: {access_key[:10]}..." if access_key else "None")
    
    if not all([bucket_name, access_key, secret_key]):
        print("❌ Missing S3 configuration")
        return
    
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        # Test file
        test_key = "test/bank_statement_test.txt"
        test_content = b"Test bank statement content"
        
        print(f"🚀 Uploading test file: {test_key}")
        
        # Upload test file
        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content,
            ContentType='text/plain',
            Metadata={
                'test': 'true',
                'document_type': 'bank_statement'
            }
        )
        
        print("✅ Upload successful!")
        
        # List files to verify
        print("📋 Files in bucket:")
        response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=10)
        
        if 'Contents' in response:
            for obj in response['Contents']:
                print(f"  - {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("  No files found")
            
    except Exception as e:
        print(f"❌ S3 test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_s3_direct()