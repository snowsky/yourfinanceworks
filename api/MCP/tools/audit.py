"""
Audit log and analytics-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GetAuditLogsArgs(BaseModel):
    user_id: Optional[int] = Field(default=None, description="Filter by user ID")
    user_email: Optional[str] = Field(default=None, description="Filter by user email")
    action: Optional[str] = Field(default=None, description="Filter by action")
    resource_type: Optional[str] = Field(default=None, description="Filter by resource type")
    resource_id: Optional[str] = Field(default=None, description="Filter by resource ID")
    status: Optional[str] = Field(default=None, description="Filter by status")
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)")
    limit: int = Field(default=100, description="Maximum number of results")
    offset: int = Field(default=0, description="Number of results to skip")


class GetPageViewsAnalyticsArgs(BaseModel):
    days: int = Field(default=7, description="Number of days to look back")
    path_filter: Optional[str] = Field(default=None, description="Filter by path")


class AuditToolsMixin:
    # Analytics Tools
    async def get_page_views_analytics(self, days: int = 7, path_filter: Optional[str] = None) -> Dict[str, Any]:
        """Get page view analytics"""
        try:
            analytics = await self.api_client.get_page_views_analytics(days=days, path_filter=path_filter)
            return {
                "success": True,
                "data": analytics,
                "message": f"Analytics for the past {days} days"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get analytics: {e}"}

    # Audit Log Tools
    async def get_audit_logs(
        self,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get audit logs with optional filters"""
        # Validate pagination parameters
        if offset < 0:
            offset = 0
        if limit < 1:
            limit = 100
        if limit > 10000:  # Prevent excessive load
            limit = 10000

        try:
            logs = await self.api_client.get_audit_logs(
                user_id=user_id,
                user_email=user_email,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                status=status,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )
            return {
                "success": True,
                "data": logs,
                "message": f"Found audit logs"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get audit logs: {e}"}
