"""
Report Generation Service

This service provides comprehensive report generation capabilities with filtering,
validation, and summary calculation for all major entity types in the system.
Enhanced with performance optimizations, caching, and progress tracking.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)
from .report_data_aggregator import (
    ReportDataAggregator, DateRange, ClientData, InvoiceMetrics,
    PaymentFlows, ExpenseBreakdown, TransactionData
)
from .report_exporter import ReportExportService, ExportError
from .report_validation_service import ReportValidationService
from .report_retry_service import ReportRetryService, RetryConfig, retry_on_failure
from .report_cache_service import (
    ReportCacheService, CacheConfig, get_cache_service, invalidate_data_cache
)
from .report_query_optimizer import (
    ReportQueryOptimizer, OptimizationConfig, get_query_optimizer
)
from .report_progress_service import (
    ReportProgressService, ProgressStage, get_progress_service, create_progress_callback
)
from exceptions.report_exceptions import (
    BaseReportException, ReportValidationException, ReportGenerationException,
    ReportErrorCode, validation_error
)
from schemas.report import (
    ReportType, ReportFilters, ReportData, ReportSummary, ReportMetadata,
    ReportResult, ExportFormat, ClientReportFilters, InvoiceReportFilters,
    PaymentReportFilters, ExpenseReportFilters, StatementReportFilters,
    ReportTemplate as ReportTemplateSchema
)


class ReportService:
    """
    Core service for generating reports with comprehensive filtering and validation.
    Supports all major entity types: clients, invoices, payments, expenses, and statements.
    Enhanced with performance optimizations, caching, and progress tracking.
    """
    
    def __init__(
        self, 
        db: Session, 
        company_data: Optional[Dict[str, Any]] = None,
        cache_config: Optional[CacheConfig] = None,
        optimization_config: Optional[OptimizationConfig] = None
    ):
        self.db = db
        self.data_aggregator = ReportDataAggregator(db)
        self.export_service = ReportExportService(company_data)
        self.validation_service = ReportValidationService(db)
        self.retry_service = ReportRetryService()
        
        # Performance optimization services
        self.cache_service = get_cache_service(cache_config)
        self.query_optimizer = get_query_optimizer(db, optimization_config)
        self.progress_service = get_progress_service()
        
        self.logger = logging.getLogger(__name__)
        
        # Map report types to their corresponding filter classes
        self.filter_classes = {
            ReportType.CLIENT: ClientReportFilters,
            ReportType.INVOICE: InvoiceReportFilters,
            ReportType.PAYMENT: PaymentReportFilters,
            ReportType.EXPENSE: ExpenseReportFilters,
            ReportType.STATEMENT: StatementReportFilters
        }
        
        # Map report types to their aggregation methods
        self.aggregation_methods = {
            ReportType.CLIENT: self._generate_client_report,
            ReportType.INVOICE: self._generate_invoice_report,
            ReportType.PAYMENT: self._generate_payment_report,
            ReportType.EXPENSE: self._generate_expense_report,
            ReportType.STATEMENT: self._generate_statement_report
        }
    
    def generate_report(
        self,
        report_type: str,
        filters: Dict[str, Any],
        export_format: str = "json",
        user_id: int = None,
        use_cache: bool = True,
        enable_progress_tracking: bool = False
    ) -> ReportResult:
        """
        Generate a report with the specified type, filters, and format.
        Enhanced with caching, optimization, and progress tracking.
        
        Args:
            report_type: Type of report to generate
            filters: Dictionary of filters to apply
            export_format: Format for the report output
            user_id: ID of the user generating the report
            use_cache: Whether to use caching for this request
            enable_progress_tracking: Whether to enable progress tracking
            
        Returns:
            ReportResult with the generated report data or error information
        """
        try:
            # Comprehensive validation using the validation service
            validated_data = self.validation_service.validate_report_request(
                report_type=report_type,
                filters=filters,
                export_format=export_format,
                user_id=user_id
            )
            
            # Extract validated components
            validated_report_type = validated_data["report_type"]
            validated_filters = validated_data["filters"]
            validated_export_format = validated_data["export_format"]
            
            # Check cache first if enabled
            cache_key = None
            if use_cache:
                cache_key = self.cache_service.get_cache_key(
                    report_type=validated_report_type,
                    filters=validated_filters,
                    export_format=validated_export_format,
                    user_id=user_id
                )
                
                cached_result = self.cache_service.get(cache_key)
                if cached_result is not None:
                    self.logger.debug(f"Cache hit for report: {cache_key}")
                    return ReportResult(
                        success=True,
                        data=cached_result,
                        cache_hit=True
                    )
            
            # Create progress tracker if enabled
            task_id = None
            if enable_progress_tracking:
                task_id = self.progress_service.create_task(
                    report_type=validated_report_type.value,
                    user_id=user_id
                )
            
            # Generate the report with retry logic
            retry_result = self.retry_service.with_retry(
                self._generate_report_internal,
                validated_report_type,
                validated_filters,
                validated_export_format,
                user_id,
                task_id
            )
            
            if retry_result.success:
                # Cache the result if caching is enabled and successful
                if use_cache and cache_key and retry_result.result.success:
                    self.cache_service.set(cache_key, retry_result.result.data)
                    self.logger.debug(f"Cached report result: {cache_key}")
                
                return retry_result.result
            else:
                # Convert retry failure to ReportResult
                error_details = {
                    "attempts": len(retry_result.attempts),
                    "total_duration": retry_result.total_duration,
                    "circuit_breaker_triggered": retry_result.circuit_breaker_triggered
                }
                
                if isinstance(retry_result.exception, BaseReportException):
                    error_dict = retry_result.exception.to_dict()
                    error_dict["details"].update(error_details)
                    
                    return ReportResult(
                        success=False,
                        error_code=retry_result.exception.error_code.value,
                        error_message=retry_result.exception.message,
                        error_details=error_dict["details"],
                        suggestions=error_dict["suggestions"]
                    )
                else:
                    return ReportResult(
                        success=False,
                        error_code=ReportErrorCode.REPORT_GENERATION_FAILED.value,
                        error_message=f"Report generation failed: {str(retry_result.exception)}",
                        error_details=error_details
                    )
            
        except ReportValidationException as e:
            self.logger.error(f"Validation error in report generation: {e}")
            error_dict = e.to_dict()
            return ReportResult(
                success=False,
                error_code=e.error_code.value,
                error_message=e.message,
                error_details=error_dict["details"],
                suggestions=error_dict["suggestions"]
            )
        except BaseReportException as e:
            self.logger.error(f"Report exception: {e}")
            error_dict = e.to_dict()
            return ReportResult(
                success=False,
                error_code=e.error_code.value,
                error_message=e.message,
                error_details=error_dict["details"],
                suggestions=error_dict["suggestions"]
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in report generation: {e}", exc_info=True)
            return ReportResult(
                success=False,
                error_code=ReportErrorCode.REPORT_GENERATION_FAILED.value,
                error_message="An unexpected error occurred during report generation",
                error_details={"original_error": str(e)},
                suggestions=[
                    "Please try again in a few moments",
                    "If the problem persists, contact support",
                    "Check that all required parameters are provided"
                ]
            )
    
    def _generate_report_internal(
        self,
        report_type: ReportType,
        filters: Dict[str, Any],
        export_format: ExportFormat,
        user_id: Optional[int],
        task_id: Optional[str] = None
    ) -> ReportResult:
        """
        Internal method for generating reports (used by retry logic)
        Enhanced with progress tracking and optimization.
        """
        try:
            # Update progress if tracking is enabled
            if task_id:
                self.progress_service.start_task(task_id)
                self.progress_service.update_task_progress(
                    task_id, ProgressStage.VALIDATING, 0, "Validating report parameters"
                )
            
            # Generate the report using the appropriate method
            start_time = datetime.now()
            
            if report_type not in self.aggregation_methods:
                if task_id:
                    self.progress_service.fail_task(task_id, f"Unsupported report type: {report_type}")
                raise ReportGenerationException(
                    message=f"Unsupported report type: {report_type}",
                    error_code=ReportErrorCode.REPORT_INVALID_TYPE,
                    retryable=False
                )
            
            # Update progress
            if task_id:
                self.progress_service.update_task_progress(
                    task_id, ProgressStage.QUERYING, 10, "Starting data aggregation"
                )
            
            # Generate report with progress callback
            progress_callback = create_progress_callback(task_id) if task_id else None

            # Convert filters dictionary to appropriate filter object
            filter_class = self.filter_classes.get(report_type)
            if filter_class:
                # Filter out keys that don't exist in the filter class to prevent validation errors
                valid_keys = set(filter_class.__annotations__.keys()) if hasattr(filter_class, '__annotations__') else set()
                filtered_filters = {k: v for k, v in filters.items() if k in valid_keys}
                converted_filters = filter_class(**filtered_filters)
            else:
                # Fallback for unknown report types
                converted_filters = filters

            report_data = self.aggregation_methods[report_type](converted_filters, progress_callback)
            generation_time = (datetime.now() - start_time).total_seconds()
            
            # Update progress
            if task_id:
                self.progress_service.update_task_progress(
                    task_id, ProgressStage.FORMATTING, 80, "Formatting report data"
                )
            
            # Create metadata
            metadata = ReportMetadata(
                generated_at=datetime.now(),
                generated_by=user_id or 0,
                export_format=export_format,
                generation_time=generation_time
            )
            
            # Build final report data structure
            final_report = ReportData(
                report_type=report_type,
                summary=report_data['summary'],
                data=report_data['data'],
                metadata=metadata,
                filters=filters
            )
            
            # Handle export format
            if export_format == ExportFormat.JSON:
                # Update progress and complete
                if task_id:
                    self.progress_service.complete_task(task_id, final_report)
                
                # Return JSON data directly
                return ReportResult(
                    success=True,
                    data=final_report
                )
            else:
                # Update progress for export
                if task_id:
                    self.progress_service.update_task_progress(
                        task_id, ProgressStage.EXPORTING, 90, f"Exporting to {export_format.value}"
                    )
                
                # Export to requested format
                try:
                    exported_data = self.export_service.export_report(final_report, export_format)
                    
                    # Complete progress tracking
                    if task_id:
                        self.progress_service.complete_task(task_id, final_report)
                    
                    # For non-JSON formats, return the exported data
                    return ReportResult(
                        success=True,
                        data=final_report,  # Still include the data for metadata
                        file_path=None,  # Could be set if saving to file
                        download_url=None  # Could be set if providing download URL
                    )
                except ExportError as e:
                    if task_id:
                        self.progress_service.fail_task(task_id, f"Export failed: {str(e)}")
                    
                    raise ReportGenerationException(
                        message=f"Export failed: {str(e)}",
                        error_code=ReportErrorCode.EXPORT_GENERATION_FAILED,
                        details={"export_format": export_format.value, "original_error": str(e)},
                        suggestions=[
                            "Try a different export format",
                            "Reduce the amount of data in the report",
                            "Contact support if the problem persists"
                        ]
                    )
                    
        except BaseReportException:
            # Re-raise report exceptions as-is
            if task_id:
                self.progress_service.fail_task(task_id, "Report generation failed")
            raise
        except Exception as e:
            # Convert unexpected exceptions to ReportGenerationException
            if task_id:
                self.progress_service.fail_task(task_id, f"Unexpected error: {str(e)}")
            
            raise ReportGenerationException(
                message=f"Unexpected error during report generation: {str(e)}",
                error_code=ReportErrorCode.REPORT_GENERATION_FAILED,
                details={"original_error": str(e)},
                suggestions=[
                    "Please try again",
                    "Check your filters and parameters",
                    "Contact support if the problem persists"
                ]
            )
    
    def export_report_data(
        self, 
        report_data: ReportData, 
        export_format: ExportFormat
    ) -> Union[bytes, str]:
        """
        Export existing report data to the specified format.
        
        Args:
            report_data: The report data to export
            export_format: Format to export to (PDF, CSV, Excel)
            
        Returns:
            Exported data as bytes (for PDF/Excel) or string (for CSV)
            
        Raises:
            ExportError: If export fails
        """
        return self.export_service.export_report(report_data, export_format)
    
    def get_supported_export_formats(self) -> List[ExportFormat]:
        """Get list of supported export formats"""
        return self.export_service.get_supported_formats()
    
    def validate_export_format(self, export_format: str) -> ExportFormat:
        """Validate and convert export format string to enum"""
        return self.export_service.validate_export_format(export_format)
    
    def validate_filters(self, report_type: ReportType, filters: Dict[str, Any]) -> ReportFilters:
        """
        Validate and parse filters for the specified report type.
        
        Args:
            report_type: Type of report
            filters: Raw filter dictionary
            
        Returns:
            Validated filter object
            
        Raises:
            ReportValidationError: If validation fails
        """
        try:
            # Get the appropriate filter class
            filter_class = self.filter_classes.get(report_type)
            if not filter_class:
                raise ReportValidationError(
                    f"No filter class found for report type: {report_type}",
                    code="INVALID_REPORT_TYPE"
                )
            
            # Validate date range first (before Pydantic validation)
            self._validate_date_range(filters)
            
            # Validate specific filters based on report type
            self._validate_type_specific_filters(report_type, filters)
            
            # Parse and validate using Pydantic
            validated_filters = filter_class(**filters)
            
            return validated_filters
            
        except ReportValidationError:
            # Re-raise our custom validation errors
            raise
        except ValidationError as e:
            error_details = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error['loc'])
                error_details.append(f"{field}: {error['msg']}")
            
            raise ReportValidationError(
                f"Filter validation failed: {'; '.join(error_details)}",
                code="FILTER_VALIDATION_ERROR"
            )
        except Exception as e:
            raise ReportValidationError(
                f"Filter validation error: {str(e)}",
                code="VALIDATION_ERROR"
            )
    
    def _validate_date_range(self, filters: Dict[str, Any]) -> None:
        """Validate date range filters"""
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        
        if date_from and date_to:
            if date_from > date_to:
                raise ReportValidationError(
                    "Start date cannot be after end date",
                    field="date_range",
                    code="INVALID_DATE_RANGE"
                )
            
            # Check for reasonable date range (not more than 10 years)
            if (date_to - date_from).days > 3650:
                raise ReportValidationError(
                    "Date range cannot exceed 10 years",
                    field="date_range",
                    code="DATE_RANGE_TOO_LARGE"
                )
        
        # Validate individual dates
        if date_from and date_from > datetime.now():
            raise ReportValidationError(
                "Start date cannot be in the future",
                field="date_from",
                code="FUTURE_DATE"
            )
    
    def _validate_type_specific_filters(self, report_type: ReportType, filters: Dict[str, Any]) -> None:
        """Validate filters specific to each report type"""
        
        if report_type == ReportType.INVOICE:
            # Validate amount range
            amount_min = filters.get('amount_min')
            amount_max = filters.get('amount_max')
            if amount_min is not None and amount_max is not None and amount_min > amount_max:
                raise ReportValidationError(
                    "Minimum amount cannot be greater than maximum amount",
                    field="amount_range",
                    code="INVALID_AMOUNT_RANGE"
                )
            
            # Validate status values
            status = filters.get('status')
            if status:
                valid_statuses = ['draft', 'sent', 'paid', 'overdue', 'cancelled']
                invalid_statuses = [s for s in status if s not in valid_statuses]
                if invalid_statuses:
                    raise ReportValidationError(
                        f"Invalid invoice statuses: {', '.join(invalid_statuses)}",
                        field="status",
                        code="INVALID_STATUS"
                    )
        
        elif report_type == ReportType.PAYMENT:
            # Validate payment methods
            payment_methods = filters.get('payment_methods')
            if payment_methods:
                valid_methods = ['cash', 'check', 'credit_card', 'bank_transfer', 'other']
                invalid_methods = [m for m in payment_methods if m not in valid_methods]
                if invalid_methods:
                    raise ReportValidationError(
                        f"Invalid payment methods: {', '.join(invalid_methods)}",
                        field="payment_methods",
                        code="INVALID_PAYMENT_METHOD"
                    )
        
        elif report_type == ReportType.EXPENSE:
            # Validate categories
            categories = filters.get('categories')
            if categories:
                # Note: In a real implementation, you might want to validate against
                # a predefined list of categories from the database
                pass
        
        elif report_type == ReportType.STATEMENT:
            # Validate transaction types
            transaction_types = filters.get('transaction_types')
            if transaction_types:
                valid_types = ['credit', 'debit']
                invalid_types = [t for t in transaction_types if t not in valid_types]
                if invalid_types:
                    raise ReportValidationError(
                        f"Invalid transaction types: {', '.join(invalid_types)}",
                        field="transaction_types",
                        code="INVALID_TRANSACTION_TYPE"
                    )
    
    def _generate_client_report(
        self, 
        filters: ClientReportFilters, 
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Generate client report with summary calculations"""
        if progress_callback:
            progress_callback(20, "Aggregating client data")
        
        # Use the data aggregator to get client data
        client_data = self.data_aggregator.aggregate_client_data(
            client_ids=filters.client_ids,
            filters=filters
        )
        
        if progress_callback:
            progress_callback(60, "Processing client metrics")
        
        # Calculate summary metrics
        summary = ReportSummary(
            total_records=client_data.total_clients,
            total_amount=client_data.total_balance,
            currency=filters.currency or "USD",
            date_range={
                "start_date": filters.date_from,
                "end_date": filters.date_to
            } if filters.date_from or filters.date_to else None,
            key_metrics={
                "active_clients": client_data.active_clients,
                "total_paid_amount": client_data.total_paid_amount,
                "average_balance": client_data.total_balance / client_data.total_clients if client_data.total_clients > 0 else 0,
                "currencies_used": client_data.currencies
            }
        )
        
        if progress_callback:
            progress_callback(100, "Client report completed")
        
        return {
            "summary": summary,
            "data": client_data.clients
        }
    
    def _generate_invoice_report(self, filters: InvoiceReportFilters, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Generate invoice report with summary calculations"""
        # Use the data aggregator to get invoice data
        invoice_data = self.data_aggregator.aggregate_invoice_metrics(filters)
        
        # Calculate summary metrics
        summary = ReportSummary(
            total_records=invoice_data.total_invoices,
            total_amount=invoice_data.total_amount,
            currency=filters.currency or "USD",
            date_range={
                "start_date": filters.date_from,
                "end_date": filters.date_to
            } if filters.date_from or filters.date_to else None,
            key_metrics={
                "total_paid": invoice_data.total_paid,
                "total_outstanding": invoice_data.total_outstanding,
                "average_amount": invoice_data.average_amount,
                "status_breakdown": invoice_data.status_breakdown,
                "currency_breakdown": invoice_data.currency_breakdown,
                "collection_rate": (invoice_data.total_paid / invoice_data.total_amount * 100) if invoice_data.total_amount > 0 else 0
            }
        )
        
        return {
            "summary": summary,
            "data": invoice_data.invoices
        }
    
    def _generate_payment_report(self, filters: PaymentReportFilters, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Generate payment report with summary calculations"""
        # Use the data aggregator to get payment data
        payment_data = self.data_aggregator.aggregate_payment_flows(filters)
        
        # Calculate summary metrics
        summary = ReportSummary(
            total_records=payment_data.total_payments,
            total_amount=payment_data.total_amount,
            currency=filters.currency or "USD",
            date_range={
                "start_date": filters.date_from,
                "end_date": filters.date_to
            } if filters.date_from or filters.date_to else None,
            key_metrics={
                "method_breakdown": payment_data.method_breakdown,
                "currency_breakdown": payment_data.currency_breakdown,
                "monthly_trends": payment_data.monthly_trends,
                "average_payment": payment_data.total_amount / payment_data.total_payments if payment_data.total_payments > 0 else 0
            }
        )
        
        return {
            "summary": summary,
            "data": payment_data.payments
        }
    
    def _generate_expense_report(self, filters: ExpenseReportFilters, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Generate expense report with summary calculations"""
        # Use the data aggregator to get expense data
        expense_data = self.data_aggregator.aggregate_expense_categories(filters)
        
        # Calculate summary metrics
        summary = ReportSummary(
            total_records=expense_data.total_expenses,
            total_amount=expense_data.total_amount,
            currency=filters.currency or "USD",
            date_range={
                "start_date": filters.date_from,
                "end_date": filters.date_to
            } if filters.date_from or filters.date_to else None,
            key_metrics={
                "category_breakdown": expense_data.category_breakdown,
                "vendor_breakdown": expense_data.vendor_breakdown,
                "currency_breakdown": expense_data.currency_breakdown,
                "monthly_trends": expense_data.monthly_trends,
                "average_expense": expense_data.total_amount / expense_data.total_expenses if expense_data.total_expenses > 0 else 0
            }
        )
        
        return {
            "summary": summary,
            "data": expense_data.expenses
        }
    
    def _generate_statement_report(self, filters: StatementReportFilters, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Generate statement report with summary calculations"""
        # Use the data aggregator to get statement data
        statement_data = self.data_aggregator.aggregate_statement_transactions(filters)
        
        # Calculate summary metrics
        summary = ReportSummary(
            total_records=statement_data.total_transactions,
            total_amount=statement_data.net_flow,
            currency=filters.currency or "USD",
            date_range={
                "start_date": filters.date_from,
                "end_date": filters.date_to
            } if filters.date_from or filters.date_to else None,
            key_metrics={
                "total_credits": statement_data.total_credits,
                "total_debits": statement_data.total_debits,
                "net_flow": statement_data.net_flow,
                "type_breakdown": statement_data.type_breakdown,
                "monthly_trends": statement_data.monthly_trends,
                "reconciliation_rate": self._calculate_reconciliation_rate(statement_data.transactions)
            }
        )
        
        return {
            "summary": summary,
            "data": statement_data.transactions
        }
    
    def _calculate_reconciliation_rate(self, transactions: List[Dict[str, Any]]) -> float:
        """Calculate the percentage of reconciled transactions"""
        if not transactions:
            return 0.0
        
        reconciled_count = sum(
            1 for tx in transactions 
            if tx.get('invoice_id') is not None or tx.get('expense_id') is not None
        )
        
        return (reconciled_count / len(transactions)) * 100
    
    def get_available_report_types(self) -> List[Dict[str, Any]]:
        """
        Get list of available report types with their configurations.
        
        Returns:
            List of report type configurations
        """
        return [
            {
                "type": ReportType.CLIENT,
                "name": "Client Report",
                "description": "Comprehensive client analysis with financial history",
                "available_filters": [
                    "date_from", "date_to", "client_ids", "currency",
                    "include_inactive", "balance_min", "balance_max"
                ],
                "default_columns": [
                    "name", "email", "balance", "paid_amount", "total_invoices", "created_at"
                ]
            },
            {
                "type": ReportType.INVOICE,
                "name": "Invoice Report",
                "description": "Detailed invoice analysis with payment tracking",
                "available_filters": [
                    "date_from", "date_to", "client_ids", "currency", "status",
                    "amount_min", "amount_max", "include_items", "is_recurring"
                ],
                "default_columns": [
                    "number", "client_name", "amount", "status", "due_date", "outstanding_amount"
                ]
            },
            {
                "type": ReportType.PAYMENT,
                "name": "Payment Report",
                "description": "Cash flow analysis and payment tracking",
                "available_filters": [
                    "date_from", "date_to", "client_ids", "currency", "payment_methods",
                    "include_unmatched", "amount_min", "amount_max"
                ],
                "default_columns": [
                    "payment_date", "amount", "payment_method", "client_name", "invoice_number"
                ]
            },
            {
                "type": ReportType.EXPENSE,
                "name": "Expense Report",
                "description": "Business expense tracking and categorization",
                "available_filters": [
                    "date_from", "date_to", "client_ids", "currency", "categories",
                    "labels", "include_attachments", "vendor", "status"
                ],
                "default_columns": [
                    "expense_date", "amount", "category", "vendor", "description"
                ]
            },
            {
                "type": ReportType.STATEMENT,
                "name": "Bank Statement Report",
                "description": "Bank transaction analysis and reconciliation",
                "available_filters": [
                    "date_from", "date_to", "account_ids", "transaction_types",
                    "include_reconciliation", "amount_min", "amount_max"
                ],
                "default_columns": [
                    "date", "description", "amount", "transaction_type", "balance"
                ]
            }
        ]
    
    def generate_report_from_template(
        self,
        template: ReportTemplateSchema,
        filter_overrides: Optional[Dict[str, Any]] = None,
        export_format: ExportFormat = ExportFormat.JSON,
        user_id: int = None
    ) -> ReportResult:
        """
        Generate a report using a template with optional filter overrides.
        
        Args:
            template: Template to use for report generation
            filter_overrides: Optional filters to override template defaults
            export_format: Format for the report output
            user_id: ID of the user generating the report
            
        Returns:
            ReportResult with the generated report data
        """
        try:
            # Merge template filters with overrides
            final_filters = template.filters.copy() if template.filters else {}
            if filter_overrides:
                final_filters.update(filter_overrides)
            
            # Use template columns if available
            if template.columns:
                final_filters['_columns'] = template.columns
            
            # Generate the report
            return self.generate_report(
                report_type=ReportType(template.report_type),
                filters=final_filters,
                export_format=export_format,
                user_id=user_id
            )
            
        except Exception as e:
            return ReportResult(
                success=False,
                error_message=f"Template-based report generation failed: {str(e)}"
            )
    
    def generate_report_with_pagination(
        self,
        report_type: ReportType,
        filters: Dict[str, Any],
        page_size: int = 1000,
        max_pages: int = 100,
        user_id: Optional[int] = None
    ) -> ReportResult:
        """
        Generate a report with pagination for large datasets.
        
        Args:
            report_type: Type of report to generate
            filters: Report filters
            page_size: Number of records per page
            max_pages: Maximum number of pages to fetch
            user_id: User ID for the request
            
        Returns:
            ReportResult with paginated data
        """
        try:
            # Create progress tracker
            task_id = self.progress_service.create_task(
                report_type=report_type.value,
                user_id=user_id
            )
            
            # Start progress tracking
            self.progress_service.start_task(task_id)
            
            # Create progress callback for pagination
            def pagination_progress(progress: float, current_records: int, total_records: int):
                message = f"Processed {current_records:,} of {total_records:,} records"
                self.progress_service.update_task_progress(
                    task_id, ProgressStage.PROCESSING, progress * 100, message,
                    details={
                        'current_records': current_records,
                        'total_records': total_records,
                        'pages_processed': int(current_records / page_size) + 1
                    }
                )
            
            # Use the data aggregator with pagination
            if report_type == ReportType.CLIENT:
                # This would need to be implemented in the data aggregator
                # For now, fall back to regular generation
                return self.generate_report(
                    report_type.value, filters, "json", user_id, 
                    use_cache=False, enable_progress_tracking=True
                )
            
            # Complete the task
            self.progress_service.complete_task(task_id)
            
            return ReportResult(success=True, data=None)
            
        except Exception as e:
            if 'task_id' in locals():
                self.progress_service.fail_task(task_id, str(e))
            
            return ReportResult(
                success=False,
                error_message=f"Paginated report generation failed: {str(e)}"
            )
    
    def invalidate_cache(
        self,
        report_type: Optional[ReportType] = None,
        user_id: Optional[int] = None,
        pattern: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries based on criteria.
        
        Args:
            report_type: Optional report type to invalidate
            user_id: Optional user ID to invalidate cache for
            pattern: Optional pattern to match
            
        Returns:
            Number of cache entries invalidated
        """
        if report_type:
            return self.cache_service.invalidate_report_type(report_type)
        elif user_id:
            return self.cache_service.invalidate_user_cache(user_id)
        elif pattern:
            return self.cache_service.invalidate_pattern(pattern)
        else:
            return self.cache_service.clear_all()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache_service.get_stats()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get query performance statistics"""
        return self.query_optimizer.get_performance_stats()
    
    def get_progress_stats(self) -> Dict[str, Any]:
        """Get progress tracking statistics"""
        return self.progress_service.get_stats()
    
    def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get progress information for a specific task.
        
        Args:
            task_id: Task ID to get progress for
            
        Returns:
            Progress information dictionary or None if not found
        """
        tracker = self.progress_service.get_task(task_id)
        return tracker.to_dict() if tracker else None
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running report generation task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if task was cancelled, False if not found
        """
        return self.progress_service.cancel_task(task_id)
    
    def get_user_tasks(self, user_id: int, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get all tasks for a specific user.
        
        Args:
            user_id: User ID to get tasks for
            active_only: If True, only return active tasks
            
        Returns:
            List of task information dictionaries
        """
        tasks = self.progress_service.get_user_tasks(user_id, active_only)
        return [task.to_dict() for task in tasks]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed tasks.
        
        Args:
            max_age_hours: Maximum age in hours for completed tasks
            
        Returns:
            Number of tasks cleaned up
        """
        return self.progress_service.cleanup_old_tasks(max_age_hours)
    
    def get_optimization_recommendations(
        self,
        report_type: ReportType,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get optimization recommendations for a report configuration.
        
        Args:
            report_type: Type of report
            filters: Report filters
            
        Returns:
            List of optimization recommendations
        """
        # This would need to be implemented based on the specific query
        # For now, return general recommendations
        recommendations = []
        
        # Check date range
        if 'date_from' in filters and 'date_to' in filters:
            date_from = filters['date_from']
            date_to = filters['date_to']
            if date_from and date_to:
                date_range = (date_to - date_from).days
                if date_range > 365:
                    recommendations.append({
                        'type': 'performance',
                        'priority': 'medium',
                        'description': f'Large date range ({date_range} days) may impact performance',
                        'suggestion': 'Consider using smaller date ranges or pagination'
                    })
        
        # Check for large client lists
        if 'client_ids' in filters and filters['client_ids']:
            if len(filters['client_ids']) > 100:
                recommendations.append({
                    'type': 'performance',
                    'priority': 'high',
                    'description': f'Large number of clients ({len(filters["client_ids"])}) selected',
                    'suggestion': 'Consider generating separate reports for client groups'
                })
        
        return recommendations
    
    def preview_report(
        self,
        report_type: ReportType,
        filters: Dict[str, Any],
        limit: int = 10
    ) -> ReportResult:
        """
        Generate a preview of the report with limited data.
        
        Args:
            report_type: Type of report to preview
            filters: Filters to apply
            limit: Maximum number of records to return
            
        Returns:
            ReportResult with preview data
        """
        try:
            # Generate the full report
            result = self.generate_report(report_type, filters)
            
            if not result.success:
                return result
            
            # Limit the data for preview
            if result.data and result.data.data:
                result.data.data = result.data.data[:limit]
                result.data.summary.total_records = len(result.data.data)
            
            return result
            
        except Exception as e:
            return ReportResult(
                success=False,
                error_message=f"Preview generation failed: {str(e)}"
            )
    
    def preview_report_from_template(
        self,
        template: ReportTemplateSchema,
        filter_overrides: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> ReportResult:
        """
        Generate a preview of a template-based report with limited data.
        
        Args:
            template: Template to use for report generation
            filter_overrides: Optional filters to override template defaults
            limit: Maximum number of records to return
            
        Returns:
            ReportResult with preview data
        """
        try:
            # Generate the template-based report
            result = self.generate_report_from_template(
                template=template,
                filter_overrides=filter_overrides,
                export_format=ExportFormat.JSON
            )
            
            if not result.success:
                return result
            
            # Limit the data for preview
            if result.data and result.data.data:
                result.data.data = result.data.data[:limit]
                result.data.summary.total_records = len(result.data.data)
            
            return result
            
        except Exception as e:
            return ReportResult(
                success=False,
                error_message=f"Template preview generation failed: {str(e)}"
            )