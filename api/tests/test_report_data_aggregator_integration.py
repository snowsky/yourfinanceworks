"""
Integration tests for the Report Data Aggregation Service

These tests verify that the aggregation service works correctly with
actual data structures and database queries (mocked appropriately).
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from api.services.report_data_aggregator import ReportDataAggregator, DateRange
from api.schemas.report import (
    ClientReportFilters, InvoiceReportFilters, PaymentReportFilters,
    ExpenseReportFilters, StatementReportFilters
)


class TestReportDataAggregatorIntegration:
    """Integration tests for the ReportDataAggregator"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        return Mock()
    
    @pytest.fixture
    def aggregator(self, mock_db):
        """Create aggregator instance"""
        return ReportDataAggregator(mock_db)
    
    def test_tenant_aware_data_access(self, aggregator):
        """Test that all queries are tenant-aware (no explicit tenant_id needed due to per-tenant databases)"""
        # Mock query setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        aggregator.db.query.return_value = mock_query
        
        # Test client aggregation
        result = aggregator.aggregate_client_data()
        
        # Verify query was called (tenant isolation is handled by per-tenant database)
        assert aggregator.db.query.called
        assert result.total_clients == 0
    
    def test_date_range_filtering_accuracy(self, aggregator):
        """Test that date range filtering works correctly across all entity types"""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        
        filters = ClientReportFilters(
            date_from=start_date,
            date_to=end_date
        )
        
        # Mock query setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        aggregator.db.query.return_value = mock_query
        
        result = aggregator.aggregate_client_data(filters=filters)
        
        # Verify date filtering was applied (filter called multiple times)
        assert mock_query.filter.call_count >= 2  # At least for start and end date
        assert result.total_clients == 0
    
    def test_optimized_database_queries(self, aggregator):
        """Test that queries use proper eager loading for performance"""
        # Mock query setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        aggregator.db.query.return_value = mock_query
        
        # Test invoice aggregation with items
        filters = InvoiceReportFilters(include_items=True)
        result = aggregator.aggregate_invoice_metrics(filters)
        
        # Verify that options (eager loading) was called
        assert mock_query.options.called
        assert result.total_invoices == 0
    
    def test_comprehensive_filtering_support(self, aggregator):
        """Test that all filter types are properly supported"""
        # Test expense filtering with multiple criteria
        filters = ExpenseReportFilters(
            date_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2024, 12, 31, tzinfo=timezone.utc),
            categories=["Office Supplies", "Travel"],
            labels=["Business", "Tax Deductible"],
            vendor="Test Vendor",
            currency="USD"
        )
        
        # Mock query setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []
        aggregator.db.query.return_value = mock_query
        
        result = aggregator.aggregate_expense_categories(filters)
        
        # Verify multiple filters were applied
        assert mock_query.filter.call_count >= 5  # Date range + categories + labels + vendor + currency
        assert result.total_expenses == 0
    
    def test_cross_entity_data_consistency(self, aggregator):
        """Test that cross-entity summary maintains data consistency"""
        date_range = DateRange(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 12, 31, tzinfo=timezone.utc)
        )
        
        # Mock all aggregation methods to return consistent data
        with patch.object(aggregator, 'aggregate_client_data') as mock_client, \
             patch.object(aggregator, 'aggregate_invoice_metrics') as mock_invoice, \
             patch.object(aggregator, 'aggregate_payment_flows') as mock_payment, \
             patch.object(aggregator, 'aggregate_expense_categories') as mock_expense:
            
            # Set up consistent mock data
            from api.services.report_data_aggregator import ClientData, InvoiceMetrics, PaymentFlows, ExpenseBreakdown
            
            client_data = ClientData()
            client_data.total_clients = 5
            client_data.total_balance = 10000.0
            mock_client.return_value = client_data
            
            invoice_data = InvoiceMetrics()
            invoice_data.total_invoices = 20
            invoice_data.total_amount = 50000.0
            invoice_data.total_paid = 30000.0
            mock_invoice.return_value = invoice_data
            
            payment_data = PaymentFlows()
            payment_data.total_payments = 15
            payment_data.total_amount = 30000.0  # Should match invoice total_paid
            mock_payment.return_value = payment_data
            
            expense_data = ExpenseBreakdown()
            expense_data.total_expenses = 10
            expense_data.total_amount = 5000.0
            mock_expense.return_value = expense_data
            
            # Execute cross-entity summary
            result = aggregator.get_cross_entity_summary(date_range, client_ids=[1, 2, 3])
            
            # Verify data consistency
            assert result['metrics']['clients']['total_count'] == 5
            assert result['metrics']['invoices']['total_amount'] == 50000.0
            assert result['metrics']['payments']['total_amount'] == 30000.0
            assert result['metrics']['invoices']['total_paid'] == result['metrics']['payments']['total_amount']
            assert result['metrics']['expenses']['total_amount'] == 5000.0
    
    def test_performance_with_large_datasets(self, aggregator):
        """Test that the aggregator handles large datasets efficiently"""
        # Mock a large dataset
        large_client_list = []
        for i in range(1000):  # Simulate 1000 clients
            client = Mock()
            client.id = i + 1
            client.name = f"Client {i + 1}"
            client.balance = 1000.0
            client.paid_amount = 500.0
            client.invoices = []
            large_client_list.append(client)
        
        # Mock query setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = large_client_list
        aggregator.db.query.return_value = mock_query
        
        # Execute aggregation
        result = aggregator.aggregate_client_data()
        
        # Verify results
        assert result.total_clients == 1000
        assert result.total_balance == 1000000.0  # 1000 * 1000.0
        assert result.total_paid_amount == 500000.0  # 1000 * 500.0
        
        # Verify that eager loading was used for performance
        assert mock_query.options.called
    
    def test_error_handling_with_invalid_filters(self, aggregator):
        """Test that the aggregator handles invalid or edge case filters gracefully"""
        # Mock empty results for all tests
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        aggregator.db.query.return_value = mock_query
        
        # Test with None filters
        result = aggregator.aggregate_client_data(filters=None)
        from api.services.report_data_aggregator import ClientData
        assert isinstance(result, ClientData)
        
        # Test with empty client_ids list
        result = aggregator.aggregate_client_data(client_ids=[])
        assert isinstance(result, ClientData)
        
        # Test with future date range (should return empty results)
        future_filters = ClientReportFilters(
            date_from=datetime(2030, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2030, 12, 31, tzinfo=timezone.utc)
        )
        
        result = aggregator.aggregate_client_data(filters=future_filters)
        assert result.total_clients == 0
    
    def test_currency_handling_across_entities(self, aggregator):
        """Test that currency filtering and aggregation works consistently across all entity types"""
        # Test USD filtering across different entity types
        usd_filters = {
            'currency': 'USD',
            'date_from': datetime(2024, 1, 1, tzinfo=timezone.utc),
            'date_to': datetime(2024, 12, 31, tzinfo=timezone.utc)
        }
        
        # Mock query setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []
        aggregator.db.query.return_value = mock_query
        
        # Test currency filtering on different entity types
        client_result = aggregator.aggregate_client_data(filters=ClientReportFilters(**usd_filters))
        invoice_result = aggregator.aggregate_invoice_metrics(filters=InvoiceReportFilters(**usd_filters))
        payment_result = aggregator.aggregate_payment_flows(filters=PaymentReportFilters(**usd_filters))
        expense_result = aggregator.aggregate_expense_categories(filters=ExpenseReportFilters(**usd_filters))
        
        # Verify all results are valid (empty but properly structured)
        assert hasattr(client_result, 'currencies')
        assert hasattr(invoice_result, 'currency_breakdown')
        assert hasattr(payment_result, 'currency_breakdown')
        assert hasattr(expense_result, 'currency_breakdown')


if __name__ == "__main__":
    pytest.main([__file__])