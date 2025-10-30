#!/usr/bin/env python3
"""
Check S3 permissions for the configured IAM user.
"""

import os
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_s3_permissions():
    """Check what S3 permissions the current IAM user has."""
    
    print("🔍 Checking S3 Permissions...")
    
    try:
        # Get AWS credentials
        access_key = os.getenv('AWS_S3_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_S3_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_S3_REGION', 'us-east-1')
        bucket_name = os.getenv('AWS_S3_BUCKET_NAME')
        
        if not all([access_key, secret_key, bucket_name]):
            print("❌ Missing AWS credentials or bucket name")
            return
        
        print(f"AWS Access Key: {access_key}")
        print(f"S3 Bucket: {bucket_name}")
        print(f"Region: {region}")
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        # Create IAM client to check user info
        iam_client = boto3.client(
            'iam',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        # Test different S3 operations
        test_key = "permission-test/test.txt"
        test_content = b"Permission test content"
        
        print(f"\n🧪 Testing S3 Operations:")
        
        # Test 1: List bucket (s3:ListBucket)
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print("✅ s3:HeadBucket - SUCCESS")
        except Exception as e:
            print(f"❌ s3:HeadBucket - FAILED: {str(e)}")
        
        # Test 2: List objects (s3:ListBucket)
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            print("✅ s3:ListBucket - SUCCESS")
        except Exception as e:
            print(f"❌ s3:ListBucket - FAILED: {str(e)}")
        
        # Test 3: Put object (s3:PutObject)
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=test_content,
                ContentType='text/plain'
            )
            print("✅ s3:PutObject - SUCCESS")
            put_success = True
        except Exception as e:
            print(f"❌ s3:PutObject - FAILED: {str(e)}")
            put_success = False
        
        # Test 4: Get object (s3:GetObject) - only if put succeeded
        if put_success:
            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
                content = response['Body'].read()
                if content == test_content:
                    print("✅ s3:GetObject - SUCCESS")
                else:
                    print("❌ s3:GetObject - FAILED: Content mismatch")
            except Exception as e:
                print(f"❌ s3:GetObject - FAILED: {str(e)}")
            
            # Test 5: Delete object (s3:DeleteObject)
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=test_key)
                print("✅ s3:DeleteObject - SUCCESS")
            except Exception as e:
                print(f"❌ s3:DeleteObject - FAILED: {str(e)}")
        
        # Get IAM user info
        try:
            user_info = iam_client.get_user()
            user_name = user_info['User']['UserName']
            user_arn = user_info['User']['Arn']
            print(f"\n👤 IAM User Information:")
            print(f"   User Name: {user_name}")
            print(f"   User ARN: {user_arn}")
            
            # List attached policies
            try:
                policies = iam_client.list_attached_user_policies(UserName=user_name)
                print(f"   Attached Policies:")
                for policy in policies['AttachedPolicies']:
                    print(f"     - {policy['PolicyName']} ({policy['PolicyArn']})")
                
                if not policies['AttachedPolicies']:
                    print("     - No attached policies found")
                    
            except Exception as e:
                print(f"   Could not list policies: {str(e)}")
                
        except Exception as e:
            print(f"\n⚠️  Could not get IAM user info: {str(e)}")
        
        print(f"\n💡 Recommendations:")
        print(f"   1. Ensure the IAM user has the following permissions:")
        print(f"      - s3:ListBucket on arn:aws:s3:::{bucket_name}")
        print(f"      - s3:GetObject on arn:aws:s3:::{bucket_name}/*")
        print(f"      - s3:PutObject on arn:aws:s3:::{bucket_name}/*")
        print(f"      - s3:DeleteObject on arn:aws:s3:::{bucket_name}/*")
        print(f"   2. Apply the IAM policy from s3-iam-policy.json")
        print(f"   3. Wait a few minutes for IAM changes to propagate")
        
    except Exception as e:
        print(f"❌ Permission check failed: {str(e)}")

if __name__ == "__main__":
    check_s3_permissions()