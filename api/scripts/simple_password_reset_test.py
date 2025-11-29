#!/usr/bin/env python3
"""
Simple test for password reset email functionality
"""

import requests
import sys
import os

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000/api/v1"

def test_password_reset_simple():
    """Simple test of password reset functionality"""
    
    print("Testing password reset email integration...")
    print("=" * 50)
    
    # Test 1: Request password reset
    print("\n1. Testing password reset request...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/request-password-reset",
            json={"email": "test.user@example.com"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Password reset request successful")
            print(f"   Message: {data.get('message')}")
            print(f"   Success: {data.get('success')}")
            
            # Check API logs for email status
            print("\n📧 Email Status:")
            print("   Check the API container logs for email sending attempts:")
            print("   docker-compose logs api | grep -i 'password reset'")
            
        else:
            print(f"❌ Password reset request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during password reset request: {e}")
    
    # Test 2: Test email template creation
    print("\n2. Testing email template creation...")
    try:
        from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider
        
        # Create test configuration
        config = EmailProviderConfig(
            provider=EmailProvider.AWS_SES,
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
            aws_region="us-east-1"
        )
        
        email_service = EmailService(config)
        
        # Test message creation
        message = email_service._create_password_reset_message(
            user_email="test@example.com",
            user_name="Test User",
            reset_token="test-token-123",
            company_name="Test Company",
            from_name="Test App",
            from_email="noreply@testapp.com"
        )
        
        print(f"✅ Email message created successfully")
        print(f"   Subject: {message.subject}")
        print(f"   From: {message.from_name} <{message.from_email}>")
        print(f"   To: {message.to_name} <{message.to_email}>")
        
        # Check if reset URL is in the message
        reset_url = "http://localhost:8080/reset-password?token=test-token-123"
        if reset_url in message.html_body:
            print(f"✅ Reset URL correctly included in HTML body")
        else:
            print(f"❌ Reset URL not found in HTML body")
            
        if reset_url in message.text_body:
            print(f"✅ Reset URL correctly included in text body")
        else:
            print(f"❌ Reset URL not found in text body")
            
    except Exception as e:
        print(f"❌ Error testing email template: {e}")
    
    # Test 3: Test with non-existing user
    print("\n3. Testing with non-existing user...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/request-password-reset",
            json={"email": "nonexistent@example.com"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Non-existing user handled correctly")
            print(f"   Message: {data.get('message')}")
            print(f"   Success: {data.get('success')}")
        else:
            print(f"❌ Non-existing user request failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing non-existing user: {e}")
    
    # Test 4: Test invalid email format
    print("\n4. Testing invalid email format...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/request-password-reset",
            json={"email": "invalid-email"}
        )
        
        if response.status_code == 422:
            print(f"✅ Invalid email format properly rejected")
        else:
            print(f"❌ Expected 422 for invalid email, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing invalid email: {e}")
    
    print("\n" + "=" * 50)
    print("Password reset email integration test completed!")
    print("\n📝 Important Notes:")
    print("1. Check API logs for actual email sending attempts")
    print("2. Configure real email provider credentials in tenant settings")
    print("3. Email templates support both HTML and plain text")
    print("4. Password reset tokens expire in 1 hour")
    print("5. Reset URLs point to: http://localhost:8080/reset-password?token=...")
    
    print("\n🔧 To configure email service:")
    print("1. Login to your application")
    print("2. Go to Settings → Email Settings")
    print("3. Enable email service and configure your provider")
    print("4. Test the configuration")

if __name__ == "__main__":
    test_password_reset_simple() 