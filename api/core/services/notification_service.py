from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from core.models.models_per_tenant import EmailNotificationSettings, User
from core.services.email_service import EmailService, EmailMessage
from jinja2 import Template
import logging
from datetime import datetime, timezone

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
        company_name: str = "Invoice Management System"
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
        event_info = self._get_event_info(event_type, resource_type)
        
        # Create subject
        subject = f"{company_name} - {event_info['title']}: {resource_name}"
        
        # Create HTML template
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ subject }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #f0f0f0;
                }
                .logo {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .title {
                    color: #333;
                    font-size: 20px;
                    margin-bottom: 10px;
                }
                .event-badge {
                    display: inline-block;
                    background-color: {{ event_color }};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                .content {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .details {
                    background-color: #f8f9fa;
                    border-left: 4px solid {{ event_color }};
                    padding: 15px;
                    margin: 20px 0;
                }
                .details-title {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .detail-item {
                    margin: 5px 0;
                    font-size: 14px;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 14px;
                    text-align: center;
                }
                .timestamp {
                    color: #999;
                    font-size: 12px;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{{ company_name }}</div>
                    <h1 class="title">{{ event_title }}</h1>
                    <span class="event-badge">{{ event_type.replace('_', ' ').title() }}</span>
                </div>
                
                <div class="content">
                    <p>Hello {{ recipient_name }},</p>
                    <p>{{ event_description }}</p>
                </div>
                
                <div class="details">
                    <div class="details-title">Details:</div>
                    <div class="detail-item"><strong>{{ resource_type.title() }}:</strong> {{ resource_name }}</div>
                    {% for key, value in details.items() %}
                    <div class="detail-item"><strong>{{ key.replace('_', ' ').title() }}:</strong> {{ value }}</div>
                    {% endfor %}
                    <div class="timestamp">{{ timestamp }}</div>
                </div>
                
                <div class="footer">
                    <p>This is an automated notification from {{ company_name }}.</p>
                    <p>You can manage your notification preferences in your account settings.</p>
                </div>
            </div>
        </body>
        </html>
        """)
        
        # Create text template
        text_template = Template("""
        {{ company_name }} - {{ event_title }}
        
        Hello {{ recipient_name }},
        
        {{ event_description }}
        
        Details:
        {{ resource_type.title() }}: {{ resource_name }}
        {% for key, value in details.items() %}
        {{ key.replace('_', ' ').title() }}: {{ value }}
        {% endfor %}
        
        Timestamp: {{ timestamp }}
        
        This is an automated notification from {{ company_name }}.
        You can manage your notification preferences in your account settings.
        """)
        
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
    
    def _get_event_info(self, event_type: str, resource_type: str) -> Dict[str, str]:
        """Get event information for notification"""
        event_map = {
            # User events
            'user_created': {
                'title': 'New User Created',
                'description': 'A new user has been added to your organization.',
                'color': '#28a745'
            },
            'user_updated': {
                'title': 'User Updated',
                'description': 'A user\'s information has been updated.',
                'color': '#ffc107'
            },
            'user_deleted': {
                'title': 'User Deleted',
                'description': 'A user has been removed from your organization.',
                'color': '#dc3545'
            },
            'user_login': {
                'title': 'User Login',
                'description': 'A user has logged into the system.',
                'color': '#17a2b8'
            },
            
            # Client events
            'client_created': {
                'title': 'New Client Added',
                'description': 'A new client has been added to your system.',
                'color': '#28a745'
            },
            'client_updated': {
                'title': 'Client Updated',
                'description': 'A client\'s information has been updated.',
                'color': '#ffc107'
            },
            'client_deleted': {
                'title': 'Client Deleted',
                'description': 'A client has been removed from your system.',
                'color': '#dc3545'
            },
            
            # Invoice events
            'invoice_created': {
                'title': 'New Invoice Created',
                'description': 'A new invoice has been created.',
                'color': '#28a745'
            },
            'invoice_updated': {
                'title': 'Invoice Updated',
                'description': 'An invoice has been updated.',
                'color': '#ffc107'
            },
            'invoice_deleted': {
                'title': 'Invoice Deleted',
                'description': 'An invoice has been deleted.',
                'color': '#dc3545'
            },
            'invoice_sent': {
                'title': 'Invoice Sent',
                'description': 'An invoice has been sent to a client.',
                'color': '#17a2b8'
            },
            'invoice_paid': {
                'title': 'Invoice Paid',
                'description': 'An invoice has been marked as paid.',
                'color': '#28a745'
            },
            'invoice_overdue': {
                'title': 'Invoice Overdue',
                'description': 'An invoice is now overdue.',
                'color': '#dc3545'
            },
            
            # Payment events
            'payment_created': {
                'title': 'Payment Recorded',
                'description': 'A new payment has been recorded.',
                'color': '#28a745'
            },
            'payment_updated': {
                'title': 'Payment Updated',
                'description': 'A payment has been updated.',
                'color': '#ffc107'
            },
            'payment_deleted': {
                'title': 'Payment Deleted',
                'description': 'A payment has been deleted.',
                'color': '#dc3545'
            },
            
            # Settings events
            'settings_updated': {
                'title': 'Settings Updated',
                'description': 'System settings have been updated.',
                'color': '#6f42c1'
            },
            
            # Approval events
            'expense_submitted_for_approval': {
                'title': 'Expense Submitted for Approval',
                'description': 'An expense has been submitted and requires your approval.',
                'color': '#ffc107'
            },
            'expense_approved': {
                'title': 'Expense Approved',
                'description': 'Your expense has been approved.',
                'color': '#28a745'
            },
            'expense_rejected': {
                'title': 'Expense Rejected',
                'description': 'Your expense has been rejected and requires attention.',
                'color': '#dc3545'
            },
            'expense_level_approved': {
                'title': 'Expense Level Approved',
                'description': 'Your expense has been approved at one level and is proceeding to the next approval level.',
                'color': '#17a2b8'
            },
            'expense_fully_approved': {
                'title': 'Expense Fully Approved',
                'description': 'Your expense has been fully approved and is ready for reimbursement.',
                'color': '#28a745'
            },
            'expense_auto_approved': {
                'title': 'Expense Auto-Approved',
                'description': 'Your expense has been automatically approved based on company policies.',
                'color': '#28a745'
            },
            'approval_reminder': {
                'title': 'Approval Reminder',
                'description': 'You have pending expense approvals that require your attention.',
                'color': '#fd7e14'
            },
            'approval_escalation': {
                'title': 'Approval Escalation',
                'description': 'An expense approval is overdue and requires immediate attention.',
                'color': '#dc3545'
            }
        }
        
        return event_map.get(event_type, {
            'title': f'{resource_type.title()} {event_type.replace("_", " ").title()}',
            'description': f'A {resource_type} operation has occurred.',
            'color': '#6c757d'
        })
    
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
        company_name: str = "Invoice Management System"
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
        company_name: str = "Invoice Management System"
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
        company_name: str = "Invoice Management System"
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
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ subject }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #f0f0f0;
                }
                .logo {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .title {
                    color: #333;
                    font-size: 20px;
                    margin-bottom: 10px;
                }
                .reminder-badge {
                    display: inline-block;
                    background-color: #fd7e14;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                .content {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .summary-box {
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                }
                .summary-item {
                    display: flex;
                    justify-content: space-between;
                    margin: 10px 0;
                    font-size: 16px;
                }
                .summary-label {
                    font-weight: bold;
                    color: #333;
                }
                .summary-value {
                    color: #666;
                }
                .pending-list {
                    background-color: #f8f9fa;
                    border-left: 4px solid #fd7e14;
                    padding: 15px;
                    margin: 20px 0;
                }
                .pending-title {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .action-button {
                    display: inline-block;
                    background-color: #fd7e14;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-align: center;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 14px;
                    text-align: center;
                }
                .timestamp {
                    color: #999;
                    font-size: 12px;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{{ company_name }}</div>
                    <h1 class="title">Pending Approvals Reminder</h1>
                    <span class="reminder-badge">Action Required</span>
                </div>
                
                <div class="content">
                    <p>Hello {{ recipient_name }},</p>
                    <p>You have <strong>{{ pending_count }}</strong> expense approval{{ 's' if pending_count != 1 else '' }} waiting for your review.</p>
                </div>
                
                <div class="summary-box">
                    <div class="summary-item">
                        <span class="summary-label">Total Pending:</span>
                        <span class="summary-value">{{ details.total_pending }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Total Amount:</span>
                        <span class="summary-value">{{ details.total_amount }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Oldest Submission:</span>
                        <span class="summary-value">{{ details.oldest_submission }}</span>
                    </div>
                </div>
                
                <div class="pending-list">
                    <div class="pending-title">Pending Expenses:</div>
                    <div>{{ details.pending_list }}</div>
                    {% if details.additional_count %}
                    <div style="margin-top: 10px; font-style: italic;">
                        ... and {{ details.additional_count }} more
                    </div>
                    {% endif %}
                </div>
                
                <div style="text-align: center;">
                    <a href="#" class="action-button">Review Pending Approvals</a>
                </div>
                
                <div class="footer">
                    <p>This is an automated reminder from {{ company_name }}.</p>
                    <p>You can manage your notification preferences in your account settings.</p>
                    <div class="timestamp">{{ timestamp }}</div>
                </div>
            </div>
        </body>
        </html>
        """)
        
        # Create text template for reminder
        text_template = Template("""
        {{ company_name }} - Pending Approvals Reminder
        
        Hello {{ recipient_name }},
        
        You have {{ pending_count }} expense approval{{ 's' if pending_count != 1 else '' }} waiting for your review.
        
        Summary:
        - Total Pending: {{ details.total_pending }}
        - Total Amount: {{ details.total_amount }}
        - Oldest Submission: {{ details.oldest_submission }}
        
        Pending Expenses:
        {{ details.pending_list }}
        {% if details.additional_count %}
        ... and {{ details.additional_count }} more
        {% endif %}
        
        Please log in to review and approve these expenses.
        
        Timestamp: {{ timestamp }}
        
        This is an automated reminder from {{ company_name }}.
        You can manage your notification preferences in your account settings.
        """)
        
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
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ subject }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #f0f0f0;
                }
                .logo {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .title {
                    color: #dc3545;
                    font-size: 20px;
                    margin-bottom: 10px;
                }
                .urgent-badge {
                    display: inline-block;
                    background-color: #dc3545;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.7; }
                    100% { opacity: 1; }
                }
                .content {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .alert-box {
                    background-color: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                }
                .summary-item {
                    display: flex;
                    justify-content: space-between;
                    margin: 10px 0;
                    font-size: 16px;
                }
                .summary-label {
                    font-weight: bold;
                    color: #333;
                }
                .summary-value {
                    color: #666;
                }
                .overdue-list {
                    background-color: #f8f9fa;
                    border-left: 4px solid #dc3545;
                    padding: 15px;
                    margin: 20px 0;
                }
                .overdue-title {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .action-button {
                    display: inline-block;
                    background-color: #dc3545;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-align: center;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 14px;
                    text-align: center;
                }
                .timestamp {
                    color: #999;
                    font-size: 12px;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{{ company_name }}</div>
                    <h1 class="title">Overdue Approvals Escalation</h1>
                    <span class="urgent-badge">URGENT</span>
                </div>
                
                <div class="content">
                    <p>Hello {{ recipient_name }},</p>
                    <p><strong>{{ details.approver_name }}</strong> has <strong>{{ overdue_count }}</strong> overdue expense approval{{ 's' if overdue_count != 1 else '' }} that require immediate attention.</p>
                    <p>These approvals have exceeded the expected response time and may be impacting employee reimbursements.</p>
                </div>
                
                <div class="alert-box">
                    <div class="summary-item">
                        <span class="summary-label">Approver:</span>
                        <span class="summary-value">{{ details.approver_name }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Total Overdue:</span>
                        <span class="summary-value">{{ details.total_overdue }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Total Amount:</span>
                        <span class="summary-value">{{ details.total_amount }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Oldest Submission:</span>
                        <span class="summary-value">{{ details.oldest_submission }}</span>
                    </div>
                </div>
                
                <div class="overdue-list">
                    <div class="overdue-title">Overdue Expenses:</div>
                    <div>{{ details.overdue_list }}</div>
                    {% if details.additional_count %}
                    <div style="margin-top: 10px; font-style: italic;">
                        ... and {{ details.additional_count }} more
                    </div>
                    {% endif %}
                </div>
                
                <div style="text-align: center;">
                    <a href="#" class="action-button">Take Action</a>
                </div>
                
                <div class="footer">
                    <p>This is an automated escalation from {{ company_name }}.</p>
                    <p>Please follow up with the approver or take appropriate action to resolve these overdue approvals.</p>
                    <div class="timestamp">{{ timestamp }}</div>
                </div>
            </div>
        </body>
        </html>
        """)
        
        # Create text template for escalation
        text_template = Template("""
        {{ company_name }} - URGENT: Overdue Approvals Escalation
        
        Hello {{ recipient_name }},
        
        {{ details.approver_name }} has {{ overdue_count }} overdue expense approval{{ 's' if overdue_count != 1 else '' }} that require immediate attention.
        
        These approvals have exceeded the expected response time and may be impacting employee reimbursements.
        
        Details:
        - Approver: {{ details.approver_name }}
        - Total Overdue: {{ details.total_overdue }}
        - Total Amount: {{ details.total_amount }}
        - Oldest Submission: {{ details.oldest_submission }}
        
        Overdue Expenses:
        {{ details.overdue_list }}
        {% if details.additional_count %}
        ... and {{ details.additional_count }} more
        {% endif %}
        
        Please follow up with the approver or take appropriate action to resolve these overdue approvals.
        
        Timestamp: {{ timestamp }}
        
        This is an automated escalation from {{ company_name }}.
        """)
        
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
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ subject }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #f0f0f0;
                }
                .logo {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .title {
                    color: #333;
                    font-size: 20px;
                    margin-bottom: 10px;
                }
                .digest-badge {
                    display: inline-block;
                    background-color: #17a2b8;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                .content {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .digest-section {
                    margin: 20px 0;
                    padding: 15px;
                    border-left: 4px solid #17a2b8;
                    background-color: #f8f9fa;
                }
                .section-title {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                    font-size: 16px;
                }
                .digest-item {
                    margin: 8px 0;
                    padding: 8px;
                    background-color: white;
                    border-radius: 4px;
                    border-left: 3px solid #28a745;
                }
                .digest-item.rejected {
                    border-left-color: #dc3545;
                }
                .digest-item.pending {
                    border-left-color: #ffc107;
                }
                .item-title {
                    font-weight: bold;
                    color: #333;
                }
                .item-details {
                    font-size: 14px;
                    color: #666;
                    margin-top: 4px;
                }
                .summary-stats {
                    display: flex;
                    justify-content: space-around;
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #e9ecef;
                    border-radius: 8px;
                }
                .stat-item {
                    text-align: center;
                }
                .stat-number {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                }
                .stat-label {
                    font-size: 12px;
                    color: #666;
                    text-transform: uppercase;
                }
                .action-button {
                    display: inline-block;
                    background-color: #17a2b8;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-align: center;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 14px;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{{ company_name }}</div>
                    <h1 class="title">Daily Approval Digest</h1>
                    <span class="digest-badge">{{ digest_date }}</span>
                </div>
                
                <div class="content">
                    <p>Hello {{ recipient_name }},</p>
                    <p>Here's your daily summary of approval activities:</p>
                </div>
                
                <div class="summary-stats">
                    <div class="stat-item">
                        <div class="stat-number">{{ digest_data.total_events or 0 }}</div>
                        <div class="stat-label">Total Events</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{{ digest_data.pending_count or 0 }}</div>
                        <div class="stat-label">Pending</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{{ digest_data.approved_count or 0 }}</div>
                        <div class="stat-label">Approved</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{{ digest_data.rejected_count or 0 }}</div>
                        <div class="stat-label">Rejected</div>
                    </div>
                </div>
                
                {% if digest_data.pending_approvals %}
                <div class="digest-section">
                    <div class="section-title">Pending Approvals</div>
                    {% for approval in digest_data.pending_approvals %}
                    <div class="digest-item pending">
                        <div class="item-title">Expense #{{ approval.expense_id }} - {{ approval.category }}</div>
                        <div class="item-details">
                            Amount: ${{ approval.amount }} | Submitted: {{ approval.submitted_at }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if digest_data.approved_expenses %}
                <div class="digest-section">
                    <div class="section-title">Recently Approved</div>
                    {% for expense in digest_data.approved_expenses %}
                    <div class="digest-item">
                        <div class="item-title">Expense #{{ expense.expense_id }} - {{ expense.category }}</div>
                        <div class="item-details">
                            Amount: ${{ expense.amount }} | Approved: {{ expense.approved_at }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if digest_data.rejected_expenses %}
                <div class="digest-section">
                    <div class="section-title">Recently Rejected</div>
                    {% for expense in digest_data.rejected_expenses %}
                    <div class="digest-item rejected">
                        <div class="item-title">Expense #{{ expense.expense_id }} - {{ expense.category }}</div>
                        <div class="item-details">
                            Amount: ${{ expense.amount }} | Rejected: {{ expense.rejected_at }}
                            <br>Reason: {{ expense.rejection_reason }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                <div style="text-align: center;">
                    <a href="#" class="action-button">View All Approvals</a>
                </div>
                
                <div class="footer">
                    <p>This is your daily approval digest from {{ company_name }}.</p>
                    <p>You can change your notification preferences in your account settings.</p>
                </div>
            </div>
        </body>
        </html>
        """)
        
        # Create text template for digest
        text_template = Template("""
        {{ company_name }} - Daily Approval Digest
        {{ digest_date }}
        
        Hello {{ recipient_name }},
        
        Here's your daily summary of approval activities:
        
        Summary:
        - Total Events: {{ digest_data.total_events or 0 }}
        - Pending: {{ digest_data.pending_count or 0 }}
        - Approved: {{ digest_data.approved_count or 0 }}
        - Rejected: {{ digest_data.rejected_count or 0 }}
        
        {% if digest_data.pending_approvals %}
        Pending Approvals:
        {% for approval in digest_data.pending_approvals %}
        - Expense #{{ approval.expense_id }} ({{ approval.category }}) - ${{ approval.amount }}
          Submitted: {{ approval.submitted_at }}
        {% endfor %}
        {% endif %}
        
        {% if digest_data.approved_expenses %}
        Recently Approved:
        {% for expense in digest_data.approved_expenses %}
        - Expense #{{ expense.expense_id }} ({{ expense.category }}) - ${{ expense.amount }}
          Approved: {{ expense.approved_at }}
        {% endfor %}
        {% endif %}
        
        {% if digest_data.rejected_expenses %}
        Recently Rejected:
        {% for expense in digest_data.rejected_expenses %}
        - Expense #{{ expense.expense_id }} ({{ expense.category }}) - ${{ expense.amount }}
          Rejected: {{ expense.rejected_at }}
          Reason: {{ expense.rejection_reason }}
        {% endfor %}
        {% endif %}
        
        This is your daily approval digest from {{ company_name }}.
        You can change your notification preferences in your account settings.
        """)
        
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