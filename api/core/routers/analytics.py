from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from core.models.database import get_master_db, get_tenant_context
from core.models.analytics import PageView
from .auth import get_current_user
from core.models.models import MasterUser
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/page-views")
async def get_page_views(
    days: int = Query(7, description="Number of days to look back"),
    path_filter: Optional[str] = Query(None, description="Filter by path"),
    current_user: MasterUser = Depends(get_current_user),
    master_db: Session = Depends(get_master_db)
):
    """Get page view analytics for the current user's tenant"""
    if not (current_user.is_superuser or current_user.role == 'admin'):
        raise HTTPException(status_code=403, detail="Only super users and admins can access analytics")
    
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get current tenant context - use context if available, otherwise use user's primary tenant
        current_tenant_id = get_tenant_context() or current_user.tenant_id
        
        # Filter by tenant - all users should see data for their current tenant context
        query = master_db.query(PageView).filter(
            PageView.timestamp >= start_date,
            PageView.tenant_id == current_tenant_id
        )
        
        if path_filter:
            query = query.filter(PageView.path.contains(path_filter))
        
        # Get page views by path
        path_query = master_db.query(
            PageView.path,
            func.count(PageView.id).label('views'),
            func.avg(PageView.response_time_ms).label('avg_response_time')
        ).filter(
            PageView.timestamp >= start_date,
            PageView.tenant_id == current_tenant_id
        )
        path_stats = path_query.group_by(PageView.path).order_by(desc('views')).limit(20).all()
        
        # Get daily views
        daily_query = master_db.query(
            func.date(PageView.timestamp).label('date'),
            func.count(PageView.id).label('views')
        ).filter(
            PageView.timestamp >= start_date,
            PageView.tenant_id == current_tenant_id
        )
        daily_stats = daily_query.group_by(func.date(PageView.timestamp)).order_by('date').all()
        
        # Get user activity
        user_query = master_db.query(
            PageView.user_email,
            func.count(PageView.id).label('views')
        ).filter(
            PageView.timestamp >= start_date,
            PageView.tenant_id == current_tenant_id
        )
        user_stats = user_query.group_by(PageView.user_email).order_by(desc('views')).limit(10).all()
        
        return {
            "path_stats": [{"path": p.path, "views": p.views, "avg_response_time": round(p.avg_response_time or 0, 2)} for p in path_stats],
            "daily_stats": [{"date": str(d.date), "views": d.views} for d in daily_stats],
            "user_stats": [{"user": u.user_email, "views": u.views} for u in user_stats],
            "total_views": sum(d.views for d in daily_stats)
        }
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics data")