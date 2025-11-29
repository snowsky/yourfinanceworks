"""
Test Report Security Features

Comprehensive tests for report security including:
- Role-based access control
- Data redaction
- Rate limiting
- Audit logging
- Permission validation
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import json

from main import app
from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import User, ReportTemplate, ScheduledReport, AuditLog
from core.services.report_security_service import ReportSecurityService, ReportRateLimiter
from core.services.report_audit_service import ReportAuditService
from core.schemas.report import ReportType, ExportFormat
from core.exceptions.report_exceptions import ReportAccessDeniedException, ReportErrorCode


class TestReportSecurityService:
    """Test the ReportSecurityService class."""
    
    def test_validate_report_access_admin(self, db_session: Session):
        """Test that admin users have full access."""
        security_service = ReportSecurityService(db_session)
        
        admin_user = Mock()
        admin_user.id = 1
        admin_user.role = "admin"
        
        # Admin should have access to all actions
        assert security_service.validate_report_access(admin_user, 'generate')
        assert security_service.validate_report_access(admin_user, 'view')
        assert security_service.validate_report_access(admin_user, 'download')
        assert security_service.validate_report_access(admin_user, 'create_template')
        assert security_service.validate_report_access(admin_user, 'manage_permissions')
    
    def test_validate_report_access_user(self, db_session: Session):
        """Test that regular users have appropriate access."""
        security_service = ReportSecurityService(db_session)
        
        user = Mock()
        user.id = 2
        user.role = "user"
        
        # User should have most access except admin-only features
        assert security_service.validate_report_access(user, 'generate')
        assert security_service.validate_report_access(user, 'view')
        assert security_service.validate_report_access(user, 'download')
        assert security_service.validate_report_access(user, 'create_template')
        
        # Should not have admin permissions
        with pytest.raises(ReportAccessDeniedException):
            security_service.validate_report_access(user, 'manage_permissions')
    
    def test_validate_report_access_viewer(self, db_session: Session):
        """Test that viewers have limited access."""
        security_service = ReportSecurityService(db_session)
        
        viewer = Mock()
        viewer.id = 3
        viewer.role = "viewer"
        
        # Viewer should have read-only access
        assert security_service.validate_report_access(viewer, 'generate')
        assert security_service.validate_report_access(viewer, 'view')
        assert security_service.validate_report_access(viewer, 'download')
        
        # Should not have write permissions
        with pytest.raises(ReportAccessDeniedException):
            security_service.validate_report_access(viewer, 'create_template')
        
        with pytest.raises(ReportAccessDeniedException):
            security_service.validate_report_access(viewer, 'schedule_reports')
    
    def test_validate_template_access_owner(self, db_session: Session):
        """Test template access for owner."""
        security_service = ReportSecurityService(db_session)
        
        user = Mock()
        user.id = 1
        user.role = "user"
        
        # Create a mock template
        template = Mock()
        template.id = 1
        template.user_id = 1
        template.is_shared = False
        
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = template
            
            result = security_service.validate_template_access(user, 1, 'view')
            assert result == template
    
    def test_validate_template_access_shared(self, db_session: Session):
        """Test template access for shared templates."""
        security_service = ReportSecurityService(db_session)
        
        user = Mock()
        user.id = 2
        user.role = "user"
        
        # Create a mock shared template owned by someone else
        template = Mock()
        template.id = 1
        template.user_id = 1
        template.is_shared = True
        
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = template
            
            # Should allow view access to shared template
            result = security_service.validate_template_access(user, 1, 'view')
            assert result == template
            
            # Should not allow edit access to shared template
            with pytest.raises(ReportAccessDeniedException):
                security_service.validate_template_access(user, 1, 'update_template')
    
    def test_validate_template_access_denied(self, db_session: Session):
        """Test template access denial."""
        security_service = ReportSecurityService(db_session)
        
        user = Mock()
        user.id = 2
        user.role = "user"
        
        # Create a mock private template owned by someone else
        template = Mock()
        template.id = 1
        template.user_id = 1
        template.is_shared = False
        
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = template
            
            with pytest.raises(ReportAccessDeniedException):
                security_service.validate_template_access(user, 1, 'view')
    
    def test_apply_data_redaction_admin(self, db_session: Session):
        """Test that admins don't get data redaction."""
        security_service = ReportSecurityService(db_session)
        
        admin_user = Mock()
        admin_user.id = 1
        admin_user.role = "admin"
        
        report_data = {
            'data': [
                {'client_name': 'John Doe', 'email': 'john@example.com', 'phone': '555-1234'},
                {'client_name': 'Jane Smith', 'email': 'jane@example.com', 'phone': '555-5678'}
            ]
        }
        
        result = security_service.apply_data_redaction(
            report_data, ReportType.CLIENT, admin_user, "standard"
        )
        
        # Admin should see unredacted data
        assert result['data'][0]['email'] == 'john@example.com'
        assert result['data'][0]['phone'] == '555-1234'
        assert '_redaction_applied' not in result
    
    def test_apply_data_redaction_standard(self, db_session: Session):
        """Test standard data redaction."""
        security_service = ReportSecurityService(db_session)
        
        user = Mock()
        user.id = 2
        user.role = "user"
        
        report_data = {
            'data': [
                {'client_name': 'John Doe', 'email': 'john@example.com', 'phone': '555-1234'},
                {'client_name': 'Jane Smith', 'email': 'jane@example.com', 'phone': '555-5678'}
            ]
        }
        
        result = security_service.apply_data_redaction(
            report_data, ReportType.CLIENT, user, "standard"
        )
        
        # Should have partial redaction
        assert result['data'][0]['email'] == 'j***@example.com'
        assert result['data'][0]['phone'] == '***-***-1234'
        assert '_redaction_applied' in result
        assert result['_redaction_applied']['level'] == 'standard'
    
    def test_apply_data_redaction_strict(self, db_session: Session):
        """Test strict data redaction."""
        security_service = ReportSecurityService(db_session)
        
        user = Mock()
        user.id = 2
        user.role = "user"
        
        report_data = {
            'data': [
                {'client_name': 'John Doe', 'email': 'john@example.com', 'phone': '555-1234'}
            ]
        }
        
        result = security_service.apply_data_redaction(
            report_data, ReportType.CLIENT, user, "strict"
        )
        
        # Should have full redaction
        assert result['data'][0]['email'] == '[REDACTED]'
        assert result['data'][0]['phone'] == '[REDACTED]'
        assert '_redaction_applied' in result
        assert result['_redaction_applied']['level'] == 'strict'
    
    def test_get_allowed_export_formats_viewer(self, db_session: Session):
        """Test export format restrictions for viewers."""
        security_service = ReportSecurityService(db_session)
        
        viewer = Mock()
        viewer.role = "viewer"
        
        allowed_formats = security_service.get_allowed_export_formats(viewer)
        
        # Viewers should have limited formats
        assert ExportFormat.JSON in allowed_formats
        assert ExportFormat.CSV in allowed_formats
        assert len(allowed_formats) == 2
    
    def test_get_allowed_export_formats_user(self, db_session: Session):
        """Test export format access for regular users."""
        security_service = ReportSecurityService(db_session)
        
        user = Mock()
        user.role = "user"
        
        allowed_formats = security_service.get_allowed_export_formats(user)
        
        # Users should have all formats
        assert len(allowed_formats) == len(list(ExportFormat))
    
    def test_validate_export_format_denied(self, db_session: Session):
        """Test export format validation denial."""
        security_service = ReportSecurityService(db_session)
        
        viewer = Mock()
        viewer.role = "viewer"
        
        with pytest.raises(ReportAccessDeniedException):
            security_service.validate_export_format(viewer, ExportFormat.PDF)


class TestReportRateLimiter:
    """Test the ReportRateLimiter class."""
    
    def test_check_rate_limit_within_limit(self, db_session: Session):
        """Test rate limiting when within limits."""
        rate_limiter = ReportRateLimiter(db_session)
        
        user = Mock()
        user.id = 1
        user.role = "user"
        
        # Mock the query to return a count within limits
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.scalar.return_value = 10
            
            result = rate_limiter.check_rate_limit(user, 'report_generation')
            assert result is True
    
    def test_check_rate_limit_exceeded(self, db_session: Session):
        """Test rate limiting when limits are exceeded."""
        rate_limiter = ReportRateLimiter(db_session)
        
        user = Mock()
        user.id = 1
        user.role = "user"
        
        # Mock the query to return a count exceeding limits
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.scalar.return_value = 100
            
            result = rate_limiter.check_rate_limit(user, 'report_generation')
            assert result is False
    
    def test_check_rate_limit_viewer_templates(self, db_session: Session):
        """Test that viewers can't perform template operations."""
        rate_limiter = ReportRateLimiter(db_session)
        
        viewer = Mock()
        viewer.id = 1
        viewer.role = "viewer"
        
        result = rate_limiter.check_rate_limit(viewer, 'template_operations')
        assert result is False
    
    def test_get_rate_limit_info(self, db_session: Session):
        """Test getting rate limit information."""
        rate_limiter = ReportRateLimiter(db_session)
        
        user = Mock()
        user.id = 1
        user.role = "user"
        
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.scalar.return_value = 10
            
            info = rate_limiter.get_rate_limit_info(user, 'report_generation')
            
            assert info['limit'] == 50  # User limit for report generation
            assert info['current_usage'] == 10
            assert info['remaining'] == 40
            assert info['operation_type'] == 'report_generation'
            assert info['user_role'] == 'user'


class TestReportAuditService:
    """Test the ReportAuditService class."""
    
    def test_log_report_generation(self, db_session: Session):
        """Test logging report generation."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_log.return_value = Mock()
            
            audit_service.log_report_generation(
                user_id=1,
                user_email="test@example.com",
                report_type=ReportType.CLIENT,
                export_format=ExportFormat.PDF,
                filters={'date_from': '2024-01-01'},
                template_id=1,
                report_id="report_123",
                status="success",
                execution_time_ms=1500,
                record_count=100,
                file_size_bytes=50000
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            assert call_args[1]['action'] == 'REPORT_GENERATE'
            assert call_args[1]['resource_type'] == 'report'
            assert call_args[1]['resource_id'] == 'report_123'
            assert call_args[1]['status'] == 'success'
            assert 'execution_time_ms' in call_args[1]['details']
            assert 'record_count' in call_args[1]['details']
    
    def test_log_template_operation(self, db_session: Session):
        """Test logging template operations."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_log.return_value = Mock()
            
            audit_service.log_template_operation(
                user_id=1,
                user_email="test@example.com",
                action="CREATE",
                template_id=1,
                template_name="Monthly Report",
                report_type="client",
                status="success"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            assert call_args[1]['action'] == 'TEMPLATE_CREATE'
            assert call_args[1]['resource_type'] == 'report_template'
            assert call_args[1]['resource_name'] == 'Monthly Report'
    
    def test_log_access_attempt(self, db_session: Session):
        """Test logging access attempts."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_log.return_value = Mock()
            
            audit_service.log_access_attempt(
                user_id=1,
                user_email="test@example.com",
                resource_type="report",
                resource_id="123",
                action="VIEW",
                access_granted=False,
                reason="Insufficient permissions"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            assert call_args[1]['action'] == 'ACCESS_VIEW'
            assert call_args[1]['status'] == 'access_denied'
            assert call_args[1]['error_message'] == 'Insufficient permissions'
    
    def test_log_data_redaction(self, db_session: Session):
        """Test logging data redaction."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_log.return_value = Mock()
            
            audit_service.log_data_redaction(
                user_id=1,
                user_email="test@example.com",
                report_id="report_123",
                redacted_fields=['email', 'phone'],
                redaction_reason="Standard privacy protection"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            assert call_args[1]['action'] == 'DATA_REDACTION'
            assert call_args[1]['resource_type'] == 'report'
            assert call_args[1]['resource_id'] == 'report_123'
            assert 'redacted_fields' in call_args[1]['details']


class TestReportSecurityIntegration:
    """Integration tests for report security features."""
    
    def test_generate_report_with_rate_limiting(self, client: TestClient, db_session: Session):
        """Test report generation with rate limiting."""
        # Create a user with limited rate limits
        user = Mock()
        user.id = 1
        user.email = "test@example.com"
        user.role = "viewer"
        
        # Mock the rate limiter to return False (exceeded)
        with patch('routers.reports.ReportRateLimiter') as mock_rate_limiter_class:
            mock_rate_limiter = Mock()
            mock_rate_limiter.check_rate_limit.return_value = False
            mock_rate_limiter.get_rate_limit_info.return_value = {
                'limit': 20,
                'current_usage': 20,
                'remaining': 0,
                'reset_time': '2024-01-01T01:00:00',
                'operation_type': 'report_generation',
                'user_role': 'viewer'
            }
            mock_rate_limiter_class.return_value = mock_rate_limiter
            
            with patch('routers.reports.get_current_user', return_value=user):
                response = client.post("/api/v1/reports/generate", json={
                    "report_type": "client",
                    "export_format": "json",
                    "filters": {}
                })
                
                assert response.status_code == 429
                assert "rate limit exceeded" in response.json()["detail"]["message"].lower()
    
    def test_download_report_with_access_control(self, client: TestClient, db_session: Session):
        """Test report download with access control."""
        user = Mock()
        user.id = 1
        user.email = "test@example.com"
        user.role = "user"
        
        # Mock the history service to return None (no access)
        with patch('routers.reports.ReportHistoryService') as mock_history_service_class:
            mock_history_service = Mock()
            mock_history_service.get_report_history.return_value = None
            mock_history_service_class.return_value = mock_history_service
            
            with patch('routers.reports.get_current_user', return_value=user):
                response = client.get("/api/v1/reports/download/123")
                
                assert response.status_code == 404
                assert "not found" in response.json()["detail"].lower()
    
    def test_template_access_validation(self, client: TestClient, db_session: Session):
        """Test template access validation."""
        user = Mock()
        user.id = 2
        user.email = "test@example.com"
        user.role = "user"
        
        # Mock template service to simulate access denied
        with patch('routers.reports.ReportTemplateService') as mock_template_service_class:
            mock_template_service = Mock()
            mock_template_service.get_template.side_effect = Exception("Access denied")
            mock_template_service_class.return_value = mock_template_service
            
            with patch('routers.reports.get_current_user', return_value=user):
                response = client.put("/api/v1/reports/templates/1", json={
                    "name": "Updated Template"
                })
                
                # Should get an error due to access control
                assert response.status_code in [403, 404, 500]


@pytest.fixture
def db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


# Additional test utilities
def create_mock_user(user_id: int, role: str, email: str = None) -> Mock:
    """Create a mock user for testing."""
    user = Mock()
    user.id = user_id
    user.role = role
    user.email = email or f"user{user_id}@example.com"
    return user


def create_mock_template(template_id: int, user_id: int, is_shared: bool = False) -> Mock:
    """Create a mock template for testing."""
    template = Mock()
    template.id = template_id
    template.user_id = user_id
    template.is_shared = is_shared
    template.name = f"Template {template_id}"
    template.report_type = "client"
    return template


def create_mock_audit_log(user_id: int, action: str, resource_type: str) -> Mock:
    """Create a mock audit log entry for testing."""
    log = Mock()
    log.id = 1
    log.user_id = user_id
    log.action = action
    log.resource_type = resource_type
    log.created_at = datetime.utcnow()
    log.status = "success"
    return log