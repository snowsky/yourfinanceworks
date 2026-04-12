"""
Report generation endpoints.

  GET  /types                   — list available report types and their config
  POST /generate                — generate a report (JSON immediately, files in background)
  POST /preview                 — preview report data (limited result set)
  POST /regenerate/{report_id}  — regenerate a report using the same parameters
"""

import time
import traceback
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import BankStatement, BankStatementTransaction, Expense, Invoice
from core.utils.feature_gate import require_feature
from core.services.report_history_service import ReportHistoryService
from core.services.report_audit_service import ReportAuditService, extract_request_info
from core.services.report_security_service import ReportSecurityService, ReportRateLimiter
from core.services.report_exporter import ReportExportService
from core.routers.auth import get_current_user
from core.exceptions.report_exceptions import BaseReportException
from core.schemas.report import (
    ReportType, ExportFormat, ReportGenerateRequest, ReportPreviewRequest,
    ReportResult, ReportData, ReportTypesResponse, ReportStatus,
    RelationshipCloudRequest, RelationshipCloudResponse, RelationshipCloudNode,
    RelationshipCloudEdge, RelationshipCloudStats
)

from ._shared import (
    get_report_service, get_current_non_viewer_user,
    handle_report_exception, handle_generic_exception
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_filter_date(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _in_date_range(value: Optional[datetime], date_from: Optional[datetime], date_to: Optional[datetime]) -> bool:
    value = _normalize_datetime(value)
    date_from = _normalize_datetime(date_from)
    date_to = _normalize_datetime(date_to)

    if value is None:
        return True
    if date_from and value < date_from:
        return False
    if date_to and value > date_to:
        return False
    return True


def _currency_text(amount: Optional[float], currency: Optional[str]) -> str:
    if amount is None:
        return ""
    code = currency or "USD"
    try:
        return f"{code} {amount:,.0f}"
    except Exception:
        return f"{code} {amount}"


@router.get("/types", response_model=ReportTypesResponse)
@require_feature("reporting")
async def get_report_types(
    current_user: MasterUser = Depends(get_current_user)
):
    """Get available report types and their configuration options."""
    try:
        report_types = [
            {
                "type": ReportType.CLIENT,
                "name": "Client Reports",
                "description": "Comprehensive client analysis with financial history",
                "filters": [
                    {"name": "date_from", "type": "datetime", "required": False},
                    {"name": "date_to", "type": "datetime", "required": False},
                    {"name": "client_ids", "type": "list[int]", "required": False},
                    {"name": "include_inactive", "type": "boolean", "required": False},
                    {"name": "balance_min", "type": "float", "required": False},
                    {"name": "balance_max", "type": "float", "required": False}
                ],
                "columns": [
                    "client_name", "email", "phone", "total_invoiced", "total_paid",
                    "outstanding_balance", "last_invoice_date", "payment_terms"
                ]
            },
            {
                "type": ReportType.INVOICE,
                "name": "Invoice Reports",
                "description": "Detailed invoice analysis with payment tracking",
                "filters": [
                    {"name": "date_from", "type": "datetime", "required": False},
                    {"name": "date_to", "type": "datetime", "required": False},
                    {"name": "client_ids", "type": "list[int]", "required": False},
                    {"name": "status", "type": "list[str]", "required": False},
                    {"name": "amount_min", "type": "float", "required": False},
                    {"name": "amount_max", "type": "float", "required": False},
                    {"name": "include_items", "type": "boolean", "required": False}
                ],
                "columns": [
                    "invoice_number", "client_name", "date", "due_date", "amount",
                    "status", "paid_amount", "outstanding_amount", "currency"
                ]
            },
            {
                "type": ReportType.PAYMENT,
                "name": "Payment Reports",
                "description": "Cash flow analysis and payment tracking",
                "filters": [
                    {"name": "date_from", "type": "datetime", "required": False},
                    {"name": "date_to", "type": "datetime", "required": False},
                    {"name": "client_ids", "type": "list[int]", "required": False},
                    {"name": "payment_methods", "type": "list[str]", "required": False},
                    {"name": "amount_min", "type": "float", "required": False},
                    {"name": "amount_max", "type": "float", "required": False}
                ],
                "columns": [
                    "payment_date", "client_name", "invoice_number", "amount",
                    "payment_method", "reference", "currency"
                ]
            },
            {
                "type": ReportType.EXPENSE,
                "name": "Expense Reports",
                "description": "Business expense tracking and categorization",
                "filters": [
                    {"name": "date_from", "type": "datetime", "required": False},
                    {"name": "date_to", "type": "datetime", "required": False},
                    {"name": "categories", "type": "list[str]", "required": False},
                    {"name": "labels", "type": "list[str]", "required": False},
                    {"name": "vendor", "type": "str", "required": False}
                ],
                "columns": [
                    "date", "description", "amount", "category", "vendor",
                    "labels", "currency", "tax_deductible"
                ]
            },
            {
                "type": ReportType.STATEMENT,
                "name": "Statement Reports",
                "description": "Transaction analysis and reconciliation",
                "filters": [
                    {"name": "date_from", "type": "datetime", "required": False},
                    {"name": "date_to", "type": "datetime", "required": False},
                    {"name": "account_ids", "type": "list[int]", "required": False},
                    {"name": "transaction_types", "type": "list[str]", "required": False},
                    {"name": "amount_min", "type": "float", "required": False},
                    {"name": "amount_max", "type": "float", "required": False}
                ],
                "columns": [
                    "transaction_date", "description", "amount", "balance",
                    "transaction_type", "account_name", "reference"
                ]
            },
            {
                "type": ReportType.INVENTORY,
                "name": "Inventory Reports",
                "description": "Stock levels, valuation, and movement analysis",
                "filters": [
                    {"name": "date_from", "type": "datetime", "required": False},
                    {"name": "date_to", "type": "datetime", "required": False},
                    {"name": "date_filter_type", "type": "str", "required": False, "default": "both"},
                    {"name": "category_ids", "type": "list[int]", "required": False},
                    {"name": "item_type", "type": "list[str]", "required": False},
                    {"name": "low_stock_only", "type": "boolean", "required": False},
                    {"name": "value_min", "type": "float", "required": False},
                    {"name": "value_max", "type": "float", "required": False},
                    {"name": "include_inactive", "type": "boolean", "required": False}
                ],
                "columns": [
                    "item_name", "sku", "category", "unit_price", "cost_price",
                    "current_stock", "minimum_stock", "total_value", "last_movement",
                    "item_type", "currency", "is_active"
                ]
            }
        ]

        return ReportTypesResponse(report_types=report_types)

    except Exception as e:
        logger.error(f"Failed to get report types: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve report types"
        )


@router.post("/generate", response_model=ReportResult)
@require_feature("reporting")
async def generate_report(
    request: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_non_viewer_user)
):
    """
    Generate a report with the specified parameters.

    Supports all report types with comprehensive filtering options.
    Can generate reports immediately for JSON format or in background for file formats.
    """
    start_time = time.time()

    security_service = ReportSecurityService(db)
    audit_service = ReportAuditService(db)
    rate_limiter = ReportRateLimiter(db)

    ip_address, user_agent = extract_request_info(http_request)

    try:
        security_service.validate_report_access(current_user, 'generate')

        if not rate_limiter.check_rate_limit(current_user, 'report_generation'):
            rate_info = rate_limiter.get_rate_limit_info(current_user, 'report_generation')

            audit_service.log_access_attempt(
                user_id=current_user.id,
                user_email=current_user.email,
                resource_type='report',
                resource_id='rate_limit',
                action='GENERATE',
                access_granted=False,
                reason=f"Rate limit exceeded: {rate_info['current_usage']}/{rate_info['limit']} requests per hour",
                ip_address=ip_address,
                user_agent=user_agent
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Report generation rate limit exceeded",
                    "details": rate_info,
                    "suggestions": [
                        f"Wait until {rate_info['reset_time']} to generate more reports",
                        "Consider upgrading your account for higher limits"
                    ]
                }
            )

        security_service.validate_export_format(current_user, request.export_format)

        if not security_service.can_access_report_type(current_user, request.report_type):
            audit_service.log_access_attempt(
                user_id=current_user.id,
                user_email=current_user.email,
                resource_type='report',
                resource_id=request.report_type.value,
                action='GENERATE',
                access_granted=False,
                reason=f"Access denied to report type: {request.report_type.value}",
                ip_address=ip_address,
                user_agent=user_agent
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to {request.report_type.value} reports"
            )

        report_service = get_report_service(db)
        security_filters = security_service.get_data_access_filters(current_user)
        combined_filters = {**request.filters, **security_filters}

        if request.export_format == ExportFormat.JSON:
            result = report_service.generate_report(
                report_type=request.report_type,
                filters=combined_filters,
                export_format=request.export_format,
                user_id=current_user.id,
                use_cache=True,
                enable_progress_tracking=False
            )

            if not result.success:
                execution_time_ms = int((time.time() - start_time) * 1000)

                audit_service.log_report_generation(
                    user_id=current_user.id,
                    user_email=current_user.email,
                    report_type=request.report_type,
                    export_format=request.export_format,
                    filters=request.filters,
                    template_id=request.template_id,
                    status="error",
                    error_message=result.error_message,
                    execution_time_ms=execution_time_ms,
                    ip_address=ip_address,
                    user_agent=user_agent
                )

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.error_message or "Report generation failed"
                )

            if result.data:
                result.data = security_service.apply_data_redaction(
                    result.data,
                    request.report_type,
                    current_user,
                    redaction_level="standard"
                )

            execution_time_ms = int((time.time() - start_time) * 1000)
            record_count = len(result.data.data) if result.data else 0

            audit_service.log_report_generation(
                user_id=current_user.id,
                user_email=current_user.email,
                report_type=request.report_type,
                export_format=request.export_format,
                filters=request.filters,
                template_id=request.template_id,
                report_id=result.report_id,
                status="success",
                execution_time_ms=execution_time_ms,
                record_count=record_count,
                ip_address=ip_address,
                user_agent=user_agent
            )

            return result

        else:
            history_service = ReportHistoryService(db)
            report_history = history_service.create_report_history(
                report_type=request.report_type,
                parameters={
                    "filters": combined_filters,
                    "columns": request.columns,
                    "export_format": request.export_format,
                    "template_id": request.template_id,
                    "redaction_level": "standard",
                    "security_filters_applied": bool(security_filters)
                },
                user_id=current_user.id,
                template_id=request.template_id
            )

            audit_service.log_report_generation(
                user_id=current_user.id,
                user_email=current_user.email,
                report_type=request.report_type,
                export_format=request.export_format,
                filters=request.filters,
                template_id=request.template_id,
                report_id=str(report_history.id),
                status="success",
                execution_time_ms=int((time.time() - start_time) * 1000),
                ip_address=ip_address,
                user_agent=user_agent
            )

            background_tasks.add_task(
                _generate_report_background,
                db, report_history.id, request,
                current_user.id, current_user.email,
                ip_address, user_agent
            )

            return ReportResult(
                success=True,
                report_id=report_history.id,
                download_url=f"/api/v1/reports/download/{report_history.id}"
            )

    except BaseReportException as e:
        execution_time_ms = int((time.time() - start_time) * 1000)

        audit_service.log_report_generation(
            user_id=current_user.id,
            user_email=current_user.email,
            report_type=request.report_type,
            export_format=request.export_format,
            filters=request.filters,
            template_id=request.template_id,
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.warning(f"Report exception: {e.error_code.value} - {e.message}")
        raise handle_report_exception(e)
    except HTTPException:
        raise
    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)

        audit_service.log_report_generation(
            user_id=current_user.id,
            user_email=current_user.email,
            report_type=request.report_type,
            export_format=request.export_format,
            filters=request.filters,
            template_id=request.template_id,
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.error(f"Failed to generate report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise handle_generic_exception(e, "report generation")


@router.post("/preview", response_model=ReportData)
@require_feature("reporting")
async def preview_report(
    request: ReportPreviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_non_viewer_user)
):
    """Preview a report with current filters showing limited results."""
    try:
        report_service = get_report_service(db)

        result = report_service.generate_report(
            report_type=request.report_type,
            filters={**request.filters, "_limit": request.limit or 10},
            export_format=ExportFormat.JSON,
            user_id=current_user.id
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message or "Report preview failed"
            )

        return result.data

    except BaseReportException as e:
        logger.warning(f"Report preview exception: {e.error_code.value} - {e.message}")
        raise handle_report_exception(e)
    except Exception as e:
        logger.error(f"Failed to preview report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise handle_generic_exception(e, "report preview")


@router.post("/relationship-cloud", response_model=RelationshipCloudResponse)
@require_feature("reporting")
async def relationship_cloud(
    request: RelationshipCloudRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_non_viewer_user)
):
    """Return a compact relationship graph for invoice, expense, and statement reports."""
    try:
        if request.report_type not in {ReportType.INVOICE, ReportType.EXPENSE, ReportType.STATEMENT}:
            return RelationshipCloudResponse(
                report_type=request.report_type,
                filters=request.filters,
            )

        date_from = _parse_filter_date(request.filters.get("date_from"))
        date_to = _parse_filter_date(request.filters.get("date_to"))
        limit = max(1, min(request.limit or 40, 100))

        invoice_query = (
            db.query(Invoice)
            .options(selectinload(Invoice.client))
            .filter(Invoice.is_deleted == False)
            .order_by(Invoice.created_at.desc())
        )
        expense_query = (
            db.query(Expense)
            .filter(Expense.is_deleted == False)
            .order_by(Expense.created_at.desc())
        )
        statement_query = (
            db.query(BankStatement)
            .filter(BankStatement.is_deleted == False)
            .order_by(BankStatement.created_at.desc())
        )

        invoice_statement_pairs = db.query(
            BankStatementTransaction.invoice_id,
            BankStatementTransaction.statement_id
        ).filter(BankStatementTransaction.invoice_id.isnot(None)).all()
        expense_statement_pairs = db.query(
            BankStatementTransaction.expense_id,
            BankStatementTransaction.statement_id
        ).filter(BankStatementTransaction.expense_id.isnot(None)).all()
        invoice_to_statement = {invoice_id: statement_id for invoice_id, statement_id in invoice_statement_pairs if invoice_id}
        expense_to_statement = {expense_id: statement_id for expense_id, statement_id in expense_statement_pairs if expense_id}

        if request.report_type == ReportType.INVOICE:
            invoices = invoice_query.limit(limit).all()
            invoices = [
                invoice for invoice in invoices
                if _in_date_range(invoice.created_at, date_from, date_to)
            ]
            if request.filters.get("client_ids"):
                allowed_client_ids = set(request.filters["client_ids"])
                invoices = [invoice for invoice in invoices if invoice.client_id in allowed_client_ids]
            if request.filters.get("currency"):
                invoices = [invoice for invoice in invoices if invoice.currency == request.filters["currency"]]
            if request.filters.get("status"):
                allowed_status = set(request.filters["status"])
                invoices = [invoice for invoice in invoices if invoice.status in allowed_status]
            if request.filters.get("amount_min") is not None:
                invoices = [invoice for invoice in invoices if invoice.amount >= float(request.filters["amount_min"])]
            if request.filters.get("amount_max") is not None:
                invoices = [invoice for invoice in invoices if invoice.amount <= float(request.filters["amount_max"])]

            focal_invoice_ids = {invoice.id for invoice in invoices}
            expenses = [
                expense for expense in expense_query.limit(limit * 2).all()
                if expense.invoice_id in focal_invoice_ids
            ]
            focal_statement_ids = {
                invoice_to_statement[invoice.id] for invoice in invoices if invoice.id in invoice_to_statement
            }
            focal_statement_ids.update({
                expense_to_statement[expense.id] for expense in expenses if expense.id in expense_to_statement
            })
            statements = [statement for statement in statement_query.limit(limit * 2).all() if statement.id in focal_statement_ids]

        elif request.report_type == ReportType.EXPENSE:
            expenses = expense_query.limit(limit).all()
            expenses = [
                expense for expense in expenses
                if _in_date_range(expense.expense_date, date_from, date_to)
            ]
            if request.filters.get("client_ids"):
                allowed_client_ids = set(request.filters["client_ids"])
                expenses = [expense for expense in expenses if expense.client_id in allowed_client_ids]
            if request.filters.get("currency"):
                expenses = [expense for expense in expenses if expense.currency == request.filters["currency"]]
            if request.filters.get("status"):
                allowed_status = set(request.filters["status"])
                expenses = [expense for expense in expenses if expense.status in allowed_status]
            if request.filters.get("categories"):
                allowed_categories = set(request.filters["categories"])
                expenses = [expense for expense in expenses if expense.category in allowed_categories]
            if request.filters.get("vendor"):
                vendor_query = str(request.filters["vendor"]).lower()
                expenses = [expense for expense in expenses if expense.vendor and vendor_query in expense.vendor.lower()]
            if request.filters.get("labels"):
                wanted_labels = set(request.filters["labels"])
                expenses = [expense for expense in expenses if wanted_labels.intersection(set(expense.labels or []))]
            if request.filters.get("amount_min") is not None:
                expenses = [expense for expense in expenses if (expense.amount or 0) >= float(request.filters["amount_min"])]
            if request.filters.get("amount_max") is not None:
                expenses = [expense for expense in expenses if (expense.amount or 0) <= float(request.filters["amount_max"])]

            focal_invoice_ids = {expense.invoice_id for expense in expenses if expense.invoice_id}
            focal_statement_ids = {expense_to_statement[expense.id] for expense in expenses if expense.id in expense_to_statement}
            invoices = [invoice for invoice in invoice_query.limit(limit * 2).all() if invoice.id in focal_invoice_ids]
            focal_statement_ids.update({
                invoice_to_statement[invoice.id] for invoice in invoices if invoice.id in invoice_to_statement
            })
            statements = [statement for statement in statement_query.limit(limit * 2).all() if statement.id in focal_statement_ids]

        else:
            statements = statement_query.limit(limit).all()
            statements = [
                statement for statement in statements
                if _in_date_range(statement.created_at, date_from, date_to)
            ]
            focal_statement_ids = {statement.id for statement in statements}
            invoices = [
                invoice for invoice in invoice_query.limit(limit * 3).all()
                if invoice_to_statement.get(invoice.id) in focal_statement_ids
            ]
            expenses = [
                expense for expense in expense_query.limit(limit * 3).all()
                if expense_to_statement.get(expense.id) in focal_statement_ids
            ]
            focal_invoice_ids = {invoice.id for invoice in invoices}
            linked_invoice_ids = {expense.invoice_id for expense in expenses if expense.invoice_id}
            if linked_invoice_ids - focal_invoice_ids:
                extra_invoices = [
                    invoice for invoice in invoice_query.limit(limit * 4).all()
                    if invoice.id in linked_invoice_ids
                ]
                merged = {invoice.id: invoice for invoice in invoices}
                for invoice in extra_invoices:
                    merged[invoice.id] = invoice
                invoices = list(merged.values())

        nodes = []
        edges = []

        for statement in statements:
            nodes.append(RelationshipCloudNode(
                id=f"statement-{statement.id}",
                entity_id=statement.id,
                type="statement",
                title=statement.original_filename,
                subtitle=f"{statement.extracted_count or 0} txns",
                status=statement.status,
            ))

        for invoice in invoices:
            client_name = invoice.client.name if invoice.client else "Client"
            nodes.append(RelationshipCloudNode(
                id=f"invoice-{invoice.id}",
                entity_id=invoice.id,
                type="invoice",
                title=invoice.number,
                subtitle=f"{client_name} • {_currency_text(invoice.amount, invoice.currency)}",
                status=invoice.status,
            ))
            if invoice.id in invoice_to_statement:
                edges.append(RelationshipCloudEdge(
                    id=f"statement-invoice-{invoice.id}",
                    source=f"statement-{invoice_to_statement[invoice.id]}",
                    target=f"invoice-{invoice.id}",
                    label="statement link",
                ))

        for expense in expenses:
            nodes.append(RelationshipCloudNode(
                id=f"expense-{expense.id}",
                entity_id=expense.id,
                type="expense",
                title=expense.vendor or expense.category or f"Expense #{expense.id}",
                subtitle=f"{expense.category} • {_currency_text(expense.amount, expense.currency)}",
                status=expense.status,
            ))
            if expense.invoice_id:
                edges.append(RelationshipCloudEdge(
                    id=f"invoice-expense-{expense.id}",
                    source=f"invoice-{expense.invoice_id}",
                    target=f"expense-{expense.id}",
                    label="invoice link",
                ))
            if expense.id in expense_to_statement:
                edges.append(RelationshipCloudEdge(
                    id=f"statement-expense-{expense.id}",
                    source=f"statement-{expense_to_statement[expense.id]}",
                    target=f"expense-{expense.id}",
                    label="transaction match",
                ))

        node_ids = {node.id for node in nodes}
        edges = [edge for edge in edges if edge.source in node_ids and edge.target in node_ids]

        return RelationshipCloudResponse(
            report_type=request.report_type,
            nodes=nodes,
            edges=edges,
            stats=RelationshipCloudStats(
                statements=len([node for node in nodes if node.type == "statement"]),
                invoices=len([node for node in nodes if node.type == "invoice"]),
                expenses=len([node for node in nodes if node.type == "expense"]),
                orphan_expenses=len([
                    expense for expense in expenses
                    if not expense.invoice_id and expense.id not in expense_to_statement
                ]),
            ),
            filters=request.filters,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to build relationship cloud: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise handle_generic_exception(e, "relationship cloud generation")


@router.post("/regenerate/{report_id}", response_model=ReportResult)
@require_feature("reporting")
async def regenerate_report(
    report_id: int,
    background_tasks: BackgroundTasks,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_non_viewer_user)
):
    """Regenerate a report with current data using the same parameters."""
    try:
        history_service = ReportHistoryService(db)

        original_report = history_service.get_report_history(report_id, current_user.id)

        if not original_report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original report not found"
            )

        request = ReportGenerateRequest(
            report_type=original_report.report_type,
            filters=original_report.parameters.get("filters", {}),
            columns=original_report.parameters.get("columns"),
            export_format=original_report.parameters.get("export_format", ExportFormat.JSON),
            template_id=original_report.parameters.get("template_id")
        )

        return await generate_report(request, background_tasks, http_request, db, current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate report"
        )


async def _generate_report_background(
    db: Session,
    report_history_id: int,
    request: ReportGenerateRequest,
    user_id: int,
    user_email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """Background task for generating reports in file formats."""
    import time as _time
    start_time = _time.time()

    history_service = ReportHistoryService(db)
    audit_service = ReportAuditService(db)

    try:
        history_service.update_report_status(report_history_id, ReportStatus.GENERATING)

        report_service = get_report_service(db)
        result = report_service.generate_report(
            report_type=request.report_type,
            filters=request.filters,
            export_format=request.export_format,
            user_id=user_id,
            use_cache=True,
            enable_progress_tracking=True
        )

        if result.success and result.data:
            export_service = ReportExportService()
            exported_data = export_service.export_report(result.data, request.export_format)

            file_content = exported_data if isinstance(exported_data, bytes) else exported_data.encode('utf-8')

            file_path = history_service.store_report_file(
                report_history_id,
                file_content,
                request.export_format,
                f"{request.report_type}_report"
            )

            execution_time_ms = int((_time.time() - start_time) * 1000)
            record_count = len(result.data.data) if result.data else 0
            file_size_bytes = len(file_content)

            audit_service.log_report_generation(
                user_id=user_id,
                user_email=user_email,
                report_type=request.report_type,
                export_format=request.export_format,
                filters=request.filters,
                template_id=request.template_id,
                report_id=str(report_history_id),
                status="success",
                execution_time_ms=execution_time_ms,
                record_count=record_count,
                file_size_bytes=file_size_bytes,
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info(f"Report {report_history_id} generated successfully: {file_path}")
        else:
            execution_time_ms = int((_time.time() - start_time) * 1000)

            audit_service.log_report_generation(
                user_id=user_id,
                user_email=user_email,
                report_type=request.report_type,
                export_format=request.export_format,
                filters=request.filters,
                template_id=request.template_id,
                report_id=str(report_history_id),
                status="error",
                error_message=result.error_message or "Report generation failed",
                execution_time_ms=execution_time_ms,
                ip_address=ip_address,
                user_agent=user_agent
            )

            history_service.update_report_status(
                report_history_id,
                ReportStatus.FAILED,
                error_message=result.error_message or "Report generation failed"
            )

    except Exception as e:
        import traceback as _tb
        execution_time_ms = int((_time.time() - start_time) * 1000)

        audit_service.log_report_generation(
            user_id=user_id,
            user_email=user_email,
            report_type=request.report_type,
            export_format=request.export_format,
            filters=request.filters,
            template_id=request.template_id,
            report_id=str(report_history_id),
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.error(f"Background report generation failed: {str(e)}")
        logger.error(f"Traceback: {_tb.format_exc()}")

        try:
            history_service = ReportHistoryService(db)
            history_service.update_report_status(
                report_history_id,
                ReportStatus.FAILED,
                error_message=str(e)
            )
        except Exception as update_error:
            logger.error(f"Failed to update report status: {str(update_error)}")
