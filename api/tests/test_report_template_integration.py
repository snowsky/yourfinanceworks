"""
Integration tests for Report Template Service with Report Service

Tests the integration between template management and report generation.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.services.report_template_service import ReportTemplateService
from core.services.report_service import ReportService
from core.schemas.report import (
    ReportTemplateCreate, ReportType, ExportFormat, ReportResult
)
from core.models.models_per_tenant import ReportTemplate, User


class TestReportTemplateIntegration:
    """Integration test cases for template service with report service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def template_service(self, mock_db):
        """Template service instance with mocked database"""
        return ReportTemplateService(mock_db)
    
    @pytest.fixture
    def sample_user(self):
        """Sample user for testing"""
        return User(
            id=1,
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
    
    @pytest.fixture
    def sample_template(self, sample_user):
        """Sample template database object"""
        return ReportTemplate(
            id=1,
            name="Test Invoice Report",
            report_type="invoice",
            filters={
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
                "status": ["sent", "paid"]
            },
            columns=["number", "client_name", "amount", "status"],
            formatting={"currency": "USD", "date_format": "YYYY-MM-DD"},
            user_id=sample_user.id,
            is_shared=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    @patch('core.services.report_template_service.ReportService')
    def test_template_based_report_generation_integration(
        self, 
        mock_report_service_class, 
        template_service, 
        mock_db, 
        sample_template
    ):
        """Test complete workflow of template-based report generation"""
        # Mock template retrieval
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Mock report service
        mock_report_service = Mock()
        mock_successful_result = Mock()
        mock_successful_result.success = True
        mock_successful_result.data = Mock()
        mock_successful_result.data.report_type = "invoice"
        mock_successful_result.data.summary = Mock()
        mock_successful_result.data.data = [{"invoice_id": 1, "amount": 100}]
        
        mock_report_service.generate_report.return_value = mock_successful_result
        mock_report_service.validate_export_format.return_value = ExportFormat.PDF
        mock_report_service_class.return_value = mock_report_service
        
        # Generate report from template
        result = template_service.generate_report_from_template(
            template_id=sample_template.id,
            user_id=sample_template.user_id,
            export_format="pdf"
        )
        
        # Verify the integration
        assert result.success == True
        
        # Verify report service was called with correct parameters
        mock_report_service.generate_report.assert_called_once()
        call_args = mock_report_service.generate_report.call_args
        
        # Check that the report type matches template
        assert call_args[1]['report_type'] == ReportType.INVOICE
        
        # Check that template filters were used
        called_filters = call_args[1]['filters']
        assert called_filters['date_from'] == "2024-01-01"
        assert called_filters['date_to'] == "2024-12-31"
        assert called_filters['status'] == ["sent", "paid"]
        
        # Check that user_id was passed
        assert call_args[1]['user_id'] == sample_template.user_id
    
    @patch('core.services.report_template_service.ReportService')
    def test_template_with_filter_overrides_integration(
        self, 
        mock_report_service_class, 
        template_service, 
        mock_db, 
        sample_template
    ):
        """Test template-based report generation with filter overrides"""
        # Mock template retrieval
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Mock report service
        mock_report_service = Mock()
        mock_successful_result = Mock()
        mock_successful_result.success = True
        mock_report_service.generate_report.return_value = mock_successful_result
        mock_report_service.validate_export_format.return_value = ExportFormat.CSV
        mock_report_service_class.return_value = mock_report_service
        
        # Filter overrides
        filter_overrides = {
            "status": ["paid"],  # Override template status
            "amount_min": 50     # Add new filter
        }
        
        # Generate report from template with overrides
        result = template_service.generate_report_from_template(
            template_id=sample_template.id,
            user_id=sample_template.user_id,
            filter_overrides=filter_overrides,
            export_format="csv"
        )
        
        # Verify the integration
        assert result.success == True
        
        # Verify report service was called with merged filters
        call_args = mock_report_service.generate_report.call_args
        called_filters = call_args[1]['filters']
        
        # Check that overrides were applied
        assert called_filters['status'] == ["paid"]  # Overridden
        assert called_filters['amount_min'] == 50    # Added
        
        # Check that non-overridden template filters remain
        assert called_filters['date_from'] == "2024-01-01"
        assert called_filters['date_to'] == "2024-12-31"
    
    def test_template_validation_with_report_service_filters(self, template_service, mock_db):
        """Test that template filter validation uses report service validation"""
        with patch('core.services.report_template_service.ReportService') as mock_report_service_class:
            # Mock report service
            mock_report_service = Mock()
            mock_validated_filters = Mock()
            mock_validated_filters.model_dump.return_value = {
                "date_from": "2024-01-01",
                "status": ["sent"]
            }
            mock_report_service.validate_filters.return_value = mock_validated_filters
            mock_report_service_class.return_value = mock_report_service
            
            # Test filter validation
            filters = {"date_from": "2024-01-01", "status": ["sent"]}
            result = template_service.validate_template_filters(ReportType.INVOICE, filters)
            
            # Verify report service validation was used
            mock_report_service.validate_filters.assert_called_once_with(ReportType.INVOICE, filters)
            assert result == {"date_from": "2024-01-01", "status": ["sent"]}
    
    def test_template_creation_with_report_service_integration(self, template_service, mock_db):
        """Test template creation integrates properly with report service validation"""
        # Mock database queries - no existing template
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock refresh to set the created template
        def mock_refresh(obj):
            obj.id = 1
            obj.created_at = datetime.now()
            obj.updated_at = datetime.now()
        
        mock_db.refresh.side_effect = mock_refresh
        
        # Create template with valid invoice filters
        template_data = ReportTemplateCreate(
            name="Integration Test Template",
            report_type=ReportType.INVOICE,
            filters={
                "date_from": "2024-01-01",
                "status": ["sent", "paid"],
                "amount_min": 100
            },
            columns=["number", "client_name", "amount"],
            is_shared=False
        )
        
        # Create template
        result = template_service.create_template(template_data, 1)
        
        # Verify template was created successfully
        assert result.name == template_data.name
        assert result.report_type == template_data.report_type.value
        assert result.filters == template_data.filters
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    @patch('core.services.report_template_service.ReportService')
    def test_error_handling_in_template_report_generation(
        self, 
        mock_report_service_class, 
        template_service, 
        mock_db, 
        sample_template
    ):
        """Test error handling when report generation fails"""
        # Mock template retrieval
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Mock report service to return failure
        mock_report_service = Mock()
        mock_failed_result = Mock()
        mock_failed_result.success = False
        mock_failed_result.error_message = "Report generation failed"
        mock_report_service.generate_report.return_value = mock_failed_result
        mock_report_service.validate_export_format.return_value = ExportFormat.JSON
        mock_report_service_class.return_value = mock_report_service
        
        # Generate report from template
        result = template_service.generate_report_from_template(
            template_id=sample_template.id,
            user_id=sample_template.user_id,
            export_format="json"
        )
        
        # Verify error is propagated
        assert result.success == False
        assert result.error_message == "Report generation failed"
    
    def test_template_usage_stats_integration(self, template_service, mock_db, sample_template):
        """Test template usage statistics integration with report history"""
        # Mock template retrieval
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Mock report history queries
        mock_history_query = Mock()
        mock_history_query.filter.return_value = mock_history_query
        mock_history_query.count.side_effect = [5, 4, 1]  # total, successful, failed
        mock_history_query.order_by.return_value = mock_history_query
        mock_history_query.limit.return_value = mock_history_query
        
        # Mock recent usage data
        mock_recent_uses = [
            Mock(generated_at=datetime.now(), status="completed", generated_by=1),
            Mock(generated_at=datetime.now(), status="completed", generated_by=2),
            Mock(generated_at=datetime.now(), status="failed", generated_by=1)
        ]
        mock_history_query.all.return_value = mock_recent_uses
        
        # Mock the query method to return our mock query for ReportHistory
        def mock_query_side_effect(model):
            if hasattr(model, '__name__') and model.__name__ == 'ReportHistory':
                return mock_history_query
            else:
                return mock_db.query.return_value
        
        mock_db.query.side_effect = mock_query_side_effect
        
        # Get usage stats
        result = template_service.get_template_usage_stats(sample_template.id, sample_template.user_id)
        
        # Verify integration with report history
        assert result["template_id"] == sample_template.id
        assert result["total_uses"] == 5
        assert result["successful_uses"] == 4
        assert result["failed_uses"] == 1
        assert result["success_rate"] == 80.0
        assert len(result["recent_uses"]) == 3
        
        # Verify recent uses structure
        for use in result["recent_uses"]:
            assert "generated_at" in use
            assert "status" in use
            assert "generated_by" in use


class TestReportServiceTemplateIntegration:
    """Test template integration methods in ReportService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def report_service(self, mock_db):
        """Report service instance with mocked database"""
        return ReportService(mock_db)
    
    @pytest.fixture
    def sample_template_schema(self):
        """Sample template schema for testing"""
        from core.schemas.report import ReportTemplate as ReportTemplateSchema
        return ReportTemplateSchema(
            id=1,
            name="Test Template",
            report_type="invoice",
            filters={"status": ["sent"], "date_from": "2024-01-01"},
            columns=["number", "amount", "status"],
            formatting={"currency": "USD"},
            user_id=1,
            is_shared=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    def test_generate_report_from_template_method(self, report_service, sample_template_schema):
        """Test the generate_report_from_template method in ReportService"""
        with patch.object(report_service, 'generate_report') as mock_generate:
            mock_result = Mock()
            mock_result.success = True
            mock_generate.return_value = mock_result
            
            # Generate report from template
            result = report_service.generate_report_from_template(
                template=sample_template_schema,
                export_format=ExportFormat.PDF,
                user_id=1
            )
            
            # Verify the method works correctly
            assert result.success == True
            
            # Verify generate_report was called with template data
            mock_generate.assert_called_once()
            call_args = mock_generate.call_args
            
            assert call_args[1]['report_type'] == ReportType.INVOICE
            assert call_args[1]['filters']['status'] == ["sent"]
            assert call_args[1]['filters']['date_from'] == "2024-01-01"
            assert call_args[1]['export_format'] == ExportFormat.PDF
            assert call_args[1]['user_id'] == 1
    
    def test_generate_report_from_template_with_overrides(self, report_service, sample_template_schema):
        """Test template-based report generation with filter overrides"""
        with patch.object(report_service, 'generate_report') as mock_generate:
            mock_result = Mock()
            mock_result.success = True
            mock_generate.return_value = mock_result
            
            # Filter overrides
            filter_overrides = {"status": ["paid"], "amount_min": 100}
            
            # Generate report from template with overrides
            result = report_service.generate_report_from_template(
                template=sample_template_schema,
                filter_overrides=filter_overrides,
                export_format=ExportFormat.CSV,
                user_id=2
            )
            
            # Verify the method works correctly
            assert result.success == True
            
            # Verify generate_report was called with merged filters
            call_args = mock_generate.call_args
            called_filters = call_args[1]['filters']
            
            # Check overrides were applied
            assert called_filters['status'] == ["paid"]  # Overridden
            assert called_filters['amount_min'] == 100   # Added
            
            # Check template filters that weren't overridden
            assert called_filters['date_from'] == "2024-01-01"  # From template
    
    def test_preview_report_from_template_method(self, report_service, sample_template_schema):
        """Test the preview_report_from_template method"""
        with patch.object(report_service, 'generate_report_from_template') as mock_generate_from_template:
            # Mock successful report generation
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = Mock()
            mock_result.data.data = [{"id": i, "amount": i * 100} for i in range(20)]  # 20 records
            mock_result.data.summary = Mock()
            mock_result.data.summary.total_records = 20
            
            mock_generate_from_template.return_value = mock_result
            
            # Generate preview
            result = report_service.preview_report_from_template(
                template=sample_template_schema,
                limit=5
            )
            
            # Verify preview works correctly
            assert result.success == True
            assert len(result.data.data) == 5  # Limited to 5 records
            assert result.data.summary.total_records == 5  # Updated count
            
            # Verify generate_report_from_template was called correctly
            mock_generate_from_template.assert_called_once_with(
                template=sample_template_schema,
                filter_overrides=None,
                export_format=ExportFormat.JSON
            )