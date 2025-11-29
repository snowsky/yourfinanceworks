"""
Integration tests for the Reports API Router

Tests all report endpoints including generation, templates, scheduling,
and history with proper authentication and authorization checks.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from main import app
from core.models.models import MasterUser
from core.models.models_per_tenant import ReportTemplate, ScheduledReport, ReportHistory, Client, Invoice
from core.schemas.report import ReportType, ExportFormat, ScheduleType
from tests.conftest import TestingSessionLocal, create_test_user, create_test_client


class TestReportsRouter:
    """Test class for reports router endpoints"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def test_user(self, db_session):
        return create_test_user(db_session)
    
    @pytest.fixture
    def test_client_data(self, db_session):
        return create_test_client(db_session)
    
    @pytest.fixture
    def auth_headers(self, test_user):
        # Mock authentication - in real tests, you'd get a proper JWT token
        return {"Authorization": f"Bearer test-token-{test_user.id}"}
    
    @pytest.fixture
    def sample_template_data(self):
        return {
            "name": "Monthly Client Report",
            "report_type": ReportType.CLIENT,
            "filters": {
                "date_from": "2024-01-01T00:00:00",
                "date_to": "2024-01-31T23:59:59",
                "include_inactive": False
            },
            "columns": ["client_name", "total_invoiced", "total_paid", "outstanding_balance"],
            "formatting": {"currency": "USD"},
            "is_shared": False
        }
    
    @pytest.fixture
    def sample_schedule_data(self):
        return {
            "template_id": 1,
            "schedule_config": {
                "schedule_type": ScheduleType.MONTHLY,
                "time_of_day": "09:00",
                "day_of_month": 1,
                "timezone": "UTC"
            },
            "recipients": ["admin@example.com", "manager@example.com"],
            "export_format": ExportFormat.PDF,
            "is_active": True
        }


class TestReportTypesEndpoint(TestReportsRouter):
    """Test the /reports/types endpoint"""
    
    def test_get_report_types_success(self, client, auth_headers):
        """Test successful retrieval of report types"""
        response = client.get("/api/v1/reports/types", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "report_types" in data
        assert len(data["report_types"]) == 5  # CLIENT, INVOICE, PAYMENT, EXPENSE, STATEMENT
        
        # Check that each report type has required fields
        for report_type in data["report_types"]:
            assert "type" in report_type
            assert "name" in report_type
            assert "description" in report_type
            assert "filters" in report_type
            assert "columns" in report_type
    
    def test_get_report_types_unauthorized(self, client):
        """Test unauthorized access to report types"""
        response = client.get("/api/v1/reports/types")
        assert response.status_code == 401


class TestReportGenerationEndpoints(TestReportsRouter):
    """Test report generation endpoints"""
    
    @patch('api.services.report_service.ReportService.generate_report')
    def test_generate_report_json_success(self, mock_generate, client, auth_headers):
        """Test successful JSON report generation"""
        # Mock successful report generation
        mock_generate.return_value = MagicMock(
            success=True,
            data=MagicMock(
                report_type=ReportType.CLIENT,
                summary=MagicMock(total_records=5, total_amount=10000.0),
                data=[{"client_name": "Test Client", "total_invoiced": 5000.0}],
                metadata=MagicMock(generated_at=datetime.now())
            )
        )
        
        request_data = {
            "report_type": ReportType.CLIENT,
            "filters": {"date_from": "2024-01-01T00:00:00"},
            "export_format": ExportFormat.JSON
        }
        
        response = client.post("/api/v1/reports/generate", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
    
    @patch('api.services.report_service.ReportService.generate_report')
    def test_generate_report_pdf_background(self, mock_generate, client, auth_headers, db_session):
        """Test PDF report generation in background"""
        request_data = {
            "report_type": ReportType.INVOICE,
            "filters": {"date_from": "2024-01-01T00:00:00"},
            "export_format": ExportFormat.PDF
        }
        
        response = client.post("/api/v1/reports/generate", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "report_id" in data
        assert "download_url" in data
    
    def test_generate_report_invalid_type(self, client, auth_headers):
        """Test report generation with invalid report type"""
        request_data = {
            "report_type": "invalid_type",
            "filters": {},
            "export_format": ExportFormat.JSON
        }
        
        response = client.post("/api/v1/reports/generate", json=request_data, headers=auth_headers)
        assert response.status_code == 422  # Validation error
    
    def test_generate_report_unauthorized(self, client):
        """Test unauthorized report generation"""
        request_data = {
            "report_type": ReportType.CLIENT,
            "filters": {},
            "export_format": ExportFormat.JSON
        }
        
        response = client.post("/api/v1/reports/generate", json=request_data)
        assert response.status_code == 401
    
    @patch('api.services.report_service.ReportService.generate_report')
    def test_preview_report_success(self, mock_generate, client, auth_headers):
        """Test successful report preview"""
        mock_generate.return_value = MagicMock(
            success=True,
            data=MagicMock(
                report_type=ReportType.CLIENT,
                summary=MagicMock(total_records=2),
                data=[{"client_name": "Test Client 1"}, {"client_name": "Test Client 2"}]
            )
        )
        
        request_data = {
            "report_type": ReportType.CLIENT,
            "filters": {"date_from": "2024-01-01T00:00:00"},
            "limit": 10
        }
        
        response = client.post("/api/v1/reports/preview", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "data" in data
    
    @patch('api.services.report_service.ReportService.generate_report')
    def test_preview_report_validation_error(self, mock_generate, client, auth_headers):
        """Test report preview with validation error"""
        from api.services.report_service import ReportValidationError
        mock_generate.side_effect = ReportValidationError("Invalid date range", "date_from")
        
        request_data = {
            "report_type": ReportType.CLIENT,
            "filters": {"date_from": "invalid-date"},
            "limit": 10
        }
        
        response = client.post("/api/v1/reports/preview", json=request_data, headers=auth_headers)
        assert response.status_code == 400


class TestReportTemplateEndpoints(TestReportsRouter):
    """Test report template management endpoints"""
    
    def test_get_templates_success(self, client, auth_headers, db_session, test_user):
        """Test successful retrieval of report templates"""
        # Create test template
        template = ReportTemplate(
            name="Test Template",
            report_type=ReportType.CLIENT,
            filters={"date_from": "2024-01-01"},
            user_id=test_user.id,
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        response = client.get("/api/v1/reports/templates", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert "total" in data
        assert data["total"] >= 1
    
    def test_get_templates_with_filters(self, client, auth_headers):
        """Test template retrieval with filters"""
        params = {
            "report_type": ReportType.CLIENT,
            "include_shared": True,
            "skip": 0,
            "limit": 50
        }
        
        response = client.get("/api/v1/reports/templates", params=params, headers=auth_headers)
        assert response.status_code == 200
    
    @patch('api.services.report_service.ReportService.validate_filters')
    def test_create_template_success(self, mock_validate, client, auth_headers, sample_template_data):
        """Test successful template creation"""
        mock_validate.return_value = True
        
        response = client.post("/api/v1/reports/templates", json=sample_template_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_template_data["name"]
        assert data["report_type"] == sample_template_data["report_type"]
    
    def test_create_template_invalid_data(self, client, auth_headers):
        """Test template creation with invalid data"""
        invalid_data = {
            "name": "",  # Empty name
            "report_type": ReportType.CLIENT,
            "filters": {}
        }
        
        response = client.post("/api/v1/reports/templates", json=invalid_data, headers=auth_headers)
        assert response.status_code == 422
    
    def test_update_template_success(self, client, auth_headers, db_session, test_user):
        """Test successful template update"""
        # Create test template
        template = ReportTemplate(
            name="Original Template",
            report_type=ReportType.CLIENT,
            filters={"date_from": "2024-01-01"},
            user_id=test_user.id,
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        update_data = {
            "name": "Updated Template",
            "filters": {"date_from": "2024-02-01"}
        }
        
        response = client.put(f"/api/v1/reports/templates/{template.id}", json=update_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Template"
    
    def test_update_template_not_found(self, client, auth_headers):
        """Test updating non-existent template"""
        update_data = {"name": "Updated Template"}
        
        response = client.put("/api/v1/reports/templates/99999", json=update_data, headers=auth_headers)
        assert response.status_code == 404
    
    def test_update_template_unauthorized(self, client, auth_headers, db_session):
        """Test updating template owned by another user"""
        # Create template owned by different user
        template = ReportTemplate(
            name="Other User Template",
            report_type=ReportType.CLIENT,
            filters={},
            user_id=99999,  # Different user
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        update_data = {"name": "Hacked Template"}
        
        response = client.put(f"/api/v1/reports/templates/{template.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 403
    
    def test_delete_template_success(self, client, auth_headers, db_session, test_user):
        """Test successful template deletion"""
        template = ReportTemplate(
            name="Template to Delete",
            report_type=ReportType.CLIENT,
            filters={},
            user_id=test_user.id,
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        response = client.delete(f"/api/v1/reports/templates/{template.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_delete_template_not_found(self, client, auth_headers):
        """Test deleting non-existent template"""
        response = client.delete("/api/v1/reports/templates/99999", headers=auth_headers)
        assert response.status_code == 404


class TestScheduledReportEndpoints(TestReportsRouter):
    """Test scheduled report management endpoints"""
    
    def test_get_scheduled_reports_success(self, client, auth_headers):
        """Test successful retrieval of scheduled reports"""
        response = client.get("/api/v1/reports/scheduled", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "scheduled_reports" in data
        assert "total" in data
    
    def test_get_scheduled_reports_with_filters(self, client, auth_headers):
        """Test scheduled reports retrieval with filters"""
        params = {
            "active_only": True,
            "skip": 0,
            "limit": 50
        }
        
        response = client.get("/api/v1/reports/scheduled", params=params, headers=auth_headers)
        assert response.status_code == 200
    
    def test_create_scheduled_report_success(self, client, auth_headers, db_session, test_user, sample_schedule_data):
        """Test successful scheduled report creation"""
        # Create template first
        template = ReportTemplate(
            name="Schedule Template",
            report_type=ReportType.CLIENT,
            filters={},
            user_id=test_user.id,
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        sample_schedule_data["template_id"] = template.id
        
        response = client.post("/api/v1/reports/scheduled", json=sample_schedule_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["template_id"] == template.id
        assert data["is_active"] is True
    
    def test_create_scheduled_report_template_not_found(self, client, auth_headers, sample_schedule_data):
        """Test scheduled report creation with non-existent template"""
        sample_schedule_data["template_id"] = 99999
        
        response = client.post("/api/v1/reports/scheduled", json=sample_schedule_data, headers=auth_headers)
        assert response.status_code == 404
    
    def test_create_scheduled_report_unauthorized_template(self, client, auth_headers, db_session, sample_schedule_data):
        """Test scheduled report creation with unauthorized template"""
        # Create template owned by different user
        template = ReportTemplate(
            name="Other User Template",
            report_type=ReportType.CLIENT,
            filters={},
            user_id=99999,  # Different user
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        sample_schedule_data["template_id"] = template.id
        
        response = client.post("/api/v1/reports/scheduled", json=sample_schedule_data, headers=auth_headers)
        assert response.status_code == 403
    
    def test_update_scheduled_report_success(self, client, auth_headers, db_session, test_user):
        """Test successful scheduled report update"""
        # Create template and scheduled report
        template = ReportTemplate(
            name="Schedule Template",
            report_type=ReportType.CLIENT,
            filters={},
            user_id=test_user.id,
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        scheduled_report = ScheduledReport(
            template_id=template.id,
            schedule_config={
                "schedule_type": "monthly",
                "day_of_month": 1
            },
            recipients=["test@example.com"],
            export_format=ExportFormat.PDF,
            is_active=True
        )
        db_session.add(scheduled_report)
        db_session.commit()
        
        update_data = {
            "recipients": ["updated@example.com", "admin@example.com"],
            "is_active": False
        }
        
        response = client.put(f"/api/v1/reports/scheduled/{scheduled_report.id}", json=update_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["recipients"]) == 2
        assert data["is_active"] is False
    
    def test_delete_scheduled_report_success(self, client, auth_headers, db_session, test_user):
        """Test successful scheduled report deletion"""
        # Create template and scheduled report
        template = ReportTemplate(
            name="Schedule Template",
            report_type=ReportType.CLIENT,
            filters={},
            user_id=test_user.id,
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        scheduled_report = ScheduledReport(
            template_id=template.id,
            schedule_config={"schedule_type": "monthly"},
            recipients=["test@example.com"],
            export_format=ExportFormat.PDF,
            is_active=True
        )
        db_session.add(scheduled_report)
        db_session.commit()
        
        response = client.delete(f"/api/v1/reports/scheduled/{scheduled_report.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestReportHistoryEndpoints(TestReportsRouter):
    """Test report history and download endpoints"""
    
    def test_get_report_history_success(self, client, auth_headers, db_session, test_user):
        """Test successful retrieval of report history"""
        # Create test report history
        report_history = ReportHistory(
            report_type=ReportType.CLIENT,
            parameters={"filters": {"date_from": "2024-01-01"}},
            status="completed",
            generated_by=test_user.id,
            generated_at=datetime.now()
        )
        db_session.add(report_history)
        db_session.commit()
        
        response = client.get("/api/v1/reports/history", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        assert "total" in data
        assert data["total"] >= 1
    
    def test_get_report_history_with_filters(self, client, auth_headers):
        """Test report history retrieval with filters"""
        params = {
            "report_type": ReportType.CLIENT,
            "status": "completed",
            "skip": 0,
            "limit": 50
        }
        
        response = client.get("/api/v1/reports/history", params=params, headers=auth_headers)
        assert response.status_code == 200
    
    def test_download_report_success(self, client, auth_headers, db_session, test_user):
        """Test successful report download"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            f.write("Test PDF content")
            temp_file_path = f.name
        
        try:
            # Create report history with file
            report_history = ReportHistory(
                report_type=ReportType.CLIENT,
                parameters={"filters": {}},
                status="completed",
                generated_by=test_user.id,
                generated_at=datetime.now(),
                file_path=temp_file_path,
                expires_at=datetime.now() + timedelta(days=30)
            )
            db_session.add(report_history)
            db_session.commit()
            
            response = client.get(f"/api/v1/reports/download/{report_history.id}", headers=auth_headers)
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def test_download_report_not_found(self, client, auth_headers):
        """Test downloading non-existent report"""
        response = client.get("/api/v1/reports/download/99999", headers=auth_headers)
        assert response.status_code == 404
    
    def test_download_report_not_ready(self, client, auth_headers, db_session, test_user):
        """Test downloading report that's not ready"""
        report_history = ReportHistory(
            report_type=ReportType.CLIENT,
            parameters={"filters": {}},
            status="generating",  # Not completed
            generated_by=test_user.id,
            generated_at=datetime.now()
        )
        db_session.add(report_history)
        db_session.commit()
        
        response = client.get(f"/api/v1/reports/download/{report_history.id}", headers=auth_headers)
        assert response.status_code == 400
    
    def test_download_report_expired(self, client, auth_headers, db_session, test_user):
        """Test downloading expired report"""
        report_history = ReportHistory(
            report_type=ReportType.CLIENT,
            parameters={"filters": {}},
            status="completed",
            generated_by=test_user.id,
            generated_at=datetime.now(),
            file_path="/tmp/test.pdf",
            expires_at=datetime.now() - timedelta(days=1)  # Expired
        )
        db_session.add(report_history)
        db_session.commit()
        
        response = client.get(f"/api/v1/reports/download/{report_history.id}", headers=auth_headers)
        assert response.status_code == 410
    
    def test_regenerate_report_success(self, client, auth_headers, db_session, test_user):
        """Test successful report regeneration"""
        # Create original report history
        report_history = ReportHistory(
            report_type=ReportType.CLIENT,
            parameters={
                "filters": {"date_from": "2024-01-01"},
                "export_format": ExportFormat.JSON
            },
            status="completed",
            generated_by=test_user.id,
            generated_at=datetime.now()
        )
        db_session.add(report_history)
        db_session.commit()
        
        with patch('api.services.report_service.ReportService.generate_report') as mock_generate:
            mock_generate.return_value = MagicMock(success=True, data=MagicMock())
            
            response = client.post(f"/api/v1/reports/regenerate/{report_history.id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestReportAuthorizationAndSecurity(TestReportsRouter):
    """Test authorization and security aspects of the reports API"""
    
    def test_viewer_role_restrictions(self, client):
        """Test that viewer role users cannot generate reports"""
        # This would require mocking the RBAC system to simulate a viewer user
        # For now, we test the unauthorized case
        request_data = {
            "report_type": ReportType.CLIENT,
            "filters": {},
            "export_format": ExportFormat.JSON
        }
        
        response = client.post("/api/v1/reports/generate", json=request_data)
        assert response.status_code == 401
    
    def test_template_access_control(self, client, auth_headers, db_session):
        """Test that users cannot access templates they don't own"""
        # Create template owned by different user
        template = ReportTemplate(
            name="Private Template",
            report_type=ReportType.CLIENT,
            filters={},
            user_id=99999,  # Different user
            is_shared=False
        )
        db_session.add(template)
        db_session.commit()
        
        # Try to update the template
        update_data = {"name": "Hacked Template"}
        response = client.put(f"/api/v1/reports/templates/{template.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 403
        
        # Try to delete the template
        response = client.delete(f"/api/v1/reports/templates/{template.id}", headers=auth_headers)
        assert response.status_code == 403
    
    def test_report_history_isolation(self, client, auth_headers, db_session):
        """Test that users can only see their own report history"""
        # Create report history for different user
        report_history = ReportHistory(
            report_type=ReportType.CLIENT,
            parameters={"filters": {}},
            status="completed",
            generated_by=99999,  # Different user
            generated_at=datetime.now()
        )
        db_session.add(report_history)
        db_session.commit()
        
        # Try to download the report
        response = client.get(f"/api/v1/reports/download/{report_history.id}", headers=auth_headers)
        assert response.status_code == 404  # Should not be found for this user
    
    def test_input_validation(self, client, auth_headers):
        """Test input validation for various endpoints"""
        # Test invalid report generation request
        invalid_requests = [
            {"report_type": "invalid", "filters": {}},
            {"report_type": ReportType.CLIENT, "filters": "not_a_dict"},
            {"report_type": ReportType.CLIENT, "export_format": "invalid_format"}
        ]
        
        for invalid_request in invalid_requests:
            response = client.post("/api/v1/reports/generate", json=invalid_request, headers=auth_headers)
            assert response.status_code in [400, 422]
        
        # Test invalid template creation
        invalid_templates = [
            {"name": "", "report_type": ReportType.CLIENT},  # Empty name
            {"name": "Test", "report_type": "invalid"},  # Invalid type
            {"name": "Test", "report_type": ReportType.CLIENT, "filters": "not_a_dict"}  # Invalid filters
        ]
        
        for invalid_template in invalid_templates:
            response = client.post("/api/v1/reports/templates", json=invalid_template, headers=auth_headers)
            assert response.status_code in [400, 422]


if __name__ == "__main__":
    pytest.main([__file__])