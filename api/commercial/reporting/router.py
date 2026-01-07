"""
Report API Router

Comprehensive API endpoints for report generation, template management,
scheduling, and history tracking with proper authentication and authorization.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import traceback
from datetime import datetime
import os
import mimetypes
import time

from core.models.database import get_db
from core.models.models import MasterUser
from core.utils.feature_gate import require_feature
from core.services.report_service import ReportService
from core.services.report_template_service import ReportTemplateService
from core.services.scheduled_report_service import ScheduledReportService
from core.services.report_history_service import ReportHistoryService
from core.services.report_cache_service import CacheConfig, CacheStrategy
from core.services.report_query_optimizer import OptimizationConfig
from config import get_settings


def get_report_service(db: Session) -> ReportService:
    """
    Get a ReportService instance with performance optimizations configured.
    
    Args:
        db: Database session
        
    Returns:
        Configured ReportService instance
    """
    settings = get_settings()
    
    # Configure caching
    cache_config = CacheConfig(
        strategy=CacheStrategy.REDIS_ONLY if settings.REDIS_URL else CacheStrategy.MEMORY_ONLY,
        default_ttl=settings.CACHE_DEFAULT_TTL,
        max_memory_size=settings.CACHE_MAX_MEMORY_SIZE,
        redis_url=settings.REDIS_URL,
        enable_compression=True
    )
    
    # Configure query optimization
    optimization_config = OptimizationConfig(
        enable_pagination=True,
        enable_query_monitoring=settings.QUERY_OPTIMIZATION_ENABLED,
        slow_query_threshold=settings.SLOW_QUERY_THRESHOLD,
        max_result_size=settings.MAX_RESULT_SIZE
    )
    
    return ReportService(
        db=db,
        cache_config=cache_config,
        optimization_config=optimization_config
    )
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer, require_admin
from core.utils.audit import log_audit_event
from core.services.report_service import ReportService
from core.services.report_template_service import ReportTemplateService
from core.services.scheduled_report_service import ScheduledReportService
from core.services.report_exporter import ReportExportService, ExportError
from core.services.report_history_service import ReportHistoryService
from core.services.report_audit_service import ReportAuditService, extract_request_info
from core.services.report_security_service import ReportSecurityService, ReportRateLimiter
from core.exceptions.report_exceptions import (
    BaseReportException, ReportValidationException, ReportGenerationException,
    ReportTemplateException, ReportScheduleException, ReportExportException,
    ReportErrorCode, TemplateValidationError, TemplateAccessError,
    ReportValidationError, ReportSchedulerError
)
from core.schemas.report import (
    ReportType, ExportFormat, ReportGenerateRequest, ReportPreviewRequest,
    ReportResult, ReportData, ReportTypesResponse, ReportStatus,
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplate as ReportTemplateSchema,
    ReportTemplateListResponse, ScheduledReportCreate, ScheduledReportUpdate,
    ScheduledReport as ScheduledReportSchema, ScheduledReportListResponse,
    ReportHistory as ReportHistorySchema, ReportHistoryListResponse
)
from core.constants.error_codes import (
    FAILED_TO_GENERATE_REPORT, FAILED_TO_CREATE_TEMPLATE, FAILED_TO_UPDATE_TEMPLATE,
    FAILED_TO_DELETE_TEMPLATE, FAILED_TO_CREATE_SCHEDULE, FAILED_TO_UPDATE_SCHEDULE,
    FAILED_TO_DELETE_SCHEDULE, FAILED_TO_FETCH_REPORTS
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def get_current_non_viewer_user(current_user = Depends(get_current_user)):
    """
    FastAPI dependency that ensures the current user is not a viewer.
    
    Returns:
        The current user if they have non-viewer permissions
        
    Raises:
        HTTPException: 403 Forbidden if user is a viewer
    """
    require_non_viewer(current_user, "access reports")
    return current_user


def handle_report_exception(e: BaseReportException) -> HTTPException:
    """
    Convert report exceptions to appropriate HTTP exceptions with detailed error information.
    
    Args:
        e: The report exception to convert
        
    Returns:
        HTTPException with appropriate status code and error details
    """
    error_dict = e.to_dict()
    
    # Map error codes to HTTP status codes
    status_code_mapping = {
        # Validation errors -> 400 Bad Request
        ReportErrorCode.REPORT_INVALID_TYPE: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.REPORT_INVALID_FILTERS: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_DATE_RANGE_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_FILTER_MISSING: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_FILTER_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_CLIENT_NOT_FOUND: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_AMOUNT_RANGE_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_CURRENCY_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_EXPORT_FORMAT_INVALID: status.HTTP_400_BAD_REQUEST,
        
        # Access denied errors -> 403 Forbidden
        ReportErrorCode.REPORT_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
        ReportErrorCode.TEMPLATE_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
        ReportErrorCode.SCHEDULE_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
        ReportErrorCode.DATA_INSUFFICIENT_PERMISSIONS: status.HTTP_403_FORBIDDEN,
        
        # Not found errors -> 404 Not Found
        ReportErrorCode.REPORT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ReportErrorCode.TEMPLATE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ReportErrorCode.SCHEDULE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        
        # Conflict errors -> 409 Conflict
        ReportErrorCode.TEMPLATE_NAME_EXISTS: status.HTTP_409_CONFLICT,
        
        # Request entity too large -> 413
        ReportErrorCode.REPORT_DATA_TOO_LARGE: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        ReportErrorCode.EXPORT_FILE_TOO_LARGE: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        
        # Unsupported media type -> 415
        ReportErrorCode.EXPORT_FORMAT_UNSUPPORTED: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        
        # Request timeout -> 408
        ReportErrorCode.REPORT_TIMEOUT: status.HTTP_408_REQUEST_TIMEOUT,
        
        # Service unavailable -> 503
        ReportErrorCode.DATA_CONNECTION_FAILED: status.HTTP_503_SERVICE_UNAVAILABLE,
    }
    
    # Default to 500 Internal Server Error for unhandled error codes
    http_status = status_code_mapping.get(e.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return HTTPException(
        status_code=http_status,
        detail={
            "error_code": error_dict["error_code"],
            "message": error_dict["message"],
            "details": error_dict["details"],
            "suggestions": error_dict["suggestions"],
            "field": error_dict.get("field"),
            "retryable": error_dict["retryable"]
        }
    )


def handle_generic_exception(e: Exception, operation: str) -> HTTPException:
    """
    Handle unexpected exceptions with proper logging and user-friendly messages.
    
    Args:
        e: The exception to handle
        operation: Description of the operation that failed
        
    Returns:
        HTTPException with generic error message
    """
    logger.error(f"Unexpected error in {operation}: {str(e)}", exc_info=True)
    
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": f"An unexpected error occurred during {operation}",
            "details": {"operation": operation},
            "suggestions": [
                "Please try again in a few moments",
                "If the problem persists, contact support",
                "Check that all required parameters are provided"
            ],
            "retryable": True
        }
    )


@router.get("/types", response_model=ReportTypesResponse)
@require_feature("reporting")
async def get_report_types(
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get available report types and their configuration options.
    
    Returns information about all supported report types including
    available filters, columns, and export formats.
    """
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
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Generate a report with the specified parameters.
    
    Supports all report types with comprehensive filtering options.
    Can generate reports immediately for JSON format or in background for file formats.
    """
    start_time = time.time()
    
    # Initialize security and audit services
    security_service = ReportSecurityService(db)
    audit_service = ReportAuditService(db)
    rate_limiter = ReportRateLimiter(db)
    
    # Extract request information for audit logging
    ip_address, user_agent = extract_request_info(http_request)
    
    try:
        # Validate user permissions
        security_service.validate_report_access(current_user, 'generate')
        
        # Check rate limits
        if not rate_limiter.check_rate_limit(current_user, 'report_generation'):
            rate_info = rate_limiter.get_rate_limit_info(current_user, 'report_generation')
            
            # Log rate limit violation
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
        
        # Validate export format permissions
        security_service.validate_export_format(current_user, request.export_format)
        
        # Validate report type access
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
        
        # Initialize report service with performance optimizations
        report_service = get_report_service(db)
        
        # Apply security filters
        security_filters = security_service.get_data_access_filters(current_user)
        combined_filters = {**request.filters, **security_filters}
        
        # For JSON format, generate immediately
        if request.export_format == ExportFormat.JSON:
            result = report_service.generate_report(
                report_type=request.report_type,
                filters=combined_filters,
                export_format=request.export_format,
                user_id=current_user.id,
                use_cache=True,
                enable_progress_tracking=False  # JSON reports are typically fast
            )
            
            if not result.success:
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # Log failed generation
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
            
            # Apply data redaction if needed
            if result.data:
                result.data = security_service.apply_data_redaction(
                    result.data,
                    request.report_type,
                    current_user,
                    redaction_level="standard"
                )
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            record_count = len(result.data.data) if result.data else 0

            # Log successful generation
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
        
        # For file formats, generate in background
        else:
            # Create report history entry using the service
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
            
            # Log background generation start
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
            
            # Add background task for report generation
            background_tasks.add_task(
                _generate_report_background,
                db, report_history.id, request, current_user.id, ip_address, user_agent
            )
            
            return ReportResult(
                success=True,
                report_id=report_history.id,
                download_url=f"/api/v1/reports/download/{report_history.id}"
            )
            
    except BaseReportException as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Log exception
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
        # Re-raise HTTP exceptions (like rate limiting)
        raise
    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Log unexpected exception
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
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Preview a report with current filters showing limited results.
    
    Returns a sample of the report data to help users validate
    their filters before generating the full report.
    """
    
    try:
        report_service = get_report_service(db)
        
        # Generate preview with limited results
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


# Template Management Endpoints

@router.get("/templates", response_model=ReportTemplateListResponse)
@require_feature("reporting")
async def get_report_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    report_type: Optional[ReportType] = Query(None),
    include_shared: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get user's report templates with optional filtering.
    
    Returns templates owned by the user and optionally shared templates.
    """
    try:
        template_service = ReportTemplateService(db)
        templates = template_service.list_templates(
            user_id=current_user.id,
            report_type=report_type,
            include_shared=include_shared,
            limit=limit,
            offset=skip
        )
        
        # For now, return the templates without total count
        # In a real implementation, you'd modify the service to return total count
        return ReportTemplateListResponse(
            templates=templates,
            total=len(templates)
        )
        
    except Exception as e:
        logger.error(f"Failed to get report templates: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve report templates"
        )


@router.post("/templates", response_model=ReportTemplateSchema)
@require_feature("reporting")
async def create_report_template(
    template: ReportTemplateCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Create a new report template.
    
    Templates can be used to save common report configurations
    and can be shared with other users in the organization.
    """
    
    try:
        template_service = ReportTemplateService(db)
        
        # Validate template filters
        report_service = get_report_service(db)
        report_service.validate_filters(template.report_type, template.filters)
        
        created_template = template_service.create_template(
            template_data=template,
            user_id=current_user.id
        )
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "template_create",
            f"Created report template: {template.name}",
            {"template_id": created_template.id, "report_type": template.report_type}
        )
        
        return ReportTemplateSchema.model_validate(created_template)
        
    except (TemplateValidationError, TemplateAccessError) as e:
        logger.warning(f"Template creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ReportValidationError as e:
        logger.warning(f"Template validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template validation error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to create report template: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_CREATE_TEMPLATE
        )


@router.put("/templates/{template_id}", response_model=ReportTemplateSchema)
@require_feature("reporting")
async def update_report_template(
    template_id: int,
    template: ReportTemplateUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Update an existing report template.
    
    Users can only update templates they own or have permission to modify.
    """
    
    try:
        template_service = ReportTemplateService(db)
        
        # Check if template exists and user has permission
        try:
            existing_template = template_service.get_template(template_id, current_user.id)
        except TemplateAccessError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report template not found"
            )
        
        # Validate filters if provided
        if template.filters is not None:
            report_service = get_report_service(db)
            report_service.validate_filters(existing_template.report_type, template.filters)
        
        updated_template = template_service.update_template(
            template_id=template_id,
            template_data=template,
            user_id=current_user.id
        )
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "template_update",
            f"Updated report template: {updated_template.name}",
            {"template_id": template_id}
        )
        
        return ReportTemplateSchema.model_validate(updated_template)
        
    except (TemplateValidationError, TemplateAccessError) as e:
        logger.warning(f"Template update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ReportValidationError as e:
        logger.warning(f"Template validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template validation error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to update report template: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_UPDATE_TEMPLATE
        )


@router.delete("/templates/{template_id}")
@require_feature("reporting")
async def delete_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Delete a report template.
    
    Users can only delete templates they own.
    This will also cancel any scheduled reports using this template.
    """
    
    try:
        template_service = ReportTemplateService(db)
        
        # Check if template exists and user has permission
        try:
            existing_template = template_service.get_template(template_id, current_user.id)
        except TemplateAccessError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report template not found"
            )
        
        # Note: Any scheduled reports using this template will need to be handled separately
        # This could be implemented as a background task or handled by the scheduler service
        
        # Delete the template
        template_service.delete_template(template_id, current_user.id)
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "template_delete",
            f"Deleted report template: {existing_template.name}",
            {"template_id": template_id}
        )
        
        return {"message": "Report template deleted successfully"}
        
    except (TemplateValidationError, TemplateAccessError) as e:
        logger.warning(f"Template deletion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete report template: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_DELETE_TEMPLATE
        )


# Scheduled Reports Endpoints

@router.get("/scheduled", response_model=ScheduledReportListResponse)
@require_feature("reporting")
async def get_scheduled_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get user's scheduled reports.
    
    Returns scheduled reports for templates owned by the user.
    """
    try:
        from core.services.report_scheduler import ReportScheduler
        report_scheduler = ReportScheduler(db)
        scheduled_service = ScheduledReportService(db, report_scheduler)
        result = scheduled_service.get_scheduled_reports(
            user_id=current_user.id,
            offset=skip,
            limit=limit,
            active_only=active_only
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get scheduled reports: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve scheduled reports"
        )


@router.post("/scheduled", response_model=ScheduledReportSchema)
@require_feature("reporting")
async def create_scheduled_report(
    scheduled_report: ScheduledReportCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Create a new scheduled report.
    
    Schedules automatic report generation and email delivery
    based on the specified template and schedule configuration.
    """
    
    try:
        # Verify template exists and user has access
        template_service = ReportTemplateService(db)
        try:
            template = template_service.get_template(scheduled_report.template_id, current_user.id)
        except TemplateAccessError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report template not found or access denied"
            )
        
        from core.services.report_scheduler import ReportScheduler
        report_scheduler = ReportScheduler(db)
        scheduled_service = ScheduledReportService(db, report_scheduler)
        created_schedule = scheduled_service.create_scheduled_report(
            schedule_data=scheduled_report,
            user_id=current_user.id
        )
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "schedule_create",
            f"Created scheduled report for template: {template.name}",
            {"schedule_id": created_schedule.id, "template_id": scheduled_report.template_id}
        )
        
        return ScheduledReportSchema.model_validate(created_schedule)
        
    except ReportSchedulerError as e:
        logger.warning(f"Scheduling error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create scheduled report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_CREATE_SCHEDULE
        )


@router.put("/scheduled/{schedule_id}", response_model=ScheduledReportSchema)
@require_feature("reporting")
async def update_scheduled_report(
    schedule_id: int,
    scheduled_report: ScheduledReportUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Update an existing scheduled report.
    
    Users can only update schedules for templates they own or have access to.
    """
    
    try:
        from core.services.report_scheduler import ReportScheduler
        report_scheduler = ReportScheduler(db)
        scheduled_service = ScheduledReportService(db, report_scheduler)
        
        updated_schedule = scheduled_service.update_scheduled_report(
            schedule_id=schedule_id,
            update_data=scheduled_report,
            user_id=current_user.id
        )
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "schedule_update",
            f"Updated scheduled report",
            {"schedule_id": schedule_id}
        )
        
        return ScheduledReportSchema.model_validate(updated_schedule)
        
    except ReportSchedulerError as e:
        logger.warning(f"Scheduling update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update scheduled report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_UPDATE_SCHEDULE
        )


@router.delete("/scheduled/{schedule_id}")
@require_feature("reporting")
async def delete_scheduled_report(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Delete a scheduled report.
    
    Users can only delete schedules for templates they own.
    """
    
    try:
        from core.services.report_scheduler import ReportScheduler
        report_scheduler = ReportScheduler(db)
        scheduled_service = ScheduledReportService(db, report_scheduler)
        
        scheduled_service.delete_scheduled_report(schedule_id, current_user.id)
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "schedule_delete",
            f"Deleted scheduled report",
            {"schedule_id": schedule_id}
        )
        
        return {"message": "Scheduled report deleted successfully"}
        
    except ReportSchedulerError as e:
        logger.warning(f"Scheduling deletion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete scheduled report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_DELETE_SCHEDULE
        )


# Report History and Download Endpoints

@router.get("/history", response_model=ReportHistoryListResponse)
@require_feature("reporting")
async def get_report_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    report_type: Optional[ReportType] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get user's report generation history.
    
    Returns reports generated by the user with optional filtering.
    """
    try:
        history_service = ReportHistoryService(db)
        
        # Get reports with filtering
        reports = history_service.list_user_reports(
            user_id=current_user.id,
            report_type=report_type,
            status=ReportStatus(status) if status else None,
            limit=limit,
            offset=skip
        )
        
        # Get total count
        total = history_service.count_user_reports(
            user_id=current_user.id,
            report_type=report_type,
            status=ReportStatus(status) if status else None
        )
        
        return ReportHistoryListResponse(
            reports=[ReportHistorySchema.model_validate(r) for r in reports],
            total=total
        )
        
    except Exception as e:
        logger.error(f"Failed to get report history: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_FETCH_REPORTS
        )


@router.get("/download/{report_id}")
@require_feature("reporting")
async def download_report(
    report_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Download a generated report file.
    
    Users can only download reports they generated or have access to.
    """
    # Initialize services
    security_service = ReportSecurityService(db)
    audit_service = ReportAuditService(db)
    history_service = ReportHistoryService(db)
    
    # Extract request information for audit logging
    ip_address, user_agent = extract_request_info(http_request)
    
    try:
        # Validate download permissions
        security_service.validate_report_access(current_user, 'download')
        
        # Get report history entry with access control
        report = history_service.get_report_history(report_id, current_user.id)
        
        if not report:
            # Log access attempt
            audit_service.log_access_attempt(
                user_id=current_user.id,
                user_email=current_user.email,
                resource_type='report',
                resource_id=str(report_id),
                action='DOWNLOAD',
                access_granted=False,
                reason="Report not found or access denied",
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        if report.status != ReportStatus.COMPLETED:
            # Log access attempt for incomplete report
            audit_service.log_access_attempt(
                user_id=current_user.id,
                user_email=current_user.email,
                resource_type='report',
                resource_id=str(report_id),
                action='DOWNLOAD',
                access_granted=False,
                reason=f"Report not ready: {report.status}",
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report is not ready for download. Status: {report.status}"
            )
        
        # Get file path with access control and expiration check
        file_path = history_service.get_report_file_path(report_id, current_user.id)
        
        if not file_path:
            # Log access attempt for missing file
            audit_service.log_access_attempt(
                user_id=current_user.id,
                user_email=current_user.email,
                resource_type='report',
                resource_id=str(report_id),
                action='DOWNLOAD',
                access_granted=False,
                reason="Report file not found or expired",
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report file not found or has expired"
            )
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"
        
        # Generate filename
        filename = f"report_{report.id}_{report.report_type}_{report.generated_at.strftime('%Y%m%d_%H%M%S')}"
        if file_path.endswith('.pdf'):
            filename += '.pdf'
        elif file_path.endswith('.csv'):
            filename += '.csv'
        elif file_path.endswith('.xlsx'):
            filename += '.xlsx'
        
        # Get file size for audit logging
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        # Log successful download
        audit_service.log_report_download(
            user_id=current_user.id,
            user_email=current_user.email,
            report_id=str(report_id),
            report_type=report.report_type,
            export_format=report.parameters.get('export_format', 'unknown'),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Log successful access
        audit_service.log_access_attempt(
            user_id=current_user.id,
            user_email=current_user.email,
            resource_type='report',
            resource_id=str(report_id),
            action='DOWNLOAD',
            access_granted=True,
            reason=f"File size: {file_size} bytes",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Validate file path before serving
        from core.utils.file_validation import validate_file_path
        validated_path = validate_file_path(file_path)

        return FileResponse(
            path=validated_path,
            filename=filename,
            media_type=content_type
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log unexpected exception
        audit_service.log_access_attempt(
            user_id=current_user.id,
            user_email=current_user.email,
            resource_type='report',
            resource_id=str(report_id),
            action='DOWNLOAD',
            access_granted=False,
            reason=f"System error: {str(e)}",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.error(f"Failed to download report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download report"
        )


@router.post("/regenerate/{report_id}", response_model=ReportResult)
@require_feature("reporting")
async def regenerate_report(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_non_viewer_user)
):
    """
    Regenerate a report with current data using the same parameters.
    
    Creates a new report entry with the same filters and settings
    but with current data from the database.
    """
    
    try:
        history_service = ReportHistoryService(db)
        
        # Get original report with access control
        original_report = history_service.get_report_history(report_id, current_user.id)
        
        if not original_report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original report not found"
            )
        
        # Create new report request from original parameters
        request = ReportGenerateRequest(
            report_type=original_report.report_type,
            filters=original_report.parameters.get("filters", {}),
            columns=original_report.parameters.get("columns"),
            export_format=original_report.parameters.get("export_format", ExportFormat.JSON),
            template_id=original_report.parameters.get("template_id")
        )
        
        # Generate new report
        return await generate_report(request, background_tasks, db, current_user)
        
    except Exception as e:
        logger.error(f"Failed to regenerate report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate report"
        )


@router.delete("/history/{report_id}")
@require_feature("reporting")
async def delete_report_file(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(require_non_viewer)
):
    """
    Delete a report file and clear its file path from history.
    
    Users can only delete reports they generated.
    """
    try:
        history_service = ReportHistoryService(db)
        
        success = history_service.delete_report_file(report_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found or already deleted"
            )
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "report_delete",
            f"Deleted report file",
            {"report_id": report_id}
        )
        
        return {"message": "Report file deleted successfully"}
        
    except ReportHistoryError as e:
        logger.warning(f"Report deletion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete report file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete report file"
        )


@router.get("/storage/stats")
@require_feature("reporting")
async def get_storage_stats(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(require_admin)
):
    """
    Get report storage statistics.
    
    Admin-only endpoint for monitoring storage usage.
    """
    try:
        history_service = ReportHistoryService(db)
        stats = history_service.get_storage_stats()
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get storage stats: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve storage statistics"
        )


@router.post("/cleanup/expired")
@require_feature("reporting")
async def cleanup_expired_reports(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(require_admin)
):
    """
    Clean up expired report files.
    
    Admin-only endpoint for manual cleanup of expired reports.
    """
    try:
        history_service = ReportHistoryService(db)
        cleanup_stats = history_service.cleanup_expired_reports()
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "cleanup_expired",
            f"Cleaned up expired reports",
            cleanup_stats
        )
        
        return {
            "message": "Expired reports cleanup completed",
            "stats": cleanup_stats
        }
        
    except ReportHistoryError as e:
        logger.warning(f"Cleanup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to cleanup expired reports: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup expired reports"
        )


@router.post("/cleanup/orphaned")
@require_feature("reporting")
async def cleanup_orphaned_files(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(require_admin)
):
    """
    Clean up orphaned report files that no longer have database records.
    
    Admin-only endpoint for cleaning up orphaned files.
    """
    try:
        history_service = ReportHistoryService(db)
        cleanup_stats = history_service.cleanup_orphaned_files()
        
        # Log audit event
        await log_audit_event(
            db, current_user.id, "cleanup_orphaned",
            f"Cleaned up orphaned files",
            cleanup_stats
        )
        
        return {
            "message": "Orphaned files cleanup completed",
            "stats": cleanup_stats
        }
        
    except ReportHistoryError as e:
        logger.warning(f"Cleanup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned files: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup orphaned files"
        )


# Background task for report generation
async def _generate_report_background(
    db: Session,
    report_history_id: int,
    request: ReportGenerateRequest,
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """
    Background task for generating reports in file formats.
    
    Updates the report history entry with the result and logs audit events.
    """
    start_time = time.time()
    
    # Initialize services
    history_service = ReportHistoryService(db)
    audit_service = ReportAuditService(db)
    security_service = ReportSecurityService(db)
    
    # Get user info for audit logging (from master database)
    from core.models.models import MasterUser
    from core.models.database import get_master_db
    master_db = next(get_master_db())
    try:
        user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
        user_email = user.email if user else "unknown@system"
    finally:
        master_db.close()
    
    try:
        # Update status to generating
        history_service.update_report_status(
            report_history_id, 
            ReportStatus.GENERATING
        )
        
        # Generate the report
        report_service = get_report_service(db)
        result = report_service.generate_report(
            report_type=request.report_type,
            filters=request.filters,
            export_format=request.export_format,
            user_id=user_id,
            use_cache=True,
            enable_progress_tracking=True  # Background reports benefit from progress tracking
        )
        
        if result.success and result.data:
            # Apply data redaction if needed
            if user:
                result.data = security_service.apply_data_redaction(
                    result.data,
                    request.report_type,
                    user,
                    redaction_level="standard"
                )
            
            # Export the report to file format
            export_service = ReportExportService()
            exported_data = export_service.export_report(result.data, request.export_format)
            
            # Store the file
            if isinstance(exported_data, bytes):
                file_content = exported_data
            else:
                file_content = exported_data.encode('utf-8')
            
            file_path = history_service.store_report_file(
                report_history_id,
                file_content,
                request.export_format,
                f"{request.report_type}_report"
            )
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            record_count = len(result.data.data) if result.data else 0
            file_size_bytes = len(file_content)
            
            # Log successful background generation
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
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Log failed generation
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
            
            # Update status to failed
            history_service.update_report_status(
                report_history_id,
                ReportStatus.FAILED,
                error_message=result.error_message or "Report generation failed"
            )
        
    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Log exception
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
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Update status to failed
        try:
            history_service = ReportHistoryService(db)
            history_service.update_report_status(
                report_history_id,
                ReportStatus.FAILED,
                error_message=str(e)
            )
        except Exception as update_error:
            logger.error(f"Failed to update report status: {str(update_error)}")


# Performance Monitoring and Cache Management Endpoints

@router.get("/performance/cache/stats")
@require_feature("reporting")
async def get_cache_stats(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get cache performance statistics.
    
    Returns cache hit rates, memory usage, and other performance metrics.
    """
    try:
        report_service = get_report_service(db)
        stats = report_service.get_cache_stats()
        
        return {
            "cache_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache statistics: {str(e)}"
        )


@router.delete("/performance/cache")
@require_feature("reporting")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="Pattern to match for selective clearing"),
    report_type: Optional[str] = Query(None, description="Report type to clear cache for"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear cache entries based on criteria.
    
    Args:
        pattern: Optional pattern to match cache keys
        report_type: Optional report type to clear cache for
    """
    try:
        report_service = get_report_service(db)
        
        if report_type:
            from core.schemas.report import ReportType
            invalidated = report_service.invalidate_cache(report_type=ReportType(report_type))
        elif pattern:
            invalidated = report_service.invalidate_cache(pattern=pattern)
        else:
            invalidated = report_service.invalidate_cache()
        
        return {
            "message": "Cache cleared successfully",
            "entries_invalidated": invalidated,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.get("/performance/query/stats")
@require_feature("reporting")
async def get_query_performance_stats(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get query performance statistics.
    
    Returns query execution times, slow query counts, and optimization metrics.
    """
    try:
        report_service = get_report_service(db)
        stats = report_service.get_performance_stats()
        
        return {
            "query_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting query stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get query statistics: {str(e)}"
        )


@router.get("/performance/progress/stats")
@require_feature("reporting")
async def get_progress_stats(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get progress tracking statistics.
    
    Returns task counts, completion rates, and progress service metrics.
    """
    try:
        report_service = get_report_service(db)
        stats = report_service.get_progress_stats()
        
        return {
            "progress_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting progress stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get progress statistics: {str(e)}"
        )


@router.get("/tasks")
@require_feature("reporting")
async def get_user_tasks(
    active_only: bool = Query(False, description="Return only active tasks"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all tasks for the current user.
    
    Args:
        active_only: If True, only return active (running/pending) tasks
    """
    try:
        report_service = get_report_service(db)
        tasks = report_service.get_user_tasks(current_user.id, active_only)
        
        return {
            "tasks": tasks,
            "total": len(tasks),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting user tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user tasks: {str(e)}"
        )


@router.get("/tasks/{task_id}")
@require_feature("reporting")
async def get_task_progress(
    task_id: str,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get progress information for a specific task.
    
    Args:
        task_id: ID of the task to get progress for
    """
    try:
        report_service = get_report_service(db)
        progress = report_service.get_task_progress(task_id)
        
        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # Check if user owns this task
        if progress.get('user_id') != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this task"
            )
        
        return progress
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task progress: {str(e)}"
        )


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a running task.
    
    Args:
        task_id: ID of the task to cancel
    """
    try:
        report_service = get_report_service(db)
        
        # Check if task exists and user owns it
        progress = report_service.get_task_progress(task_id)
        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        if progress.get('user_id') != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this task"
            )
        
        # Cancel the task
        cancelled = report_service.cancel_task(task_id)
        
        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task could not be cancelled (may already be completed)"
            )
        
        return {
            "message": "Task cancelled successfully",
            "task_id": task_id,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )


@router.get("/optimization/recommendations")
async def get_optimization_recommendations(
    report_type: str = Query(..., description="Type of report to analyze"),
    date_from: Optional[datetime] = Query(None, description="Start date filter"),
    date_to: Optional[datetime] = Query(None, description="End date filter"),
    client_ids: Optional[List[int]] = Query(None, description="Client IDs filter"),
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get optimization recommendations for a report configuration.
    
    Args:
        report_type: Type of report to analyze
        date_from: Optional start date filter
        date_to: Optional end date filter
        client_ids: Optional client IDs filter
    """
    try:
        from core.schemas.report import ReportType
        
        # Build filters dictionary
        filters = {}
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        if client_ids:
            filters['client_ids'] = client_ids
        
        report_service = get_report_service(db)
        recommendations = report_service.get_optimization_recommendations(
            ReportType(report_type), filters
        )
        
        return {
            "recommendations": recommendations,
            "report_type": report_type,
            "filters_analyzed": filters,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting optimization recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get optimization recommendations: {str(e)}"
        )