"""
Test Report Audit Logging

Comprehensive tests for audit logging functionality in the reporting module.
Tests audit log creation, retrieval, and security monitoring features.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

from main import app
from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import User, AuditLog
from core.services.report_audit_service import ReportAuditService, extract_request_info
from core.schemas.report import ReportType, ExportFormat


class TestReportAuditService:
    """Test audit logging service functionality."""
    
    def test_log_report_generation_success(self, db_session: Session):
        """Test logging successful report generation."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_audit_log.id = 1
            mock_log.return_value = mock_audit_log
            
            result = audit_service.log_report_generation(
                user_id=1,
                user_email="test@example.com",
                report_type=ReportType.CLIENT,
                export_format=ExportFormat.PDF,
                filters={'date_from': '2024-01-01', 'client_ids': [1, 2]},
                template_id=5,
                report_id="report_123",
                status="success",
                execution_time_ms=2500,
                record_count=150,
                file_size_bytes=75000,
                ip_address="192.168.1.100",
                user_agent="Mozilla/5.0 Test Browser"
            )
            
            # Verify the audit log was created with correct parameters
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['user_id'] == 1
            assert call_kwargs['user_email'] == "test@example.com"
            assert call_kwargs['action'] == "REPORT_GENERATE"
            assert call_kwargs['resource_type'] == "report"
            assert call_kwargs['resource_id'] == "report_123"
            assert call_kwargs['resource_name'] == "client_report"
            assert call_kwargs['status'] == "success"
            assert call_kwargs['ip_address'] == "192.168.1.100"
            assert call_kwargs['user_agent'] == "Mozilla/5.0 Test Browser"
            
            # Check details
            details = call_kwargs['details']
            assert details['report_type'] == 'client'
            assert details['export_format'] == 'pdf'
            assert details['template_id'] == 5
            assert details['execution_time_ms'] == 2500
            assert details['record_count'] == 150
            assert details['file_size_bytes'] == 75000
            assert 'filters' in details
            
            assert result == mock_audit_log
    
    def test_log_report_generation_failure(self, db_session: Session):
        """Test logging failed report generation."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            audit_service.log_report_generation(
                user_id=1,
                user_email="test@example.com",
                report_type=ReportType.INVOICE,
                export_format=ExportFormat.CSV,
                filters={'invalid_filter': 'bad_value'},
                status="error",
                error_message="Invalid filter parameters",
                execution_time_ms=500
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['status'] == "error"
            assert call_kwargs['error_message'] == "Invalid filter parameters"
            assert call_kwargs['details']['execution_time_ms'] == 500
            assert 'record_count' not in call_kwargs['details']  # Should be None and filtered out
    
    def test_log_report_download(self, db_session: Session):
        """Test logging report download activity."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            result = audit_service.log_report_download(
                user_id=2,
                user_email="user@example.com",
                report_id="report_456",
                report_type="payment",
                export_format="excel",
                ip_address="10.0.0.1",
                user_agent="Chrome/91.0"
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['action'] == "REPORT_DOWNLOAD"
            assert call_kwargs['resource_type'] == "report"
            assert call_kwargs['resource_id'] == "report_456"
            assert call_kwargs['resource_name'] == "payment_report"
            assert call_kwargs['status'] == "success"
            
            details = call_kwargs['details']
            assert details['report_type'] == "payment"
            assert details['export_format'] == "excel"
            assert details['action_type'] == "download"
    
    def test_log_template_operation_create(self, db_session: Session):
        """Test logging template creation."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            audit_service.log_template_operation(
                user_id=3,
                user_email="admin@example.com",
                action="CREATE",
                template_id=10,
                template_name="Monthly Sales Report",
                report_type="invoice",
                ip_address="172.16.0.1"
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['action'] == "TEMPLATE_CREATE"
            assert call_kwargs['resource_type'] == "report_template"
            assert call_kwargs['resource_id'] == "10"
            assert call_kwargs['resource_name'] == "Monthly Sales Report"
            
            details = call_kwargs['details']
            assert details['template_name'] == "Monthly Sales Report"
            assert details['report_type'] == "invoice"
    
    def test_log_template_operation_share(self, db_session: Session):
        """Test logging template sharing."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            audit_service.log_template_operation(
                user_id=1,
                user_email="owner@example.com",
                action="SHARE",
                template_id=5,
                template_name="Expense Summary",
                shared_with=[2, 3, 4],
                status="success"
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['action'] == "TEMPLATE_SHARE"
            details = call_kwargs['details']
            assert details['shared_with'] == [2, 3, 4]
    
    def test_log_schedule_operation(self, db_session: Session):
        """Test logging scheduled report operations."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            schedule_config = {
                'frequency': 'weekly',
                'day_of_week': 'monday',
                'time': '09:00'
            }
            
            audit_service.log_schedule_operation(
                user_id=2,
                user_email="scheduler@example.com",
                action="CREATE",
                schedule_id=15,
                template_id=8,
                template_name="Weekly Revenue Report",
                schedule_config=schedule_config,
                recipients=["manager@example.com", "cfo@example.com"]
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['action'] == "SCHEDULE_CREATE"
            assert call_kwargs['resource_type'] == "scheduled_report"
            assert call_kwargs['resource_id'] == "15"
            assert call_kwargs['resource_name'] == "schedule_for_Weekly Revenue Report"
            
            details = call_kwargs['details']
            assert details['template_id'] == 8
            assert details['schedule_config'] == schedule_config
            assert details['recipients'] == ["manager@example.com", "cfo@example.com"]
    
    def test_log_scheduled_execution(self, db_session: Session):
        """Test logging automated scheduled report execution."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            audit_service.log_scheduled_execution(
                schedule_id=20,
                template_id=12,
                template_name="Daily Summary",
                report_id="auto_report_789",
                recipients=["team@example.com"],
                execution_time_ms=3000,
                status="success"
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['user_id'] == 0  # System user
            assert call_kwargs['user_email'] == "system@automated"
            assert call_kwargs['action'] == "REPORT_GENERATE_SCHEDULED"
            assert call_kwargs['resource_type'] == "scheduled_report"
            assert call_kwargs['resource_id'] == "20"
            
            details = call_kwargs['details']
            assert details['automated'] is True
            assert details['report_id'] == "auto_report_789"
            assert details['execution_time_ms'] == 3000
    
    def test_log_access_attempt_denied(self, db_session: Session):
        """Test logging denied access attempts."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            audit_service.log_access_attempt(
                user_id=5,
                user_email="unauthorized@example.com",
                resource_type="report",
                resource_id="secret_report_123",
                action="VIEW",
                access_granted=False,
                reason="Insufficient permissions - viewer role cannot access admin reports",
                ip_address="203.0.113.1"
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['action'] == "ACCESS_VIEW"
            assert call_kwargs['status'] == "access_denied"
            assert call_kwargs['error_message'] == "Insufficient permissions - viewer role cannot access admin reports"
            
            details = call_kwargs['details']
            assert details['access_granted'] is False
            assert details['attempted_action'] == "VIEW"
    
    def test_log_access_attempt_granted(self, db_session: Session):
        """Test logging successful access attempts."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            audit_service.log_access_attempt(
                user_id=1,
                user_email="admin@example.com",
                resource_type="template",
                resource_id="template_456",
                action="EDIT",
                access_granted=True,
                reason="Template owner"
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['status'] == "success"
            assert call_kwargs['error_message'] is None
            
            details = call_kwargs['details']
            assert details['access_granted'] is True
            assert details['reason'] == "Template owner"
    
    def test_log_data_redaction(self, db_session: Session):
        """Test logging data redaction operations."""
        audit_service = ReportAuditService(db_session)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_audit_log = Mock()
            mock_log.return_value = mock_audit_log
            
            audit_service.log_data_redaction(
                user_id=3,
                user_email="user@example.com",
                report_id="report_with_pii",
                redacted_fields=["email", "phone", "ssn", "credit_card"],
                redaction_reason="Standard privacy protection for user role"
            )
            
            call_kwargs = mock_log.call_args[1]
            
            assert call_kwargs['action'] == "DATA_REDACTION"
            assert call_kwargs['resource_type'] == "report"
            assert call_kwargs['resource_id'] == "report_with_pii"
            assert call_kwargs['status'] == "success"
            
            details = call_kwargs['details']
            assert details['redacted_fields'] == ["email", "phone", "ssn", "credit_card"]
            assert details['redaction_reason'] == "Standard privacy protection for user role"
            assert details['redaction_applied'] is True
    
    def test_get_user_report_activity(self, db_session: Session):
        """Test retrieving user report activity."""
        audit_service = ReportAuditService(db_session)
        
        # Mock audit logs
        mock_logs = [
            Mock(id=1, action="REPORT_GENERATE", created_at=datetime.utcnow()),
            Mock(id=2, action="TEMPLATE_CREATE", created_at=datetime.utcnow() - timedelta(hours=1)),
            Mock(id=3, action="REPORT_DOWNLOAD", created_at=datetime.utcnow() - timedelta(hours=2))
        ]
        
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_logs
            
            result = audit_service.get_user_report_activity(
                user_id=1,
                start_date=datetime.utcnow() - timedelta(days=7),
                limit=50
            )
            
            assert len(result) == 3
            assert result[0].action == "REPORT_GENERATE"
    
    def test_get_report_access_logs(self, db_session: Session):
        """Test retrieving access logs for a specific report."""
        audit_service = ReportAuditService(db_session)
        
        mock_logs = [
            Mock(id=1, action="REPORT_GENERATE", user_id=1),
            Mock(id=2, action="REPORT_DOWNLOAD", user_id=1),
            Mock(id=3, action="ACCESS_VIEW", user_id=2, status="access_denied")
        ]
        
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_logs
            
            result = audit_service.get_report_access_logs("report_123")
            
            assert len(result) == 3
            # Should include both successful and failed access attempts
            assert any(log.status == "access_denied" for log in result)
    
    def test_get_failed_operations(self, db_session: Session):
        """Test retrieving failed operations for monitoring."""
        audit_service = ReportAuditService(db_session)
        
        mock_failed_logs = [
            Mock(id=1, action="REPORT_GENERATE", status="error", error_message="Database timeout"),
            Mock(id=2, action="ACCESS_VIEW", status="access_denied", error_message="Insufficient permissions")
        ]
        
        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_failed_logs
            
            result = audit_service.get_failed_operations(
                start_date=datetime.utcnow() - timedelta(hours=24)
            )
            
            assert len(result) == 2
            assert all(log.status in ["error", "access_denied"] for log in result)


class TestExtractRequestInfo:
    """Test request information extraction utility."""
    
    def test_extract_request_info_with_headers(self):
        """Test extracting IP and user agent from request headers."""
        mock_request = Mock()
        mock_request.headers = {
            "X-Forwarded-For": "203.0.113.1, 198.51.100.1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        ip_address, user_agent = extract_request_info(mock_request)
        
        assert ip_address == "203.0.113.1"  # First IP from X-Forwarded-For
        assert "Mozilla/5.0" in user_agent
    
    def test_extract_request_info_with_real_ip(self):
        """Test extracting IP from X-Real-IP header."""
        mock_request = Mock()
        mock_request.headers = {
            "X-Real-IP": "198.51.100.5",
            "User-Agent": "curl/7.68.0"
        }
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        
        ip_address, user_agent = extract_request_info(mock_request)
        
        assert ip_address == "198.51.100.5"
        assert user_agent == "curl/7.68.0"
    
    def test_extract_request_info_fallback_to_client(self):
        """Test falling back to client IP when no proxy headers."""
        mock_request = Mock()
        mock_request.headers = {
            "User-Agent": "PostmanRuntime/7.28.0"
        }
        mock_request.client = Mock()
        mock_request.client.host = "10.0.0.100"
        
        ip_address, user_agent = extract_request_info(mock_request)
        
        assert ip_address == "10.0.0.100"
        assert user_agent == "PostmanRuntime/7.28.0"
    
    def test_extract_request_info_no_client(self):
        """Test handling request with no client information."""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.client = None
        
        ip_address, user_agent = extract_request_info(mock_request)
        
        assert ip_address is None
        assert user_agent is None
    
    def test_extract_request_info_none_request(self):
        """Test handling None request."""
        ip_address, user_agent = extract_request_info(None)
        
        assert ip_address is None
        assert user_agent is None


class TestAuditLoggingIntegration:
    """Integration tests for audit logging in report endpoints."""
    
    def test_report_generation_audit_logging(self, client: TestClient):
        """Test that report generation creates audit logs."""
        user = Mock()
        user.id = 1
        user.email = "test@example.com"
        user.role = "user"
        
        with patch('routers.reports.get_current_user', return_value=user):
            with patch('routers.reports.ReportAuditService') as mock_audit_service_class:
                mock_audit_service = Mock()
                mock_audit_service_class.return_value = mock_audit_service
                
                with patch('routers.reports.ReportSecurityService') as mock_security_service_class:
                    mock_security_service = Mock()
                    mock_security_service.validate_report_access.return_value = True
                    mock_security_service.validate_export_format.return_value = True
                    mock_security_service.can_access_report_type.return_value = True
                    mock_security_service.get_data_access_filters.return_value = {}
                    mock_security_service_class.return_value = mock_security_service
                    
                    with patch('routers.reports.ReportRateLimiter') as mock_rate_limiter_class:
                        mock_rate_limiter = Mock()
                        mock_rate_limiter.check_rate_limit.return_value = True
                        mock_rate_limiter_class.return_value = mock_rate_limiter
                        
                        with patch('routers.reports.get_report_service') as mock_get_service:
                            mock_service = Mock()
                            mock_result = Mock()
                            mock_result.success = True
                            mock_result.data = {'data': [{'test': 'data'}]}
                            mock_result.report_id = "test_report_123"
                            mock_service.generate_report.return_value = mock_result
                            mock_get_service.return_value = mock_service
                            
                            response = client.post("/api/v1/reports/generate", json={
                                "report_type": "client",
                                "export_format": "json",
                                "filters": {"date_from": "2024-01-01"}
                            })
                            
                            # Verify audit logging was called
                            mock_audit_service.log_report_generation.assert_called()
                            call_args = mock_audit_service.log_report_generation.call_args[1]
                            assert call_args['user_id'] == 1
                            assert call_args['user_email'] == "test@example.com"
                            assert call_args['status'] == "success"
    
    def test_failed_report_generation_audit_logging(self, client: TestClient):
        """Test that failed report generation creates error audit logs."""
        user = Mock()
        user.id = 1
        user.email = "test@example.com"
        user.role = "user"
        
        with patch('routers.reports.get_current_user', return_value=user):
            with patch('routers.reports.ReportAuditService') as mock_audit_service_class:
                mock_audit_service = Mock()
                mock_audit_service_class.return_value = mock_audit_service
                
                with patch('routers.reports.ReportSecurityService') as mock_security_service_class:
                    mock_security_service = Mock()
                    mock_security_service.validate_report_access.return_value = True
                    mock_security_service.validate_export_format.return_value = True
                    mock_security_service.can_access_report_type.return_value = True
                    mock_security_service.get_data_access_filters.return_value = {}
                    mock_security_service_class.return_value = mock_security_service
                    
                    with patch('routers.reports.ReportRateLimiter') as mock_rate_limiter_class:
                        mock_rate_limiter = Mock()
                        mock_rate_limiter.check_rate_limit.return_value = True
                        mock_rate_limiter_class.return_value = mock_rate_limiter
                        
                        with patch('routers.reports.get_report_service') as mock_get_service:
                            mock_service = Mock()
                            mock_result = Mock()
                            mock_result.success = False
                            mock_result.error_message = "Invalid date range"
                            mock_service.generate_report.return_value = mock_result
                            mock_get_service.return_value = mock_service
                            
                            response = client.post("/api/v1/reports/generate", json={
                                "report_type": "client",
                                "export_format": "json",
                                "filters": {"date_from": "invalid_date"}
                            })
                            
                            # Verify error audit logging was called
                            mock_audit_service.log_report_generation.assert_called()
                            call_args = mock_audit_service.log_report_generation.call_args[1]
                            assert call_args['status'] == "error"
                            assert call_args['error_message'] == "Invalid date range"


@pytest.fixture
def db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)