"""
Unit tests for the Report Data Aggregation Service

Tests cover all aggregation methods, filtering capabilities, and data accuracy
across all entity types: clients, invoices, payments, expenses, and statements.
"""

import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from core.services.report_data_aggregator import (
    ReportDataAggregator, DateRange, ClientData, InvoiceMetrics,
    PaymentFlows, ExpenseBreakdown, TransactionData
)
from core.schemas.report import (
    ClientReportFilters, InvoiceReportFilters, PaymentReportFilters,
    ExpenseReportFilters, StatementReportFilters
)
from core.models.models_per_tenant import (
    Client, Invoice, Payment, Expense, BankStatement, BankStatementTransaction,
    InvoiceItem, User
)


class TestDateRange:
    """Test the DateRange helper class"""
    
    def test_date_range_initialization(self):
        """Test DateRange initialization with various parameters"""
        # Test with no dates
        dr = DateRange()
        assert dr.start_date is None
        assert dr.end_date is None
        
        # Test with both dates
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        dr = DateRange(start, end)
        assert dr.start_date == start
        assert dr.end_date == end
    
    def test_date_range_to_dict(self):
        """Test DateRange to_dict method"""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        dr = DateRange(start, end)
        
        result = dr.to_dict()
        expected = {
            "start_date": start,
            "end_date": end
        }
        assert result == expected


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return Mock(spec=Session)

@pytest.fixture
def aggregator(mock_db):
    """Create a ReportDataAggregator instance with mock database"""
    return ReportDataAggregator(mock_db)

@pytest.fixture
def sample_clients():
    """Create sample client data for testing"""
    clients = []
    for i in range(3):
        client = Mock(spec=Client)
        client.id = i + 1
        client.name = f"Client {i + 1}"
        client.email = f"client{i + 1}@example.com"
        client.phone = f"555-000{i + 1}"
        client.address = f"Address {i + 1}"
        client.balance = 1000.0 * (i + 1)
        client.paid_amount = 500.0 * (i + 1)
        client.preferred_currency = "USD"
        client.created_at = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
        client.updated_at = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
        client.invoices = []  # Will be populated in invoice tests
        clients.append(client)
    return clients

@pytest.fixture
def sample_invoices(sample_clients):
    """Create sample invoice data for testing"""
    invoices = []
    for i, client in enumerate(sample_clients):
        for j in range(2):  # 2 invoices per client
            invoice = Mock(spec=Invoice)
            invoice.id = i * 2 + j + 1
            invoice.number = f"INV-{invoice.id:04d}"
            invoice.amount = 1000.0 + (i * 100) + (j * 50)
            invoice.currency = "USD"
            invoice.status = "paid" if j == 0 else "pending"
            invoice.due_date = datetime(2024, 2, i + j + 1, tzinfo=timezone.utc)
            invoice.client_id = client.id
            invoice.client = client
            invoice.is_recurring = j == 0
            invoice.recurring_frequency = "monthly" if j == 0 else None
            invoice.discount_type = "percentage"
            invoice.discount_value = 10.0
            invoice.subtotal = invoice.amount * 1.1  # Before discount
            invoice.is_deleted = False
            invoice.created_at = datetime(2024, 1, i + j + 1, tzinfo=timezone.utc)
            invoice.updated_at = datetime(2024, 1, i + j + 1, tzinfo=timezone.utc)
            invoice.payments = []  # Will be populated in payment tests
            invoice.items = []
            invoices.append(invoice)
            client.invoices.append(invoice)
    return invoices

@pytest.fixture
def sample_payments(sample_invoices):
    """Create sample payment data for testing"""
    payments = []
    for i, invoice in enumerate(sample_invoices):
        if invoice.status == "paid":  # Only paid invoices have payments
            payment = Mock(spec=Payment)
            payment.id = i + 1
            payment.amount = invoice.amount
            payment.currency = "USD"
            payment.payment_date = datetime(2024, 2, i + 1, tzinfo=timezone.utc)
            payment.payment_method = "credit_card" if i % 2 == 0 else "bank_transfer"
            payment.reference_number = f"PAY-{payment.id:04d}"
            payment.notes = f"Payment for {invoice.number}"
            payment.invoice_id = invoice.id
            payment.invoice = invoice
            payment.user_id = 1
            payment.user = Mock()
            payment.created_at = datetime(2024, 2, i + 1, tzinfo=timezone.utc)
            payment.updated_at = datetime(2024, 2, i + 1, tzinfo=timezone.utc)
            payments.append(payment)
            invoice.payments.append(payment)
    return payments

@pytest.fixture
def sample_expenses():
    """Create sample expense data for testing"""
    expenses = []
    categories = ["Office Supplies", "Travel", "Marketing"]
    vendors = ["Vendor A", "Vendor B", "Vendor C"]
    
    for i in range(5):
        expense = Mock(spec=Expense)
        expense.id = i + 1
        expense.amount = 100.0 + (i * 25)
        expense.currency = "USD"
        expense.expense_date = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
        expense.category = categories[i % len(categories)]
        expense.vendor = vendors[i % len(vendors)]
        expense.label = f"Label {i + 1}"
        expense.labels = [f"Tag{i + 1}", "Business"]
        expense.tax_rate = 0.1
        expense.tax_amount = expense.amount * 0.1
        expense.total_amount = expense.amount * 1.1
        expense.payment_method = "credit_card"
        expense.reference_number = f"EXP-{expense.id:04d}"
        expense.status = "recorded"
        expense.notes = f"Expense {i + 1}"
        expense.invoice_id = None
        expense.invoice = None
        expense.user_id = 1
        expense.user = Mock()
        expense.receipt_path = f"/receipts/receipt_{i + 1}.pdf"
        expense.receipt_filename = f"receipt_{i + 1}.pdf"
        expense.imported_from_attachment = False
        expense.analysis_status = "done"
        expense.created_at = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
        expense.updated_at = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
        expenses.append(expense)
    return expenses

@pytest.fixture
def sample_statements_and_transactions():
    """Create sample bank statement and transaction data for testing"""
    statements = []
    transactions = []
    
    # Create 2 statements
    for i in range(2):
        statement = Mock(spec=BankStatement)
        statement.id = i + 1
        statement.original_filename = f"statement_{i + 1}.pdf"
        statement.status = "processed"
        statement.extracted_count = 3
        statement.notes = f"Statement {i + 1}"
        statement.labels = ["Bank A", "Checking"]
        statement.created_at = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
        statement.updated_at = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
        statements.append(statement)
        
        # Create 3 transactions per statement
        for j in range(3):
            transaction = Mock(spec=BankStatementTransaction)
            transaction.id = i * 3 + j + 1
            transaction.statement_id = statement.id
            transaction.statement = statement
            transaction.date = date(2024, 1, i * 3 + j + 1)
            transaction.description = f"Transaction {transaction.id}"
            transaction.amount = 100.0 * (j + 1) * (1 if j % 2 == 0 else -1)
            transaction.transaction_type = "credit" if j % 2 == 0 else "debit"
            transaction.balance = 1000.0 + transaction.amount
            transaction.category = "Business"
            transaction.invoice_id = None
            transaction.expense_id = None
            transaction.created_at = datetime(2024, 1, i * 3 + j + 1, tzinfo=timezone.utc)
            transaction.updated_at = datetime(2024, 1, i * 3 + j + 1, tzinfo=timezone.utc)
            transactions.append(transaction)
    
    return statements, transactions


class TestReportDataAggregator:
    """Test the main ReportDataAggregator class"""
    pass


class TestClientDataAggregation:
    """Test client data aggregation functionality"""
    
    def test_aggregate_client_data_basic(self, aggregator, sample_clients):
        """Test basic client data aggregation without filters"""
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_clients
        aggregator.db.query.return_value = mock_query
        
        result = aggregator.aggregate_client_data()
        
        assert isinstance(result, ClientData)
        assert result.total_clients == 3
        assert result.total_balance == 6000.0  # 1000 + 2000 + 3000
        assert result.total_paid_amount == 3000.0  # 500 + 1000 + 1500
        assert result.active_clients == 3  # All have positive balance
        assert len(result.clients) == 3
        assert "USD" in result.currencies
    
    def test_aggregate_client_data_with_filters(self, aggregator, sample_clients):
        """Test client data aggregation with filters"""
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_clients[0]]  # Only first client
        aggregator.db.query.return_value = mock_query
        
        filters = ClientReportFilters(
            balance_min=500.0,
            balance_max=1500.0,
            currency="USD"
        )
        
        result = aggregator.aggregate_client_data(filters=filters)
        
        assert result.total_clients == 1
        assert result.total_balance == 1000.0
        assert len(result.clients) == 1
        assert result.clients[0]['name'] == "Client 1"
    
    def test_aggregate_client_data_with_client_ids(self, aggregator, sample_clients):
        """Test client data aggregation with specific client IDs"""
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_clients[:2]  # First two clients
        aggregator.db.query.return_value = mock_query
        
        result = aggregator.aggregate_client_data(client_ids=[1, 2])
        
        assert result.total_clients == 2
        assert result.total_balance == 3000.0  # 1000 + 2000
        assert len(result.clients) == 2


class TestInvoiceMetricsAggregation:
    """Test invoice metrics aggregation functionality"""
    
    def test_aggregate_invoice_metrics_basic(self, aggregator, sample_invoices):
        """Test basic invoice metrics aggregation"""
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_invoices
        aggregator.db.query.return_value = mock_query
        
        result = aggregator.aggregate_invoice_metrics()
        
        assert isinstance(result, InvoiceMetrics)
        assert result.total_invoices == 6  # 3 clients * 2 invoices each
        assert result.total_amount > 0
        assert len(result.status_breakdown) > 0
        assert "paid" in result.status_breakdown
        assert "pending" in result.status_breakdown
        assert len(result.currency_breakdown) > 0
        assert "USD" in result.currency_breakdown
    
    def test_aggregate_invoice_metrics_with_filters(self, aggregator, sample_invoices):
        """Test invoice metrics aggregation with filters"""
        # Filter for only paid invoices
        paid_invoices = [inv for inv in sample_invoices if inv.status == "paid"]
        
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = paid_invoices
        aggregator.db.query.return_value = mock_query
        
        filters = InvoiceReportFilters(
            status=["paid"],
            amount_min=1000.0
        )
        
        result = aggregator.aggregate_invoice_metrics(filters)
        
        assert result.total_invoices == len(paid_invoices)
        assert all(inv['status'] == 'paid' for inv in result.invoices)
        assert result.status_breakdown.get("paid", 0) == len(paid_invoices)
    
    def test_aggregate_invoice_metrics_with_items(self, aggregator, sample_invoices):
        """Test invoice metrics aggregation including items"""
        # Add mock items to first invoice
        item = Mock()
        item.id = 1
        item.description = "Test Item"
        item.quantity = 2.0
        item.price = 100.0
        item.amount = 200.0
        sample_invoices[0].items = [item]
        
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_invoices
        aggregator.db.query.return_value = mock_query
        
        filters = InvoiceReportFilters(include_items=True)
        result = aggregator.aggregate_invoice_metrics(filters)
        
        # Check that items are included for the first invoice
        first_invoice = result.invoices[0]
        assert 'items' in first_invoice
        assert len(first_invoice['items']) == 1
        assert first_invoice['items'][0]['description'] == "Test Item"


class TestPaymentFlowsAggregation:
    """Test payment flows aggregation functionality"""
    
    def test_aggregate_payment_flows_basic(self, aggregator, sample_payments):
        """Test basic payment flows aggregation"""
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = sample_payments
        aggregator.db.query.return_value = mock_query
        
        result = aggregator.aggregate_payment_flows()
        
        assert isinstance(result, PaymentFlows)
        assert result.total_payments == len(sample_payments)
        assert result.total_amount > 0
        assert len(result.method_breakdown) > 0
        assert len(result.currency_breakdown) > 0
        assert len(result.monthly_trends) > 0
    
    def test_aggregate_payment_flows_with_filters(self, aggregator, sample_payments):
        """Test payment flows aggregation with filters"""
        # Filter for credit card payments only
        cc_payments = [p for p in sample_payments if p.payment_method == "credit_card"]
        
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = cc_payments
        aggregator.db.query.return_value = mock_query
        
        filters = PaymentReportFilters(payment_methods=["credit_card"])
        result = aggregator.aggregate_payment_flows(filters)
        
        assert result.total_payments == len(cc_payments)
        assert all(p['payment_method'] == 'credit_card' for p in result.payments)
        assert "credit_card" in result.method_breakdown
    
    def test_aggregate_payment_flows_exclude_unmatched(self, aggregator, sample_payments):
        """Test payment flows aggregation excluding unmatched payments"""
        # Add an unmatched payment
        unmatched_payment = Mock(spec=Payment)
        unmatched_payment.invoice_id = None
        unmatched_payment.invoice = None
        sample_payments.append(unmatched_payment)
        
        # Mock the database query to return only matched payments
        matched_payments = [p for p in sample_payments if p.invoice_id is not None]
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = matched_payments
        aggregator.db.query.return_value = mock_query
        
        filters = PaymentReportFilters(include_unmatched=False)
        result = aggregator.aggregate_payment_flows(filters)
        
        assert result.total_payments == len(matched_payments)
        assert all(p['invoice_id'] is not None for p in result.payments)


class TestExpenseBreakdownAggregation:
    """Test expense breakdown aggregation functionality"""
    
    def test_aggregate_expense_categories_basic(self, aggregator, sample_expenses):
        """Test basic expense categories aggregation"""
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = sample_expenses
        aggregator.db.query.return_value = mock_query
        
        result = aggregator.aggregate_expense_categories()
        
        assert isinstance(result, ExpenseBreakdown)
        assert result.total_expenses == len(sample_expenses)
        assert result.total_amount > 0
        assert len(result.category_breakdown) > 0
        assert len(result.vendor_breakdown) > 0
        assert len(result.currency_breakdown) > 0
        assert len(result.monthly_trends) > 0
    
    def test_aggregate_expense_categories_with_filters(self, aggregator, sample_expenses):
        """Test expense categories aggregation with filters"""
        # Filter for specific category
        office_expenses = [e for e in sample_expenses if e.category == "Office Supplies"]
        
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = office_expenses
        aggregator.db.query.return_value = mock_query
        
        filters = ExpenseReportFilters(categories=["Office Supplies"])
        result = aggregator.aggregate_expense_categories(filters)
        
        assert result.total_expenses == len(office_expenses)
        assert all(e['category'] == 'Office Supplies' for e in result.expenses)
        assert "Office Supplies" in result.category_breakdown
    
    def test_aggregate_expense_categories_with_attachments(self, aggregator, sample_expenses):
        """Test expense categories aggregation including attachments"""
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = sample_expenses
        aggregator.db.query.return_value = mock_query
        
        filters = ExpenseReportFilters(include_attachments=True)
        result = aggregator.aggregate_expense_categories(filters)
        
        # Check that attachment info is included
        first_expense = result.expenses[0]
        assert 'receipt_path' in first_expense
        assert 'receipt_filename' in first_expense
        assert 'imported_from_attachment' in first_expense
        assert 'analysis_status' in first_expense


class TestStatementTransactionAggregation:
    """Test statement transaction aggregation functionality"""
    
    def test_aggregate_statement_transactions_basic(self, aggregator, sample_statements_and_transactions):
        """Test basic statement transaction aggregation"""
        statements, transactions = sample_statements_and_transactions
        
        # Mock the database queries
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = transactions
        aggregator.db.query.return_value = mock_query
        
        result = aggregator.aggregate_statement_transactions()
        
        assert isinstance(result, TransactionData)
        assert result.total_transactions == len(transactions)
        assert result.total_credits > 0
        assert result.total_debits > 0
        assert len(result.type_breakdown) > 0
        assert len(result.monthly_trends) > 0
    
    def test_aggregate_statement_transactions_with_filters(self, aggregator, sample_statements_and_transactions):
        """Test statement transaction aggregation with filters"""
        statements, transactions = sample_statements_and_transactions
        
        # Filter for credit transactions only
        credit_transactions = [t for t in transactions if t.transaction_type == "credit"]
        
        # Mock the database query
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = credit_transactions
        aggregator.db.query.return_value = mock_query
        
        filters = StatementReportFilters(transaction_types=["credit"])
        result = aggregator.aggregate_statement_transactions(filters)
        
        assert result.total_transactions == len(credit_transactions)
        assert all(t['transaction_type'] == 'credit' for t in result.transactions)
        assert result.total_debits == 0  # No debit transactions
    
    def test_aggregate_statement_transactions_with_reconciliation(self, aggregator, sample_statements_and_transactions):
        """Test statement transaction aggregation including reconciliation status"""
        statements, transactions = sample_statements_and_transactions
        
        # Set some transactions as reconciled
        transactions[0].invoice_id = 1
        transactions[1].expense_id = 1
        
        # Mock the database queries
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = transactions
        aggregator.db.query.return_value = mock_query
        
        # Mock statement query
        mock_statement_query = Mock()
        mock_statement_query.filter.return_value = mock_statement_query
        mock_statement_query.all.return_value = statements
        
        # Set up query method to return different mocks based on model
        def mock_query_method(model):
            if model == BankStatementTransaction:
                return mock_query
            elif model == BankStatement:
                return mock_statement_query
            return Mock()
        
        aggregator.db.query.side_effect = mock_query_method
        
        filters = StatementReportFilters(include_reconciliation=True)
        result = aggregator.aggregate_statement_transactions(filters)
        
        # Check that reconciliation info is included
        first_transaction = result.transactions[0]
        assert 'is_reconciled' in first_transaction
        assert 'reconciled_with' in first_transaction


class TestCrossEntitySummary:
    """Test cross-entity summary functionality"""
    
    def test_get_cross_entity_summary(self, aggregator, sample_clients, sample_invoices, sample_payments, sample_expenses):
        """Test comprehensive cross-entity summary"""
        date_range = DateRange(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 12, 31, tzinfo=timezone.utc)
        )
        
        # Mock all the individual aggregation methods
        with patch.object(aggregator, 'aggregate_client_data') as mock_client, \
             patch.object(aggregator, 'aggregate_invoice_metrics') as mock_invoice, \
             patch.object(aggregator, 'aggregate_payment_flows') as mock_payment, \
             patch.object(aggregator, 'aggregate_expense_categories') as mock_expense:
            
            # Set up mock return values
            mock_client_data = ClientData()
            mock_client_data.total_clients = 3
            mock_client_data.active_clients = 3
            mock_client_data.total_balance = 6000.0
            mock_client_data.total_paid_amount = 3000.0
            mock_client.return_value = mock_client_data
            
            mock_invoice_data = InvoiceMetrics()
            mock_invoice_data.total_invoices = 6
            mock_invoice_data.total_amount = 7000.0
            mock_invoice_data.total_paid = 3000.0
            mock_invoice_data.total_outstanding = 4000.0
            mock_invoice_data.average_amount = 1166.67
            mock_invoice_data.status_breakdown = {"paid": 3, "pending": 3}
            mock_invoice.return_value = mock_invoice_data
            
            mock_payment_data = PaymentFlows()
            mock_payment_data.total_payments = 3
            mock_payment_data.total_amount = 3000.0
            mock_payment_data.method_breakdown = {"credit_card": 1500.0, "bank_transfer": 1500.0}
            mock_payment_data.monthly_trends = {"2024-02": 3000.0}
            mock_payment.return_value = mock_payment_data
            
            mock_expense_data = ExpenseBreakdown()
            mock_expense_data.total_expenses = 5
            mock_expense_data.total_amount = 625.0
            mock_expense_data.category_breakdown = {"Office Supplies": 200.0, "Travel": 225.0, "Marketing": 200.0}
            mock_expense_data.monthly_trends = {"2024-01": 625.0}
            mock_expense.return_value = mock_expense_data
            
            # Execute the method
            result = aggregator.get_cross_entity_summary(date_range, client_ids=[1, 2, 3])
            
            # Verify the result structure
            assert 'date_range' in result
            assert 'client_ids' in result
            assert 'metrics' in result
            
            assert result['client_ids'] == [1, 2, 3]
            assert result['date_range']['start_date'] == date_range.start_date
            assert result['date_range']['end_date'] == date_range.end_date
            
            # Verify metrics structure
            metrics = result['metrics']
            assert 'clients' in metrics
            assert 'invoices' in metrics
            assert 'payments' in metrics
            assert 'expenses' in metrics
            
            # Verify client metrics
            assert metrics['clients']['total_count'] == 3
            assert metrics['clients']['active_count'] == 3
            assert metrics['clients']['total_balance'] == 6000.0
            assert metrics['clients']['total_paid'] == 3000.0
            
            # Verify invoice metrics
            assert metrics['invoices']['total_count'] == 6
            assert metrics['invoices']['total_amount'] == 7000.0
            assert metrics['invoices']['total_paid'] == 3000.0
            assert metrics['invoices']['total_outstanding'] == 4000.0
            
            # Verify payment metrics
            assert metrics['payments']['total_count'] == 3
            assert metrics['payments']['total_amount'] == 3000.0
            
            # Verify expense metrics
            assert metrics['expenses']['total_count'] == 5
            assert metrics['expenses']['total_amount'] == 625.0


class TestHelperMethods:
    """Test helper methods in the aggregator"""
    
    def test_apply_date_filter(self, aggregator):
        """Test the _apply_date_filter helper method"""
        # Create a mock query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        
        # Create a mock date field that supports comparison operations
        mock_date_field = Mock()
        mock_date_field.__ge__ = Mock(return_value=True)
        mock_date_field.__le__ = Mock(return_value=True)
        
        date_range = DateRange(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 12, 31, tzinfo=timezone.utc)
        )
        
        result = aggregator._apply_date_filter(mock_query, mock_date_field, date_range)
        
        # Verify that filter was called twice (for start and end date)
        assert mock_query.filter.call_count == 2
        assert result == mock_query
    
    def test_get_date_range_from_filters(self, aggregator):
        """Test the _get_date_range_from_filters helper method"""
        filters = {
            'date_from': datetime(2024, 1, 1, tzinfo=timezone.utc),
            'date_to': datetime(2024, 12, 31, tzinfo=timezone.utc)
        }
        
        result = aggregator._get_date_range_from_filters(filters)
        
        assert isinstance(result, DateRange)
        assert result.start_date == filters['date_from']
        assert result.end_date == filters['date_to']
    
    def test_get_date_range_from_empty_filters(self, aggregator):
        """Test _get_date_range_from_filters with empty filters"""
        filters = {}
        
        result = aggregator._get_date_range_from_filters(filters)
        
        assert isinstance(result, DateRange)
        assert result.start_date is None
        assert result.end_date is None


if __name__ == "__main__":
    pytest.main([__file__])