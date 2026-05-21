from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from core.models import EmailNotificationSettings, User
from core.services.email_service import EmailService, EmailMessage
from core.services.notification_event_info import get_event_info
from core.services.notification_templates import (
    APPROVAL_DIGEST_HTML_TEMPLATE,
    APPROVAL_DIGEST_TEXT_TEMPLATE,
    APPROVAL_ESCALATION_HTML_TEMPLATE,
    APPROVAL_ESCALATION_TEXT_TEMPLATE,
    APPROVAL_REMINDER_HTML_TEMPLATE,
    APPROVAL_REMINDER_TEXT_TEMPLATE,
    OPERATION_HTML_TEMPLATE,
    OPERATION_TEXT_TEMPLATE,
)
import logging
from datetime import datetime, timezone
from config import APP_NAME

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling email notifications for user operations"""
    
    def __init__(self, db: Session, email_service: Optional[EmailService] = None):
        self.db = db
        self.email_service = email_service
    
    def get_user_notification_settings(self, user_id: int) -> Optional[EmailNotificationSettings]:
        """Get notification settings for a user"""
        return self.db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == user_id
        ).first()
    
    def create_default_notification_settings(self, user_id: int) -> EmailNotificationSettings:
        """Create default notification settings for a new user"""
        settings = EmailNotificationSettings(user_id=user_id)
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings
    
    def _get_from_email_info(self, company_name: str) -> tuple[str, str]:
        """Get from_email and from_name from email service config"""
        from_email = "noreply@invoiceapp.com"
        from_name = company_name
        
        if self.email_service and hasattr(self.email_service, 'config'):
            from_email = self.email_service.config.from_email or from_email
            from_name = self.email_service.config.from_name or from_name
        
        return from_email, from_name
    
    def should_send_notification(self, user_id: int, event_type: str, channel: str = "email") -> bool:
        """Check if notification should be sent for a specific event and channel"""
        settings = self.get_user_notification_settings(user_id)
        if not settings:
            settings = self.create_default_notification_settings(user_id)
        
        # Check if the event type is enabled
        if not getattr(settings, event_type, False):
            return False
        
        # For approval events, check frequency and channel preferences
        if event_type.startswith('expense_') or event_type.startswith('approval_'):
            # Check if channel is enabled for approval notifications
            approval_channels = getattr(settings, 'approval_notification_channels', ['email'])
            if channel not in approval_channels:
                return False
            
            # Check frequency for immediate vs digest notifications
            frequency = getattr(settings, 'approval_notification_frequency', 'immediate')
            if frequency == 'daily_digest' and event_type != 'approval_daily_digest':
                # For digest mode, only send digest notifications, not individual ones
                return False
            elif frequency == 'immediate' and event_type == 'approval_daily_digest':
                # For immediate mode, don't send digest notifications
                return False
        
        return True
    
    def send_operation_notification(
        self,
        event_type: str,
        user_id: int,
        resource_type: str,
        resource_id: str,
        resource_name: str,
        details: Dict[str, Any],
        company_name: str = APP_NAME
    ) -> bool:
        """Send notification for a user operation"""
        try:
            # Check if user wants this notification
            if not self.should_send_notification(user_id, event_type):
                return True  # Not an error, just not enabled
            
            # Get user info
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User {user_id} not found for notification")
                return False
            
            # Get notification settings to check for custom email
            settings = self.get_user_notification_settings(user_id)
            notification_email = settings.notification_email if settings else None
            recipient_email = notification_email or user.email
            recipient_name = f"{user.first_name} {user.last_name}".strip() or user.email
            
            # Create email message
            message = self._create_notification_message(
                event_type=event_type,
                resource_type=resource_type,
                resource_name=resource_name,
                details=details,
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                company_name=company_name
            )
            
            # Send email if service is available
            if self.email_service:
                return self.email_service.send_email(message)
            else:
                logger.info(f"Email service not configured, skipping notification")
                return True  # Consider it successful if no email service
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return False
    
    def _create_notification_message(
        self,
        event_type: str,
        resource_type: str,
        resource_name: str,
        details: Dict[str, Any],
        recipient_email: str,
        recipient_name: str,
        company_name: str
    ) -> EmailMessage:
        """Create email message for notification"""
        
        # Get event details
        event_info = get_event_info(event_type, resource_type)
        
        # Create subject
        subject = f"{company_name} - {event_info['title']}: {resource_name}"
        
        # Create HTML template
        html_template = OPERATION_HTML_TEMPLATE
        
        # Create text template
        text_template = OPERATION_TEXT_TEMPLATE
        
        # Render templates
        context = {
            'subject': subject,
            'company_name': company_name,
            'event_title': event_info['title'],
            'event_type': event_type,
            'event_description': event_info['description'],
            'event_color': event_info['color'],
            'resource_type': resource_type,
            'resource_name': resource_name,
            'details': details,
            'recipient_name': recipient_name,
            'timestamp': datetime.now(timezone.utc).strftime('%B %d, %Y at %I:%M %p UTC')
        }
        
        html_body = html_template.render(**context)
        text_body = text_template.render(**context)
        
        # Get from_email and from_name from email service config
        from_email, from_name = self._get_from_email_info(company_name)
        
        return EmailMessage(
            to_email=recipient_email,
            to_name=recipient_name,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=from_email,
            from_name=from_name
        )
    
    def send_daily_summary(self, user_id: int) -> bool:
        """Send daily summary notification"""
        # Implementation for daily summary
        pass
    
    def send_weekly_summary(self, user_id: int) -> bool:
        """Send weekly summary notification"""
        # Implementation for weekly summary
        pass
    
    def send_approval_daily_digest(
        self,
        user_id: int,
        digest_data: Dict[str, Any],
        company_name: str = APP_NAME
    ) -> bool:
        """Send daily digest of approval notifications"""
        try:
            # Check if user wants daily digest notifications
            if not self.should_send_notification(user_id, 'approval_daily_digest', 'email'):
                return True
            
            # Get user info
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User {user_id} not found for daily digest")
                return False
            
            # Get notification settings
            settings = self.get_user_notification_settings(user_id)
            notification_email = settings.notification_email if settings else None
            recipient_email = notification_email or user.email
            recipient_name = f"{user.first_name} {user.last_name}".strip() or user.email
            
            # Create digest message
            message = self._create_approval_digest_message(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                company_name=company_name,
                digest_data=digest_data
            )
            
            # Send email if service is available
            if self.email_service:
                return self.email_service.send_email(message)
            else:
                logger.info(f"Email service not configured, skipping notification")
                return True  # Consider it successful if no email service
            
        except Exception as e:
            logger.error(f"Failed to send approval daily digest: {str(e)}")
            return False
    
    def create_in_app_notification(
        self,
        user_id: int,
        event_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create an in-app notification"""
        try:
            # Check if user wants in-app notifications for this event
            if not self.should_send_notification(user_id, event_type, 'in_app'):
                return True
            
            # For now, we'll just log the in-app notification
            # In a full implementation, this would store in a notifications table
            logger.info(f"In-app notification for user {user_id}: {title} - {message}")
            
            # TODO: Implement actual in-app notification storage
            # This would typically involve:
            # 1. Creating a notification record in the database
            # 2. Sending via WebSocket to connected clients
            # 3. Storing for later retrieval via API
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {str(e)}")
            return False
    
    def send_approval_reminder(
        self,
        approver_id: int,
        pending_approvals: List[Dict[str, Any]],
        company_name: str = APP_NAME
    ) -> bool:
        """Send reminder notification for pending approvals"""
        try:
            if not pending_approvals:
                return True
            
            # Check if user wants reminder notifications
            if not self.should_send_notification(approver_id, 'approval_reminder'):
                return True
            
            # Get user info
            user = self.db.query(User).filter(User.id == approver_id).first()
            if not user:
                logger.error(f"User {approver_id} not found for reminder notification")
                return False
            
            # Get notification settings
            settings = self.get_user_notification_settings(approver_id)
            notification_email = settings.notification_email if settings else None
            recipient_email = notification_email or user.email
            recipient_name = f"{user.first_name} {user.last_name}".strip() or user.email
            
            # Create reminder details
            total_amount = sum(approval.get('amount', 0) for approval in pending_approvals)
            oldest_date = min(approval.get('submitted_at') for approval in pending_approvals if approval.get('submitted_at'))
            
            details = {
                'total_pending': len(pending_approvals),
                'total_amount': f"${total_amount:.2f}",
                'oldest_submission': oldest_date.strftime('%Y-%m-%d %H:%M') if oldest_date else 'N/A',
                'pending_list': ', '.join([
                    f"#{approval.get('expense_id', 'N/A')} ({approval.get('category', 'N/A')})"
                    for approval in pending_approvals[:5]  # Show first 5
                ])
            }
            
            if len(pending_approvals) > 5:
                details['additional_count'] = len(pending_approvals) - 5
            
            # Create email message
            message = self._create_approval_reminder_message(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                company_name=company_name,
                pending_count=len(pending_approvals),
                details=details
            )
            
            # Send email if service is available
            if self.email_service:
                return self.email_service.send_email(message)
            else:
                logger.info(f"Email service not configured, skipping notification")
                return True  # Consider it successful if no email service
            
        except Exception as e:
            logger.error(f"Failed to send approval reminder: {str(e)}")
            return False
    
    def send_approval_escalation(
        self,
        approver_id: int,
        overdue_approvals: List[Dict[str, Any]],
        escalation_recipient_id: int,
        company_name: str = APP_NAME
    ) -> bool:
        """Send escalation notification for overdue approvals"""
        try:
            if not overdue_approvals:
                return True
            
            # Check if escalation recipient wants these notifications
            if not self.should_send_notification(escalation_recipient_id, 'approval_escalation'):
                return True
            
            # Get user info for escalation recipient
            user = self.db.query(User).filter(User.id == escalation_recipient_id).first()
            if not user:
                logger.error(f"Escalation recipient {escalation_recipient_id} not found")
                return False
            
            # Get approver info
            approver = self.db.query(User).filter(User.id == approver_id).first()
            approver_name = f"{approver.first_name} {approver.last_name}".strip() if approver else f"User {approver_id}"
            
            # Get notification settings
            settings = self.get_user_notification_settings(escalation_recipient_id)
            notification_email = settings.notification_email if settings else None
            recipient_email = notification_email or user.email
            recipient_name = f"{user.first_name} {user.last_name}".strip() or user.email
            
            # Create escalation details
            total_amount = sum(approval.get('amount', 0) for approval in overdue_approvals)
            oldest_date = min(approval.get('submitted_at') for approval in overdue_approvals if approval.get('submitted_at'))
            
            details = {
                'approver_name': approver_name,
                'total_overdue': len(overdue_approvals),
                'total_amount': f"${total_amount:.2f}",
                'oldest_submission': oldest_date.strftime('%Y-%m-%d %H:%M') if oldest_date else 'N/A',
                'overdue_list': ', '.join([
                    f"#{approval.get('expense_id', 'N/A')} ({approval.get('category', 'N/A')})"
                    for approval in overdue_approvals[:5]  # Show first 5
                ])
            }
            
            if len(overdue_approvals) > 5:
                details['additional_count'] = len(overdue_approvals) - 5
            
            # Create email message
            message = self._create_approval_escalation_message(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                company_name=company_name,
                overdue_count=len(overdue_approvals),
                details=details
            )
            
            # Send email if service is available
            if self.email_service:
                return self.email_service.send_email(message)
            else:
                logger.info(f"Email service not configured, skipping notification")
                return True  # Consider it successful if no email service
            
        except Exception as e:
            logger.error(f"Failed to send approval escalation: {str(e)}")
            return False
    
    def _create_approval_reminder_message(
        self,
        recipient_email: str,
        recipient_name: str,
        company_name: str,
        pending_count: int,
        details: Dict[str, Any]
    ) -> EmailMessage:
        """Create email message for approval reminder"""
        
        subject = f"{company_name} - You have {pending_count} pending approval{'s' if pending_count != 1 else ''}"
        
        # Create HTML template for reminder
        html_template = APPROVAL_REMINDER_HTML_TEMPLATE
        
        # Create text template for reminder
        text_template = APPROVAL_REMINDER_TEXT_TEMPLATE
        
        # Render templates
        context = {
            'subject': subject,
            'company_name': company_name,
            'recipient_name': recipient_name,
            'pending_count': pending_count,
            'details': details,
            'timestamp': datetime.now(timezone.utc).strftime('%B %d, %Y at %I:%M %p UTC')
        }
        
        html_body = html_template.render(**context)
        text_body = text_template.render(**context)
        
        # Get from_email and from_name from email service config
        from_email, from_name = self._get_from_email_info(company_name)
        
        return EmailMessage(
            to_email=recipient_email,
            to_name=recipient_name,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=from_email,
            from_name=from_name
        )
    
    def _create_approval_escalation_message(
        self,
        recipient_email: str,
        recipient_name: str,
        company_name: str,
        overdue_count: int,
        details: Dict[str, Any]
    ) -> EmailMessage:
        """Create email message for approval escalation"""
        
        subject = f"{company_name} - URGENT: {overdue_count} overdue approval{'s' if overdue_count != 1 else ''} require attention"
        
        # Create HTML template for escalation
        html_template = APPROVAL_ESCALATION_HTML_TEMPLATE
        
        # Create text template for escalation
        text_template = APPROVAL_ESCALATION_TEXT_TEMPLATE
        
        # Render templates
        context = {
            'subject': subject,
            'company_name': company_name,
            'recipient_name': recipient_name,
            'overdue_count': overdue_count,
            'details': details,
            'timestamp': datetime.now(timezone.utc).strftime('%B %d, %Y at %I:%M %p UTC')
        }
        
        html_body = html_template.render(**context)
        text_body = text_template.render(**context)
        
        # Get from_email and from_name from email service config
        from_email, from_name = self._get_from_email_info(company_name)
        
        return EmailMessage(
            to_email=recipient_email,
            to_name=recipient_name,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=from_email,
            from_name=from_name
        )
    
    def _create_approval_digest_message(
        self,
        recipient_email: str,
        recipient_name: str,
        company_name: str,
        digest_data: Dict[str, Any]
    ) -> EmailMessage:
        """Create email message for approval daily digest"""
        
        subject = f"{company_name} - Daily Approval Digest"
        
        # Create HTML template for digest
        html_template = APPROVAL_DIGEST_HTML_TEMPLATE
        
        # Create text template for digest
        text_template = APPROVAL_DIGEST_TEXT_TEMPLATE
        
        # Render templates
        context = {
            'subject': subject,
            'company_name': company_name,
            'recipient_name': recipient_name,
            'digest_data': digest_data,
            'digest_date': datetime.now(timezone.utc).strftime('%B %d, %Y')
        }
        
        html_body = html_template.render(**context)
        text_body = text_template.render(**context)
        
        # Get from_email and from_name from email service config
        from_email, from_name = self._get_from_email_info(company_name)
        
        return EmailMessage(
            to_email=recipient_email,
            to_name=recipient_name,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=from_email,
            from_name=from_name
        )
