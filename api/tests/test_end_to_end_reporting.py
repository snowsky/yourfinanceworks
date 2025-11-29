"""
End-to-End Tests for Reporting Module

This module contains comprehensive end-to-end tests that simulate real user workflows
from the API layer through to file generation and delivery.

Requirements covered: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.models.models_per_tenant import User, Client, Invoice, Payment
from core.schemas.report import ReportType, ExportFormat
from tests.test_comprehensive_reporting_suite import TestDataFactory


class TestEndToEndReportGeneration:
    """End-to-end tests for complete report generation workflows"""
    
    @pytest.fixture
    def client(self):
        """Test client for API calls"""
        return TestClient(app)
    
    @pytest.fixture
    def authenticated_user(self):
        """Mock authenticated user"""
        user = TestDataFactory.create_user(1, "test@example.com", "user", 1)
        return user
    
    @pytest.fixture
    def admin_user(self):
        """Mock admin user"""
        user = TestDataFactory.create_user(2, "admin@example.com", "admin", 1)
        return user
    
    def test_complete_client_report_e2e(self, client, authenticated_user):
        """Test complete client report generation from API to file"""
        # Mock authentication
        with patch('routers.reports.get_current_user', return_value=authenticated_user):
            with patch('routers.reports.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                # Mock the entire report service chain
                with patch('routers.reports.ReportService') as mock_service_class:
                    mock_service = Mock()
                    mock_service_class.return_value = mock_service
                    
                    # Mock successful report generation
                    mock_service.generate_report.return_value = Mock(
                        success=True,
                        file_path="/tmp/client_report_e2e.json",
                        report_id="e2e_client_123",
                        file_size=2048,
                        record_count=25,
                        execution_time_ms=1500
                    )
                    
                    # Make API request
                    response = client.post("/api/v1/reports/generate", json={
                        "report_type": "client",
                        "export_format": "json",
                        "filters": {
                            "status": ["active"],
                            "date_from": "2024-01-01",
                            "date_to": "2024-12-31"
                        },
                        "columns": ["name", "email", "total_invoices", "total_amount"]
                    })
                    
                    # Verify API response
                    assert response.status_code == 200
                    response_data = response.json()
                    
                    assert response_data["success"] is True
                    assert response_data["report_id"] == "e2e_client_123"
                    assert response_data["file_path"] == "/tmp/client_report_e2e.json"
                    assert response_data["record_count"] == 25
                    
                    # Verify service was called with correct parameters
                    mock_service.generate_report.assert_called_once()
                    call_args = mock_service.generate_report.call_args
                    
                    assert call_args[1]["report_type"] == "client"
                    assert call_args[1]["export_format"] == "json"
                    assert call_args[1]["user_id"] == authenticated_user.id
    
    def test_template_creation_and_usage_e2e(self, client, authenticated_user):
        """Test complete template creation and usage workflow"""
        with patch('routers.reports.get_current_user', return_value=authenticated_user):
            with patch('routers.reports.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                # Step 1: Create template
                with patch('routers.reports.ReportTemplateService') as mock_template_service_class:
                    mock_template_service = Mock()
                    mock_template_service_class.return_value = mock_template_service
                    
                    created_template = TestDataFactory.create_report_template(
                        1, authenticated_user.id, "invoice", "Monthly Invoice Report"
                    )
                    mock_template_service.create_template.return_value = created_template
                    
                    # Create template via API
                    create_response = client.post("/api/v1/reports/templates", json={
                        "name": "Monthly Invoice Report",
                        "report_type": "invoice",
                        "filters": {
                            "status": ["paid", "pending"],
                            "date_from": "2024-01-01",
                            "date_to": "2024-01-31"
                        },
                        "columns": ["invoice_number", "client_name", "total_amount", "status"],
                        "formatting": {
                            "currency": "USD",
                            "date_format": "MM/DD/YYYY"
                        }
                    })
                    
                    assert create_response.status_code == 201
                    template_data = create_response.json()
                    assert template_data["id"] == 1
                    assert template_data["name"] == "Monthly Invoice Report"
                
                # Step 2: Generate report from template
                with patch('routers.reports.ReportTemplateService') as mock_template_service_class:
                    with patch('routers.reports.ReportService') as mock_report_service_class:
                        mock_template_service = Mock()
                        mock_report_service = Mock()
                        mock_template_service_class.return_value = mock_template_service
                        mock_report_service_class.return_value = mock_report_service
                        
                        # Mock template retrieval
                        mock_template_service.get_template.return_value = created_template
                        
                        # Mock report generation
                        mock_report_service.generate_report.return_value = Mock(
                            success=True,
                            file_path="/tmp/template_report_e2e.pdf",
                            report_id="template_report_456",
                            template_id=1
                        )
                        
                        # Generate report from template
                        generate_response = client.post(f"/api/v1/reports/templates/{created_template.id}/generate", json={
                            "export_format": "pdf"
                        })
                        
                        assert generate_response.status_code == 200
                        report_data = generate_response.json()
                        
                        assert report_data["success"] is True
                        assert report_data["template_id"] == 1
                        assert report_data["file_path"] == "/tmp/template_report_e2e.pdf"
    
    def test_scheduled_report_full_lifecycle_e2e(self, client, authenticated_user):
        """Test complete scheduled report lifecycle"""
        with patch('routers.reports.get_current_user', return_value=authenticated_user):
            with patch('routers.reports.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                # Step 1: Create template for scheduling
                template = TestDataFactory.create_report_template(
                    1, authenticated_user.id, "payment", "Weekly Payment Report"
                )
                
                # Step 2: Create scheduled report
                with patch('routers.reports.ScheduledReportService') as mock_scheduled_service_class:
                    mock_scheduled_service = Mock()
                    mock_scheduled_service_class.return_value = mock_scheduled_service
                    
                    scheduled_report = TestDataFactory.create_scheduled_report(1, template.id, authenticated_user.id)
                    mock_scheduled_service.create_scheduled_report.return_value = scheduled_report
                    
                    schedule_response = client.post("/api/v1/reports/scheduled", json={
                        "template_id": template.id,
                        "schedule_type": "weekly",
                        "schedule_config": {
                            "day_of_week": 1,  # Monday
                            "hour": 9,
                            "minute": 0
                        },
                        "recipients": ["user@example.com", "manager@example.com"],
                        "export_format": "pdf"
                    })
                    
                    assert schedule_response.status_code == 201
                    schedule_data = schedule_response.json()
                    assert schedule_data["id"] == 1
                    assert schedule_data["template_id"] == template.id
                
                # Step 3: Execute scheduled report (simulate scheduler)
                with patch('services.report_scheduler.ReportService') as mock_report_service_class:
                    with patch('services.report_scheduler.EmailService') as mock_email_service_class:
                        mock_report_service = Mock()
                        mock_email_service = Mock()
                        mock_report_service_class.return_value = mock_report_service
                        mock_email_service_class.return_value = mock_email_service
                        
                        # Mock report generation
                        mock_report_service.generate_report.return_value = Mock(
                            success=True,
                            file_path="/tmp/scheduled_payment_report.pdf",
                            report_id="scheduled_789"
                        )
                        
                        # Mock email delivery
                        mock_email_service.send_report_email.return_value = True
                        
                        # Simulate scheduler execution
                        from core.services.report_scheduler import ReportScheduler
                        scheduler = ReportScheduler(mock_db)
                        
                        with patch.object(mock_db, 'query') as mock_query:
                            mock_query.return_value.filter.return_value.all.return_value = [scheduled_report]
                            
                            results = scheduler.execute_due_reports()
                            
                            # Verify execution
                            assert len(results) == 1
                            assert results[0]['success'] is True
                            assert results[0]['report_id'] == "scheduled_789"
                            
                            # Verify email was sent to all recipients
                            assert mock_email_service.send_report_email.call_count == 2
    
    def test_report_download_e2e(self, client, authenticated_user):
        """Test complete report download workflow"""
        with patch('routers.reports.get_current_user', return_value=authenticated_user):
            with patch('routers.reports.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                # Mock report history service
                with patch('routers.reports.ReportHistoryService') as mock_history_service_class:
                    mock_history_service = Mock()
                    mock_history_service_class.return_value = mock_history_service
                    
                    # Create mock report history entry
                    report_history = Mock()
                    report_history.id = "download_test_123"
                    report_history.file_path = "/tmp/download_test_report.pdf"
                    report_history.user_id = authenticated_user.id
                    report_history.generated_at = datetime.now()
                    report_history.expires_at = datetime.now() + timedelta(days=7)
                    
                    mock_history_service.get_report_history.return_value = report_history
                    
                    # Mock file existence and content
                    with patch('os.path.exists', return_value=True):
                        with patch('builtins.open', mock_open_file(b'PDF content here')):
                            # Download report
                            download_response = client.get(f"/api/v1/reports/download/{report_history.id}")
                            
                            assert download_response.status_code == 200
                            assert download_response.headers["content-type"] == "application/pdf"
                            assert "attachment" in download_response.headers["content-disposition"]
    
    def test_report_sharing_e2e(self, client, authenticated_user, admin_user):
        """Test complete report sharing workflow"""
        with patch('routers.reports.get_current_user', return_value=authenticated_user):
            with patch('routers.reports.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                # Step 1: Generate a report
                with patch('routers.reports.ReportService') as mock_service_class:
                    mock_service = Mock()
                    mock_service_class.return_value = mock_service
                    
                    mock_service.generate_report.return_value = Mock(
                        success=True,
                        file_path="/tmp/shared_report.pdf",
                        report_id="shared_123"
                    )
                    
                    generate_response = client.post("/api/v1/reports/generate", json={
                        "report_type": "expense",
                        "export_format": "pdf",
                        "filters": {"category": ["travel", "meals"]}
                    })
                    
                    assert generate_response.status_code == 200
                    report_id = generate_response.json()["report_id"]
                
                # Step 2: Share the report
                with patch('routers.reports.ReportSharingService') as mock_sharing_service_class:
                    mock_sharing_service = Mock()
                    mock_sharing_service_class.return_value = mock_sharing_service
                    
                    share_token = "share_token_abc123"
                    mock_sharing_service.create_share_link.return_value = Mock(
                        share_token=share_token,
                        expires_at=datetime.now() + timedelta(days=7),
                        access_count=0
                    )
                    
                    share_response = client.post(f"/api/v1/reports/{report_id}/share", json={
                        "expires_in_days": 7,
                        "max_access_count": 10,
                        "require_authentication": False
                    })
                    
                    assert share_response.status_code == 200
                    share_data = share_response.json()
                    assert share_data["share_token"] == share_token
                
                # Step 3: Access shared report (simulate different user)
                with patch('routers.reports.get_current_user', return_value=None):  # Anonymous access
                    with patch('routers.reports.ReportSharingService') as mock_sharing_service_class:
                        mock_sharing_service = Mock()
                        mock_sharing_service_class.return_value = mock_sharing_service
                        
                        # Mock shared report retrieval
                        mock_sharing_service.get_shared_report.return_value = Mock(
                            report_id=report_id,
                            file_path="/tmp/shared_report.pdf",
                            is_valid=True
                        )
                        
                        with patch('os.path.exists', return_value=True):
                            with patch('builtins.open', mock_open_file(b'Shared PDF content')):
                                access_response = client.get(f"/api/v1/reports/shared/{share_token}")
                                
                                assert access_response.status_code == 200
                                assert access_response.headers["content-type"] == "application/pdf"
    
    def test_error_handling_e2e(self, client, authenticated_user):
        """Test end-to-end error handling scenarios"""
        with patch('routers.reports.get_current_user', return_value=authenticated_user):
            with patch('routers.reports.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                # Test validation error
                validation_response = client.post("/api/v1/reports/generate", json={
                    "report_type": "invalid_type",
                    "export_format": "json",
                    "filters": {}
                })
                
                assert validation_response.status_code == 422  # Validation error
                
                # Test service error
                with patch('routers.reports.ReportService') as mock_service_class:
                    mock_service = Mock()
                    mock_service_class.return_value = mock_service
                    
                    mock_service.generate_report.return_value = Mock(
                        success=False,
                        error_message="Database connection failed",
                        error_code="DB_CONNECTION_ERROR"
                    )
                    
                    service_error_response = client.post("/api/v1/reports/generate", json={
                        "report_type": "client",
                        "export_format": "json",
                        "filters": {}
                    })
                    
                    assert service_error_response.status_code == 500
                    error_data = service_error_response.json()
                    assert "Database connection failed" in error_data["detail"]["message"]
                
                # Test access denied
                with patch('routers.reports.ReportSecurityService') as mock_security_service_class:
                    mock_security_service = Mock()
                    mock_security_service_class.return_value = mock_security_service
                    
                    from core.exceptions.report_exceptions import ReportAccessDeniedException
                    mock_security_service.validate_report_access.side_effect = ReportAccessDeniedException(
                        "Insufficient permissions"
                    )
                    
                    access_denied_response = client.post("/api/v1/reports/generate", json={
                        "report_type": "client",
                        "export_format": "json",
                        "filters": {}
                    })
                    
                    assert access_denied_response.status_code == 403


class TestReportingAPIIntegration:
    """Integration tests for the reporting API endpoints"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        return TestDataFactory.create_user(1, "api_test@example.com", "user", 1)
    
    def test_api_endpoint_availability(self, client):
        """Test that all reporting API endpoints are available"""
        endpoints_to_test = [
            ("/api/v1/reports/generate", "POST"),
            ("/api/v1/reports/templates", "GET"),
            ("/api/v1/reports/templates", "POST"),
            ("/api/v1/reports/scheduled", "GET"),
            ("/api/v1/reports/scheduled", "POST"),
            ("/api/v1/reports/history", "GET"),
        ]
        
        for endpoint, method in endpoints_to_test:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            
            # Should not return 404 (endpoint exists)
            assert response.status_code != 404
            # May return 401/403 (auth required) or 422 (validation error), but endpoint exists
            assert response.status_code in [200, 401, 403, 422, 500]
    
    def test_api_authentication_required(self, client):
        """Test that API endpoints require authentication"""
        protected_endpoints = [
            ("/api/v1/reports/generate", "POST", {}),
            ("/api/v1/reports/templates", "GET", None),
            ("/api/v1/reports/templates", "POST", {}),
            ("/api/v1/reports/scheduled", "GET", None),
            ("/api/v1/reports/scheduled", "POST", {}),
        ]
        
        for endpoint, method, data in protected_endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json=data)
            
            # Should require authentication
            assert response.status_code in [401, 403]
    
    def test_api_request_validation(self, client, mock_user):
        """Test API request validation"""
        with patch('routers.reports.get_current_user', return_value=mock_user):
            with patch('routers.reports.get_db'):
                
                # Test invalid report type
                response = client.post("/api/v1/reports/generate", json={
                    "report_type": "invalid_type",
                    "export_format": "json"
                })
                assert response.status_code == 422
                
                # Test invalid export format
                response = client.post("/api/v1/reports/generate", json={
                    "report_type": "client",
                    "export_format": "invalid_format"
                })
                assert response.status_code == 422
                
                # Test missing required fields
                response = client.post("/api/v1/reports/generate", json={})
                assert response.status_code == 422
    
    def test_api_response_format(self, client, mock_user):
        """Test API response format consistency"""
        with patch('routers.reports.get_current_user', return_value=mock_user):
            with patch('routers.reports.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                with patch('routers.reports.ReportService') as mock_service_class:
                    mock_service = Mock()
                    mock_service_class.return_value = mock_service
                    
                    # Mock successful response
                    mock_service.generate_report.return_value = Mock(
                        success=True,
                        file_path="/tmp/test_report.json",
                        report_id="api_test_123",
                        file_size=1024,
                        record_count=50,
                        execution_time_ms=2000
                    )
                    
                    response = client.post("/api/v1/reports/generate", json={
                        "report_type": "client",
                        "export_format": "json",
                        "filters": {}
                    })
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    # Verify response structure
                    required_fields = ["success", "report_id", "file_path", "file_size", "record_count"]
                    for field in required_fields:
                        assert field in data
                    
                    assert data["success"] is True
                    assert isinstance(data["report_id"], str)
                    assert isinstance(data["file_size"], int)
                    assert isinstance(data["record_count"], int)


def mock_open_file(content: bytes):
    """Helper function to mock file opening"""
    from unittest.mock import mock_open
    return mock_open(read_data=content)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])