"""
Scheduled report management endpoints.

  GET    /scheduled               — list scheduled reports
  POST   /scheduled               — create scheduled report
  PUT    /scheduled/{schedule_id} — update scheduled report
  DELETE /scheduled/{schedule_id} — delete scheduled report
"""

import traceback
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.utils.feature_gate import require_feature
from core.services.report_template_service import ReportTemplateService
from core.services.scheduled_report_service import ScheduledReportService
from core.routers.auth import get_current_user
from core.utils.audit import log_audit_event
from core.exceptions.report_exceptions import TemplateAccessError, ReportSchedulerError
from core.schemas.report import (
    ScheduledReportCreate, ScheduledReportUpdate,
    ScheduledReport as ScheduledReportSchema, ScheduledReportListResponse
)
from core.constants.error_codes import (
    FAILED_TO_CREATE_SCHEDULE, FAILED_TO_UPDATE_SCHEDULE, FAILED_TO_DELETE_SCHEDULE
)

from ._shared import get_current_non_viewer_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_scheduled_service(db: Session) -> ScheduledReportService:
    from core.services.report_scheduler import ReportScheduler
    return ScheduledReportService(db, ReportScheduler(db))


@router.get("/scheduled", response_model=ScheduledReportListResponse)
@require_feature("reporting")
async def get_scheduled_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get user's scheduled reports."""
    try:
        scheduled_service = _get_scheduled_service(db)
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
    current_user=Depends(get_current_non_viewer_user)
):
    """Create a new scheduled report."""
    try:
        template_service = ReportTemplateService(db)
        try:
            template = template_service.get_template(scheduled_report.template_id, current_user.id)
        except TemplateAccessError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report template not found or access denied"
            )

        scheduled_service = _get_scheduled_service(db)
        created_schedule = scheduled_service.create_scheduled_report(
            schedule_data=scheduled_report,
            user_id=current_user.id
        )

        await log_audit_event(
            db, current_user.id, "schedule_create",
            f"Created scheduled report for template: {template.name}",
            {"schedule_id": created_schedule.id, "template_id": scheduled_report.template_id}
        )

        return ScheduledReportSchema.model_validate(created_schedule)

    except ReportSchedulerError as e:
        logger.warning(f"Scheduling error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    current_user=Depends(get_current_non_viewer_user)
):
    """Update an existing scheduled report."""
    try:
        scheduled_service = _get_scheduled_service(db)

        updated_schedule = scheduled_service.update_scheduled_report(
            schedule_id=schedule_id,
            update_data=scheduled_report,
            user_id=current_user.id
        )

        await log_audit_event(
            db, current_user.id, "schedule_update",
            "Updated scheduled report",
            {"schedule_id": schedule_id}
        )

        return ScheduledReportSchema.model_validate(updated_schedule)

    except ReportSchedulerError as e:
        logger.warning(f"Scheduling update error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    current_user=Depends(get_current_non_viewer_user)
):
    """Delete a scheduled report."""
    try:
        scheduled_service = _get_scheduled_service(db)
        scheduled_service.delete_scheduled_report(schedule_id, current_user.id)

        await log_audit_event(
            db, current_user.id, "schedule_delete",
            "Deleted scheduled report",
            {"schedule_id": schedule_id}
        )

        return {"message": "Scheduled report deleted successfully"}

    except ReportSchedulerError as e:
        logger.warning(f"Scheduling deletion error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete scheduled report: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_DELETE_SCHEDULE
        )
