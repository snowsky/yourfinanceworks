import asyncio
from datetime import datetime, timezone
import os
from concurrent.futures import ThreadPoolExecutor
from core.models.database import get_master_db
from core.models.analytics import PageView
from core.services.external_analytics import external_analytics
import logging

logger = logging.getLogger(__name__)

# Thread pool for blocking database operations
_analytics_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analytics_")

class AnalyticsService:
    @staticmethod
    def track_page_view(user_email: str, tenant_id: int, path: str, method: str, 
                       user_agent: str, ip_address: str, response_time_ms: int, status_code: int):
        """Track page view asynchronously to avoid blocking requests"""
        try:
            # Run database operation in thread pool to avoid blocking the request
            # and to properly manage database connections
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                _analytics_executor,
                AnalyticsService._save_page_view_sync,
                user_email, tenant_id, path, method, user_agent, 
                ip_address, response_time_ms, status_code
            )
            
            # Send to external analytics services
            event_data = {
                "user_email": user_email,
                "tenant_id": tenant_id,
                "path": path,
                "method": method,
                "user_agent": user_agent,
                "ip_address": ip_address,
                "response_time_ms": response_time_ms,
                "status_code": status_code
            }
            try:
                asyncio.create_task(external_analytics.send_event(event_data))
            except Exception as e:
                logger.debug(f"Failed to send external analytics: {e}")
        except Exception as e:
            logger.debug(f"Failed to track page view: {e}")
    
    @staticmethod
    def _save_page_view_sync(user_email: str, tenant_id: int, path: str, method: str,
                            user_agent: str, ip_address: str, response_time_ms: int, status_code: int):
        """Save page view to database - runs in thread pool"""
        try:
            master_db = next(get_master_db())
            try:
                page_view = PageView(
                    user_email=user_email,
                    tenant_id=tenant_id,
                    path=path,
                    method=method,
                    user_agent=user_agent,
                    ip_address=ip_address,
                    response_time_ms=response_time_ms,
                    status_code=status_code,
                    timestamp=datetime.now(timezone.utc)
                )
                master_db.add(page_view)
                master_db.commit()
            finally:
                master_db.close()
        except Exception as e:
            logger.debug(f"Failed to save page view: {e}")

analytics_service = AnalyticsService()