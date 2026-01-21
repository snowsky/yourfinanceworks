#!/usr/bin/env python3
"""
Script to run approval notification processing.

This script can be used to manually trigger approval notification processing
or can be scheduled to run periodically (e.g., via cron job).
"""

import sys
import os
import logging
from datetime import datetime, timezone

# Add the parent directory to the path so we can import from api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from core.models.database import get_database_url, create_engine
from core.services.notification_service import NotificationService
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider
from config import APP_NAME
from commercial.workflows.approvals.services.approval_notification_scheduler import ApprovalNotificationScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_database_session():
    """Create database session."""
    try:
        database_url = get_database_url()
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal()
    except Exception as e:
        logger.error(f"Failed to create database session: {str(e)}")
        return None


def create_email_service():
    """Create email service instance."""
    try:
        # Configure email provider (this would typically come from environment variables)
        config = EmailProviderConfig(
            provider=EmailProvider.AWS_SES,  # or other provider
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            aws_region=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        return EmailService(config)
    except Exception as e:
        logger.error(f"Failed to create email service: {str(e)}")
        return None


def main():
    """Main function to run approval notifications."""
    logger.info("Starting approval notification processing")
    
    # Create database session
    db = create_database_session()
    if not db:
        logger.error("Failed to create database session. Exiting.")
        sys.exit(1)
    
    try:
        # Create email service
        email_service = create_email_service()
        if not email_service:
            logger.warning("Email service not available. Notifications will not be sent.")
            # You might want to exit here or continue with a mock service
            return
        
        # Create notification service
        notification_service = NotificationService(db, email_service)
        
        # Create approval notification scheduler
        scheduler = ApprovalNotificationScheduler(db, notification_service)
        
        # Configure thresholds (optional - can be set via environment variables)
        reminder_threshold = int(os.getenv('APPROVAL_REMINDER_THRESHOLD_HOURS', '24'))
        escalation_threshold = int(os.getenv('APPROVAL_ESCALATION_THRESHOLD_HOURS', '72'))
        reminder_frequency = int(os.getenv('APPROVAL_REMINDER_FREQUENCY_HOURS', '24'))
        
        scheduler.configure_thresholds(
            reminder_threshold_hours=reminder_threshold,
            escalation_threshold_hours=escalation_threshold,
            reminder_frequency_hours=reminder_frequency
        )
        
        logger.info(f"Configured thresholds: reminder={reminder_threshold}h, "
                   f"escalation={escalation_threshold}h, frequency={reminder_frequency}h")
        
        # Get company name from environment or use default
        company_name = os.getenv('COMPANY_NAME', APP_NAME)
        
        # Process all approval notifications
        results = scheduler.process_all_approval_notifications(company_name)
        
        # Log results
        logger.info(f"Notification processing complete:")
        logger.info(f"  Total notifications sent: {results['total_notifications_sent']}")
        logger.info(f"  Reminders sent: {results['reminders']['total_reminders_sent']}")
        logger.info(f"  Approvers notified: {results['reminders']['approvers_notified']}")
        logger.info(f"  Escalations sent: {results['escalations']['total_escalations_sent']}")
        logger.info(f"  Approvers escalated: {results['escalations']['approvers_escalated']}")
        
        if results['errors']:
            logger.warning(f"Errors encountered: {len(results['errors'])}")
            for error in results['errors']:
                logger.warning(f"  - {error}")
        
        # Get summary for monitoring
        summary = scheduler.get_pending_approval_summary()
        logger.info(f"Current pending approval summary:")
        logger.info(f"  Total pending: {summary.get('total_pending', 0)}")
        logger.info(f"  Need reminders: {summary.get('needs_reminder', 0)}")
        logger.info(f"  Need escalation: {summary.get('needs_escalation', 0)}")
        logger.info(f"  Approvers with pending: {summary.get('approvers_with_pending', 0)}")
        
    except Exception as e:
        logger.error(f"Error during notification processing: {str(e)}")
        sys.exit(1)
    
    finally:
        # Close database session
        if db:
            db.close()
    
    logger.info("Approval notification processing completed successfully")


def show_summary_only():
    """Show only the pending approval summary without sending notifications."""
    logger.info("Getting pending approval summary")
    
    # Create database session
    db = create_database_session()
    if not db:
        logger.error("Failed to create database session. Exiting.")
        sys.exit(1)
    
    try:
        # Create a minimal scheduler (no email service needed for summary)
        scheduler = ApprovalNotificationScheduler(db, None)
        
        # Get summary
        summary = scheduler.get_pending_approval_summary()
        
        print("\n" + "="*50)
        print("PENDING APPROVAL SUMMARY")
        print("="*50)
        print(f"Total pending approvals: {summary.get('total_pending', 0)}")
        print(f"Need reminder notifications: {summary.get('needs_reminder', 0)}")
        print(f"Need escalation notifications: {summary.get('needs_escalation', 0)}")
        print(f"Approvers with pending items: {summary.get('approvers_with_pending', 0)}")
        
        thresholds = summary.get('thresholds', {})
        print(f"\nThresholds:")
        print(f"  Reminder threshold: {thresholds.get('reminder_hours', 24)} hours")
        print(f"  Escalation threshold: {thresholds.get('escalation_hours', 72)} hours")
        
        approver_breakdown = summary.get('approver_breakdown', {})
        if approver_breakdown:
            print(f"\nBreakdown by approver:")
            for approver_id, counts in approver_breakdown.items():
                print(f"  Approver {approver_id}: {counts['total']} total, "
                      f"{counts['needs_reminder']} need reminder, "
                      f"{counts['needs_escalation']} need escalation")
        
        print(f"\nGenerated at: {summary.get('generated_at', 'Unknown')}")
        print("="*50)
        
    except Exception as e:
        logger.error(f"Error getting summary: {str(e)}")
        sys.exit(1)
    
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--summary-only":
        show_summary_only()
    else:
        main()