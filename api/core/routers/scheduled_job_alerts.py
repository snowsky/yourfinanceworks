"""
Scheduled Job Alert management endpoints.

  GET    /alerts                          — list alerts for user
  POST   /alerts                          — create alert
  GET    /alerts/{alert_id}               — get alert details
  PUT    /alerts/{alert_id}               — update alert
  DELETE /alerts/{alert_id}               — delete alert
  GET    /alerts/{alert_id}/history       — get alert trigger history
"""

import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.utils.audit import log_audit_event
from core.services.scheduled_job_alerting_service import ScheduledJobAlertingService
from core.schemas.scheduled_job_alerts import (
    ScheduledJobAlertCreate,
    ScheduledJobAlertUpdate,
    ScheduledJobAlertResponse,
    ScheduledJobAlertListResponse,
    ScheduledJobAlertHistoryResponse,
    ScheduledJobAlertHistoryListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-job-alerts", tags=["scheduled-job-alerts"])


def _get_alerting_service(db: Session) -> ScheduledJobAlertingService:
    return ScheduledJobAlertingService(db)


@router.get("", response_model=ScheduledJobAlertListResponse)
async def list_alerts(
    scheduled_report_id: int = Query(None, description="Filter by scheduled report ID"),
    active_only: bool = Query(False, description="Show only active alerts"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """List all alerts for the current user."""
    try:
        service = _get_alerting_service(db)
        alerts = service.list_alerts(
            user_id=current_user.id,
            scheduled_report_id=scheduled_report_id,
            active_only=active_only,
        )
        return ScheduledJobAlertListResponse(
            alerts=[ScheduledJobAlertResponse.model_validate(a) for a in alerts],
            total=len(alerts),
        )
    except Exception as e:
        logger.error(f"Failed to list alerts: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts",
        )


@router.post("", response_model=ScheduledJobAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_data: ScheduledJobAlertCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Create a new alert for a scheduled report."""
    try:
        service = _get_alerting_service(db)
        alert = service.create_alert(alert_data, user_id=current_user.id)

        await log_audit_event(
            db,
            current_user.id,
            "scheduled_job_alert_create",
            f"Created alert '{alert.name}' for schedule {alert.scheduled_report_id}",
            {"alert_id": alert.id, "scheduled_report_id": alert.scheduled_report_id},
        )

        return ScheduledJobAlertResponse.model_validate(alert)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create alert: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create alert",
        )


@router.get("/{alert_id}", response_model=ScheduledJobAlertResponse)
async def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get details of a specific alert."""
    try:
        service = _get_alerting_service(db)
        alert = service.get_alert(alert_id, user_id=current_user.id)
        return ScheduledJobAlertResponse.model_validate(alert)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get alert {alert_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert",
        )


@router.put("/{alert_id}", response_model=ScheduledJobAlertResponse)
async def update_alert(
    alert_id: int,
    alert_data: ScheduledJobAlertUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Update an existing alert."""
    try:
        service = _get_alerting_service(db)
        alert = service.update_alert(alert_id, alert_data, user_id=current_user.id)

        await log_audit_event(
            db,
            current_user.id,
            "scheduled_job_alert_update",
            f"Updated alert '{alert.name}'",
            {"alert_id": alert.id},
        )

        return ScheduledJobAlertResponse.model_validate(alert)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update alert {alert_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update alert",
        )


@router.delete("/{alert_id}", status_code=status.HTTP_200_OK)
async def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Delete an alert."""
    try:
        service = _get_alerting_service(db)
        service.delete_alert(alert_id, user_id=current_user.id)

        await log_audit_event(
            db,
            current_user.id,
            "scheduled_job_alert_delete",
            f"Deleted alert {alert_id}",
            {"alert_id": alert_id},
        )

        return {"message": "Alert deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete alert {alert_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete alert",
        )


@router.get("/{alert_id}/history", response_model=ScheduledJobAlertHistoryListResponse)
async def get_alert_history(
    alert_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get the trigger history for a specific alert."""
    try:
        service = _get_alerting_service(db)
        history = service.get_alert_history(alert_id, user_id=current_user.id, limit=limit)
        return ScheduledJobAlertHistoryListResponse(
            history=[ScheduledJobAlertHistoryResponse.model_validate(h) for h in history],
            total=len(history),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get alert history: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert history",
        )
