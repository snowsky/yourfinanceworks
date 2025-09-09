"""
Comprehensive Test Suite for Reporting Module

This module provides comprehensive integration, performance, end-to-end, and security tests
for the reporting module, ensuring complete coverage of all workflows and edge cases.

Requirements covered: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import pytest
import asyncio
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
import tempfile
import os

from main import app
from models.models_per_tenant import (
    User, Client, Invoice, Payment, Expense, BankStatement,
    ReportTemplate, ScheduledReport, ReportHistory
)
from schemas.report import (
    ReportType, ExportFormat, ReportRequest, ReportTemplateCreate,
    ClientReportFilters, InvoiceReportFilters, PaymentReportFilters,
    ExpenseReportFilters, StatementReportFilters
)
from services.report_service import ReportService
from services.report_scheduler import ReportScheduler
from services.report_data_aggregator import ReportDataAggregator
from services.report_exporter import ReportExporter
from services.report_template_service import ReportTemplateService
from services.report_security_service import ReportSecurityService
from services.report_audit_service import ReportAuditService
from exceptions.report_exceptions import (
    ReportGenerationException, ReportAccessDeniedException,
    ReportValidationException, ReportErrorCode
)


class TestDataFactory:
    """Factory for creating consistent test data across all tests"""
    
    @staticmethod
    def create_user(
        user_id: int = 1,
        email: str = None,
        role: str = "user",
        tenant_id: int = 1
    ) -> Mock:
        """Create a mock user with consistent properties"""
        user = Mock(spec=User)
        user.id = user_id
        user.email = email or f"user{user_id}@example.com"
        user.role = role
        user.tenant_id = tenant_id
        user.created_at = datetime.now() - timedelta(days=30)
        user.is_active = True
        return user
    
    @staticmethod
    def create_client(
        client_id: int = 1,
        name: str = None,
        email: str = None,
        tenant_id: int = 1
    ) -> Mock:
        """Create a mock client with consistent properties"""
        client = Mock(spec=Client)
        client.id = client_id
        client.name = name or f"Client {client_id}"
        client.email = email or f"client{client_id}@example.com"
        client.phone = f"555-{client_id:04d}"
        client.address = f"{client_id} Main St"
        client.tenant_id = tenant_id
        client.created_at = datetime.now() - timedelta(days=60)
        client.is_active = True
        return client
    
    @staticmethod
    def create_invoice(
        invoice_id: int = 1,
        client_id: int = 1,
        amount: float = 1000.0,
        status: str = "paid",
        tenant_id: int = 1
    ) -> Mock:
        """Create a mock invoice with consistent properties"""
        invoice = Mock(spec=Invoice)
        invoice.id = invoice_id
        invoice.invoice_number = f"INV-{invoice_id:04d}"
        invoice.client_id = client_id
        invoice.total_amount = amount
        invoice.status = status
        invoice.invoice_date = datetime.now() - timedelta(days=30)
        invoice.due_date = datetime.now() - timedelta(days=15)
        invoice.tenant_id = tenant_id
        invoice.currency = "USD"
        invoice.tax_amount = amount * 0.1
        invoice.subtotal = amount * 0.9
        return invoice
    
    @staticmethod
    def create_payment(
        payment_id: int = 1,
        invoice_id: int = 1,
        amount: float = 1000.0,
        method: str = "credit_card",
        tenant_id: int = 1
    ) -> Mock:
        """Create a mock payment with consistent properties"""
        payment = Mock(spec=Payment)
        payment.id = payment_id
        payment.invoice_id = invoice_id
        payment.amount = amount
        payment.payment_method = method
        payment.payment_date = datetime.now() - timedelta(days=20)
        payment.tenant_id = tenant_id
        payment.currency = "USD"
        payment.status = "completed"
        payment.reference_number = f"PAY-{payment_id:04d}"
        return payment
    
    @staticmethod
    def create_expense(
        expense_id: int = 1,
        amount: float = 500.0,
        category: str = "office_supplies",
        tenant_id: int = 1
    ) -> Mock:
        """Create a mock expense with consistent properties"""
        expense = Mock(spec=Expense)
        expense.id = expense_id
        expense.amount = amount
        expense.category = category
        expense.description = f"Expense {expense_id} - {category}"
        expense.expense_date = datetime.now() - timedelta(days=25)
        expense.tenant_id = tenant_id
        expense.currency = "USD"
        expense.receipt_url = f"/receipts/expense_{expense_id}.pdf"
        expense.is_billable = True
        return expense
    
    @staticmethod
    def create_bank_statement(
        statement_id: int = 1,
        account_name: str = "Business Checking",
        tenant_id: int = 1
    ) -> Mock:
        """Create a mock bank statement with consistent properties"""
        statement = Mock(spec=BankStatement)
        statement.id = statement_id
        statement.account_name = account_name
        statement.statement_date = datetime.now() - timedelta(days=30)
        statement.beginning_balance = 10000.0
        statement.ending_balance = 12000.0
        statement.tenant_id = tenant_id
        statement.currency = "USD"
        statement.transaction_count = 50
        return statement
    
    @staticmethod
    def create_report_template(
        template_id: int = 1,
        user_id: int = 1,
        report_type: str = "client",
        name: str = None
    ) -> Mock:
        """Create a mock report template with consistent properties"""
        template = Mock(spec=ReportTemplate)
        template.id = template_id
        template.name = name or f"Template {template_id}"
        template.report_type = report_type
        template.user_id = user_id
        template.filters = {"status": ["active"]}
        template.columns = ["name", "email", "total_invoices"]
        template.formatting = {"currency": "USD", "date_format": "YYYY-MM-DD"}
        template.is_shared = False
        template.created_at = datetime.now() - timedelta(days=10)
        template.updated_at = datetime.now() - timedelta(days=5)
        return template
    
    @staticmethod
    def create_scheduled_report(
        schedule_id: int = 1,
        template_id: int = 1,
        user_id: int = 1
    ) -> Mock:
        """Create a mock scheduled report with consistent properties"""
        scheduled = Mock(spec=ScheduledReport)
        scheduled.id = schedule_id
        scheduled.template_id = template_id
        scheduled.user_id = user_id
        scheduled.schedule_type = "weekly"
        scheduled.schedule_config = {"day_of_week": 1, "hour": 9}
        scheduled.recipients = ["user@example.com"]
        scheduled.is_active = True
        scheduled.last_run = datetime.now() - timedelta(days=7)
        scheduled.next_run = datetime.now() + timedelta(days=7)
        scheduled.created_at = datetime.now() - timedelta(days=30)
        return scheduled
    
    @staticmethod
    def create_large_dataset(
        num_clients: int = 1000,
        num_invoices: int = 5000,
        num_payments: int = 3000,
        tenant_id: int = 1
    ) -> Dict[str, List[Mock]]:
        """Create a large dataset for performance testing"""
        clients = [
            TestDataFactory.create_client(i, f"Client {i}", f"client{i}@example.com", tenant_id)
            for i in range(1, num_clients + 1)
        ]
        
        invoices = []
        for i in range(1, num_invoices + 1):
            client_id = ((i - 1) % num_clients) + 1
            amount = 500.0 + (i % 2000)
            status = "paid" if i % 3 == 0 else "pending"
            invoices.append(
                TestDataFactory.create_invoice(i, client_id, amount, status, tenant_id)
            )
        
        payments = []
        for i in range(1, num_payments + 1):
            invoice_id = ((i - 1) % num_invoices) + 1
            amount = invoices[invoice_id - 1].total_amount
            method = ["credit_card", "bank_transfer", "check"][i % 3]
            payments.append(
                TestDataFactory.create_payment(i, invoice_id, amount, method, tenant_id)
            )
        
        return {
            "clients": clients,
            "invoices": invoices,
            "payments": payments
        }


class TestCompleteReportWorkflows:
    """Integration tests for complete report generation workflows"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session with consistent behavior"""
        session = Mock(spec=Session)
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session
    
    @pytest.fixture
    def test_user(self):
        """Standard test user"""
        return TestDataFactory.create_user(1, "test@example.com", "user", 1)
    
    @pytest.fixture
    def admin_user(self):
        """Admin test user"""
        return TestDataFactory.create_user(2, "admin@example.com", "admin", 1)
    
    def test_complete_client_report_workflow(self, mock_db_session, test_user):
        """Test complete client report generation workflow"""
        # Setup test data
        clients = [TestDataFactory.create_client(i) for i in range(1, 6)]
        invoices = [TestDataFactory.create_invoice(i, (i % 5) + 1) for i in range(1, 11)]
        
        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.all.return_value = clients
        
        # Create services
        report_service = ReportService(mock_db_session)
        
        # Mock internal services
        with patch.object(report_service, 'data_aggregator') as mock_aggregator:
            with patch.object(report_service, 'export_service') as mock_exporter:
                with patch.object(report_service, 'validation_service') as mock_validator:
                    
                    # Setup mocks
                    mock_validator.validate_report_request.return_value = {
                        'report_type': ReportType.CLIENT,
                        'filters': ClientReportFilters(),
                        'export_format': ExportFormat.JSON
                    }
                    
                    mock_aggregator.aggregate_client_data.return_value = {
                        'clients': clients,
                        'summary': {
                            'total_clients': 5,
                            'total_invoices': 10,
                            'total_revenue': 10000.0
                        }
                    }
                    
                    mock_exporter.export_report.return_value = Mock(
                        success=True,
                        file_path="/tmp/client_report.json",
                        file_size=1024
                    )
                    
                    # Execute workflow
                    result = report_service.generate_report(
                        report_type="client",
                        filters={},
                        export_format="json",
                        user_id=test_user.id
                    )
                    
                    # Verify workflow completion
                    assert result.success is True
                    assert result.file_path is not None
                    
                    # Verify service interactions
                    mock_validator.validate_report_request.assert_called_once()
                    mock_aggregator.aggregate_client_data.assert_called_once()
                    mock_exporter.export_report.assert_called_once()
    
    def test_complete_invoice_report_workflow_with_filters(self, mock_db_session, test_user):
        """Test invoice report workflow with complex filters"""
        # Setup test data with various statuses and dates
        invoices = []
        for i in range(1, 21):
            status = ["paid", "pending", "overdue"][i % 3]
            date = datetime.now() - timedelta(days=i * 5)
            invoice = TestDataFactory.create_invoice(i, (i % 5) + 1, 1000.0 + i * 100, status)
            invoice.invoice_date = date
            invoices.append(invoice)
        
        report_service = ReportService(mock_db_session)
        
        with patch.object(report_service, 'data_aggregator') as mock_aggregator:
            with patch.object(report_service, 'export_service') as mock_exporter:
                with patch.object(report_service, 'validation_service') as mock_validator:
                    
                    # Setup complex filters
                    filters = InvoiceReportFilters(
                        date_from=datetime.now() - timedelta(days=60),
                        date_to=datetime.now(),
                        status=["paid", "pending"],
                        amount_min=1000.0,
                        amount_max=5000.0,
                        client_ids=[1, 2, 3]
                    )
                    
                    mock_validator.validate_report_request.return_value = {
                        'report_type': ReportType.INVOICE,
                        'filters': filters,
                        'export_format': ExportFormat.PDF
                    }
                    
                    # Filter invoices based on criteria
                    filtered_invoices = [
                        inv for inv in invoices 
                        if inv.status in ["paid", "pending"] and 1000.0 <= inv.total_amount <= 5000.0
                    ]
                    
                    mock_aggregator.aggregate_invoice_data.return_value = {
                        'invoices': filtered_invoices,
                        'summary': {
                            'total_invoices': len(filtered_invoices),
                            'total_amount': sum(inv.total_amount for inv in filtered_invoices),
                            'average_amount': sum(inv.total_amount for inv in filtered_invoices) / len(filtered_invoices)
                        }
                    }
                    
                    mock_exporter.export_report.return_value = Mock(
                        success=True,
                        file_path="/tmp/invoice_report.pdf",
                        file_size=2048
                    )
                    
                    # Execute workflow
                    result = report_service.generate_report(
                        report_type="invoice",
                        filters=filters.dict(),
                        export_format="pdf",
                        user_id=test_user.id
                    )
                    
                    # Verify results
                    assert result.success is True
                    assert result.file_path.endswith('.pdf')
                    
                    # Verify filtering was applied
                    call_args = mock_aggregator.aggregate_invoice_data.call_args[0][0]
                    assert call_args['status'] == ["paid", "pending"]
                    assert call_args['amount_min'] == 1000.0
    
    def test_multi_format_export_workflow(self, mock_db_session, test_user):
        """Test generating the same report in multiple formats"""
        # Setup test data
        payments = [TestDataFactory.create_payment(i, i, 500.0 + i * 50) for i in range(1, 11)]
        
        report_service = ReportService(mock_db_session)
        
        formats_to_test = [ExportFormat.JSON, ExportFormat.CSV, ExportFormat.PDF, ExportFormat.EXCEL]
        results = {}
        
        for export_format in formats_to_test:
            with patch.object(report_service, 'data_aggregator') as mock_aggregator:
                with patch.object(report_service, 'export_service') as mock_exporter:
                    with patch.object(report_service, 'validation_service') as mock_validator:
                        
                        mock_validator.validate_report_request.return_value = {
                            'report_type': ReportType.PAYMENT,
                            'filters': PaymentReportFilters(),
                            'export_format': export_format
                        }
                        
                        mock_aggregator.aggregate_payment_data.return_value = {
                            'payments': payments,
                            'summary': {
                                'total_payments': len(payments),
                                'total_amount': sum(p.amount for p in payments)
                            }
                        }
                        
                        file_extension = {
                            ExportFormat.JSON: 'json',
                            ExportFormat.CSV: 'csv',
                            ExportFormat.PDF: 'pdf',
                            ExportFormat.EXCEL: 'xlsx'
                        }[export_format]
                        
                        mock_exporter.export_report.return_value = Mock(
                            success=True,
                            file_path=f"/tmp/payment_report.{file_extension}",
                            file_size=1024 * (1 if export_format == ExportFormat.JSON else 2)
                        )
                        
                        # Execute workflow
                        result = report_service.generate_report(
                            report_type="payment",
                            filters={},
                            export_format=export_format.value,
                            user_id=test_user.id
                        )
                        
                        results[export_format] = result
        
        # Verify all formats were generated successfully
        for export_format, result in results.items():
            assert result.success is True
            assert result.file_path is not None
            
            # Verify correct file extension
            expected_ext = {
                ExportFormat.JSON: '.json',
                ExportFormat.CSV: '.csv', 
                ExportFormat.PDF: '.pdf',
                ExportFormat.EXCEL: '.xlsx'
            }[export_format]
            assert result.file_path.endswith(expected_ext)
    
    def test_template_based_report_workflow(self, mock_db_session, test_user):
        """Test report generation using saved templates"""
        # Create a template
        template = TestDataFactory.create_report_template(
            1, test_user.id, "expense", "Monthly Expenses"
        )
        template.filters = {
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "categories": ["office_supplies", "travel"]
        }
        template.columns = ["description", "amount", "category", "expense_date"]
        
        # Setup services
        template_service = ReportTemplateService(mock_db_session)
        report_service = ReportService(mock_db_session)
        
        with patch.object(template_service, 'get_template') as mock_get_template:
            with patch.object(report_service, 'generate_report') as mock_generate:
                
                mock_get_template.return_value = template
                mock_generate.return_value = Mock(
                    success=True,
                    file_path="/tmp/expense_report.pdf",
                    template_id=template.id
                )
                
                # Execute template-based generation
                result = template_service.generate_from_template(
                    template_id=template.id,
                    user_id=test_user.id,
                    export_format="pdf"
                )
                
                # Verify template was used
                assert result.success is True
                assert result.template_id == template.id
                
                # Verify report service was called with template filters
                mock_generate.assert_called_once()
                call_args = mock_generate.call_args
                assert call_args[1]['filters'] == template.filters
    
    def test_error_handling_in_workflow(self, mock_db_session, test_user):
        """Test error handling throughout the report workflow"""
        report_service = ReportService(mock_db_session)
        
        # Test validation error
        with patch.object(report_service, 'validation_service') as mock_validator:
            mock_validator.validate_report_request.side_effect = ReportValidationException(
                "Invalid date range", ReportErrorCode.INVALID_FILTERS
            )
            
            result = report_service.generate_report(
                report_type="client",
                filters={"date_from": "invalid-date"},
                export_format="json",
                user_id=test_user.id
            )
            
            assert result.success is False
            assert "Invalid date range" in result.error_message
        
        # Test data aggregation error
        with patch.object(report_service, 'validation_service') as mock_validator:
            with patch.object(report_service, 'data_aggregator') as mock_aggregator:
                
                mock_validator.validate_report_request.return_value = {
                    'report_type': ReportType.CLIENT,
                    'filters': ClientReportFilters(),
                    'export_format': ExportFormat.JSON
                }
                
                mock_aggregator.aggregate_client_data.side_effect = Exception("Database connection error")
                
                result = report_service.generate_report(
                    report_type="client",
                    filters={},
                    export_format="json",
                    user_id=test_user.id
                )
                
                assert result.success is False
                assert "Database connection error" in result.error_message
        
        # Test export error
        with patch.object(report_service, 'validation_service') as mock_validator:
            with patch.object(report_service, 'data_aggregator') as mock_aggregator:
                with patch.object(report_service, 'export_service') as mock_exporter:
                    
                    mock_validator.validate_report_request.return_value = {
                        'report_type': ReportType.CLIENT,
                        'filters': ClientReportFilters(),
                        'export_format': ExportFormat.PDF
                    }
                    
                    mock_aggregator.aggregate_client_data.return_value = {'clients': []}
                    
                    mock_exporter.export_report.return_value = Mock(
                        success=False,
                        error_message="PDF generation failed"
                    )
                    
                    result = report_service.generate_report(
                        report_type="client",
                        filters={},
                        export_format="pdf",
                        user_id=test_user.id
                    )
                    
                    assert result.success is False
                    assert "PDF generation failed" in result.error_message


class TestLargeDatasetPerformance:
    """Performance tests for handling large datasets"""
    
    @pytest.fixture
    def large_dataset(self):
        """Create a large dataset for performance testing"""
        return TestDataFactory.create_large_dataset(
            num_clients=1000,
            num_invoices=5000,
            num_payments=3000
        )
    
    @pytest.fixture
    def mock_db_session_with_large_data(self, large_dataset):
        """Mock database session that returns large datasets"""
        session = Mock(spec=Session)
        
        def mock_query_side_effect(*args):
            query_mock = Mock()
            
            # Configure different return values based on the model being queried
            if args and hasattr(args[0], '__name__'):
                model_name = args[0].__name__
                if model_name == 'Client':
                    query_mock.filter.return_value.all.return_value = large_dataset['clients']
                elif model_name == 'Invoice':
                    query_mock.filter.return_value.all.return_value = large_dataset['invoices']
                elif model_name == 'Payment':
                    query_mock.filter.return_value.all.return_value = large_dataset['payments']
                else:
                    query_mock.filter.return_value.all.return_value = []
            else:
                query_mock.filter.return_value.all.return_value = []
            
            return query_mock
        
        session.query.side_effect = mock_query_side_effect
        return session
    
    def test_large_client_report_performance(self, mock_db_session_with_large_data, large_dataset):
        """Test performance with large client dataset"""
        data_aggregator = ReportDataAggregator(mock_db_session_with_large_data)
        
        # Measure performance
        start_time = time.time()
        
        with patch.object(data_aggregator, '_get_client_data') as mock_get_clients:
            mock_get_clients.return_value = large_dataset['clients']
            
            result = data_aggregator.aggregate_client_data({})
            
            execution_time = time.time() - start_time
            
            # Performance assertions
            assert execution_time < 5.0  # Should complete within 5 seconds
            assert result is not None
            
            # Verify data handling
            mock_get_clients.assert_called_once()
    
    def test_large_invoice_report_with_pagination(self, mock_db_session_with_large_data, large_dataset):
        """Test large invoice report with pagination"""
        data_aggregator = ReportDataAggregator(mock_db_session_with_large_data)
        
        # Test with pagination
        filters = {
            'page': 1,
            'page_size': 1000,
            'date_from': datetime.now() - timedelta(days=365),
            'date_to': datetime.now()
        }
        
        start_time = time.time()
        
        with patch.object(data_aggregator, '_get_invoice_data') as mock_get_invoices:
            # Return paginated results
            mock_get_invoices.return_value = large_dataset['invoices'][:1000]
            
            result = data_aggregator.aggregate_invoice_data(filters)
            
            execution_time = time.time() - start_time
            
            # Performance assertions
            assert execution_time < 3.0  # Pagination should improve performance
            assert result is not None
            
            # Verify pagination was applied
            mock_get_invoices.assert_called_once()
    
    def test_memory_usage_with_large_dataset(self, mock_db_session_with_large_data, large_dataset):
        """Test memory usage with large datasets"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        data_aggregator = ReportDataAggregator(mock_db_session_with_large_data)
        
        with patch.object(data_aggregator, '_get_invoice_data') as mock_get_invoices:
            mock_get_invoices.return_value = large_dataset['invoices']
            
            # Process large dataset
            result = data_aggregator.aggregate_invoice_data({})
            
            peak_memory = process.memory_info().rss
            memory_increase = peak_memory - initial_memory
            
            # Memory usage should be reasonable (less than 100MB increase)
            assert memory_increase < 100 * 1024 * 1024  # 100MB
            assert result is not None
    
    def test_concurrent_large_report_generation(self, mock_db_session_with_large_data):
        """Test concurrent generation of large reports"""
        results = []
        errors = []
        
        def generate_report_worker(worker_id: int):
            try:
                data_aggregator = ReportDataAggregator(mock_db_session_with_large_data)
                
                with patch.object(data_aggregator, '_get_client_data') as mock_get_clients:
                    # Each worker gets a subset of data
                    mock_clients = [
                        TestDataFactory.create_client(i + worker_id * 100) 
                        for i in range(100)
                    ]
                    mock_get_clients.return_value = mock_clients
                    
                    start_time = time.time()
                    result = data_aggregator.aggregate_client_data({})
                    execution_time = time.time() - start_time
                    
                    results.append({
                        'worker_id': worker_id,
                        'execution_time': execution_time,
                        'success': True
                    })
            except Exception as e:
                errors.append({
                    'worker_id': worker_id,
                    'error': str(e)
                })
        
        # Start multiple worker threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=generate_report_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 5  # All workers should complete
        assert len(errors) == 0   # No errors should occur
        
        # All executions should be reasonably fast
        for result in results:
            assert result['execution_time'] < 10.0
            assert result['success'] is True
    
    def test_export_performance_large_dataset(self, large_dataset):
        """Test export performance with large datasets"""
        exporter = ReportExporter()
        
        # Create large report data
        report_data = {
            'data': large_dataset['invoices'],
            'summary': {
                'total_records': len(large_dataset['invoices']),
                'total_amount': sum(inv.total_amount for inv in large_dataset['invoices'])
            },
            'metadata': {
                'generated_at': datetime.now(),
                'report_type': 'invoice'
            }
        }
        
        # Test different export formats
        formats_to_test = [ExportFormat.JSON, ExportFormat.CSV, ExportFormat.EXCEL]
        
        for export_format in formats_to_test:
            start_time = time.time()
            
            with patch.object(exporter, '_write_to_file') as mock_write:
                mock_write.return_value = Mock(
                    success=True,
                    file_path=f"/tmp/large_report.{export_format.value}",
                    file_size=len(large_dataset['invoices']) * 100  # Estimate
                )
                
                result = exporter.export_report(report_data, export_format)
                
                execution_time = time.time() - start_time
                
                # Performance assertions
                assert execution_time < 30.0  # Should complete within 30 seconds
                assert result.success is True
                
                # Verify export was called
                mock_write.assert_called_once()


class TestScheduledReportExecution:
    """End-to-end tests for scheduled report execution"""
    
    @pytest.fixture
    def mock_scheduler_db(self):
        """Mock database session for scheduler tests"""
        session = Mock(spec=Session)
        return session
    
    @pytest.fixture
    def test_scheduled_report(self):
        """Create a test scheduled report"""
        return TestDataFactory.create_scheduled_report(1, 1, 1)
    
    def test_scheduled_report_creation_and_execution(self, mock_scheduler_db, test_scheduled_report):
        """Test complete scheduled report lifecycle"""
        scheduler = ReportScheduler(mock_scheduler_db)
        
        # Mock the scheduled report retrieval
        with patch.object(mock_scheduler_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = [test_scheduled_report]
            
            # Mock report generation
            with patch.object(scheduler, 'report_service') as mock_report_service:
                mock_report_service.generate_report.return_value = Mock(
                    success=True,
                    file_path="/tmp/scheduled_report.pdf",
                    report_id="scheduled_123"
                )
                
                # Mock email service
                with patch.object(scheduler, 'email_service') as mock_email_service:
                    mock_email_service.send_report_email.return_value = True
                    
                    # Execute scheduled reports
                    results = scheduler.execute_due_reports()
                    
                    # Verify execution
                    assert len(results) > 0
                    assert results[0]['success'] is True
                    
                    # Verify report was generated
                    mock_report_service.generate_report.assert_called_once()
                    
                    # Verify email was sent
                    mock_email_service.send_report_email.assert_called_once()
    
    def test_scheduled_report_failure_handling(self, mock_scheduler_db, test_scheduled_report):
        """Test handling of scheduled report failures"""
        scheduler = ReportScheduler(mock_scheduler_db)
        
        with patch.object(mock_scheduler_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = [test_scheduled_report]
            
            # Mock report generation failure
            with patch.object(scheduler, 'report_service') as mock_report_service:
                mock_report_service.generate_report.return_value = Mock(
                    success=False,
                    error_message="Database connection failed"
                )
                
                # Mock notification service
                with patch.object(scheduler, 'notification_service') as mock_notification:
                    mock_notification.send_failure_notification.return_value = True
                    
                    # Execute scheduled reports
                    results = scheduler.execute_due_reports()
                    
                    # Verify failure handling
                    assert len(results) > 0
                    assert results[0]['success'] is False
                    assert "Database connection failed" in results[0]['error_message']
                    
                    # Verify failure notification was sent
                    mock_notification.send_failure_notification.assert_called_once()
    
    def test_scheduled_report_retry_mechanism(self, mock_scheduler_db, test_scheduled_report):
        """Test retry mechanism for failed scheduled reports"""
        scheduler = ReportScheduler(mock_scheduler_db)
        
        with patch.object(mock_scheduler_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = [test_scheduled_report]
            
            # Mock report service with retry logic
            with patch.object(scheduler, 'report_service') as mock_report_service:
                # First call fails, second succeeds
                mock_report_service.generate_report.side_effect = [
                    Mock(success=False, error_message="Temporary failure"),
                    Mock(success=True, file_path="/tmp/retry_report.pdf")
                ]
                
                with patch.object(scheduler, 'email_service') as mock_email_service:
                    mock_email_service.send_report_email.return_value = True
                    
                    # Execute with retry
                    results = scheduler.execute_due_reports(max_retries=2)
                    
                    # Verify retry worked
                    assert len(results) > 0
                    assert results[0]['success'] is True
                    assert results[0]['retry_count'] == 1
                    
                    # Verify report service was called twice
                    assert mock_report_service.generate_report.call_count == 2
    
    def test_scheduled_report_concurrency(self, mock_scheduler_db):
        """Test concurrent execution of multiple scheduled reports"""
        scheduler = ReportScheduler(mock_scheduler_db)
        
        # Create multiple scheduled reports
        scheduled_reports = [
            TestDataFactory.create_scheduled_report(i, i, 1) 
            for i in range(1, 6)
        ]
        
        with patch.object(mock_scheduler_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = scheduled_reports
            
            with patch.object(scheduler, 'report_service') as mock_report_service:
                mock_report_service.generate_report.return_value = Mock(
                    success=True,
                    file_path="/tmp/concurrent_report.pdf"
                )
                
                with patch.object(scheduler, 'email_service') as mock_email_service:
                    mock_email_service.send_report_email.return_value = True
                    
                    # Execute concurrently
                    start_time = time.time()
                    results = scheduler.execute_due_reports(max_concurrent=3)
                    execution_time = time.time() - start_time
                    
                    # Verify all reports were processed
                    assert len(results) == 5
                    assert all(r['success'] for r in results)
                    
                    # Concurrent execution should be faster than sequential
                    assert execution_time < 10.0  # Should complete quickly with concurrency
                    
                    # Verify all reports were generated
                    assert mock_report_service.generate_report.call_count == 5
    
    def test_scheduled_report_email_delivery(self, mock_scheduler_db, test_scheduled_report):
        """Test email delivery for scheduled reports"""
        scheduler = ReportScheduler(mock_scheduler_db)
        
        # Set up multiple recipients
        test_scheduled_report.recipients = [
            "user1@example.com",
            "user2@example.com", 
            "admin@example.com"
        ]
        
        with patch.object(mock_scheduler_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = [test_scheduled_report]
            
            with patch.object(scheduler, 'report_service') as mock_report_service:
                mock_report_service.generate_report.return_value = Mock(
                    success=True,
                    file_path="/tmp/email_report.pdf",
                    file_size=2048
                )
                
                with patch.object(scheduler, 'email_service') as mock_email_service:
                    mock_email_service.send_report_email.return_value = True
                    
                    # Execute scheduled report
                    results = scheduler.execute_due_reports()
                    
                    # Verify email was sent to all recipients
                    assert mock_email_service.send_report_email.call_count == 3
                    
                    # Verify email content
                    for call in mock_email_service.send_report_email.call_args_list:
                        args, kwargs = call
                        assert kwargs['attachment_path'] == "/tmp/email_report.pdf"
                        assert kwargs['recipient'] in test_scheduled_report.recipients
    
    def test_scheduled_report_cleanup(self, mock_scheduler_db):
        """Test cleanup of old scheduled report files"""
        scheduler = ReportScheduler(mock_scheduler_db)
        
        # Create old report history entries
        old_reports = []
        for i in range(1, 6):
            report = Mock()
            report.id = i
            report.file_path = f"/tmp/old_report_{i}.pdf"
            report.generated_at = datetime.now() - timedelta(days=35)  # Older than 30 days
            report.expires_at = datetime.now() - timedelta(days=5)
            old_reports.append(report)
        
        with patch.object(mock_scheduler_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = old_reports
            
            with patch('os.path.exists') as mock_exists:
                with patch('os.remove') as mock_remove:
                    mock_exists.return_value = True
                    
                    # Run cleanup
                    cleaned_count = scheduler.cleanup_old_reports(max_age_days=30)
                    
                    # Verify cleanup
                    assert cleaned_count == 5
                    assert mock_remove.call_count == 5
                    
                    # Verify database cleanup
                    mock_scheduler_db.delete.assert_called()
                    mock_scheduler_db.commit.assert_called()


class TestSecurityAndAccessControl:
    """Security tests for access control and data isolation"""
    
    @pytest.fixture
    def security_service(self):
        """Security service for testing"""
        mock_db = Mock(spec=Session)
        return ReportSecurityService(mock_db)
    
    @pytest.fixture
    def audit_service(self):
        """Audit service for testing"""
        mock_db = Mock(spec=Session)
        return ReportAuditService(mock_db)
    
    def test_tenant_data_isolation(self, security_service):
        """Test that users can only access their tenant's data"""
        # Create users from different tenants
        user_tenant_1 = TestDataFactory.create_user(1, "user1@example.com", "user", 1)
        user_tenant_2 = TestDataFactory.create_user(2, "user2@example.com", "user", 2)
        
        # Create data for different tenants
        tenant_1_clients = [TestDataFactory.create_client(i, tenant_id=1) for i in range(1, 4)]
        tenant_2_clients = [TestDataFactory.create_client(i, tenant_id=2) for i in range(4, 7)]
        
        # Mock database to return all clients
        all_clients = tenant_1_clients + tenant_2_clients
        
        with patch.object(security_service.db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = all_clients
            
            # Test tenant 1 user access
            filtered_data_1 = security_service.filter_data_by_tenant(
                all_clients, user_tenant_1
            )
            
            # Should only get tenant 1 data
            assert len(filtered_data_1) == 3
            assert all(client.tenant_id == 1 for client in filtered_data_1)
            
            # Test tenant 2 user access
            filtered_data_2 = security_service.filter_data_by_tenant(
                all_clients, user_tenant_2
            )
            
            # Should only get tenant 2 data
            assert len(filtered_data_2) == 3
            assert all(client.tenant_id == 2 for client in filtered_data_2)
    
    def test_role_based_report_access(self, security_service):
        """Test role-based access to different report types"""
        # Create users with different roles
        admin_user = TestDataFactory.create_user(1, "admin@example.com", "admin", 1)
        regular_user = TestDataFactory.create_user(2, "user@example.com", "user", 1)
        viewer_user = TestDataFactory.create_user(3, "viewer@example.com", "viewer", 1)
        
        # Test admin access (should have all permissions)
        assert security_service.validate_report_access(admin_user, 'generate')
        assert security_service.validate_report_access(admin_user, 'create_template')
        assert security_service.validate_report_access(admin_user, 'schedule_reports')
        assert security_service.validate_report_access(admin_user, 'manage_permissions')
        
        # Test regular user access (should have most permissions)
        assert security_service.validate_report_access(regular_user, 'generate')
        assert security_service.validate_report_access(regular_user, 'create_template')
        assert security_service.validate_report_access(regular_user, 'schedule_reports')
        
        # Should not have admin permissions
        with pytest.raises(ReportAccessDeniedException):
            security_service.validate_report_access(regular_user, 'manage_permissions')
        
        # Test viewer access (should have limited permissions)
        assert security_service.validate_report_access(viewer_user, 'generate')
        assert security_service.validate_report_access(viewer_user, 'view')
        
        # Should not have write permissions
        with pytest.raises(ReportAccessDeniedException):
            security_service.validate_report_access(viewer_user, 'create_template')
        
        with pytest.raises(ReportAccessDeniedException):
            security_service.validate_report_access(viewer_user, 'schedule_reports')
    
    def test_template_ownership_and_sharing(self, security_service):
        """Test template ownership and sharing permissions"""
        # Create users
        owner_user = TestDataFactory.create_user(1, "owner@example.com", "user", 1)
        other_user = TestDataFactory.create_user(2, "other@example.com", "user", 1)
        
        # Create templates
        private_template = TestDataFactory.create_report_template(1, owner_user.id, "client", "Private Template")
        private_template.is_shared = False
        
        shared_template = TestDataFactory.create_report_template(2, owner_user.id, "invoice", "Shared Template")
        shared_template.is_shared = True
        
        with patch.object(security_service.db, 'query') as mock_query:
            # Test owner access to private template
            mock_query.return_value.filter.return_value.first.return_value = private_template
            
            result = security_service.validate_template_access(owner_user, 1, 'view')
            assert result == private_template
            
            result = security_service.validate_template_access(owner_user, 1, 'update_template')
            assert result == private_template
            
            # Test other user access to private template (should fail)
            with pytest.raises(ReportAccessDeniedException):
                security_service.validate_template_access(other_user, 1, 'view')
            
            # Test other user access to shared template
            mock_query.return_value.filter.return_value.first.return_value = shared_template
            
            result = security_service.validate_template_access(other_user, 2, 'view')
            assert result == shared_template
            
            # Should not be able to modify shared template
            with pytest.raises(ReportAccessDeniedException):
                security_service.validate_template_access(other_user, 2, 'update_template')
    
    def test_data_redaction_by_role(self, security_service):
        """Test data redaction based on user role"""
        # Create users with different roles
        admin_user = TestDataFactory.create_user(1, "admin@example.com", "admin", 1)
        regular_user = TestDataFactory.create_user(2, "user@example.com", "user", 1)
        viewer_user = TestDataFactory.create_user(3, "viewer@example.com", "viewer", 1)
        
        # Create sensitive report data
        report_data = {
            'data': [
                {
                    'client_name': 'John Doe',
                    'email': 'john.doe@example.com',
                    'phone': '555-1234',
                    'ssn': '123-45-6789',
                    'total_amount': 5000.00
                }
            ]
        }
        
        # Test admin (no redaction)
        admin_result = security_service.apply_data_redaction(
            report_data.copy(), ReportType.CLIENT, admin_user, "standard"
        )
        assert admin_result['data'][0]['email'] == 'john.doe@example.com'
        assert admin_result['data'][0]['ssn'] == '123-45-6789'
        
        # Test regular user (standard redaction)
        user_result = security_service.apply_data_redaction(
            report_data.copy(), ReportType.CLIENT, regular_user, "standard"
        )
        assert 'j***' in user_result['data'][0]['email']
        assert '***-**-6789' in user_result['data'][0]['ssn']
        
        # Test viewer (strict redaction)
        viewer_result = security_service.apply_data_redaction(
            report_data.copy(), ReportType.CLIENT, viewer_user, "strict"
        )
        assert viewer_result['data'][0]['email'] == '[REDACTED]'
        assert viewer_result['data'][0]['ssn'] == '[REDACTED]'
    
    def test_audit_logging_for_security_events(self, audit_service):
        """Test audit logging for security-related events"""
        user = TestDataFactory.create_user(1, "test@example.com", "user", 1)
        
        with patch('services.report_audit_service.log_audit_event') as mock_log:
            mock_log.return_value = Mock()
            
            # Test access denied logging
            audit_service.log_access_attempt(
                user_id=user.id,
                user_email=user.email,
                resource_type="report_template",
                resource_id="123",
                action="UPDATE",
                access_granted=False,
                reason="Insufficient permissions"
            )
            
            # Verify audit log was created
            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            
            assert call_args['action'] == 'ACCESS_UPDATE'
            assert call_args['status'] == 'access_denied'
            assert call_args['error_message'] == 'Insufficient permissions'
            assert call_args['user_id'] == user.id
            
            # Test data redaction logging
            mock_log.reset_mock()
            
            audit_service.log_data_redaction(
                user_id=user.id,
                user_email=user.email,
                report_id="report_123",
                redacted_fields=['email', 'phone', 'ssn'],
                redaction_reason="Standard privacy protection"
            )
            
            # Verify redaction was logged
            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            
            assert call_args['action'] == 'DATA_REDACTION'
            assert call_args['resource_id'] == 'report_123'
            assert 'redacted_fields' in call_args['details']
            assert call_args['details']['redacted_fields'] == ['email', 'phone', 'ssn']
    
    def test_rate_limiting_by_user_role(self, security_service):
        """Test rate limiting based on user role"""
        from services.report_security_service import ReportRateLimiter
        
        rate_limiter = ReportRateLimiter(security_service.db)
        
        # Create users with different roles
        admin_user = TestDataFactory.create_user(1, "admin@example.com", "admin", 1)
        regular_user = TestDataFactory.create_user(2, "user@example.com", "user", 1)
        viewer_user = TestDataFactory.create_user(3, "viewer@example.com", "viewer", 1)
        
        with patch.object(security_service.db, 'query') as mock_query:
            # Mock current usage counts
            mock_query.return_value.filter.return_value.scalar.return_value = 10
            
            # Test admin limits (should be higher)
            admin_info = rate_limiter.get_rate_limit_info(admin_user, 'report_generation')
            assert admin_info['limit'] >= 100  # Admins should have high limits
            
            # Test regular user limits
            user_info = rate_limiter.get_rate_limit_info(regular_user, 'report_generation')
            assert user_info['limit'] == 50  # Standard user limit
            
            # Test viewer limits (should be lower)
            viewer_info = rate_limiter.get_rate_limit_info(viewer_user, 'report_generation')
            assert viewer_info['limit'] == 20  # Viewers should have lower limits
            
            # Test viewer template restrictions
            viewer_template_check = rate_limiter.check_rate_limit(viewer_user, 'template_operations')
            assert viewer_template_check is False  # Viewers can't create templates
    
    def test_cross_tenant_access_prevention(self, security_service):
        """Test prevention of cross-tenant data access"""
        # Create users from different tenants
        user_tenant_1 = TestDataFactory.create_user(1, "user1@example.com", "admin", 1)
        user_tenant_2 = TestDataFactory.create_user(2, "user2@example.com", "admin", 2)
        
        # Create template owned by tenant 1 user
        template_tenant_1 = TestDataFactory.create_report_template(1, user_tenant_1.id, "client")
        template_tenant_1.tenant_id = 1
        
        with patch.object(security_service.db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = template_tenant_1
            
            # Tenant 1 user should have access
            result = security_service.validate_template_access(user_tenant_1, 1, 'view')
            assert result == template_tenant_1
            
            # Tenant 2 user should not have access (even as admin)
            with pytest.raises(ReportAccessDeniedException):
                security_service.validate_template_access(user_tenant_2, 1, 'view')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])