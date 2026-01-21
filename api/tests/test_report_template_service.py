"""
Unit tests for Report Template Service

Tests template CRUD operations, sharing functionality, validation,
and template-based report generation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.services.report_template_service import ReportTemplateService

from core.exceptions.report_exceptions import TemplateValidationError, TemplateAccessError
from core.schemas.report import (
    ReportTemplateCreate, ReportTemplateUpdate, ReportType, ExportFormat
)
from core.models.models_per_tenant import ReportTemplate, User, ReportHistory


class TestReportTemplateService:
    """Test cases for ReportTemplateService"""
    
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
    def sample_template_data(self):
        """Sample template creation data"""
        return ReportTemplateCreate(
            name="Test Invoice Report",
            report_type=ReportType.INVOICE,
            filters={
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
                "status": ["sent", "paid"]
            },
            columns=["number", "client_name", "amount", "status"],
            formatting={"currency": "USD", "date_format": "YYYY-MM-DD"},
            is_shared=False
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
    
    def test_create_template_success(self, template_service, mock_db, sample_template_data, sample_user):
        """Test successful template creation"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing template
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock the created template
        created_template = ReportTemplate(
            id=1,
            name=sample_template_data.name,
            report_type=sample_template_data.report_type.value,
            filters=sample_template_data.filters,
            columns=sample_template_data.columns,
            formatting=sample_template_data.formatting,
            user_id=sample_user.id,
            is_shared=sample_template_data.is_shared,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Mock refresh to set the created template
        def mock_refresh(obj):
            obj.id = created_template.id
            obj.created_at = created_template.created_at
            obj.updated_at = created_template.updated_at
        
        mock_db.refresh.side_effect = mock_refresh
        
        # Create template
        result = template_service.create_template(sample_template_data, sample_user.id)
        
        # Assertions
        assert result.name == sample_template_data.name
        assert result.report_type == sample_template_data.report_type.value
        assert result.filters == sample_template_data.filters
        assert result.user_id == sample_user.id
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_create_template_duplicate_name(self, template_service, mock_db, sample_template_data, sample_template):
        """Test template creation with duplicate name"""
        # Mock existing template with same name
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Attempt to create template
        with pytest.raises(TemplateValidationError) as exc_info:
            template_service.create_template(sample_template_data, sample_template.user_id)
        
        assert "already exists" in str(exc_info.value)
        assert exc_info.value.code == "DUPLICATE_TEMPLATE_NAME"
    
    def test_create_template_invalid_report_type(self, template_service, mock_db):
        """Test template creation with invalid report type"""
        # This should fail at Pydantic level before reaching our service
        with pytest.raises(ValueError):
            ReportTemplateCreate(
                name="Test Report",
                report_type="invalid_type",  # This will fail Pydantic validation
                filters={},
                columns=["col1"],
                is_shared=False
            )
    
    def test_create_template_empty_name(self, template_service, mock_db):
        """Test template creation with empty name"""
        invalid_data = ReportTemplateCreate(
            name="",
            report_type=ReportType.INVOICE,
            filters={},
            columns=["col1"],
            is_shared=False
        )
        
        with pytest.raises(TemplateValidationError) as exc_info:
            template_service.create_template(invalid_data, 1)
        
        assert "cannot be empty" in str(exc_info.value)
        assert exc_info.value.code == "EMPTY_TEMPLATE_NAME"
    
    def test_create_template_invalid_filters(self, template_service, mock_db):
        """Test template creation with invalid filters"""
        invalid_data = ReportTemplateCreate(
            name="Test Report",
            report_type=ReportType.INVOICE,
            filters={"invalid_filter": "value"},  # Invalid filter for invoice reports
            columns=["col1"],
            is_shared=False
        )
        
        with pytest.raises(TemplateValidationError) as exc_info:
            template_service.create_template(invalid_data, 1)
        
        assert "Invalid filter" in str(exc_info.value)
        assert exc_info.value.code == "INVALID_FILTER_KEY"
    
    def test_get_template_success(self, template_service, mock_db, sample_template):
        """Test successful template retrieval"""
        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Get template
        result = template_service.get_template(sample_template.id, sample_template.user_id)
        
        # Assertions
        assert result.id == sample_template.id
        assert result.name == sample_template.name
        assert result.user_id == sample_template.user_id
    
    def test_get_template_not_found(self, template_service, mock_db):
        """Test template retrieval when template not found"""
        # Mock database query returning None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Attempt to get template
        with pytest.raises(TemplateAccessError) as exc_info:
            template_service.get_template(999, 1)
        
        assert "not found or access denied" in str(exc_info.value)
        assert exc_info.value.template_id == 999
        assert exc_info.value.user_id == 1
    
    def test_get_shared_template(self, template_service, mock_db, sample_template):
        """Test accessing a shared template by different user"""
        # Make template shared
        sample_template.is_shared = True
        sample_template.user_id = 2  # Different user owns it
        
        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Get template as different user
        result = template_service.get_template(sample_template.id, 1)  # User 1 accessing user 2's shared template
        
        # Assertions
        assert result.id == sample_template.id
        assert result.is_shared == True
    
    def test_update_template_success(self, template_service, mock_db, sample_template):
        """Test successful template update"""
        # Mock database queries - first call returns template, second call returns None (no duplicate)
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_template, None]
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Update data
        update_data = ReportTemplateUpdate(
            name="Updated Template Name",
            filters={"status": ["paid"]},
            is_shared=True
        )
        
        # Update template
        result = template_service.update_template(sample_template.id, update_data, sample_template.user_id)
        
        # Assertions
        assert result.name == "Updated Template Name"
        assert result.filters == {"status": ["paid"]}
        assert result.is_shared == True
        
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_update_template_not_owner(self, template_service, mock_db):
        """Test template update by non-owner"""
        # Mock database query returning None (user doesn't own template)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        update_data = ReportTemplateUpdate(name="New Name")
        
        # Attempt to update template
        with pytest.raises(TemplateAccessError) as exc_info:
            template_service.update_template(1, update_data, 999)
        
        assert "don't have permission" in str(exc_info.value)
    
    def test_delete_template_success(self, template_service, mock_db, sample_template):
        """Test successful template deletion"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        mock_db.delete = Mock()
        mock_db.commit = Mock()
        
        # Delete template
        result = template_service.delete_template(sample_template.id, sample_template.user_id)
        
        # Assertions
        assert result == True
        mock_db.delete.assert_called_once_with(sample_template)
        mock_db.commit.assert_called_once()
    
    def test_delete_template_not_owner(self, template_service, mock_db):
        """Test template deletion by non-owner"""
        # Mock database query returning None (user doesn't own template)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Attempt to delete template
        with pytest.raises(TemplateAccessError) as exc_info:
            template_service.delete_template(1, 999)
        
        assert "don't have permission" in str(exc_info.value)
    
    def test_list_templates_user_only(self, template_service, mock_db, sample_template):
        """Test listing user's own templates"""
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [sample_template]
        
        mock_db.query.return_value = mock_query
        
        # List templates
        result = template_service.list_templates(sample_template.user_id, include_shared=False)
        
        # Assertions
        assert len(result) == 1
        assert result[0].id == sample_template.id
    
    def test_list_templates_with_shared(self, template_service, mock_db, sample_template):
        """Test listing templates including shared ones"""
        # Create shared template with proper filters
        shared_template = ReportTemplate(
            id=2,
            name="Shared Template",
            report_type="client",
            filters={"currency": "USD"},  # Add filters to avoid None validation error
            user_id=2,  # Different user
            is_shared=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [sample_template, shared_template]
        
        mock_db.query.return_value = mock_query
        
        # List templates
        result = template_service.list_templates(sample_template.user_id, include_shared=True)
        
        # Assertions
        assert len(result) == 2
    
    def test_share_template_success(self, template_service, mock_db, sample_template):
        """Test successful template sharing"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Share template
        result = template_service.share_template(sample_template.id, sample_template.user_id, True)
        
        # Assertions
        assert result.is_shared == True
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_share_template_not_owner(self, template_service, mock_db):
        """Test template sharing by non-owner"""
        # Mock database query returning None (user doesn't own template)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Attempt to share template
        with pytest.raises(TemplateAccessError) as exc_info:
            template_service.share_template(1, 999, True)
        
        assert "don't have permission" in str(exc_info.value)
    
    @patch('core.services.report_template_service.ReportService')
    def test_generate_report_from_template_success(self, mock_report_service_class, template_service, mock_db, sample_template):
        """Test successful report generation from template"""
        # Mock template retrieval
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Mock report service
        mock_report_service = Mock()
        mock_report_service.generate_report.return_value = Mock(success=True)
        mock_report_service.validate_export_format.return_value = ExportFormat.JSON
        mock_report_service_class.return_value = mock_report_service
        
        # Generate report from template
        result = template_service.generate_report_from_template(
            template_id=sample_template.id,
            user_id=sample_template.user_id,
            export_format="json"
        )
        
        # Assertions
        assert result.success == True
        mock_report_service.generate_report.assert_called_once()
    
    @patch('core.services.report_template_service.ReportService')
    def test_generate_report_from_template_with_overrides(self, mock_report_service_class, template_service, mock_db, sample_template):
        """Test report generation from template with filter overrides"""
        # Mock template retrieval
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Mock report service
        mock_report_service = Mock()
        mock_report_service.generate_report.return_value = Mock(success=True)
        mock_report_service.validate_export_format.return_value = ExportFormat.PDF
        mock_report_service_class.return_value = mock_report_service
        
        # Filter overrides
        filter_overrides = {"status": ["paid"]}
        
        # Generate report from template
        result = template_service.generate_report_from_template(
            template_id=sample_template.id,
            user_id=sample_template.user_id,
            filter_overrides=filter_overrides,
            export_format="pdf"
        )
        
        # Verify that generate_report was called with merged filters
        call_args = mock_report_service.generate_report.call_args
        called_filters = call_args[1]['filters']
        
        # Should contain both template filters and overrides
        assert "date_from" in called_filters  # From template
        assert called_filters["status"] == ["paid"]  # Override
    
    @patch('core.services.report_template_service.ReportService')
    def test_validate_template_filters_success(self, mock_report_service_class, template_service, mock_db):
        """Test successful template filter validation"""
        # Mock report service
        mock_report_service = Mock()
        mock_validated_filters = Mock()
        mock_validated_filters.model_dump.return_value = {"date_from": "2024-01-01"}
        mock_report_service.validate_filters.return_value = mock_validated_filters
        mock_report_service_class.return_value = mock_report_service
        
        # Validate filters
        filters = {"date_from": "2024-01-01"}
        result = template_service.validate_template_filters(ReportType.INVOICE, filters)
        
        # Assertions
        assert result == {"date_from": "2024-01-01"}
        mock_report_service.validate_filters.assert_called_once_with(ReportType.INVOICE, filters)
    
    def test_get_template_usage_stats(self, template_service, mock_db, sample_template):
        """Test getting template usage statistics"""
        # Mock template retrieval
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Mock report history queries
        mock_history_query = Mock()
        mock_history_query.filter.return_value = mock_history_query
        mock_history_query.count.side_effect = [10, 8, 2]  # total, successful, failed
        mock_history_query.order_by.return_value = mock_history_query
        mock_history_query.limit.return_value = mock_history_query
        mock_history_query.all.return_value = [
            Mock(generated_at=datetime.now(), status="completed", generated_by=1),
            Mock(generated_at=datetime.now(), status="failed", generated_by=1)
        ]
        
        # Mock the query method to return our mock query for ReportHistory
        def mock_query_side_effect(model):
            if model.__name__ == 'ReportHistory':
                return mock_history_query
            else:
                return mock_db.query.return_value
        
        mock_db.query.side_effect = mock_query_side_effect
        
        # Get usage stats
        result = template_service.get_template_usage_stats(sample_template.id, sample_template.user_id)
        
        # Assertions
        assert result["template_id"] == sample_template.id
        assert result["total_uses"] == 10
        assert result["successful_uses"] == 8
        assert result["failed_uses"] == 2
        assert result["success_rate"] == 80.0
        assert len(result["recent_uses"]) == 2
    
    def test_template_name_too_long(self, template_service, mock_db):
        """Test template creation with name too long"""
        long_name = "x" * 256  # Exceeds 255 character limit
        
        invalid_data = ReportTemplateCreate(
            name=long_name,
            report_type=ReportType.INVOICE,
            filters={},
            columns=["col1"],
            is_shared=False
        )
        
        with pytest.raises(TemplateValidationError) as exc_info:
            template_service.create_template(invalid_data, 1)
        
        assert "cannot exceed 255 characters" in str(exc_info.value)
        assert exc_info.value.code == "TEMPLATE_NAME_TOO_LONG"
    
    def test_template_no_columns(self, template_service, mock_db):
        """Test template creation with no columns specified"""
        # Mock database queries - no existing template
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        invalid_data = ReportTemplateCreate(
            name="Test Report No Columns",  # Unique name to avoid duplicate error
            report_type=ReportType.INVOICE,
            filters={},
            columns=[],  # Empty columns list
            is_shared=False
        )
        
        with pytest.raises(TemplateValidationError) as exc_info:
            template_service.create_template(invalid_data, 1)
        
        assert "At least one column must be specified" in str(exc_info.value)
        assert exc_info.value.code == "NO_COLUMNS_SPECIFIED"
    
    def test_template_too_many_columns(self, template_service, mock_db):
        """Test template creation with too many columns"""
        too_many_columns = [f"col_{i}" for i in range(51)]  # 51 columns, exceeds limit of 50
        
        invalid_data = ReportTemplateCreate(
            name="Test Report",
            report_type=ReportType.INVOICE,
            filters={},
            columns=too_many_columns,
            is_shared=False
        )
        
        with pytest.raises(TemplateValidationError) as exc_info:
            template_service.create_template(invalid_data, 1)
        
        assert "Too many columns specified" in str(exc_info.value)
        assert exc_info.value.code == "TOO_MANY_COLUMNS"


class TestTemplateValidation:
    """Test cases for template validation logic"""
    
    @pytest.fixture
    def template_service(self):
        """Template service instance with mocked database"""
        return ReportTemplateService(Mock(spec=Session))
    
    def test_valid_filters_for_each_report_type(self, template_service):
        """Test that valid filters are accepted for each report type"""
        test_cases = [
            (ReportType.CLIENT, {"date_from": "2024-01-01", "currency": "USD"}),
            (ReportType.INVOICE, {"status": ["sent"], "amount_min": 100}),
            (ReportType.PAYMENT, {"payment_methods": ["cash"], "include_unmatched": True}),
            (ReportType.EXPENSE, {"categories": ["office"], "vendor": "Test Vendor"}),
            (ReportType.STATEMENT, {"transaction_types": ["credit"], "include_reconciliation": True})
        ]
        
        for report_type, filters in test_cases:
            # Should not raise an exception
            template_service._validate_template_filters(report_type, filters)
    
    def test_invalid_filters_for_report_types(self, template_service):
        """Test that invalid filters are rejected"""
        test_cases = [
            (ReportType.CLIENT, {"invalid_filter": "value"}),
            (ReportType.INVOICE, {"nonexistent_field": "value"}),
            (ReportType.PAYMENT, {"wrong_filter": "value"}),
            (ReportType.EXPENSE, {"bad_filter": "value"}),
            (ReportType.STATEMENT, {"unknown_filter": "value"})
        ]
        
        for report_type, filters in test_cases:
            with pytest.raises(TemplateValidationError) as exc_info:
                template_service._validate_template_filters(report_type, filters)
            
            assert "Invalid filter" in str(exc_info.value)
            assert exc_info.value.code == "INVALID_FILTER_KEY"