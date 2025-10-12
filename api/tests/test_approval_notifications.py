"""
Tests for approval notification functionality.

This module tests the notification service extensions for approval events
and the approval notification scheduler service.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from services.notification_service import NotificationService
from services.approval_notification_scheduler import ApprovalNotificationScheduler
from services.email_service import EmailService, EmailMessage
from models.models_per_tenant import (
    User, Expense, ExpenseApproval, EmailNotificationSettings
)
from schemas.approval import ApprovalStatus


class TestNotificationServiceApprovalExtensions:
    """Test approval-specific extensions to the notification service."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_email_service(self):
        """Mock email service."""
        mock = Mock()
        mock.send_email = Mock(return_value=True)
        return mock
    
    @pytest.fixture
    def notification_service(self, mock_db, mock_email_service):
        """Create notification service instance."""
        return NotificationService(mock_db, mock_email_service)
    
    @pytest.fixture
    def sample_user(self):
        """Create sample user."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "approver@example.com"
        user.first_name = "John"
        user.last_name = "Doe"
        return user
    
    @pytest.fixture
    def sample_notification_settings(self):
        """Create sample notification settings."""
        settings = Mock(spec=EmailNotificationSettings)
        settings.expense_submitted_for_approval = True
        settings.expense_approved = True
        settings.expense_rejected = True
        settings.approval_reminder = True
        settings.approval_escalation = True
        settings.notification_email = None
        return settings
    
    def test_approval_event_info_mapping(self, notification_service):
        """Test that approval events are properly mapped."""
        # Test expense submitted for approval
        event_info = notification_service._get_event_info('expense_submitted_for_approval', 'expense_approval')
        assert event_info['title'] == 'Expense Submitted for Approval'
        assert event_info['color'] == '#ffc107'
        assert 'requires your approval' in event_info['description']
        
        # Test expense approved
        event_info = notification_service._get_event_info('expense_approved', 'expense_approval')
        assert event_info['title'] == 'Expense Approved'
        assert event_info['color'] == '#28a745'
        
        # Test expense rejected
        event_info = notification_service._get_event_info('expense_rejected', 'expense_approval')
        assert event_info['title'] == 'Expense Rejected'
        assert event_info['color'] == '#dc3545'
        
        # Test approval reminder
        event_info = notification_service._get_event_info('approval_reminder', 'expense_approval')
        assert event_info['title'] == 'Approval Reminder'
        assert event_info['color'] == '#fd7e14'
        
        # Test approval escalation
        event_info = notification_service._get_event_info('approval_escalation', 'expense_approval')
        assert event_info['title'] == 'Approval Escalation'
        assert event_info['color'] == '#dc3545'
    
    def test_send_approval_reminder_success(self, notification_service, mock_db, mock_email_service, 
                                          sample_user, sample_notification_settings):
        """Test successful approval reminder sending."""
        # Setup mocks for notification service methods
        notification_service.should_send_notification = Mock(return_value=True)
        notification_service.get_user_notification_settings = Mock(return_value=sample_notification_settings)
        
        # Setup database query mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user
        mock_email_service.send_email.return_value = True
        
        # Test data
        pending_approvals = [
            {
                'expense_id': 1,
                'amount': 100.50,
                'category': 'Travel',
                'submitted_at': datetime.now(timezone.utc) - timedelta(hours=25)
            },
            {
                'expense_id': 2,
                'amount': 75.25,
                'category': 'Meals',
                'submitted_at': datetime.now(timezone.utc) - timedelta(hours=30)
            }
        ]
        
        # Call method
        result = notification_service.send_approval_reminder(
            approver_id=1,
            pending_approvals=pending_approvals,
            company_name="Test Company"
        )
        
        # Assertions
        assert result is True
        mock_email_service.send_email.assert_called_once()
        
        # Check email message
        call_args = mock_email_service.send_email.call_args[0][0]
        assert isinstance(call_args, EmailMessage)
        assert call_args.to_email == "approver@example.com"
        assert call_args.to_name == "John Doe"
        assert "2 pending approval" in call_args.subject
        assert "Test Company" in call_args.subject
    
    def test_send_approval_reminder_disabled(self, notification_service, mock_db, 
                                           sample_notification_settings):
        """Test approval reminder when notifications are disabled."""
        # Setup mocks - user has disabled approval reminders
        sample_notification_settings.approval_reminder = False
        mock_db.query.return_value.filter.return_value.first.return_value = sample_notification_settings
        
        # Call method
        result = notification_service.send_approval_reminder(
            approver_id=1,
            pending_approvals=[{'expense_id': 1}],
            company_name="Test Company"
        )
        
        # Should return True but not send email
        assert result is True
    
    def test_send_approval_reminder_no_approvals(self, notification_service):
        """Test approval reminder with empty approvals list."""
        result = notification_service.send_approval_reminder(
            approver_id=1,
            pending_approvals=[],
            company_name="Test Company"
        )
        
        assert result is True
    
    def test_send_approval_escalation_success(self, notification_service, mock_db, mock_email_service,
                                            sample_user, sample_notification_settings):
        """Test successful approval escalation sending."""
        # Setup mocks for notification service methods
        notification_service.should_send_notification = Mock(return_value=True)
        notification_service.get_user_notification_settings = Mock(return_value=sample_notification_settings)
        
        # Setup mocks
        approver_user = Mock(spec=User)
        approver_user.id = 2
        approver_user.first_name = "Jane"
        approver_user.last_name = "Smith"
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_user,  # Escalation recipient
            approver_user  # Approver
        ]
        mock_email_service.send_email.return_value = True
        
        # Test data
        overdue_approvals = [
            {
                'expense_id': 1,
                'amount': 200.00,
                'category': 'Travel',
                'submitted_at': datetime.now(timezone.utc) - timedelta(hours=80)
            }
        ]
        
        # Call method
        result = notification_service.send_approval_escalation(
            approver_id=2,
            overdue_approvals=overdue_approvals,
            escalation_recipient_id=1,
            company_name="Test Company"
        )
        
        # Assertions
        assert result is True
        mock_email_service.send_email.assert_called_once()
        
        # Check email message
        call_args = mock_email_service.send_email.call_args[0][0]
        assert isinstance(call_args, EmailMessage)
        assert call_args.to_email == "approver@example.com"
        assert "URGENT" in call_args.subject
        assert "1 overdue approval" in call_args.subject
    
    def test_create_approval_reminder_message(self, notification_service):
        """Test creation of approval reminder email message."""
        details = {
            'total_pending': 3,
            'total_amount': '$375.75',
            'oldest_submission': '2024-01-15 10:30',
            'pending_list': '#1 (Travel), #2 (Meals), #3 (Office Supplies)'
        }
        
        message = notification_service._create_approval_reminder_message(
            recipient_email="test@example.com",
            recipient_name="Test User",
            company_name="Test Company",
            pending_count=3,
            details=details
        )
        
        assert isinstance(message, EmailMessage)
        assert message.to_email == "test@example.com"
        assert message.to_name == "Test User"
        assert "3 pending approval" in message.subject
        assert "Test Company" in message.subject
        assert "$375.75" in message.html_body
        assert "Action Required" in message.html_body
        assert "pending-list" in message.html_body  # Check CSS class exists
    
    def test_create_approval_escalation_message(self, notification_service):
        """Test creation of approval escalation email message."""
        details = {
            'approver_name': 'Jane Smith',
            'total_overdue': 2,
            'total_amount': '$500.00',
            'oldest_submission': '2024-01-10 09:00',
            'overdue_list': '#1 (Travel), #2 (Equipment)'
        }
        
        message = notification_service._create_approval_escalation_message(
            recipient_email="manager@example.com",
            recipient_name="Manager User",
            company_name="Test Company",
            overdue_count=2,
            details=details
        )
        
        assert isinstance(message, EmailMessage)
        assert message.to_email == "manager@example.com"
        assert message.to_name == "Manager User"
        assert "URGENT" in message.subject
        assert "2 overdue approval" in message.subject
        assert "Jane Smith" in message.html_body
        assert "$500.00" in message.html_body
        assert "pulse" in message.html_body  # Check animation CSS exists


class TestApprovalNotificationScheduler:
    """Test the approval notification scheduler service."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_notification_service(self):
        """Mock notification service."""
        return Mock(spec=NotificationService)
    
    @pytest.fixture
    def scheduler(self, mock_db, mock_notification_service):
        """Create scheduler instance."""
        return ApprovalNotificationScheduler(mock_db, mock_notification_service)
    
    @pytest.fixture
    def sample_approval(self):
        """Create sample approval."""
        approval = Mock(spec=ExpenseApproval)
        approval.id = 1
        approval.expense_id = 1
        approval.approver_id = 1
        approval.status = ApprovalStatus.PENDING
        approval.is_current_level = True
        approval.submitted_at = datetime.now(timezone.utc) - timedelta(hours=30)
        
        # Mock expense relationship
        expense = Mock(spec=Expense)
        expense.id = 1
        expense.amount = 100.50
        expense.category = "Travel"
        approval.expense = expense
        
        return approval
    
    def test_send_pending_approval_reminders_success(self, scheduler, mock_db, 
                                                   mock_notification_service, sample_approval):
        """Test successful sending of pending approval reminders."""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_approval]
        mock_notification_service.send_approval_reminder.return_value = True
        
        # Mock the _should_send_reminder method to return True
        with patch.object(scheduler, '_should_send_reminder', return_value=True):
            with patch.object(scheduler, '_update_last_reminder_time'):
                result = scheduler.send_pending_approval_reminders("Test Company")
        
        # Assertions
        assert result['total_reminders_sent'] == 1
        assert result['approvers_notified'] == 1
        assert len(result['errors']) == 0
        
        mock_notification_service.send_approval_reminder.assert_called_once()
    
    def test_send_pending_approval_reminders_no_approvals(self, scheduler, mock_db, 
                                                        mock_notification_service):
        """Test reminder sending when no approvals need reminders."""
        # Setup mocks - no pending approvals
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = scheduler.send_pending_approval_reminders("Test Company")
        
        assert result['total_reminders_sent'] == 0
        assert result['approvers_notified'] == 0
        assert len(result['errors']) == 0
        
        mock_notification_service.send_approval_reminder.assert_not_called()
    
    def test_send_pending_approval_reminders_notification_failure(self, scheduler, mock_db,
                                                                mock_notification_service, sample_approval):
        """Test handling of notification service failure."""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_approval]
        mock_notification_service.send_approval_reminder.return_value = False
        
        with patch.object(scheduler, '_should_send_reminder', return_value=True):
            result = scheduler.send_pending_approval_reminders("Test Company")
        
        assert result['total_reminders_sent'] == 0
        assert result['approvers_notified'] == 0
        assert len(result['errors']) == 1
        assert "Failed to send reminder" in result['errors'][0]
    
    def test_send_overdue_approval_escalations_success(self, scheduler, mock_db,
                                                     mock_notification_service, sample_approval):
        """Test successful sending of overdue approval escalations."""
        # Make approval overdue
        sample_approval.submitted_at = datetime.now(timezone.utc) - timedelta(hours=80)
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_approval]
        mock_notification_service.send_approval_escalation.return_value = True
        
        # Mock escalation recipient
        escalation_user = Mock(spec=User)
        escalation_user.id = 2
        escalation_user.email = "manager@example.com"
        
        with patch.object(scheduler, '_should_send_escalation', return_value=True):
            with patch.object(scheduler, '_get_escalation_recipient', return_value=escalation_user):
                with patch.object(scheduler, '_update_last_escalation_time'):
                    result = scheduler.send_overdue_approval_escalations("Test Company")
        
        # Assertions
        assert result['total_escalations_sent'] == 1
        assert result['approvers_escalated'] == 1
        assert len(result['errors']) == 0
        
        mock_notification_service.send_approval_escalation.assert_called_once()
    
    def test_send_overdue_approval_escalations_no_recipient(self, scheduler, mock_db,
                                                          mock_notification_service, sample_approval):
        """Test escalation when no escalation recipient is found."""
        # Make approval overdue
        sample_approval.submitted_at = datetime.now(timezone.utc) - timedelta(hours=80)
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_approval]
        
        with patch.object(scheduler, '_should_send_escalation', return_value=True):
            with patch.object(scheduler, '_get_escalation_recipient', return_value=None):
                result = scheduler.send_overdue_approval_escalations("Test Company")
        
        assert result['total_escalations_sent'] == 0
        assert result['approvers_escalated'] == 0
        assert len(result['errors']) == 1
        assert "No escalation recipient found" in result['errors'][0]
    
    def test_process_all_approval_notifications(self, scheduler):
        """Test processing of all approval notifications."""
        reminder_results = {
            'total_reminders_sent': 2,
            'approvers_notified': 1,
            'errors': []
        }
        
        escalation_results = {
            'total_escalations_sent': 1,
            'approvers_escalated': 1,
            'errors': ['Test error']
        }
        
        with patch.object(scheduler, 'send_pending_approval_reminders', return_value=reminder_results):
            with patch.object(scheduler, 'send_overdue_approval_escalations', return_value=escalation_results):
                result = scheduler.process_all_approval_notifications("Test Company")
        
        assert result['total_notifications_sent'] == 3
        assert result['reminders'] == reminder_results
        assert result['escalations'] == escalation_results
        assert len(result['errors']) == 1
        assert 'processed_at' in result
    
    def test_get_pending_approval_summary(self, scheduler, mock_db, sample_approval):
        """Test getting pending approval summary."""
        # Create multiple approvals with different states
        approval1 = sample_approval
        approval1.submitted_at = datetime.now(timezone.utc) - timedelta(hours=30)  # Needs reminder
        
        approval2 = Mock(spec=ExpenseApproval)
        approval2.id = 2
        approval2.approver_id = 1
        approval2.status = ApprovalStatus.PENDING
        approval2.is_current_level = True
        approval2.submitted_at = datetime.now(timezone.utc) - timedelta(hours=80)  # Needs escalation
        
        approval3 = Mock(spec=ExpenseApproval)
        approval3.id = 3
        approval3.approver_id = 2
        approval3.status = ApprovalStatus.PENDING
        approval3.is_current_level = True
        approval3.submitted_at = datetime.now(timezone.utc) - timedelta(hours=10)  # Recent
        
        mock_db.query.return_value.filter.return_value.all.return_value = [approval1, approval2, approval3]
        
        result = scheduler.get_pending_approval_summary()
        
        assert result['total_pending'] == 3
        assert result['needs_reminder'] == 2  # approval1 and approval2
        assert result['needs_escalation'] == 1  # approval2
        assert result['approvers_with_pending'] == 2  # approver 1 and 2
        assert 'thresholds' in result
        assert 'generated_at' in result
    
    def test_should_send_reminder_logic(self, scheduler, sample_approval):
        """Test the logic for determining if a reminder should be sent."""
        # Test when no previous reminder
        assert scheduler._should_send_reminder(sample_approval) is True
        
        # Test when reminder was sent recently (mock last_reminder_sent)
        recent_time = datetime.now(timezone.utc) - timedelta(hours=12)
        sample_approval.last_reminder_sent = recent_time
        assert scheduler._should_send_reminder(sample_approval) is False
        
        # Test when enough time has passed since last reminder
        old_time = datetime.now(timezone.utc) - timedelta(hours=30)
        sample_approval.last_reminder_sent = old_time
        assert scheduler._should_send_reminder(sample_approval) is True
    
    def test_should_send_escalation_logic(self, scheduler, sample_approval):
        """Test the logic for determining if an escalation should be sent."""
        # Test when no previous escalation
        assert scheduler._should_send_escalation(sample_approval) is True
        
        # Test when escalation was sent recently
        recent_time = datetime.now(timezone.utc) - timedelta(hours=12)
        sample_approval.last_escalation_sent = recent_time
        assert scheduler._should_send_escalation(sample_approval) is False
        
        # Test when enough time has passed since last escalation
        old_time = datetime.now(timezone.utc) - timedelta(hours=30)
        sample_approval.last_escalation_sent = old_time
        assert scheduler._should_send_escalation(sample_approval) is True
    
    def test_configure_thresholds(self, scheduler):
        """Test configuration of notification thresholds."""
        # Test initial values
        assert scheduler.reminder_threshold_hours == 24
        assert scheduler.escalation_threshold_hours == 72
        assert scheduler.reminder_frequency_hours == 24
        
        # Test updating thresholds
        scheduler.configure_thresholds(
            reminder_threshold_hours=12,
            escalation_threshold_hours=48,
            reminder_frequency_hours=12
        )
        
        assert scheduler.reminder_threshold_hours == 12
        assert scheduler.escalation_threshold_hours == 48
        assert scheduler.reminder_frequency_hours == 12
        
        # Test partial updates
        scheduler.configure_thresholds(reminder_threshold_hours=6)
        assert scheduler.reminder_threshold_hours == 6
        assert scheduler.escalation_threshold_hours == 48  # Unchanged
        assert scheduler.reminder_frequency_hours == 12  # Unchanged
    
    def test_get_escalation_recipient_admin_user(self, scheduler, mock_db):
        """Test finding escalation recipient with admin user."""
        admin_user = Mock(spec=User)
        admin_user.id = 2
        admin_user.role = "admin"
        
        mock_db.query.return_value.filter.return_value.first.return_value = admin_user
        
        result = scheduler._get_escalation_recipient(1)
        
        assert result == admin_user
    
    def test_get_escalation_recipient_fallback(self, scheduler, mock_db):
        """Test escalation recipient fallback logic."""
        # No admin user found
        mock_db.query.return_value.filter.return_value.first.side_effect = [None, Mock(spec=User)]
        
        result = scheduler._get_escalation_recipient(1)
        
        assert result is not None
        assert isinstance(result, Mock)
    
    def test_error_handling_in_reminder_sending(self, scheduler, mock_db, mock_notification_service):
        """Test error handling during reminder sending."""
        # Setup mock to raise exception
        mock_db.query.return_value.filter.return_value.all.side_effect = Exception("Database error")
        
        result = scheduler.send_pending_approval_reminders("Test Company")
        
        assert result['total_reminders_sent'] == 0
        assert result['approvers_notified'] == 0
        assert len(result['errors']) == 1
        assert "System error" in result['errors'][0]
    
    def test_error_handling_in_escalation_sending(self, scheduler, mock_db, mock_notification_service):
        """Test error handling during escalation sending."""
        # Setup mock to raise exception
        mock_db.query.return_value.filter.return_value.all.side_effect = Exception("Database error")
        
        result = scheduler.send_overdue_approval_escalations("Test Company")
        
        assert result['total_escalations_sent'] == 0
        assert result['approvers_escalated'] == 0
        assert len(result['errors']) == 1
        assert "System error" in result['errors'][0]


class TestApprovalNotificationIntegration:
    """Integration tests for approval notifications."""
    
    def test_notification_service_approval_integration(self):
        """Test that approval service can integrate with notification service."""
        # This would be an integration test that verifies the approval service
        # can successfully call the notification service methods
        
        # Mock the dependencies
        mock_db = Mock(spec=Session)
        mock_email_service = Mock(spec=EmailService)
        
        # Create services
        notification_service = NotificationService(mock_db, mock_email_service)
        
        # Test that the approval service can call notification methods
        # This verifies the interface compatibility
        assert hasattr(notification_service, 'send_approval_reminder')
        assert hasattr(notification_service, 'send_approval_escalation')
        assert hasattr(notification_service, 'send_operation_notification')
    
    def test_scheduler_notification_service_integration(self):
        """Test that scheduler can integrate with notification service."""
        mock_db = Mock(spec=Session)
        mock_notification_service = Mock(spec=NotificationService)
        
        # Create scheduler
        scheduler = ApprovalNotificationScheduler(mock_db, mock_notification_service)
        
        # Verify scheduler can call notification service methods
        assert scheduler.notification_service == mock_notification_service
        
        # Test configuration methods exist
        assert hasattr(scheduler, 'configure_thresholds')
        assert hasattr(scheduler, 'get_pending_approval_summary')
        assert hasattr(scheduler, 'process_all_approval_notifications')


if __name__ == "__main__":
    pytest.main([__file__])