"""
Report Validation Service

This service provides comprehensive validation for all report parameters,
filters, and configurations with detailed error messages and suggestions.
"""

from typing import Dict, Any, List, Optional, Union, Set
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from pydantic import ValidationError
import re

from core.exceptions.report_exceptions import (
    ReportValidationException, ReportErrorCode,
    date_range_error, client_not_found_error, amount_range_error,
    validation_error
)
from core.schemas.report import (
    ReportType, ExportFormat, ClientReportFilters, InvoiceReportFilters,
    PaymentReportFilters, ExpenseReportFilters, StatementReportFilters
)
from core.models.models_per_tenant import Client


class ReportValidationService:
    """
    Service for validating report parameters, filters, and configurations.
    Provides detailed error messages and suggestions for invalid inputs.
    """
    
    def __init__(self, db: Session):
        self.db = db
        
        # Define valid values for various fields
        self.valid_report_types = {rt.value for rt in ReportType}
        self.valid_export_formats = {ef.value for ef in ExportFormat}
        self.valid_invoice_statuses = {"draft", "sent", "paid", "overdue", "cancelled"}
        self.valid_payment_methods = {"cash", "check", "credit_card", "bank_transfer", "other"}
        self.valid_currencies = {"USD", "CAD", "EUR", "GBP", "AUD", "JPY"}  # Add more as needed
        
        # Maximum values for various parameters
        self.max_date_range_days = 730  # 2 years
        self.max_client_ids = 100
        self.max_amount = 999999999.99
        self.max_results = 10000
    
    def validate_report_request(
        self,
        report_type: str,
        filters: Dict[str, Any],
        export_format: str = "json",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validate a complete report request including type, filters, and format.
        
        Args:
            report_type: The type of report to generate
            filters: Dictionary of filters to apply
            export_format: The desired export format
            user_id: ID of the user making the request
            
        Returns:
            Dictionary of validated and normalized parameters
            
        Raises:
            ReportValidationException: If any validation fails
        """
        validated_data = {}
        
        # Validate report type
        validated_data["report_type"] = self._validate_report_type(report_type)
        
        # Validate export format
        validated_data["export_format"] = self._validate_export_format(export_format)
        
        # Validate filters based on report type
        validated_data["filters"] = self._validate_filters_by_type(
            validated_data["report_type"], filters
        )
        
        # Validate user permissions (if user_id provided)
        if user_id:
            self._validate_user_permissions(user_id, validated_data["filters"])
        
        return validated_data
    
    def _validate_report_type(self, report_type: str) -> ReportType:
        """Validate and convert report type"""
        if not report_type:
            raise validation_error(
                "Report type is required",
                field="report_type",
                suggestions=["Specify one of: client, invoice, payment, expense, statement"]
            )
        
        if report_type not in self.valid_report_types:
            raise ReportValidationException(
                message=f"Invalid report type: {report_type}",
                error_code=ReportErrorCode.REPORT_INVALID_TYPE,
                field="report_type",
                details={"provided_type": report_type, "valid_types": list(self.valid_report_types)},
                suggestions=[
                    "Valid report types: client, invoice, payment, expense, statement",
                    "Check the spelling of the report type",
                    "Refer to API documentation for supported types"
                ]
            )
        
        return ReportType(report_type)
    
    def _validate_export_format(self, export_format: str) -> ExportFormat:
        """Validate and convert export format"""
        if not export_format:
            export_format = "json"  # Default format
        
        export_format = export_format.lower()
        
        if export_format not in self.valid_export_formats:
            raise ReportValidationException(
                message=f"Invalid export format: {export_format}",
                error_code=ReportErrorCode.VALIDATION_EXPORT_FORMAT_INVALID,
                field="export_format",
                details={"provided_format": export_format, "valid_formats": list(self.valid_export_formats)},
                suggestions=[
                    "Valid export formats: json, pdf, csv, excel",
                    "Check the spelling of the export format",
                    "Use lowercase format names"
                ]
            )
        
        return ExportFormat(export_format)
    
    def _validate_filters_by_type(self, report_type: ReportType, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filters based on the specific report type"""
        if not isinstance(filters, dict):
            raise validation_error(
                "Filters must be a dictionary",
                field="filters",
                suggestions=["Provide filters as a JSON object with key-value pairs"]
            )
        
        # Common validations for all report types
        # For inventory reports, skip common filters (client_ids, currency) and only validate inventory-specific filters
        if report_type == ReportType.INVENTORY:
            validated_filters = self._validate_inventory_filters(filters)
        else:
            validated_filters = self._validate_common_filters(filters)

            # Type-specific validations
            if report_type == ReportType.CLIENT:
                validated_filters.update(self._validate_client_filters(filters))
            elif report_type == ReportType.INVOICE:
                validated_filters.update(self._validate_invoice_filters(filters))
            elif report_type == ReportType.PAYMENT:
                validated_filters.update(self._validate_payment_filters(filters))
            elif report_type == ReportType.EXPENSE:
                validated_filters.update(self._validate_expense_filters(filters))
            elif report_type == ReportType.STATEMENT:
                validated_filters.update(self._validate_statement_filters(filters))
        
        return validated_filters
    
    def _validate_common_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filters common to all report types"""
        validated = {}
        
        # Validate date range
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        
        if date_from or date_to:
            validated_dates = self._validate_date_range(date_from, date_to)
            validated.update(validated_dates)
        
        # Validate client IDs
        client_ids = filters.get("client_ids")
        if client_ids is not None:
            validated["client_ids"] = self._validate_client_ids(client_ids)
        
        # Validate currency
        currency = filters.get("currency")
        if currency:
            validated["currency"] = self._validate_currency(currency)
        
        return validated
    
    def _validate_date_range(
        self,
        date_from: Optional[Union[str, datetime]],
        date_to: Optional[Union[str, datetime]]
    ) -> Dict[str, datetime]:
        """Validate date range parameters"""
        validated = {}
        
        # Parse and validate date_from
        if date_from:
            try:
                if isinstance(date_from, str):
                    validated["date_from"] = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                else:
                    validated["date_from"] = date_from
            except (ValueError, TypeError):
                raise date_range_error(date_from=str(date_from))
        
        # Parse and validate date_to
        if date_to:
            try:
                if isinstance(date_to, str):
                    validated["date_to"] = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                else:
                    validated["date_to"] = date_to
            except (ValueError, TypeError):
                raise date_range_error(date_to=str(date_to))
        
        # Validate date range logic
        if "date_from" in validated and "date_to" in validated:
            if validated["date_from"] >= validated["date_to"]:
                raise date_range_error(
                    date_from=str(validated["date_from"]),
                    date_to=str(validated["date_to"])
                )
            
            # Check if date range is too large
            date_diff = validated["date_to"] - validated["date_from"]
            if date_diff.days > self.max_date_range_days:
                raise ReportValidationException(
                    message=f"Date range too large: {date_diff.days} days (max: {self.max_date_range_days})",
                    error_code=ReportErrorCode.VALIDATION_DATE_RANGE_INVALID,
                    field="date_range",
                    details={
                        "requested_days": date_diff.days,
                        "max_days": self.max_date_range_days
                    },
                    suggestions=[
                        f"Reduce date range to {self.max_date_range_days} days or less",
                        "Consider generating multiple reports for smaller date ranges",
                        "Contact support if you need larger date ranges"
                    ]
                )
        
        return validated
    
    def _validate_client_ids(self, client_ids: Union[List[int], int]) -> List[int]:
        """Validate client IDs"""
        if isinstance(client_ids, int):
            client_ids = [client_ids]
        
        if not isinstance(client_ids, list):
            raise validation_error(
                "Client IDs must be a list of integers or a single integer",
                field="client_ids",
                suggestions=["Provide client_ids as [1, 2, 3] or a single number"]
            )
        
        if len(client_ids) > self.max_client_ids:
            raise validation_error(
                f"Too many client IDs: {len(client_ids)} (max: {self.max_client_ids})",
                field="client_ids",
                suggestions=[f"Limit client selection to {self.max_client_ids} clients or fewer"]
            )
        
        # Validate that all client IDs are positive integers
        for client_id in client_ids:
            if not isinstance(client_id, int) or client_id <= 0:
                raise validation_error(
                    f"Invalid client ID: {client_id}",
                    field="client_ids",
                    suggestions=["Client IDs must be positive integers"]
                )
        
        # Check if clients exist in database
        existing_clients = self.db.query(Client.id).filter(Client.id.in_(client_ids)).all()
        existing_ids = {client.id for client in existing_clients}
        missing_ids = set(client_ids) - existing_ids
        
        if missing_ids:
            raise client_not_found_error(list(missing_ids))
        
        return client_ids
    
    def _validate_currency(self, currency: str) -> str:
        """Validate currency code"""
        if not isinstance(currency, str):
            raise validation_error(
                "Currency must be a string",
                field="currency",
                suggestions=["Use 3-letter currency codes like 'USD', 'EUR', 'CAD'"]
            )
        
        currency = currency.upper()
        
        if currency not in self.valid_currencies:
            raise ReportValidationException(
                message=f"Invalid currency code: {currency}",
                error_code=ReportErrorCode.VALIDATION_CURRENCY_INVALID,
                field="currency",
                details={"provided_currency": currency, "valid_currencies": list(self.valid_currencies)},
                suggestions=[
                    f"Valid currencies: {', '.join(self.valid_currencies)}",
                    "Use 3-letter ISO currency codes",
                    "Contact support to add additional currencies"
                ]
            )
        
        return currency
    
    def _validate_invoice_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate invoice-specific filters"""
        validated = {}
        
        # Validate invoice status
        status = filters.get("status")
        if status:
            validated["status"] = self._validate_invoice_status(status)
        
        # Validate amount range
        amount_min = filters.get("amount_min")
        amount_max = filters.get("amount_max")
        if amount_min is not None or amount_max is not None:
            validated.update(self._validate_amount_range(amount_min, amount_max))
        
        # Validate include_items flag
        include_items = filters.get("include_items")
        if include_items is not None:
            validated["include_items"] = self._validate_boolean_flag(include_items, "include_items")
        
        return validated
    
    def _validate_payment_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payment-specific filters"""
        validated = {}
        
        # Validate payment methods
        payment_methods = filters.get("payment_methods")
        if payment_methods:
            validated["payment_methods"] = self._validate_payment_methods(payment_methods)
        
        # Validate include_unmatched flag
        include_unmatched = filters.get("include_unmatched")
        if include_unmatched is not None:
            validated["include_unmatched"] = self._validate_boolean_flag(include_unmatched, "include_unmatched")
        
        return validated
    
    def _validate_expense_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate expense-specific filters"""
        validated = {}
        
        # Validate categories (basic validation - could be enhanced with database lookup)
        categories = filters.get("categories")
        if categories:
            validated["categories"] = self._validate_string_list(categories, "categories")
        
        # Validate labels
        labels = filters.get("labels")
        if labels:
            validated["labels"] = self._validate_string_list(labels, "labels")
        
        # Validate include_attachments flag
        include_attachments = filters.get("include_attachments")
        if include_attachments is not None:
            validated["include_attachments"] = self._validate_boolean_flag(include_attachments, "include_attachments")
        
        return validated
    
    def _validate_statement_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate statement-specific filters"""
        validated = {}
        
        # Validate account IDs
        account_ids = filters.get("account_ids")
        if account_ids:
            validated["account_ids"] = self._validate_integer_list(account_ids, "account_ids")
        
        # Validate transaction types
        transaction_types = filters.get("transaction_types")
        if transaction_types:
            validated["transaction_types"] = self._validate_string_list(transaction_types, "transaction_types")
        
        # Validate include_reconciliation flag
        include_reconciliation = filters.get("include_reconciliation")
        if include_reconciliation is not None:
            validated["include_reconciliation"] = self._validate_boolean_flag(include_reconciliation, "include_reconciliation")
        
        return validated
    
    def _validate_client_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate client-specific filters"""
        validated = {}
        
        # Client reports typically use common filters only
        # Add client-specific validations here if needed
        
        return validated

    def _validate_inventory_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate inventory-specific filters"""
        validated = {}

        # Validate date range
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        if date_from or date_to:
            validated_dates = self._validate_date_range(date_from, date_to)
            validated.update(validated_dates)

        # Validate category_ids
        if 'category_ids' in filters:
            category_ids = filters['category_ids']
            if category_ids is not None:
                if not isinstance(category_ids, list):
                    raise validation_error(
                        "Category IDs must be a list of integers",
                        field="category_ids"
                    )
                for cid in category_ids:
                    if not isinstance(cid, int) or cid <= 0:
                        raise validation_error(
                            "Category IDs must be positive integers",
                            field="category_ids"
                        )
                validated['category_ids'] = category_ids

        # Validate item_type
        if 'item_type' in filters:
            item_type = filters['item_type']
            if item_type is not None:
                if not isinstance(item_type, list):
                    item_type = [item_type]
                valid_types = ['product', 'service', 'material']
                for it in item_type:
                    if it not in valid_types:
                        raise validation_error(
                            f"Invalid item type: {it}",
                            field="item_type",
                            suggestions=[f"Valid types: {', '.join(valid_types)}"]
                        )
                validated['item_type'] = item_type

        # Validate low_stock_only
        if 'low_stock_only' in filters:
            low_stock_only = filters['low_stock_only']
            if low_stock_only is not None:
                if not isinstance(low_stock_only, bool):
                    raise validation_error(
                        "low_stock_only must be a boolean",
                        field="low_stock_only"
                    )
                validated['low_stock_only'] = low_stock_only

        # Validate value range
        for field in ['value_min', 'value_max']:
            if field in filters:
                value = filters[field]
                if value is not None:
                    if not isinstance(value, (int, float)) or value < 0:
                        raise validation_error(
                            f"{field} must be a non-negative number",
                            field=field
                        )
                    validated[field] = float(value)

        # Validate include_inactive
        if 'include_inactive' in filters:
            include_inactive = filters['include_inactive']
            if include_inactive is not None:
                if not isinstance(include_inactive, bool):
                    raise validation_error(
                        "include_inactive must be a boolean",
                        field="include_inactive"
                    )
                validated['include_inactive'] = include_inactive

        return validated

    def _validate_invoice_status(self, status: Union[str, List[str]]) -> List[str]:
        """Validate invoice status values"""
        if isinstance(status, str):
            status = [status]
        
        if not isinstance(status, list):
            raise validation_error(
                "Invoice status must be a string or list of strings",
                field="status",
                suggestions=["Valid statuses: draft, sent, paid, overdue, cancelled"]
            )
        
        for s in status:
            if s not in self.valid_invoice_statuses:
                raise validation_error(
                    f"Invalid invoice status: {s}",
                    field="status",
                    suggestions=[f"Valid statuses: {', '.join(self.valid_invoice_statuses)}"]
                )
        
        return status
    
    def _validate_payment_methods(self, methods: Union[str, List[str]]) -> List[str]:
        """Validate payment method values"""
        if isinstance(methods, str):
            methods = [methods]
        
        if not isinstance(methods, list):
            raise validation_error(
                "Payment methods must be a string or list of strings",
                field="payment_methods",
                suggestions=["Valid methods: cash, check, credit_card, bank_transfer, other"]
            )
        
        for method in methods:
            if method not in self.valid_payment_methods:
                raise validation_error(
                    f"Invalid payment method: {method}",
                    field="payment_methods",
                    suggestions=[f"Valid methods: {', '.join(self.valid_payment_methods)}"]
                )
        
        return methods
    
    def _validate_amount_range(
        self,
        amount_min: Optional[float],
        amount_max: Optional[float]
    ) -> Dict[str, float]:
        """Validate amount range parameters"""
        validated = {}
        
        if amount_min is not None:
            if not isinstance(amount_min, (int, float)) or amount_min < 0:
                raise amount_range_error(amount_min=amount_min)
            if amount_min > self.max_amount:
                raise validation_error(
                    f"Minimum amount too large: {amount_min}",
                    field="amount_min",
                    suggestions=[f"Maximum allowed amount: {self.max_amount}"]
                )
            validated["amount_min"] = float(amount_min)
        
        if amount_max is not None:
            if not isinstance(amount_max, (int, float)) or amount_max < 0:
                raise amount_range_error(amount_max=amount_max)
            if amount_max > self.max_amount:
                raise validation_error(
                    f"Maximum amount too large: {amount_max}",
                    field="amount_max",
                    suggestions=[f"Maximum allowed amount: {self.max_amount}"]
                )
            validated["amount_max"] = float(amount_max)
        
        if "amount_min" in validated and "amount_max" in validated:
            if validated["amount_min"] >= validated["amount_max"]:
                raise amount_range_error(
                    amount_min=validated["amount_min"],
                    amount_max=validated["amount_max"]
                )
        
        return validated
    
    def _validate_boolean_flag(self, value: Any, field_name: str) -> bool:
        """Validate boolean flag values"""
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            if value.lower() in ("true", "1", "yes", "on"):
                return True
            elif value.lower() in ("false", "0", "no", "off"):
                return False
        
        if isinstance(value, int):
            return bool(value)
        
        raise validation_error(
            f"Invalid boolean value for {field_name}: {value}",
            field=field_name,
            suggestions=["Use true/false, 1/0, or yes/no"]
        )
    
    def _validate_string_list(self, value: Union[str, List[str]], field_name: str) -> List[str]:
        """Validate list of strings"""
        if isinstance(value, str):
            value = [value]
        
        if not isinstance(value, list):
            raise validation_error(
                f"{field_name} must be a string or list of strings",
                field=field_name,
                suggestions=["Provide as a single string or array of strings"]
            )
        
        for item in value:
            if not isinstance(item, str):
                raise validation_error(
                    f"All {field_name} must be strings",
                    field=field_name,
                    suggestions=["Ensure all items in the list are strings"]
                )
        
        return value
    
    def _validate_integer_list(self, value: Union[int, List[int]], field_name: str) -> List[int]:
        """Validate list of integers"""
        if isinstance(value, int):
            value = [value]
        
        if not isinstance(value, list):
            raise validation_error(
                f"{field_name} must be an integer or list of integers",
                field=field_name,
                suggestions=["Provide as a single number or array of numbers"]
            )
        
        for item in value:
            if not isinstance(item, int) or item <= 0:
                raise validation_error(
                    f"All {field_name} must be positive integers",
                    field=field_name,
                    suggestions=["Ensure all items in the list are positive integers"]
                )
        
        return value
    
    def _validate_user_permissions(self, user_id: int, filters: Dict[str, Any]) -> None:
        """Validate user has permission to access requested data"""
        # This is a placeholder for permission validation
        # Implementation would depend on the specific RBAC system
        pass