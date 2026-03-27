"""
Report history, download, and admin cleanup endpoints.

  GET    /history              — list report generation history
  GET    /download/{report_id} — download a generated report file
  DELETE /history/{report_id}  — delete a report file
  GET    /storage/stats        — admin: storage usage stats
  POST   /cleanup/expired      — admin: purge expired reports
  POST   /cleanup/orphaned     — admin: purge orphaned files
"""

import os
import mimetypes
import traceback
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.utils.feature_gate import require_feature
from core.services.report_history_service import ReportHistoryService, ReportHistoryError
from core.services.report_audit_service import ReportAuditService, extract_request_info
from core.services.report_security_service import ReportSecurityService
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer, require_admin
from core.utils.audit import log_audit_event
from core.schemas.report import (
    ReportType, ReportStatus, ReportHistory as ReportHistorySchema, ReportHistoryListResponse
)
from core.constants.error_codes import FAILED_TO_FETCH_REPORTS

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/history", response_model=ReportHistoryListResponse)
@require_feature("reporting")
async def get_report_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    report_type: ReportType = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get user's report generation history."""
    try:
        history_service = ReportHistoryService(db)

        reports = history_service.list_user_reports(
            user_id=current_user.id,
            report_type=report_type,
            status=ReportStatus(status) if status else None,
            limit=limit,
            offset=skip
        )

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
    """Download a generated report file."""
    security_service = ReportSecurityService(db)
    audit_service = ReportAuditService(db)
    history_service = ReportHistoryService(db)

    ip_address, user_agent = extract_request_info(http_request)

    try:
        security_service.validate_report_access(current_user, 'download')

        report = history_service.get_report_history(report_id, current_user.id)

        if not report:
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

        file_path = history_service.get_report_file_path(report_id, current_user.id)

        if not file_path:
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

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        filename = f"report_{report.id}_{report.report_type}_{report.generated_at.strftime('%Y%m%d_%H%M%S')}"
        if file_path.endswith('.pdf'):
            filename += '.pdf'
        elif file_path.endswith('.csv'):
            filename += '.csv'
        elif file_path.endswith('.xlsx'):
            filename += '.xlsx'

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        audit_service.log_report_download(
            user_id=current_user.id,
            user_email=current_user.email,
            report_id=str(report_id),
            report_type=report.report_type,
            export_format=report.parameters.get('export_format', 'unknown'),
            ip_address=ip_address,
            user_agent=user_agent
        )

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

        from core.utils.file_validation import validate_file_path
        validated_path = validate_file_path(file_path)

        return FileResponse(path=validated_path, filename=filename, media_type=content_type)

    except HTTPException:
        raise
    except Exception as e:
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


@router.delete("/history/{report_id}")
@require_feature("reporting")
async def delete_report_file(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(require_non_viewer)
):
    """Delete a report file and clear its file path from history."""
    try:
        history_service = ReportHistoryService(db)

        success = history_service.delete_report_file(report_id, current_user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found or already deleted"
            )

        await log_audit_event(
            db, current_user.id, "report_delete",
            "Deleted report file",
            {"report_id": report_id}
        )

        return {"message": "Report file deleted successfully"}

    except ReportHistoryError as e:
        logger.warning(f"Report deletion error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    """Get report storage statistics (admin only)."""
    try:
        history_service = ReportHistoryService(db)
        return history_service.get_storage_stats()

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
    """Clean up expired report files (admin only)."""
    try:
        history_service = ReportHistoryService(db)
        cleanup_stats = history_service.cleanup_expired_reports()

        await log_audit_event(
            db, current_user.id, "cleanup_expired",
            "Cleaned up expired reports",
            cleanup_stats
        )

        return {"message": "Expired reports cleanup completed", "stats": cleanup_stats}

    except ReportHistoryError as e:
        logger.warning(f"Cleanup error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    """Clean up orphaned report files with no database records (admin only)."""
    try:
        history_service = ReportHistoryService(db)
        cleanup_stats = history_service.cleanup_orphaned_files()

        await log_audit_event(
            db, current_user.id, "cleanup_orphaned",
            "Cleaned up orphaned files",
            cleanup_stats
        )

        return {"message": "Orphaned files cleanup completed", "stats": cleanup_stats}

    except ReportHistoryError as e:
        logger.warning(f"Cleanup error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned files: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup orphaned files"
        )
