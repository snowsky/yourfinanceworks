"""
Unit tests for the report validation service.

Tests comprehensive validation logic for all report types and parameters.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from api.services.report_validation_service import ReportValidationService
from api.exceptions.report_exceptions import (
    ReportValidationException, ReportErrorCode
)
from api.schemas.report import ReportType, ExportFormat
from api.models.models_per_tenant import Client


class TestReportValidationService:
    """Test the report validation service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def validation_service(self, mock_db):
        """Create validation service with mocked database"""
        return ReportValidationService(mock_db)
    
    def test_validate_report_request_success(self, validation_service, mock_db):
        """Test successful validation of a complete report request"""
        # Mock database query for client validation
        mock_clients = [Mock(id=1), Mock(id=2)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_clients
        
        result = validation_service.validate_report_request(
            report_type="client",
            filters={
                "date_from": "2023-01-01T00:00:00Z",
                "date_to": "2023-12-31T23:59:59Z",
                "client_ids": [1, 2],
                "currency": "USD"
            },
            export_format="pdf",
            user_id=123
        )
        
        assert result["report_type"] == ReportType.CLIENT
        assert result["export_format"] == ExportFormat.PDF
        assert "date_from" in result["filters"]
        assert "date_to" in result["filters"]
        assert result["filters"]["client_ids"] == [1, 2]
        assert result["filters"]["currency"] == "USD"
    
    def test_validate_invoice_filters(self, validation_service):
        """Test validation of invoice-specific filters"""
        filters = {
            "status": ["draft", "sent", "paid"],
            "amount_min": 100.0,
            "amount_max": 1000.0,
            "include_items": True
        }
        
        result = validation_service._validate_invoice_filters(filters)
        
        assert result["status"] == ["draft", "sent", "paid"]
        assert result["amount_min"] == 100.0
        assert result["amount_max"] == 1000.0
        assert result["include_items"] is True
    
    def test_validate_invoice_filters_invalid_status(self, validation_service):
        """Test validation of invalid invoice status"""
        filters = {"status": ["invalid_status"]}
        
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_invoice_filters(filters)
        
        assert "Invalid invoice status" in exc_info.value.message
        assert "invalid_status" in exc_info.value.message
    
    def test_validate_payment_filters(self, validation_service):
        """Test validation of payment-specific filters"""
        filters = {
            "payment_methods": ["cash", "credit_card"],
            "include_unmatched": False
        }
        
        result = validation_service._validate_payment_filters(filters)
        
        assert result["payment_methods"] == ["cash", "credit_card"]
        assert result["include_unmatched"] is False
    
    def test_validate_payment_filters_invalid_method(self, validation_service):
        """Test validation of invalid payment method"""
        filters = {"payment_methods": ["invalid_method"]}
        
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_payment_filters(filters)
        
        assert "Invalid payment method" in exc_info.value.message
    
    def test_validate_expense_filters(self, validation_service):
        """Test validation of expense-specific filters"""
        filters = {
            "categories": ["office", "travel"],
            "labels": ["urgent", "recurring"],
            "include_attachments": True
        }
        
        result = validation_service._validate_expense_filters(filters)
        
        assert result["categories"] == ["office", "travel"]
        assert result["labels"] == ["urgent", "recurring"]
        assert result["include_attachments"] is True
    
    def test_validate_statement_filters(self, validation_service):
        """Test validation of statement-specific filters"""
        filters = {
            "account_ids": [1, 2, 3],
            "transaction_types": ["debit", "credit"],
            "include_reconciliation": False
        }
        
        result = validation_service._validate_statement_filters(filters)
        
        assert result["account_ids"] == [1, 2, 3]
        assert result["transaction_types"] == ["debit", "credit"]
        assert result["include_reconciliation"] is False
    
    def test_validate_string_list_single_string(self, validation_service):
        """Test validation of string list with single string input"""
        result = validation_service._validate_string_list("single_item", "test_field")
        assert result == ["single_item"]
    
    def test_validate_string_list_multiple_strings(self, validation_service):
        """Test validation of string list with multiple strings"""
        result = validation_service._validate_string_list(["item1", "item2"], "test_field")
        assert result == ["item1", "item2"]
    
    def test_validate_string_list_invalid_type(self, validation_service):
        """Test validation of string list with invalid type"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_string_list(123, "test_field")
        
        assert "must be a string or list of strings" in exc_info.value.message
    
    def test_validate_string_list_non_string_items(self, validation_service):
        """Test validation of string list with non-string items"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_string_list(["valid", 123], "test_field")
        
        assert "must be strings" in exc_info.value.message
    
    def test_validate_integer_list_single_integer(self, validation_service):
        """Test validation of integer list with single integer input"""
        result = validation_service._validate_integer_list(42, "test_field")
        assert result == [42]
    
    def test_validate_integer_list_multiple_integers(self, validation_service):
        """Test validation of integer list with multiple integers"""
        result = validation_service._validate_integer_list([1, 2, 3], "test_field")
        assert result == [1, 2, 3]
    
    def test_validate_integer_list_invalid_type(self, validation_service):
        """Test validation of integer list with invalid type"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_integer_list("not_int", "test_field")
        
        assert "must be an integer or list of integers" in exc_info.value.message
    
    def test_validate_integer_list_negative_integers(self, validation_service):
        """Test validation of integer list with negative integers"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_integer_list([1, -2, 3], "test_field")
        
        assert "positive integers" in exc_info.value.message
    
    def test_validate_date_range_iso_format(self, validation_service):
        """Test validation of date range with ISO format strings"""
        result = validation_service._validate_date_range(
            "2023-01-01T00:00:00Z",
            "2023-12-31T23:59:59Z"
        )
        
        assert isinstance(result["date_from"], datetime)
        assert isinstance(result["date_to"], datetime)
        assert result["date_from"] < result["date_to"]
    
    def test_validate_date_range_datetime_objects(self, validation_service):
        """Test validation of date range with datetime objects"""
        date_from = datetime(2023, 1, 1)
        date_to = datetime(2023, 12, 31)
        
        result = validation_service._validate_date_range(date_from, date_to)
        
        assert result["date_from"] == date_from
        assert result["date_to"] == date_to
    
    def test_validate_date_range_invalid_format(self, validation_service):
        """Test validation of date range with invalid format"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_date_range("invalid-date", "2023-12-31")
        
        assert exc_info.value.error_code == ReportErrorCode.VALIDATION_DATE_RANGE_INVALID
    
    def test_validate_date_range_single_date(self, validation_service):
        """Test validation with only one date provided"""
        result = validation_service._validate_date_range("2023-01-01T00:00:00Z", None)
        assert "date_from" in result
        assert "date_to" not in result
        
        result = validation_service._validate_date_range(None, "2023-12-31T23:59:59Z")
        assert "date_from" not in result
        assert "date_to" in result
    
    def test_validate_client_ids_single_id(self, validation_service, mock_db):
        """Test validation of single client ID"""
        mock_clients = [Mock(id=1)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_clients
        
        result = validation_service._validate_client_ids(1)
        assert result == [1]
    
    def test_validate_client_ids_zero_or_negative(self, validation_service):
        """Test validation of zero or negative client IDs"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_client_ids([1, 0, -1])
        
        assert "positive integers" in exc_info.value.message
    
    def test_validate_currency_case_insensitive(self, validation_service):
        """Test currency validation is case insensitive"""
        result = validation_service._validate_currency("usd")
        assert result == "USD"
        
        result = validation_service._validate_currency("eur")
        assert result == "EUR"
    
    def test_validate_currency_non_string(self, validation_service):
        """Test currency validation with non-string input"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_currency(123)
        
        assert "Currency must be a string" in exc_info.value.message
    
    def test_validate_amount_range_single_values(self, validation_service):
        """Test amount range validation with single values"""
        result = validation_service._validate_amount_range(100.0, None)
        assert result["amount_min"] == 100.0
        assert "amount_max" not in result
        
        result = validation_service._validate_amount_range(None, 1000.0)
        assert "amount_min" not in result
        assert result["amount_max"] == 1000.0
    
    def test_validate_amount_range_negative_values(self, validation_service):
        """Test amount range validation with negative values"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_amount_range(-100.0, 1000.0)
        
        assert exc_info.value.error_code == ReportErrorCode.VALIDATION_AMOUNT_RANGE_INVALID
    
    def test_validate_amount_range_too_large(self, validation_service):
        """Test amount range validation with values too large"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_amount_range(999999999999.0, None)
        
        assert "too large" in exc_info.value.message
    
    def test_validate_amount_range_integer_input(self, validation_service):
        """Test amount range validation with integer input"""
        result = validation_service._validate_amount_range(100, 1000)
        assert result["amount_min"] == 100.0
        assert result["amount_max"] == 1000.0
    
    def test_validate_boolean_flag_string_variations(self, validation_service):
        """Test boolean flag validation with various string inputs"""
        # True variations
        assert validation_service._validate_boolean_flag("true", "test") is True
        assert validation_service._validate_boolean_flag("TRUE", "test") is True
        assert validation_service._validate_boolean_flag("1", "test") is True
        assert validation_service._validate_boolean_flag("yes", "test") is True
        assert validation_service._validate_boolean_flag("on", "test") is True
        
        # False variations
        assert validation_service._validate_boolean_flag("false", "test") is False
        assert validation_service._validate_boolean_flag("FALSE", "test") is False
        assert validation_service._validate_boolean_flag("0", "test") is False
        assert validation_service._validate_boolean_flag("no", "test") is False
        assert validation_service._validate_boolean_flag("off", "test") is False
    
    def test_validate_boolean_flag_integer_input(self, validation_service):
        """Test boolean flag validation with integer input"""
        assert validation_service._validate_boolean_flag(1, "test") is True
        assert validation_service._validate_boolean_flag(0, "test") is False
        assert validation_service._validate_boolean_flag(42, "test") is True
        assert validation_service._validate_boolean_flag(-1, "test") is True
    
    def test_validate_filters_by_type_empty_filters(self, validation_service):
        """Test validation with empty filters dictionary"""
        result = validation_service._validate_filters_by_type(ReportType.CLIENT, {})
        assert isinstance(result, dict)
        assert len(result) == 0
    
    def test_validate_filters_by_type_non_dict(self, validation_service):
        """Test validation with non-dictionary filters"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_filters_by_type(ReportType.CLIENT, "not_a_dict")
        
        assert "must be a dictionary" in exc_info.value.message
    
    def test_validate_invoice_status_single_string(self, validation_service):
        """Test invoice status validation with single string"""
        result = validation_service._validate_invoice_status("paid")
        assert result == ["paid"]
    
    def test_validate_invoice_status_list(self, validation_service):
        """Test invoice status validation with list"""
        result = validation_service._validate_invoice_status(["draft", "sent"])
        assert result == ["draft", "sent"]
    
    def test_validate_invoice_status_non_list_non_string(self, validation_service):
        """Test invoice status validation with invalid type"""
        with pytest.raises(ReportValidationException) as exc_info:
            validation_service._validate_invoice_status(123)
        
        assert "must be a string or list of strings" in exc_info.value.message
    
    def test_validate_payment_methods_single_string(self, validation_service):
        """Test payment methods validation with single string"""
        result = validation_service._validate_payment_methods("cash")
        assert result == ["cash"]
    
    def test_validate_payment_methods_list(self, validation_service):
        """Test payment methods validation with list"""
        result = validation_service._validate_payment_methods(["cash", "credit_card"])
        assert result == ["cash", "credit_card"]
    
    def test_comprehensive_validation_all_filters(self, validation_service, mock_db):
        """Test comprehensive validation with all possible filters"""
        # Mock database query for client validation
        mock_clients = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_clients
        
        filters = {
            "date_from": "2023-01-01T00:00:00Z",
            "date_to": "2023-12-31T23:59:59Z",
            "client_ids": [1, 2, 3],
            "currency": "USD",
            "status": ["draft", "sent"],
            "amount_min": 100.0,
            "amount_max": 1000.0,
            "include_items": True,
            "payment_methods": ["cash", "credit_card"],
            "include_unmatched": False,
            "categories": ["office", "travel"],
            "labels": ["urgent"],
            "include_attachments": True,
            "account_ids": [1, 2],
            "transaction_types": ["debit"],
            "include_reconciliation": False
        }
        
        result = validation_service._validate_filters_by_type(ReportType.INVOICE, filters)
        
        # Check that all filters are validated and included
        assert "date_from" in result
        assert "date_to" in result
        assert result["client_ids"] == [1, 2, 3]
        assert result["currency"] == "USD"
        assert result["status"] == ["draft", "sent"]
        assert result["amount_min"] == 100.0
        assert result["amount_max"] == 1000.0
        assert result["include_items"] is True
    
    def test_edge_case_maximum_date_range(self, validation_service):
        """Test validation with maximum allowed date range"""
        start_date = datetime.now() - timedelta(days=729)  # Just under 2 years
        end_date = datetime.now()
        
        result = validation_service._validate_date_range(
            start_date.isoformat(),
            end_date.isoformat()
        )
        
        assert "date_from" in result
        assert "date_to" in result
    
    def test_edge_case_maximum_client_ids(self, validation_service, mock_db):
        """Test validation with maximum allowed client IDs"""
        client_ids = list(range(1, 101))  # Exactly 100 clients
        mock_clients = [Mock(id=i) for i in client_ids]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_clients
        
        result = validation_service._validate_client_ids(client_ids)
        assert len(result) == 100
    
    def test_edge_case_maximum_amount(self, validation_service):
        """Test validation with maximum allowed amount"""
        max_amount = validation_service.max_amount
        
        result = validation_service._validate_amount_range(0.0, max_amount)
        assert result["amount_max"] == max_amount