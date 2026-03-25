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
        # AND filter by method=GET to avoid counting API actions as page views
        # AND exclude noisy background paths
        # Helper function to apply common filters
        def apply_analytics_filters(q):
            # 1. Tenant and Method filter
            q = q.filter(
                PageView.timestamp >= start_date,
                PageView.tenant_id == current_tenant_id,
                PageView.method == 'GET'
            )
            
            # 2. Exclude specific noisy paths (and their sub-paths)
            noisy_prefixes = [
                '/api/v1/settings',                      # catches /settings, /settings/, /settings/sub
                '/api/v1/ai-config',                     # catches /ai-config, /ai-config/
                '/api/v1/reminders/unread-count',
                '/api/v1/reminders/notifications',       # covers /recent and /unread-count (polls every 30-60s)
                '/api/v1/invoices/status',
                '/api/v1/clients/status',
                '/api/v1/expenses/status',
                '/api/v1/organization-join/pending',     # admin polling every 60s
                '/api/v1/email-integration/sync/status', # polls every 2s during sync
                '/api/v1/bank-statements/',              # status polling during processing (contains IDs)
            ]
            for prefix in noisy_prefixes:
                q = q.filter(~PageView.path.startswith(prefix))

            # 3. Exclude broad patterns
            q = q.filter(~PageView.path.contains('/unread-count'))
            q = q.filter(~PageView.path.endswith('/status'))
            
            return q

        # Apply filters to all queries
        query = apply_analytics_filters(master_db.query(PageView))
        
        if path_filter:
            query = query.filter(PageView.path.contains(path_filter))
        
        # Get page views by path
        path_query = apply_analytics_filters(master_db.query(
            PageView.path,
            func.count(PageView.id).label('views'),
            func.avg(PageView.response_time_ms).label('avg_response_time')
        ))
        path_stats = path_query.group_by(PageView.path).order_by(desc('views')).limit(20).all()
        
        # Get daily views
        daily_query = apply_analytics_filters(master_db.query(
            func.date(PageView.timestamp).label('date'),
            func.count(PageView.id).label('views')
        ))
        daily_stats = daily_query.group_by(func.date(PageView.timestamp)).order_by('date').all()
        
        # Get user activity
        user_query = apply_analytics_filters(master_db.query(
            PageView.user_email,
            func.count(PageView.id).label('views')
        ))
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