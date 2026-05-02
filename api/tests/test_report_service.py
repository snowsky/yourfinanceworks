"""
Unit tests for ReportService

Tests the report generation service with comprehensive filtering capabilities,
validation logic, and summary calculations for all report types.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from core.services.report_service import ReportService
from core.exceptions.report_exceptions import ReportValidationError
from core.services.report_data_aggregator import (
    ClientData, InvoiceMetrics, PaymentFlows, ExpenseBreakdown, TransactionData
)
from core.schemas.report import (
    ReportType, ExportFormat, ClientReportFilters, InvoiceReportFilters,
    PaymentReportFilters, ExpenseReportFilters, StatementReportFilters
)


# Fixtures at module level
@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)

@pytest.fixture
def company_data():
    """Sample company data for testing"""
    return {
        "name": "Test Company Inc.",
        "address": "123 Test Street",
        "phone": "+1-555-123-4567",
        "email": "info@testcompany.com"
    }

@pytest.fixture
def report_service(mock_db):
    """Create ReportService instance with mocked dependencies"""
    return ReportService(mock_db)

@pytest.fixture
def sample_client_data():
    """Sample client data for testing"""
    data = ClientData()
    data.clients = [
        {
            'id': 1,
            'name': 'Test Client 1',
            'email': 'client1@test.com',
            'balance': 1000.0,
            'paid_amount': 2000.0,
            'total_invoices': 5,
            'created_at': datetime.now()
        },
        {
            'id': 2,
            'name': 'Test Client 2',
            'email': 'client2@test.com',
            'balance': 500.0,
            'paid_amount': 1500.0,
            'total_invoices': 3,
            'created_at': datetime.now()
        }
    ]
    data.total_clients = 2
    data.active_clients = 2
    data.total_balance = 1500.0
    data.total_paid_amount = 3500.0
    data.currencies = ['USD', 'CAD']
    return data

@pytest.fixture
def sample_invoice_data():
    """Sample invoice data for testing"""
    data = InvoiceMetrics()
    data.invoices = [
        {
            'id': 1,
            'number': 'INV-001',
            'amount': 1000.0,
            'status': 'paid',
            'client_name': 'Test Client 1',
            'outstanding_amount': 0.0,
            'created_at': datetime.now()
        },
        {
            'id': 2,
            'number': 'INV-002',
            'amount': 500.0,
            'status': 'sent',
            'client_name': 'Test Client 2',
            'outstanding_amount': 500.0,
            'created_at': datetime.now()
        }
    ]
    data.total_invoices = 2
    data.total_amount = 1500.0
    data.total_paid = 1000.0
    data.total_outstanding = 500.0
    data.average_amount = 750.0
    data.status_breakdown = {'paid': 1, 'sent': 1}
    data.currency_breakdown = {'USD': 1500.0}
    return data


class TestReportService:
    """Test suite for ReportService class"""


class TestReportGeneration:
    """Test report generation functionality"""
    
    def test_generate_client_report_success(self, report_service, sample_client_data):
        """Test successful client report generation"""
        # Mock the data aggregator
        with patch.object(report_service.data_aggregator, 'aggregate_client_data', return_value=sample_client_data):
            filters = {
                'date_from': datetime.now() - timedelta(days=30),
                'date_to': datetime.now(),
                'currency': 'USD'
            }
            
            result = report_service.generate_report(
                ReportType.CLIENT,
                filters,
                ExportFormat.JSON,
                user_id=1
            )
            
            assert result.success is True
            assert result.data is not None
            assert result.data.report_type == ReportType.CLIENT
            assert result.data.summary.total_records == 2
            assert result.data.summary.total_amount == 1500.0
            assert len(result.data.data) == 2
            assert result.error_message is None
    
    def test_generate_invoice_report_success(self, report_service, sample_invoice_data):
        """Test successful invoice report generation"""
        with patch.object(report_service.data_aggregator, 'aggregate_invoice_metrics', return_value=sample_invoice_data):
            filters = {
                'date_from': datetime.now() - timedelta(days=30),
                'date_to': datetime.now(),
                'status': ['paid', 'sent']
            }
            
            result = report_service.generate_report(
                ReportType.INVOICE,
                filters,
                ExportFormat.JSON,
                user_id=1
            )
            
            assert result.success is True
            assert result.data.report_type == ReportType.INVOICE
            assert result.data.summary.total_records == 2
            assert result.data.summary.key_metrics['collection_rate'] == 66.66666666666666  # 1000/1500 * 100
    
    def test_generate_payment_report_success(self, report_service):
        """Test successful payment report generation"""
        # Create sample payment data
        payment_data = PaymentFlows()
        payment_data.payments = [
            {
                'id': 1,
                'amount': 1000.0,
                'payment_method': 'credit_card',
                'payment_date': datetime.now(),
                'client_name': 'Test Client'
            }
        ]
        payment_data.total_payments = 1
        payment_data.total_amount = 1000.0
        payment_data.method_breakdown = {'credit_card': 1000.0}
        
        with patch.object(report_service.data_aggregator, 'aggregate_payment_flows', return_value=payment_data):
            filters = {'payment_methods': ['credit_card']}
            
            result = report_service.generate_report(
                ReportType.PAYMENT,
                filters,
                ExportFormat.JSON,
                user_id=1
            )
            
            assert result.success is True
            assert result.data.report_type == ReportType.PAYMENT
            assert result.data.summary.key_metrics['average_payment'] == 1000.0
    
    def test_generate_expense_report_success(self, report_service):
        """Test successful expense report generation"""
        # Create sample expense data
        expense_data = ExpenseBreakdown()
        expense_data.expenses = [
            {
                'id': 1,
                'amount': 500.0,
                'category': 'Office Supplies',
                'vendor': 'Test Vendor',
                'expense_date': datetime.now()
            }
        ]
        expense_data.total_expenses = 1
        expense_data.total_amount = 500.0
        expense_data.category_breakdown = {'Office Supplies': 500.0}
        
        with patch.object(report_service.data_aggregator, 'aggregate_expense_categories', return_value=expense_data):
            filters = {'categories': ['Office Supplies']}
            
            result = report_service.generate_report(
                ReportType.EXPENSE,
                filters,
                ExportFormat.JSON,
                user_id=1
            )
            
            assert result.success is True
            assert result.data.report_type == ReportType.EXPENSE
            assert result.data.summary.key_metrics['average_expense'] == 500.0
    
    def test_generate_statement_report_success(self, report_service):
        """Test successful statement report generation"""
        # Create sample transaction data
        transaction_data = TransactionData()
        transaction_data.transactions = [
            {
                'id': 1,
                'amount': 1000.0,
                'transaction_type': 'credit',
                'date': datetime.now(),
                'invoice_id': 1  # Reconciled transaction
            },
            {
                'id': 2,
                'amount': -500.0,
                'transaction_type': 'debit',
                'date': datetime.now(),
                'invoice_id': None  # Unreconciled transaction
            }
        ]
        transaction_data.total_transactions = 2
        transaction_data.total_credits = 1000.0
        transaction_data.total_debits = 500.0
        transaction_data.net_flow = 500.0
        
        with patch.object(report_service.data_aggregator, 'aggregate_statement_transactions', return_value=transaction_data):
            filters = {'transaction_types': ['credit', 'debit']}
            
            result = report_service.generate_report(
                ReportType.STATEMENT,
                filters,
                ExportFormat.JSON,
                user_id=1
            )
            
            assert result.success is True
            assert result.data.report_type == ReportType.STATEMENT
            assert result.data.summary.key_metrics['reconciliation_rate'] == 50.0  # 1 out of 2 reconciled
    
    def test_generate_report_invalid_type(self, report_service):
        """Test report generation with invalid report type"""
        result = report_service.generate_report(
            "invalid_type",  # Invalid type
            {},
            ExportFormat.JSON,
            user_id=1
        )
        
        assert result.success is False
        assert "Unsupported report type" in result.error_message
    
    def test_generate_report_aggregation_error(self, report_service):
        """Test report generation when aggregation fails"""
        with patch.object(report_service.data_aggregator, 'aggregate_client_data', side_effect=Exception("Database error")):
            filters = {'date_from': datetime.now()}
            
            result = report_service.generate_report(
                ReportType.CLIENT,
                filters,
                ExportFormat.JSON,
                user_id=1
            )
            
            assert result.success is False
            assert "Report generation failed" in result.error_message


class TestFilterValidation:
    """Test filter validation functionality"""
    
    def test_validate_client_filters_success(self, report_service):
        """Test successful client filter validation"""
        filters = {
            'date_from': datetime.now() - timedelta(days=30),
            'date_to': datetime.now(),
            'balance_min': 0.0,
            'balance_max': 10000.0,
            'currency': 'USD'
        }
        
        validated = report_service.validate_filters(ReportType.CLIENT, filters)
        
        assert isinstance(validated, ClientReportFilters)
        assert validated.currency == 'USD'
        assert validated.balance_min == 0.0
    
    def test_validate_invoice_filters_success(self, report_service):
        """Test successful invoice filter validation"""
        filters = {
            'date_from': datetime.now() - timedelta(days=30),
            'date_to': datetime.now(),
            'status': ['paid', 'sent'],
            'amount_min': 100.0,
            'amount_max': 5000.0,
            'include_items': True
        }
        
        validated = report_service.validate_filters(ReportType.INVOICE, filters)
        
        assert isinstance(validated, InvoiceReportFilters)
        assert validated.status == ['paid', 'sent']
        assert validated.include_items is True
    
    def test_validate_date_range_invalid_order(self, report_service):
        """Test validation with invalid date range (start after end)"""
        filters = {
            'date_from': datetime.now(),
            'date_to': datetime.now() - timedelta(days=30)  # End before start
        }
        
        with pytest.raises(ReportValidationError) as exc_info:
            report_service.validate_filters(ReportType.CLIENT, filters)
        
        assert "Start date cannot be after end date" in str(exc_info.value)
        assert exc_info.value.code == "INVALID_DATE_RANGE"
    
    def test_validate_date_range_too_large(self, report_service):
        """Test validation with date range too large"""
        filters = {
            'date_from': datetime.now() - timedelta(days=4000),  # More than 10 years
            'date_to': datetime.now()
        }
        
        with pytest.raises(ReportValidationError) as exc_info:
            report_service.validate_filters(ReportType.CLIENT, filters)
        
        assert "Date range cannot exceed 10 years" in str(exc_info.value)
        assert exc_info.value.code == "DATE_RANGE_TOO_LARGE"
    
    def test_validate_future_start_date(self, report_service):
        """Test validation with future start date"""
        filters = {
            'date_from': datetime.now() + timedelta(days=1)  # Future date
        }
        
        with pytest.raises(ReportValidationError) as exc_info:
            report_service.validate_filters(ReportType.CLIENT, filters)
        
        assert "Start date cannot be in the future" in str(exc_info.value)
        assert exc_info.value.code == "FUTURE_DATE"
    
    def test_validate_invoice_invalid_amount_range(self, report_service):
        """Test validation with invalid amount range"""
        filters = {
            'amount_min': 1000.0,
            'amount_max': 500.0  # Max less than min
        }
        
        with pytest.raises(ReportValidationError) as exc_info:
            report_service.validate_filters(ReportType.INVOICE, filters)
        
        assert "Minimum amount cannot be greater than maximum amount" in str(exc_info.value)
        assert exc_info.value.code == "INVALID_AMOUNT_RANGE"
    
    def test_validate_invoice_invalid_status(self, report_service):
        """Test validation with invalid invoice status"""
        filters = {
            'status': ['paid', 'invalid_status']
        }
        
        with pytest.raises(ReportValidationError) as exc_info:
            report_service.validate_filters(ReportType.INVOICE, filters)
        
        assert "Invalid invoice statuses: invalid_status" in str(exc_info.value)
        assert exc_info.value.code == "INVALID_STATUS"
    
    def test_validate_payment_invalid_method(self, report_service):
        """Test validation with invalid payment method"""
        filters = {
            'payment_methods': ['credit_card', 'invalid_method']
        }
        
        with pytest.raises(ReportValidationError) as exc_info:
            report_service.validate_filters(ReportType.PAYMENT, filters)
        
        assert "Invalid payment methods: invalid_method" in str(exc_info.value)
        assert exc_info.value.code == "INVALID_PAYMENT_METHOD"
    
    def test_validate_statement_invalid_transaction_type(self, report_service):
        """Test validation with invalid transaction type"""
        filters = {
            'transaction_types': ['credit', 'invalid_type']
        }
        
        with pytest.raises(ReportValidationError) as exc_info:
            report_service.validate_filters(ReportType.STATEMENT, filters)
        
        assert "Invalid transaction types: invalid_type" in str(exc_info.value)
        assert exc_info.value.code == "INVALID_TRANSACTION_TYPE"


class TestReportTypes:
    """Test report type functionality"""
    
    def test_get_available_report_types(self, report_service):
        """Test getting available report types"""
        report_types = report_service.get_available_report_types()
        
        assert len(report_types) == 7
        
        # Check that all expected report types are present
        type_names = [rt['type'] for rt in report_types]
        assert ReportType.CLIENT in type_names
        assert ReportType.INVOICE in type_names
        assert ReportType.PAYMENT in type_names
        assert ReportType.EXPENSE in type_names
        assert ReportType.STATEMENT in type_names
        assert ReportType.INVENTORY in type_names
        assert ReportType.CASH_FLOW in type_names
        
        # Check structure of first report type
        client_report = next(rt for rt in report_types if rt['type'] == ReportType.CLIENT)
        assert 'name' in client_report
        assert 'description' in client_report
        assert 'available_filters' in client_report
        assert 'default_columns' in client_report
        
        # Verify some expected filters
        assert 'date_from' in client_report['available_filters']
        assert 'balance_min' in client_report['available_filters']
        
        # Check cash flow report type configuration
        cash_flow_report = next(rt for rt in report_types if rt['type'] == ReportType.CASH_FLOW)
        assert 'name' in cash_flow_report
        assert 'description' in cash_flow_report
        assert 'available_filters' in cash_flow_report
        assert 'default_columns' in cash_flow_report
        assert 'include_unreconciled' in cash_flow_report['available_filters']
        assert 'flow_type' in cash_flow_report['default_columns']


class TestReportPreview:
    """Test report preview functionality"""
    
    def test_preview_report_success(self, report_service, sample_client_data):
        """Test successful report preview"""
        # Add more data to test limiting
        sample_client_data.clients.extend([
            {'id': i, 'name': f'Client {i}', 'balance': 100.0}
            for i in range(3, 15)  # Add clients 3-14
        ])
        sample_client_data.total_clients = len(sample_client_data.clients)
        
        with patch.object(report_service.data_aggregator, 'aggregate_client_data', return_value=sample_client_data):
            filters = {'currency': 'USD'}
            
            result = report_service.preview_report(
                ReportType.CLIENT,
                filters,
                limit=5
            )
            
            assert result.success is True
            assert len(result.data.data) == 5  # Limited to 5 records
            assert result.data.summary.total_records == 5  # Updated count
    
    def test_preview_report_error(self, report_service):
        """Test report preview with error"""
        with patch.object(report_service, 'generate_report', side_effect=Exception("Preview error")):
            result = report_service.preview_report(
                ReportType.CLIENT,
                {},
                limit=5
            )
            
            assert result.success is False
            assert "Preview generation failed" in result.error_message


class TestSummaryCalculations:
    """Test summary calculation methods"""
    
    def test_calculate_reconciliation_rate_full(self, report_service):
        """Test reconciliation rate calculation with fully reconciled transactions"""
        transactions = [
            {'invoice_id': 1, 'expense_id': None},
            {'invoice_id': None, 'expense_id': 2},
            {'invoice_id': 3, 'expense_id': None}
        ]
        
        rate = report_service._calculate_reconciliation_rate(transactions)
        assert rate == 100.0
    
    def test_calculate_reconciliation_rate_partial(self, report_service):
        """Test reconciliation rate calculation with partially reconciled transactions"""
        transactions = [
            {'invoice_id': 1, 'expense_id': None},
            {'invoice_id': None, 'expense_id': None},  # Unreconciled
            {'invoice_id': None, 'expense_id': 2}
        ]
        
        rate = report_service._calculate_reconciliation_rate(transactions)
        assert rate == 66.66666666666666  # 2 out of 3
    
    def test_calculate_reconciliation_rate_empty(self, report_service):
        """Test reconciliation rate calculation with empty transactions"""
        rate = report_service._calculate_reconciliation_rate([])
        assert rate == 0.0


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_validation_error_handling(self, report_service):
        """Test proper handling of validation errors"""
        # Test with invalid filter structure that would cause Pydantic validation error
        filters = {
            'date_from': "invalid_date_string",  # Should be datetime
            'amount_min': "not_a_number"  # Should be float
        }
        
        result = report_service.generate_report(
            ReportType.INVOICE,
            filters,
            ExportFormat.JSON,
            user_id=1
        )
        
        assert result.success is False
        assert "Validation error" in result.error_message
    
    def test_unknown_report_type_validation(self, report_service):
        """Test validation with unknown report type"""
        with pytest.raises(ReportValidationError) as exc_info:
            report_service.validate_filters("unknown_type", {})
        
        assert "No filter class found for report type" in str(exc_info.value)
        assert exc_info.value.code == "INVALID_REPORT_TYPE"


class TestReportExportIntegration:
    """Test cases for report export integration"""
    
    @pytest.fixture
    def report_service_with_company(self, mock_db, company_data):
        """Report service with company data for export testing"""
        return ReportService(mock_db, company_data)
    
    @pytest.fixture
    def sample_report_data(self):
        """Sample report data for export testing"""
        from core.schemas.report import ReportData, ReportSummary, ReportMetadata
        
        return ReportData(
            report_type=ReportType.INVOICE,
            summary=ReportSummary(
                total_records=2,
                total_amount=1250.00,
                currency="USD",
                key_metrics={"average_amount": 625.00}
            ),
            data=[
                {
                    "invoice_number": "INV-001",
                    "client_name": "Client A",
                    "amount": 500.00,
                    "status": "paid"
                },
                {
                    "invoice_number": "INV-002",
                    "client_name": "Client B", 
                    "amount": 750.00,
                    "status": "pending"
                }
            ],
            metadata=ReportMetadata(
                generated_at=datetime.now(),
                generated_by=1,
                export_format=ExportFormat.JSON
            ),
            filters={}
        )
    
    def test_export_report_data_pdf(self, report_service_with_company, sample_report_data):
        """Test exporting report data to PDF"""
        result = report_service_with_company.export_report_data(
            sample_report_data, 
            ExportFormat.PDF
        )
        
        assert isinstance(result, bytes)
        assert result.startswith(b'%PDF-')
    
    def test_export_report_data_csv(self, report_service_with_company, sample_report_data):
        """Test exporting report data to CSV"""
        result = report_service_with_company.export_report_data(
            sample_report_data,
            ExportFormat.CSV
        )
        
        assert isinstance(result, str)
        assert 'invoice_number' in result
        assert 'INV-001' in result
    
    def test_export_report_data_excel(self, report_service_with_company, sample_report_data):
        """Test exporting report data to Excel"""
        result = report_service_with_company.export_report_data(
            sample_report_data,
            ExportFormat.EXCEL
        )
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_get_supported_export_formats(self, report_service_with_company):
        """Test getting supported export formats"""
        formats = report_service_with_company.get_supported_export_formats()
        
        assert ExportFormat.PDF in formats
        assert ExportFormat.CSV in formats
        assert ExportFormat.EXCEL in formats
        assert len(formats) == 3
    
    def test_validate_export_format_valid(self, report_service_with_company):
        """Test export format validation with valid formats"""
        assert report_service_with_company.validate_export_format("pdf") == ExportFormat.PDF
        assert report_service_with_company.validate_export_format("csv") == ExportFormat.CSV
        assert report_service_with_company.validate_export_format("excel") == ExportFormat.EXCEL
    
    def test_validate_export_format_invalid(self, report_service_with_company):
        """Test export format validation with invalid format"""
        from core.services.report_exporter import ExportError
        
        with pytest.raises(ExportError, match="Invalid export format"):
            report_service_with_company.validate_export_format("invalid")
    
    def test_export_service_integration(self, report_service_with_company):
        """Test that export service is properly integrated"""
        # Test that the export service is initialized
        assert report_service_with_company.export_service is not None
        
        # Test that supported formats are available
        formats = report_service_with_company.get_supported_export_formats()
        assert ExportFormat.PDF in formats
        assert ExportFormat.CSV in formats
        assert ExportFormat.EXCEL in formats
    
    def test_export_format_validation_integration(self, report_service_with_company):
        """Test export format validation integration"""
        # Test valid formats
        assert report_service_with_company.validate_export_format("pdf") == ExportFormat.PDF
        assert report_service_with_company.validate_export_format("csv") == ExportFormat.CSV
        assert report_service_with_company.validate_export_format("excel") == ExportFormat.EXCEL
        
        # Test invalid format
        from core.services.report_exporter import ExportError
        with pytest.raises(ExportError):
            report_service_with_company.validate_export_format("invalid")