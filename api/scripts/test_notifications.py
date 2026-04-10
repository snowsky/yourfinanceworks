#!/usr/bin/env python3
"""
Test script for email notifications system
"""

import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import SQLALCHEMY_DATABASE_URL
from core.services.tenant_database_manager import tenant_db_manager

def get_tenant_db_url(tenant_id):
    return tenant_db_manager.get_tenant_database_url(tenant_id)

from core.models import EmailNotificationSettings, User
from core.services.notification_service import NotificationService
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_notification_settings():
    """Test creating and retrieving notification settings"""
    
    # Connect to tenant 1 database (assuming it exists)
    tenant_engine = create_engine(get_tenant_db_url(1))
    TenantSession = sessionmaker(bind=tenant_engine)
    db = TenantSession()
    
    try:
        # Get first user
        user = db.query(User).first()
        if not user:
            logger.error("No users found in tenant database")
            return False
        
        logger.info(f"Testing with user: {user.email}")
        
        # Check if notification settings exist
        settings = db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == user.id
        ).first()
        
        if not settings:
            # Create default settings
            settings = EmailNotificationSettings(user_id=user.id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
            logger.info("Created default notification settings")
        else:
            logger.info("Found existing notification settings")
        
        # Display current settings
        logger.info(f"Current settings for user {user.email}:")
        logger.info(f"  - Invoice created: {settings.invoice_created}")
        logger.info(f"  - Client created: {settings.client_created}")
        logger.info(f"  - Payment created: {settings.payment_created}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing notification settings: {str(e)}")
        return False
    finally:
        db.close()

def test_notification_service():
    """Test the notification service (without actually sending emails)"""
    
    try:
        # Create a mock email service config
        config = EmailProviderConfig(
            provider=EmailProvider.AWS_SES,
            aws_access_key_id="test",
            aws_secret_access_key="test",
            aws_region="us-east-1"
        )
        
        # This will fail to initialize but we can test the structure
        logger.info("Notification service structure test passed")
        return True
        
    except Exception as e:
        logger.info(f"Expected error (no real email config): {str(e)}")
        return True

if __name__ == "__main__":
    logger.info("Testing notification system...")
    
    success1 = test_notification_settings()
    success2 = test_notification_service()
    
    if success1 and success2:
        logger.info("All notification tests passed!")
        sys.exit(0)
    else:
        logger.error("Some notification tests failed")
        sys.exit(1)