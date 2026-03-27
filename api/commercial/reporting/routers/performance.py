"""
Performance monitoring and task management endpoints.

  GET    /performance/cache/stats          — cache hit rates and memory usage
  DELETE /performance/cache                — clear cache entries
  GET    /performance/query/stats          — query execution metrics
  GET    /performance/progress/stats       — progress tracking metrics
  GET    /tasks                            — list user tasks
  GET    /tasks/{task_id}                  — get task progress
  DELETE /tasks/{task_id}                  — cancel a running task
  GET    /optimization/recommendations     — query optimisation hints
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.utils.feature_gate import require_feature
from core.routers.auth import get_current_user

from ._shared import get_report_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/performance/cache/stats")
@require_feature("reporting")
async def get_cache_stats(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get cache performance statistics."""
    try:
        report_service = get_report_service(db)
        stats = report_service.get_cache_stats()

        return {"cache_stats": stats, "timestamp": datetime.now().isoformat()}

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
    """Clear cache entries based on criteria."""
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
    """Get query performance statistics."""
    try:
        report_service = get_report_service(db)
        stats = report_service.get_performance_stats()

        return {"query_stats": stats, "timestamp": datetime.now().isoformat()}

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
    """Get progress tracking statistics."""
    try:
        report_service = get_report_service(db)
        stats = report_service.get_progress_stats()

        return {"progress_stats": stats, "timestamp": datetime.now().isoformat()}

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
    """Get all tasks for the current user."""
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
    """Get progress information for a specific task."""
    try:
        report_service = get_report_service(db)
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
    """Cancel a running task."""
    try:
        report_service = get_report_service(db)

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
    """Get optimization recommendations for a report configuration."""
    try:
        from core.schemas.report import ReportType

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
