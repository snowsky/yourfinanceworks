"""
Report Data Aggregation Service

This service provides optimized database queries for generating reports across
all major entities in the system: clients, invoices, payments, expenses, and statements.
All queries are tenant-aware and support comprehensive filtering options.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
import logging

logger = logging.getLogger(__name__)

from core.models.models_per_tenant import (
    Client, Invoice, Payment, Expense, BankStatement, BankStatementTransaction,
    InvoiceItem, User
)
from core.schemas.report import (
    ClientReportFilters, InvoiceReportFilters, PaymentReportFilters,
    ExpenseReportFilters, StatementReportFilters, CashFlowReportFilters
)


class DateRange:
    """Helper class for date range operations"""

    def __init__(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
        from datetime import timezone, time

        # Normalize datetimes to ensure timezone awareness
        if start_date and start_date.tzinfo is None:
            # Make timezone-naive datetime timezone-aware (UTC)
            self.start_date = start_date.replace(tzinfo=timezone.utc)
        else:
            self.start_date = start_date

        if end_date:
            if end_date.tzinfo is None:
                # Make timezone-naive datetime timezone-aware (UTC)
                end_date = end_date.replace(tzinfo=timezone.utc)
            
            # If end_date is exactly at the start of the day (00:00:00), 
            # adjust it to the end of the day (23:59:59.999999) to make it inclusive
            if end_date.time() == time(0, 0, 0):
                self.end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            else:
                self.end_date = end_date
        else:
            self.end_date = end_date

    def to_dict(self) -> Dict[str, Optional[datetime]]:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date
        }


class ClientData:
    """Data structure for client aggregation results"""

    def __init__(self):
        self.clients: List[Dict[str, Any]] = []
        self.total_clients: int = 0
        self.total_balance: float = 0.0
        self.total_paid_amount: float = 0.0
        self.active_clients: int = 0
        self.currencies: List[str] = []


class InvoiceMetrics:
    """Data structure for invoice aggregation results"""

    def __init__(self):
        self.invoices: List[Dict[str, Any]] = []
        self.total_invoices: int = 0
        self.total_amount: float = 0.0
        self.total_paid: float = 0.0
        self.total_outstanding: float = 0.0
        self.status_breakdown: Dict[str, int] = {}
        self.currency_breakdown: Dict[str, float] = {}
        self.average_amount: float = 0.0


class PaymentFlows:
    """Data structure for payment aggregation results"""

    def __init__(self):
        self.payments: List[Dict[str, Any]] = []
        self.total_payments: int = 0
        self.total_amount: float = 0.0
        self.method_breakdown: Dict[str, float] = {}
        self.currency_breakdown: Dict[str, float] = {}
        self.monthly_trends: Dict[str, float] = {}


class ExpenseBreakdown:
    """Data structure for expense aggregation results"""
    def __init__(self):
        self.expenses: List[Dict[str, Any]] = []
        self.total_expenses: int = 0
        self.total_amount: float = 0.0
        self.category_breakdown: Dict[str, float] = {}
        self.vendor_breakdown: Dict[str, float] = {}
        self.currency_breakdown: Dict[str, float] = {}
        self.monthly_trends: Dict[str, float] = {}


class TransactionData:
    """Data structure for statement transaction aggregation results"""
    def __init__(self):
        self.transactions: List[Dict[str, Any]] = []
        self.statements: List[Dict[str, Any]] = []
        self.total_transactions: int = 0
        self.total_credits: float = 0.0
        self.total_debits: float = 0.0
        self.net_flow: float = 0.0
        self.type_breakdown: Dict[str, float] = {}
        self.monthly_trends: Dict[str, float] = {}


class CashFlowData:
    """Data structure for unified cash flow aggregation results"""
    def __init__(self):
        self.inflows: List[Dict[str, Any]] = []
        self.outflows: List[Dict[str, Any]] = []
        self.total_income: float = 0.0
        self.total_expenses: float = 0.0
        self.net_cash_flow: float = 0.0
        self.monthly_trends: Dict[str, Dict[str, float]] = {}
        self.unreconciled_count: int = 0
        self.currency_breakdown: Dict[str, Dict[str, float]] = {}


class ReportDataAggregator:
    """
    Core service for aggregating data across all entity types for reporting.
    Provides optimized queries with filtering, tenant isolation, and comprehensive metrics.
    """
    def __init__(self, db: Session):
        self.db = db

    def _apply_date_filter(self, query, date_field, date_range: DateRange):
        """Apply date range filtering to a query"""
        if date_range.start_date:
            query = query.filter(date_field >= date_range.start_date)
        if date_range.end_date:
            query = query.filter(date_field <= date_range.end_date)
        return query

    def _get_date_range_from_filters(self, filters: Dict[str, Any]) -> DateRange:
        """Extract date range from filter dictionary"""
        return DateRange(
            start_date=filters.get('date_from'),
            end_date=filters.get('date_to')
        )

    def aggregate_client_data(
        self, 
        client_ids: Optional[List[int]] = None, 
        filters: Optional[ClientReportFilters] = None
    ) -> ClientData:
        """
        Aggregate client data with comprehensive metrics and filtering.

        Args:
            client_ids: Optional list of specific client IDs to include
            filters: Client-specific filters

        Returns:
            ClientData object with aggregated client information
        """
        result = ClientData()

        # Build base query with eager loading for performance
        query = self.db.query(Client).options(
            joinedload(Client.invoices),
        )

        # Apply client ID filtering
        if client_ids:
            query = query.filter(Client.id.in_(client_ids))

        # Apply filters if provided
        if filters:
            date_range = DateRange(filters.date_from, filters.date_to)

            # Filter by balance range
            if filters.balance_min is not None:
                query = query.filter(Client.balance >= filters.balance_min)
            if filters.balance_max is not None:
                query = query.filter(Client.balance <= filters.balance_max)

            # Filter by currency
            if filters.currency:
                query = query.filter(Client.preferred_currency == filters.currency)

            # Apply date filtering on client creation
            if date_range.start_date or date_range.end_date:
                query = self._apply_date_filter(query, Client.created_at, date_range)

        # Execute query and process results
        clients = query.all()

        for client in clients:
            # Calculate client metrics
            client_invoices = client.invoices


            total_invoices = len(client_invoices)
            total_invoice_amount = sum(inv.amount for inv in client_invoices)

            client_data = {
                'id': client.id,
                'name': client.name,
                'email': client.email,
                'phone': client.phone,
                'address': client.address,
                'balance': client.balance,
                'paid_amount': client.paid_amount,
                'preferred_currency': client.preferred_currency,
                'total_invoices': total_invoices,
                'total_invoice_amount': total_invoice_amount,
                'created_at': client.created_at,
                'updated_at': client.updated_at
            }

            result.clients.append(client_data)
            result.total_balance += client.balance or 0.0
            result.total_paid_amount += client.paid_amount or 0.0

            if client.preferred_currency and client.preferred_currency not in result.currencies:
                result.currencies.append(client.preferred_currency)

        result.total_clients = len(result.clients)
        result.active_clients = len([c for c in result.clients if c['balance'] > 0])

        return result

    def aggregate_invoice_metrics(
        self, 
        filters: Optional[InvoiceReportFilters] = None
    ) -> InvoiceMetrics:
        """
        Aggregate invoice data with comprehensive metrics and filtering.

        Args:
            filters: Invoice-specific filters

        Returns:
            InvoiceMetrics object with aggregated invoice information
        """
        result = InvoiceMetrics()

        # Build base query with joins for performance
        options_list = [
            joinedload(Invoice.client),
            joinedload(Invoice.payments)
        ]

        # Only add items joinedload if needed
        if filters and filters.include_items:
            options_list.append(joinedload(Invoice.items))

        query = self.db.query(Invoice).options(*options_list).filter(Invoice.is_deleted == False)  # Exclude soft-deleted invoices

        # Apply filters if provided
        if filters:
            date_range = DateRange(filters.date_from, filters.date_to)

            # Apply date filtering
            if date_range.start_date or date_range.end_date:
                query = self._apply_date_filter(query, Invoice.created_at, date_range)

            # Filter by client IDs
            if filters.client_ids:
                query = query.filter(Invoice.client_id.in_(filters.client_ids))

            # Filter by status
            if filters.status:
                query = query.filter(Invoice.status.in_(filters.status))

            # Filter by amount range
            if filters.amount_min is not None:
                query = query.filter(Invoice.amount >= filters.amount_min)
            if filters.amount_max is not None:
                query = query.filter(Invoice.amount <= filters.amount_max)

            # Filter by currency
            if filters.currency:
                query = query.filter(Invoice.currency == filters.currency)

            # Filter by recurring status
            if filters.is_recurring is not None:
                query = query.filter(Invoice.is_recurring == filters.is_recurring)

        # Execute query and process results
        invoices = query.all()

        for invoice in invoices:
            # Calculate payment totals for this invoice
            total_payments = sum(payment.amount for payment in invoice.payments)
            outstanding_amount = invoice.amount - total_payments

            invoice_data = {
                'id': invoice.id,
                'number': invoice.number,
                'amount': invoice.amount,
                'currency': invoice.currency,
                'status': invoice.status,
                'due_date': invoice.due_date,
                'client_id': invoice.client_id,
                'client_name': invoice.client.name if invoice.client else None,
                'client_email': invoice.client.email if invoice.client else None,
                'total_payments': total_payments,
                'outstanding_amount': outstanding_amount,
                'is_recurring': invoice.is_recurring,
                'recurring_frequency': invoice.recurring_frequency,
                'discount_type': invoice.discount_type,
                'discount_value': invoice.discount_value,
                'subtotal': invoice.subtotal,
                'created_at': invoice.created_at,
                'updated_at': invoice.updated_at
            }

            # Include items if requested
            if filters and filters.include_items and invoice.items:
                invoice_data['items'] = [
                    {
                        'id': item.id,
                        'description': item.description,
                        'quantity': item.quantity,
                        'price': item.price,
                        'amount': item.amount
                    }
                    for item in invoice.items
                ]

            result.invoices.append(invoice_data)
            result.total_amount += invoice.amount
            result.total_paid += total_payments
            result.total_outstanding += outstanding_amount

            # Update status breakdown
            status = invoice.status
            result.status_breakdown[status] = result.status_breakdown.get(status, 0) + 1

            # Update currency breakdown
            currency = invoice.currency
            result.currency_breakdown[currency] = result.currency_breakdown.get(currency, 0.0) + invoice.amount

        result.total_invoices = len(result.invoices)
        result.average_amount = result.total_amount / result.total_invoices if result.total_invoices > 0 else 0.0

        return result

    def aggregate_payment_flows(
        self, 
        filters: Optional[PaymentReportFilters] = None
    ) -> PaymentFlows:
        """
        Aggregate payment data with comprehensive flow analysis and filtering.

        Args:
            filters: Payment-specific filters

        Returns:
            PaymentFlows object with aggregated payment information
        """
        result = PaymentFlows()

        # Build base query with joins
        query = self.db.query(Payment).options(
            joinedload(Payment.invoice).joinedload(Invoice.client),
            joinedload(Payment.user)
        )

        # Apply filters if provided
        if filters:
            date_range = DateRange(filters.date_from, filters.date_to)

            # Apply date filtering
            if date_range.start_date or date_range.end_date:
                query = self._apply_date_filter(query, Payment.payment_date, date_range)

            # Filter by client IDs (through invoice relationship)
            if filters.client_ids:
                query = query.join(Payment.invoice).filter(Invoice.client_id.in_(filters.client_ids))

            # Filter by payment methods
            if filters.payment_methods:
                query = query.filter(Payment.payment_method.in_(filters.payment_methods))

            # Filter by amount range
            if filters.amount_min is not None:
                query = query.filter(Payment.amount >= filters.amount_min)
            if filters.amount_max is not None:
                query = query.filter(Payment.amount <= filters.amount_max)

            # Filter by currency
            if filters.currency:
                query = query.filter(Payment.currency == filters.currency)

            # Include unmatched payments (payments without invoice)
            if not filters.include_unmatched:
                query = query.filter(Payment.invoice_id.isnot(None))

        # Execute query and process results
        payments = query.all()

        for payment in payments:
            payment_data = {
                'id': payment.id,
                'amount': payment.amount,
                'currency': payment.currency,
                'payment_date': payment.payment_date,
                'payment_method': payment.payment_method,
                'reference_number': payment.reference_number,
                'notes': payment.notes,
                'invoice_id': payment.invoice_id,
                'invoice_number': payment.invoice.number if payment.invoice else None,
                'client_id': payment.invoice.client_id if payment.invoice else None,
                'client_name': payment.invoice.client.name if payment.invoice and payment.invoice.client else None,
                'user_id': payment.user_id,
                'created_at': payment.created_at,
                'updated_at': payment.updated_at
            }

            result.payments.append(payment_data)
            result.total_amount += payment.amount

            # Update method breakdown
            method = payment.payment_method
            result.method_breakdown[method] = result.method_breakdown.get(method, 0.0) + payment.amount

            # Update currency breakdown
            currency = payment.currency
            result.currency_breakdown[currency] = result.currency_breakdown.get(currency, 0.0) + payment.amount

            # Update monthly trends
            month_key = payment.payment_date.strftime('%Y-%m')
            result.monthly_trends[month_key] = result.monthly_trends.get(month_key, 0.0) + payment.amount

        result.total_payments = len(result.payments)

        return result

    def aggregate_expense_categories(
        self, 
        filters: Optional[ExpenseReportFilters] = None
    ) -> ExpenseBreakdown:
        """
        Aggregate expense data with category breakdown and filtering.

        Args:
            filters: Expense-specific filters

        Returns:
            ExpenseBreakdown object with aggregated expense information
        """
        result = ExpenseBreakdown()

        # Build base query with joins
        query = self.db.query(Expense).options(
            joinedload(Expense.user),
            joinedload(Expense.invoice).joinedload(Invoice.client)
        )

        # Apply filters if provided
        if filters:
            date_range = DateRange(filters.date_from, filters.date_to)

            # Apply date filtering
            if date_range.start_date or date_range.end_date:
                query = self._apply_date_filter(query, Expense.expense_date, date_range)

            # Filter by client IDs (through invoice relationship)
            if filters.client_ids:
                query = query.join(Invoice, Expense.invoice_id == Invoice.id, isouter=True).filter(
                    or_(Invoice.client_id.in_(filters.client_ids), Expense.invoice_id.is_(None))
                )

            # Filter by categories
            if filters.categories:
                query = query.filter(Expense.category.in_(filters.categories))

            # Filter by labels (both single label and multiple labels)
            if filters.labels:
                label_conditions = []
                for label in filters.labels:
                    # Check single label field
                    label_conditions.append(Expense.label == label)
                    # Check JSON labels array - use a safer approach
                    try:
                        # Try using JSON extraction if supported by the database
                        label_conditions.append(func.json_extract(Expense.labels, '$').like(f'%"{label}"%'))
                    except Exception:
                        # Fallback for databases that don't support json_extract
                        label_conditions.append(Expense.labels.like(f'%"{label}"%'))
                if label_conditions:
                    query = query.filter(or_(*label_conditions))

            # Filter by vendor
            if filters.vendor:
                query = query.filter(Expense.vendor.ilike(f'%{filters.vendor}%'))

            # Filter by status
            if filters.status:
                query = query.filter(Expense.status.in_(filters.status))

            # Filter by currency
            if filters.currency:
                query = query.filter(Expense.currency == filters.currency)

        # Execute query and process results
        expenses = query.all()

        for expense in expenses:
            expense_data = {
                'id': expense.id,
                'amount': expense.amount,
                'currency': expense.currency,
                'expense_date': expense.expense_date,
                'category': expense.category,
                'vendor': expense.vendor,
                'label': expense.label,
                'labels': expense.labels,
                'tax_rate': expense.tax_rate,
                'tax_amount': expense.tax_amount,
                'total_amount': expense.total_amount,
                'payment_method': expense.payment_method,
                'reference_number': expense.reference_number,
                'status': expense.status,
                'notes': expense.notes,
                'invoice_id': expense.invoice_id,
                'invoice_number': expense.invoice.number if expense.invoice else None,
                'client_id': expense.invoice.client_id if expense.invoice else None,
                'client_name': expense.invoice.client.name if expense.invoice and expense.invoice.client else None,
                'user_id': expense.user_id,
                'created_at': expense.created_at,
                'updated_at': expense.updated_at
            }

            # Include attachment info if requested
            if filters and filters.include_attachments:
                expense_data.update({
                    'receipt_path': expense.receipt_path,
                    'receipt_filename': expense.receipt_filename,
                    'imported_from_attachment': expense.imported_from_attachment,
                    'analysis_status': expense.analysis_status
                })

            result.expenses.append(expense_data)
            result.total_amount += expense.amount

            # Update category breakdown
            category = expense.category
            result.category_breakdown[category] = result.category_breakdown.get(category, 0.0) + expense.amount

            # Update vendor breakdown
            if expense.vendor:
                vendor = expense.vendor
                result.vendor_breakdown[vendor] = result.vendor_breakdown.get(vendor, 0.0) + expense.amount

            # Update currency breakdown
            currency = expense.currency
            result.currency_breakdown[currency] = result.currency_breakdown.get(currency, 0.0) + expense.amount

            # Update monthly trends
            month_key = expense.expense_date.strftime('%Y-%m')
            result.monthly_trends[month_key] = result.monthly_trends.get(month_key, 0.0) + expense.amount

        result.total_expenses = len(result.expenses)

        return result

    def aggregate_statement_transactions(
        self, 
        filters: Optional[StatementReportFilters] = None
    ) -> TransactionData:
        """
        Aggregate bank statement transaction data with comprehensive analysis.

        Args:
            filters: Statement-specific filters

        Returns:
            TransactionData object with aggregated transaction information
        """
        result = TransactionData()

        # Build base query for transactions with statement info
        query = self.db.query(BankStatementTransaction).options(
            joinedload(BankStatementTransaction.statement)
        )

        # Apply filters if provided
        if filters:
            date_range = DateRange(filters.date_from, filters.date_to)

            # Apply date filtering based on statement creation date
            if date_range.start_date or date_range.end_date:
                # Join with BankStatement to filter by its created_at field
                query = query.join(BankStatementTransaction.statement)
                query = self._apply_date_filter(query, BankStatement.created_at, date_range)

            # Filter by account IDs (through statement relationship)
            # Note: join(BankStatementTransaction.statement) is already handled above if date filtering is applied,
            # but SQLAlchemy join() is idempotent for the same target relationship.
            if filters and hasattr(filters, 'account_ids') and filters.account_ids:
                if not (date_range.start_date or date_range.end_date):
                    query = query.join(BankStatementTransaction.statement)
                query = query.filter(BankStatement.id.in_(filters.account_ids))

            # Filter by transaction types
            if filters and hasattr(filters, 'transaction_types') and filters.transaction_types:
                query = query.filter(BankStatementTransaction.transaction_type.in_(filters.transaction_types))

            # Filter by amount range
            if filters and hasattr(filters, 'amount_min') and filters.amount_min is not None:
                query = query.filter(func.abs(BankStatementTransaction.amount) >= filters.amount_min)
            if filters and hasattr(filters, 'amount_max') and filters.amount_max is not None:
                query = query.filter(func.abs(BankStatementTransaction.amount) <= filters.amount_max)

        # Execute query and process results
        transactions = query.all()

        for transaction in transactions:
            transaction_data = {
                'id': transaction.id,
                'statement_id': transaction.statement_id,
                'statement_filename': transaction.statement.original_filename if transaction.statement else None,
                'date': transaction.date,
                'description': transaction.description,
                'amount': transaction.amount,
                'transaction_type': transaction.transaction_type,
                'balance': transaction.balance,
                'category': transaction.category,
                'invoice_id': transaction.invoice_id,
                'expense_id': transaction.expense_id,
                'created_at': transaction.created_at,
                'updated_at': transaction.updated_at
            }

            # Include reconciliation status if requested
            if filters and hasattr(filters, 'include_reconciliation') and filters.include_reconciliation:
                transaction_data.update({
                    'is_reconciled': transaction.invoice_id is not None or transaction.expense_id is not None,
                    'reconciled_with': 'invoice' if transaction.invoice_id else ('expense' if transaction.expense_id else None)
                })

            result.transactions.append(transaction_data)

            # Update totals based on transaction type
            if transaction.transaction_type == 'credit':
                result.total_credits += abs(transaction.amount)
            else:
                result.total_debits += abs(transaction.amount)

            # Update type breakdown
            tx_type = transaction.transaction_type
            result.type_breakdown[tx_type] = result.type_breakdown.get(tx_type, 0.0) + abs(transaction.amount)

            # Update monthly trends
            month_key = transaction.date.strftime('%Y-%m')
            result.monthly_trends[month_key] = result.monthly_trends.get(month_key, 0.0) + transaction.amount

        result.total_transactions = len(result.transactions)
        result.net_flow = result.total_credits - result.total_debits

        # Get statement summary
        statement_query = self.db.query(BankStatement)
        if filters:
            if hasattr(filters, 'account_ids') and filters.account_ids:
                statement_query = statement_query.filter(BankStatement.id.in_(filters.account_ids))
            
            # Apply date filtering to statement summary as well
            date_range = DateRange(filters.date_from, filters.date_to)
            if date_range.start_date or date_range.end_date:
                statement_query = self._apply_date_filter(statement_query, BankStatement.created_at, date_range)
    
        statements = statement_query.all()
        for statement in statements:
            statement_data = {
                'id': statement.id,
                'original_filename': statement.original_filename,
                'status': statement.status,
                'extracted_count': statement.extracted_count,
                'notes': statement.notes,
                'labels': statement.labels,
                'created_at': statement.created_at,
                'updated_at': statement.updated_at
            }
            result.statements.append(statement_data)

        return result

    def aggregate_cash_flow(
        self,
        filters: Optional[CashFlowReportFilters] = None
    ) -> CashFlowData:
        """
        Aggregate unified cash flow data combining payments (income), expenses (outflows),
        and unlinked bank transactions (credits as income, debits as expenses).

        Only bank transactions that are NOT already linked to a payment (via invoice_id)
        or an expense (via expense_id) are included to avoid double-counting.

        Args:
            filters: Cash flow-specific filters

        Returns:
            CashFlowData object with aggregated cash flow information
        """
        result = CashFlowData()

        # Build base payment filters from cash flow filters
        payment_filters = None
        expense_filters = None
        if filters:
            payment_filter_kwargs = {
                'date_from': filters.date_from,
                'date_to': filters.date_to,
                'client_ids': filters.client_ids,
                'currency': filters.currency,
                'amount_min': filters.amount_min,
                'amount_max': filters.amount_max,
            }
            if filters.payment_methods:
                payment_filter_kwargs['payment_methods'] = filters.payment_methods
            payment_filters = PaymentReportFilters(**payment_filter_kwargs)

            expense_filter_kwargs = {
                'date_from': filters.date_from,
                'date_to': filters.date_to,
                'client_ids': filters.client_ids,
                'currency': filters.currency,
            }
            if filters.categories:
                expense_filter_kwargs['categories'] = filters.categories
            expense_filters = ExpenseReportFilters(**expense_filter_kwargs)

        # 1. Payments received (income from invoices)
        payment_data = self.aggregate_payment_flows(payment_filters)
        for p in payment_data.payments:
            item = {**p, 'source': 'payment', 'flow_type': 'income'}
            result.inflows.append(item)
            amount = abs(p.get('amount', 0.0))
            result.total_income += amount

            # Monthly trends
            date_val = p.get('payment_date')
            if date_val:
                month_key = date_val.strftime('%Y-%m') if hasattr(date_val, 'strftime') else str(date_val)[:7]
                if month_key not in result.monthly_trends:
                    result.monthly_trends[month_key] = {'income': 0.0, 'expense': 0.0, 'net': 0.0}
                result.monthly_trends[month_key]['income'] += amount

            # Currency breakdown
            currency = p.get('currency', 'USD')
            if currency not in result.currency_breakdown:
                result.currency_breakdown[currency] = {'income': 0.0, 'expense': 0.0, 'net': 0.0}
            result.currency_breakdown[currency]['income'] += amount

        # 2. Recorded expenses (outflows)
        expense_data = self.aggregate_expense_categories(expense_filters)
        for e in expense_data.expenses:
            item = {**e, 'source': 'expense', 'flow_type': 'expense'}
            result.outflows.append(item)
            amount = abs(e.get('amount', 0.0))
            result.total_expenses += amount

            # Monthly trends
            date_val = e.get('expense_date')
            if date_val:
                month_key = date_val.strftime('%Y-%m') if hasattr(date_val, 'strftime') else str(date_val)[:7]
                if month_key not in result.monthly_trends:
                    result.monthly_trends[month_key] = {'income': 0.0, 'expense': 0.0, 'net': 0.0}
                result.monthly_trends[month_key]['expense'] += amount

            # Currency breakdown
            currency = e.get('currency', 'USD')
            if currency not in result.currency_breakdown:
                result.currency_breakdown[currency] = {'income': 0.0, 'expense': 0.0, 'net': 0.0}
            result.currency_breakdown[currency]['expense'] += amount

        # 3. Unlinked bank transactions (only when include_unreconciled is True or not set)
        include_unreconciled = filters.include_unreconciled if filters else True
        if include_unreconciled:
            # Query unlinked bank transactions directly (invoice_id IS NULL AND expense_id IS NULL)
            txn_query = self.db.query(BankStatementTransaction).filter(
                BankStatementTransaction.invoice_id.is_(None),
                BankStatementTransaction.expense_id.is_(None)
            )

            if filters:
                date_range = DateRange(filters.date_from, filters.date_to)

                if date_range.start_date or date_range.end_date:
                    txn_query = self._apply_date_filter(txn_query, BankStatementTransaction.date, date_range)

                if filters.account_ids:
                    txn_query = txn_query.join(BankStatementTransaction.statement)
                    txn_query = txn_query.filter(BankStatement.id.in_(filters.account_ids))

                if filters.amount_min is not None:
                    txn_query = txn_query.filter(
                        func.abs(BankStatementTransaction.amount) >= filters.amount_min
                    )
                if filters.amount_max is not None:
                    txn_query = txn_query.filter(
                        func.abs(BankStatementTransaction.amount) <= filters.amount_max
                    )

            unlinked_transactions = txn_query.all()

            for txn in unlinked_transactions:
                result.unreconciled_count += 1
                amount = abs(txn.amount)
                txn_data = {
                    'id': txn.id,
                    'statement_id': txn.statement_id,
                    'date': txn.date,
                    'description': txn.description,
                    'amount': amount,
                    'transaction_type': txn.transaction_type,
                    'balance': txn.balance,
                    'category': txn.category,
                    'invoice_id': txn.invoice_id,
                    'expense_id': txn.expense_id,
                    'created_at': txn.created_at,
                    'updated_at': txn.updated_at,
                    'source': 'bank_transaction',
                }

                # Monthly trends
                date_val = txn.date
                if date_val:
                    month_key = date_val.strftime('%Y-%m') if hasattr(date_val, 'strftime') else str(date_val)[:7]
                    if month_key not in result.monthly_trends:
                        result.monthly_trends[month_key] = {'income': 0.0, 'expense': 0.0, 'net': 0.0}

                if txn.transaction_type == 'credit':
                    txn_data['flow_type'] = 'income'
                    result.inflows.append(txn_data)
                    result.total_income += amount
                    if date_val:
                        result.monthly_trends[month_key]['income'] += amount
                else:
                    txn_data['flow_type'] = 'expense'
                    result.outflows.append(txn_data)
                    result.total_expenses += amount
                    if date_val:
                        result.monthly_trends[month_key]['expense'] += amount

        # Compute net values for monthly trends and currency breakdown
        for month_key in result.monthly_trends:
            result.monthly_trends[month_key]['net'] = (
                result.monthly_trends[month_key]['income'] - result.monthly_trends[month_key]['expense']
            )
        for currency in result.currency_breakdown:
            result.currency_breakdown[currency]['net'] = (
                result.currency_breakdown[currency]['income'] - result.currency_breakdown[currency]['expense']
            )

        result.net_cash_flow = result.total_income - result.total_expenses

        return result

    def get_cross_entity_summary(
        self, 
        date_range: DateRange,
        client_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Get a comprehensive summary across all entity types for a given date range.

        Args:
            date_range: Date range for the summary
            client_ids: Optional list of client IDs to filter by

        Returns:
            Dictionary with cross-entity summary metrics
        """
        summary = {
            'date_range': date_range.to_dict(),
            'client_ids': client_ids,
            'metrics': {}
        }

        # Get basic filters for each entity type
        base_filters = {
            'date_from': date_range.start_date,
            'date_to': date_range.end_date,
            'client_ids': client_ids
        }

        # Aggregate data from each entity type
        client_data = self.aggregate_client_data(client_ids, ClientReportFilters(**base_filters))
        invoice_data = self.aggregate_invoice_metrics(InvoiceReportFilters(**base_filters))
        payment_data = self.aggregate_payment_flows(PaymentReportFilters(**base_filters))
        expense_data = self.aggregate_expense_categories(ExpenseReportFilters(**base_filters))

        # Build comprehensive summary
        summary['metrics'] = {
            'clients': {
                'total_count': client_data.total_clients,
                'active_count': client_data.active_clients,
                'total_balance': client_data.total_balance,
                'total_paid': client_data.total_paid_amount
            },
            'invoices': {
                'total_count': invoice_data.total_invoices,
                'total_amount': invoice_data.total_amount,
                'total_paid': invoice_data.total_paid,
                'total_outstanding': invoice_data.total_outstanding,
                'average_amount': invoice_data.average_amount,
                'status_breakdown': invoice_data.status_breakdown
            },
            'payments': {
                'total_count': payment_data.total_payments,
                'total_amount': payment_data.total_amount,
                'method_breakdown': payment_data.method_breakdown,
                'monthly_trends': payment_data.monthly_trends
            },
            'expenses': {
                'total_count': expense_data.total_expenses,
                'total_amount': expense_data.total_amount,
                'category_breakdown': expense_data.category_breakdown,
                'monthly_trends': expense_data.monthly_trends
            }
        }

        return summary
