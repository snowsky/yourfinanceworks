"""
Shared helpers for reporting routers.
"""

import logging
import traceback
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from core.models.database import get_db
from core.models.models import MasterUser
from core.utils.feature_gate import require_feature
from core.services.report_service import ReportService
from core.services.report_template_service import ReportTemplateService
from core.services.scheduled_report_service import ScheduledReportService
from core.services.report_history_service import ReportHistoryService, ReportHistoryError
from core.services.report_cache_service import CacheConfig, CacheStrategy
from core.services.report_query_optimizer import OptimizationConfig
from core.services.report_exporter import ReportExportService, ExportError
from core.services.report_audit_service import ReportAuditService, extract_request_info
from core.services.report_security_service import ReportSecurityService, ReportRateLimiter
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer, require_admin
from core.utils.audit import log_audit_event
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
from config import get_settings

logger = logging.getLogger(__name__)


def get_report_service(db: Session) -> ReportService:
    settings = get_settings()

    cache_config = CacheConfig(
        strategy=CacheStrategy.REDIS_ONLY if settings.REDIS_URL else CacheStrategy.MEMORY_ONLY,
        default_ttl=settings.CACHE_DEFAULT_TTL,
        max_memory_size=settings.CACHE_MAX_MEMORY_SIZE,
        redis_url=settings.REDIS_URL,
        enable_compression=True
    )

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


def get_current_non_viewer_user(current_user=Depends(get_current_user)):
    require_non_viewer(current_user, "access reports")
    return current_user


def handle_report_exception(e: BaseReportException) -> HTTPException:
    error_dict = e.to_dict()

    status_code_mapping = {
        ReportErrorCode.REPORT_INVALID_TYPE: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.REPORT_INVALID_FILTERS: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_DATE_RANGE_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_FILTER_MISSING: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_FILTER_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_CLIENT_NOT_FOUND: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_AMOUNT_RANGE_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_CURRENCY_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.VALIDATION_EXPORT_FORMAT_INVALID: status.HTTP_400_BAD_REQUEST,
        ReportErrorCode.REPORT_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
        ReportErrorCode.TEMPLATE_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
        ReportErrorCode.SCHEDULE_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
        ReportErrorCode.DATA_INSUFFICIENT_PERMISSIONS: status.HTTP_403_FORBIDDEN,
        ReportErrorCode.REPORT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ReportErrorCode.TEMPLATE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ReportErrorCode.SCHEDULE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ReportErrorCode.TEMPLATE_NAME_EXISTS: status.HTTP_409_CONFLICT,
        ReportErrorCode.REPORT_DATA_TOO_LARGE: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        ReportErrorCode.EXPORT_FILE_TOO_LARGE: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        ReportErrorCode.EXPORT_FORMAT_UNSUPPORTED: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        ReportErrorCode.REPORT_TIMEOUT: status.HTTP_408_REQUEST_TIMEOUT,
        ReportErrorCode.DATA_CONNECTION_FAILED: status.HTTP_503_SERVICE_UNAVAILABLE,
    }

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
