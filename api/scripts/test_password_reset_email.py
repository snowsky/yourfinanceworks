#!/usr/bin/env python3
"""
Test script for password reset email functionality
"""

import requests
import json
import sys
import os
from datetime import datetime, timezone

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000/api/v1"

def test_password_reset_email_flow():
    """Test the complete password reset email flow"""
    
    print("Testing password reset email functionality...")
    print("=" * 70)
    
    # First, we need to create a test user and configure email settings
    print("\n1. Setting up test environment...")
    
    # Create a test user (if not exists)
    print("   Creating test user...")
    try:
        signup_response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": "test.user@example.com",
                "password": "testpassword123",
                "first_name": "Test",
                "last_name": "User",
                "organization_name": "Test Organization"
            }
        )
        
        if signup_response.status_code == 200:
            print("   ✅ Test user created successfully")
            signup_data = signup_response.json()
            test_token = signup_data.get("access_token")
        else:
            print("   ℹ️  Test user may already exist, trying login...")
            login_response = requests.post(
                f"{BASE_URL}/auth/login",
                json={
                    "email": "test.user@example.com",
                    "password": "testpassword123"
                }
            )
            
            if login_response.status_code == 200:
                print("   ✅ Test user logged in successfully")
                login_data = login_response.json()
                test_token = login_data.get("access_token")
            else:
                print("   ❌ Failed to create or login test user")
                return
                
    except Exception as e:
        print(f"   ❌ Error setting up test user: {e}")
        return
    
    # Configure email settings for the test tenant
    print("   Configuring email settings...")
    try:
        email_config = {
            "provider": "aws_ses",
            "from_name": "Test Invoice App",
            "from_email": "noreply@testinvoiceapp.com",
            "enabled": True,
            "aws_access_key_id": "test_key",
            "aws_secret_access_key": "test_secret",
            "aws_region": "us-east-1"
        }
        
        email_config_response = requests.put(
            f"{BASE_URL}/email/config",
            json=email_config,
            headers={"Authorization": f"Bearer {test_token}"}
        )
        
        if email_config_response.status_code == 200:
            print("   ✅ Email configuration set successfully")
        else:
            print("   ⚠️  Email configuration may have failed, but continuing test...")
            
    except Exception as e:
        print(f"   ⚠️  Error configuring email settings: {e}")
        print("   Continuing with test...")
    
    # Test 1: Request password reset for existing user
    print("\n2. Testing password reset request with email integration...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/request-password-reset",
            json={"email": "test.user@example.com"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Password reset request successful")
            print(f"   Message: {data.get('message')}")
            print(f"   Success: {data.get('success')}")
            print("   📧 Check the API logs for email sending status")
        else:
            print(f"   ❌ Password reset request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error during password reset request: {e}")
    
    # Test 2: Test email service availability
    print("\n3. Testing email service configuration...")
    try:
        config_response = requests.get(
            f"{BASE_URL}/email/config",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        
        if config_response.status_code == 200:
            config_data = config_response.json()
            print(f"   ✅ Email service configured")
            print(f"   Provider: {config_data.get('provider')}")
            print(f"   Enabled: {config_data.get('enabled')}")
            print(f"   From: {config_data.get('from_name')} <{config_data.get('from_email')}>")
        else:
            print(f"   ❌ Email service not configured: {config_response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error checking email service: {e}")
    
    # Test 3: Test with non-existing user (should still return success)
    print("\n4. Testing password reset for non-existing user...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/request-password-reset",
            json={"email": "nonexistent@example.com"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Non-existing user handled correctly (prevents email enumeration)")
            print(f"   Message: {data.get('message')}")
            print(f"   Success: {data.get('success')}")
        else:
            print(f"   ❌ Non-existing user request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error during non-existing user test: {e}")
    
    # Test 4: Test email template rendering
    print("\n5. Testing email template rendering...")
    try:
        # Import and test email service directly
        from services.email_service import EmailService, EmailProviderConfig, EmailProvider
        
        # Create a test email service
        config = EmailProviderConfig(
            provider=EmailProvider.AWS_SES,
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
            aws_region="us-east-1"
        )
        
        email_service = EmailService(config)
        
        # Test email message creation
        message = email_service._create_password_reset_message(
            user_email="test@example.com",
            user_name="Test User",
            reset_token="test-token-123",
            company_name="Test Company",
            from_name="Test App",
            from_email="noreply@testapp.com"
        )
        
        print(f"   ✅ Email template rendered successfully")
        print(f"   Subject: {message.subject}")
        print(f"   From: {message.from_name} <{message.from_email}>")
        print(f"   To: {message.to_name} <{message.to_email}>")
        print(f"   HTML body length: {len(message.html_body)} characters")
        print(f"   Text body length: {len(message.text_body)} characters")
        
    except Exception as e:
        print(f"   ❌ Error testing email template: {e}")
    
    print("\n" + "=" * 70)
    print("Password reset email testing completed!")
    print("\n📝 Notes:")
    print("- Check the API logs for actual email sending attempts")
    print("- Configure a real email provider in settings to send actual emails")
    print("- Email templates include both HTML and plain text versions")
    print("- Password reset links expire in 1 hour for security")

if __name__ == "__main__":
    test_password_reset_email_flow() 