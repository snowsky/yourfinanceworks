import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch
import json

from main import app
from core.models import User, EmailNotificationSettings
from tests.conftest import TestingSessionLocal, override_get_db, create_test_user


client = TestClient(app)


class TestApprovalNotificationPreferences:
    """Test approval notification preferences functionality"""

    def setup_method(self):
        """Set up test data"""
        self.db = TestingSessionLocal()
        self.test_user = create_test_user(self.db)
        
        # Create default notification settings
        self.notification_settings = EmailNotificationSettings(
            user_id=self.test_user.id,
            approval_notification_frequency="immediate",
            approval_reminder_frequency="daily",
            approval_notification_channels=["email"],
            expense_submitted_for_approval=True,
            expense_approved=True,
            expense_rejected=True,
            approval_reminder=True,
            approval_escalation=True
        )
        self.db.add(self.notification_settings)
        self.db.commit()
        self.db.refresh(self.notification_settings)

    def teardown_method(self):
        """Clean up test data"""
        self.db.query(EmailNotificationSettings).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    @patch('routers.notifications.get_current_user')
    @patch('routers.notifications.get_db')
    def test_get_approval_notification_preferences(self, mock_get_db, mock_get_current_user):
        """Test getting approval notification preferences"""
        mock_get_db.return_value = self.db
        mock_get_current_user.return_value = self.test_user

        response = client.get("/notifications/approval-preferences")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["approval_notification_frequency"] == "immediate"
        assert data["approval_reminder_frequency"] == "daily"
        assert data["approval_notification_channels"] == ["email"]
        assert data["approval_events"]["expense_submitted_for_approval"] is True
        assert data["approval_events"]["expense_approved"] is True
        assert data["approval_events"]["expense_rejected"] is True

    @patch('routers.notifications.get_current_user')
    @patch('routers.notifications.get_db')
    def test_get_approval_preferences_creates_default_settings(self, mock_get_db, mock_get_current_user):
        """Test that default settings are created if none exist"""
        # Delete existing settings
        self.db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == self.test_user.id
        ).delete()
        self.db.commit()

        mock_get_db.return_value = self.db
        mock_get_current_user.return_value = self.test_user

        response = client.get("/notifications/approval-preferences")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that default values are returned
        assert data["approval_notification_frequency"] == "immediate"
        assert data["approval_reminder_frequency"] == "daily"
        assert data["approval_notification_channels"] == ["email"]

    @patch('routers.notifications.get_current_user')
    @patch('routers.notifications.get_db')
    def test_update_approval_notification_preferences(self, mock_get_db, mock_get_current_user):
        """Test updating approval notification preferences"""
        mock_get_db.return_value = self.db
        mock_get_current_user.return_value = self.test_user

        update_data = {
            "approval_notification_frequency": "daily_digest",
            "approval_reminder_frequency": "weekly",
            "approval_notification_channels": ["email", "in_app"],
            "approval_events": {
                "expense_submitted_for_approval": False,
                "expense_approved": True,
                "expense_rejected": True,
                "approval_reminder": False
            }
        }

        response = client.put("/notifications/approval-preferences", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Approval notification preferences updated successfully"

        # Verify the settings were updated in the database
        updated_settings = self.db.query(EmailNotificationSettings).filter(
            EmailNotificationSettings.user_id == self.test_user.id
        ).first()
        
        assert updated_settings.approval_notification_frequency == "daily_digest"
        assert updated_settings.approval_reminder_frequency == "weekly"
        assert updated_settings.approval_notification_channels == ["email", "in_app"]
        assert updated_settings.expense_submitted_for_approval is False
        assert updated_settings.expense_approved is True
        assert updated_settings.approval_reminder is False

    @patch('routers.notifications.get_current_user')
    @patch('routers.notifications.get_db')
    def test_update_approval_preferences_invalid_frequency(self, mock_get_db, mock_get_current_user):
        """Test updating with invalid frequency values"""
        mock_get_db.return_value = self.db
        mock_get_current_user.return_value = self.test_user

        update_data = {
            "approval_notification_frequency": "invalid_frequency"
        }

        response = client.put("/notifications/approval-preferences", json=update_data)
        
        assert response.status_code == 400
        assert "Invalid approval_notification_frequency" in response.json()["detail"]

    @patch('routers.notifications.get_current_user')
    @patch('routers.notifications.get_db')
    def test_update_approval_preferences_invalid_channels(self, mock_get_db, mock_get_current_user):
        """Test updating with invalid channel values"""
        mock_get_db.return_value = self.db
        mock_get_current_user.return_value = self.test_user

        update_data = {
            "approval_notification_channels": ["invalid_channel"]
        }

        response = client.put("/notifications/approval-preferences", json=update_data)
        
        assert response.status_code == 400
        assert "Invalid channel" in response.json()["detail"]

    @patch('routers.notifications.get_current_user')
    @patch('routers.notifications.get_db')
    def test_update_approval_preferences_empty_channels(self, mock_get_db, mock_get_current_user):
        """Test updating with empty channels list"""
        mock_get_db.return_value = self.db
        mock_get_current_user.return_value = self.test_user

        update_data = {
            "approval_notification_channels": []
        }

        response = client.put("/notifications/approval-preferences", json=update_data)
        
        assert response.status_code == 400
        assert "must be a non-empty list" in response.json()["detail"]

    @patch('routers.notifications.get_current_user')
    @patch('routers.notifications.get_db')
    @patch('services.email_service.EmailService')
    @patch('models.models_per_tenant.Settings')
    def test_send_approval_digest(self, mock_settings, mock_email_service, mock_get_db, mock_get_current_user):
        """Test sending approval digest"""
        mock_get_db.return_value = self.db
        mock_get_current_user.return_value = self.test_user

        # Mock email settings
        mock_email_settings = Mock()
        mock_email_settings.value = {
            'provider': 'aws_ses',
            'aws_access_key_id': 'test_key',
            'aws_secret_access_key': 'test_secret',
            'aws_region': 'us-east-1'
        }
        self.db.query(mock_settings).filter.return_value.first.return_value = mock_email_settings

        # Mock email service
        mock_email_service_instance = Mock()
        mock_email_service.return_value = mock_email_service_instance

        response = client.post("/notifications/send-digest")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Approval digest sent successfully"

    @patch('routers.notifications.get_current_user')
    @patch('routers.notifications.get_db')
    def test_send_approval_digest_no_email_config(self, mock_get_db, mock_get_current_user):
        """Test sending approval digest without email configuration"""
        mock_get_db.return_value = self.db
        mock_get_current_user.return_value = self.test_user

        # Mock no email settings
        self.db.query().filter().first.return_value = None

        response = client.post("/notifications/send-digest")
        
        assert response.status_code == 400
        assert "Email service not configured" in response.json()["detail"]


class TestNotificationServiceApprovalPreferences:
    """Test notification service approval preferences functionality"""

    def setup_method(self):
        """Set up test data"""
        self.db = TestingSessionLocal()
        self.test_user = create_test_user(self.db)

    def teardown_method(self):
        """Clean up test data"""
        self.db.query(EmailNotificationSettings).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_should_send_notification_immediate_mode(self):
        """Test notification sending in immediate mode"""
        from core.services.notification_service import NotificationService
        
        # Create settings with immediate mode
        settings = EmailNotificationSettings(
            user_id=self.test_user.id,
            approval_notification_frequency="immediate",
            approval_notification_channels=["email"],
            expense_submitted_for_approval=True
        )
        self.db.add(settings)
        self.db.commit()

        notification_service = NotificationService(self.db, Mock())
        
        # Should send immediate notifications
        assert notification_service.should_send_notification(
            self.test_user.id, 'expense_submitted_for_approval', 'email'
        ) is True
        
        # Should not send digest notifications in immediate mode
        assert notification_service.should_send_notification(
            self.test_user.id, 'approval_daily_digest', 'email'
        ) is False

    def test_should_send_notification_digest_mode(self):
        """Test notification sending in digest mode"""
        from core.services.notification_service import NotificationService
        
        # Create settings with digest mode
        settings = EmailNotificationSettings(
            user_id=self.test_user.id,
            approval_notification_frequency="daily_digest",
            approval_notification_channels=["email"],
            expense_submitted_for_approval=True
        )
        self.db.add(settings)
        self.db.commit()

        notification_service = NotificationService(self.db, Mock())
        
        # Should not send immediate notifications in digest mode
        assert notification_service.should_send_notification(
            self.test_user.id, 'expense_submitted_for_approval', 'email'
        ) is False
        
        # Should send digest notifications
        assert notification_service.should_send_notification(
            self.test_user.id, 'approval_daily_digest', 'email'
        ) is True

    def test_should_send_notification_channel_filtering(self):
        """Test notification channel filtering"""
        from core.services.notification_service import NotificationService
        
        # Create settings with only email channel
        settings = EmailNotificationSettings(
            user_id=self.test_user.id,
            approval_notification_frequency="immediate",
            approval_notification_channels=["email"],
            expense_submitted_for_approval=True
        )
        self.db.add(settings)
        self.db.commit()

        notification_service = NotificationService(self.db, Mock())
        
        # Should send email notifications
        assert notification_service.should_send_notification(
            self.test_user.id, 'expense_submitted_for_approval', 'email'
        ) is True
        
        # Should not send in-app notifications
        assert notification_service.should_send_notification(
            self.test_user.id, 'expense_submitted_for_approval', 'in_app'
        ) is False

    def test_create_in_app_notification(self):
        """Test creating in-app notifications"""
        from core.services.notification_service import NotificationService
        
        # Create settings with in-app channel
        settings = EmailNotificationSettings(
            user_id=self.test_user.id,
            approval_notification_channels=["in_app"],
            expense_submitted_for_approval=True
        )
        self.db.add(settings)
        self.db.commit()

        notification_service = NotificationService(self.db, Mock())
        
        # Should successfully create in-app notification
        result = notification_service.create_in_app_notification(
            user_id=self.test_user.id,
            event_type='expense_submitted_for_approval',
            title='Expense Submitted',
            message='Your expense has been submitted for approval',
            data={'expense_id': 123}
        )
        
        assert result is True

    @patch('services.notification_service.logger')
    def test_send_approval_daily_digest(self, mock_logger):
        """Test sending approval daily digest"""
        from core.services.notification_service import NotificationService
        
        # Create settings with digest mode
        settings = EmailNotificationSettings(
            user_id=self.test_user.id,
            approval_notification_frequency="daily_digest",
            approval_notification_channels=["email"]
        )
        self.db.add(settings)
        self.db.commit()

        mock_email_service = Mock()
        mock_email_service.send_email.return_value = True
        
        notification_service = NotificationService(self.db, mock_email_service)
        
        digest_data = {
            "total_events": 3,
            "pending_count": 1,
            "approved_count": 2,
            "rejected_count": 0,
            "pending_approvals": [
                {
                    "expense_id": "123",
                    "category": "Travel",
                    "amount": "250.00",
                    "submitted_at": "2025-01-04 10:00"
                }
            ]
        }
        
        result = notification_service.send_approval_daily_digest(
            user_id=self.test_user.id,
            digest_data=digest_data
        )
        
        assert result is True
        mock_email_service.send_email.assert_called_once()