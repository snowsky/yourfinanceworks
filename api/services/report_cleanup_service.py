"""
Report Cleanup Background Service

This service handles automatic cleanup of expired reports and orphaned files.
Can be run as a scheduled background task or cron job.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Dict, Any

from models.database import get_db
from models.models_per_tenant import ReportHistory
from services.report_history_service import ReportHistoryService, ReportHistoryError


logger = logging.getLogger(__name__)


class ReportCleanupService:
    """
    Service for automatic cleanup of report files and history.
    
    Handles:
    - Automatic cleanup of expired reports
    - Cleanup of orphaned files
    - Logging and monitoring of cleanup operations
    """
    
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
        self.history_service = ReportHistoryService(self.db)
    
    def run_daily_cleanup(self) -> Dict[str, Any]:
        """
        Run daily cleanup operations.
        
        Returns:
            Dictionary with cleanup statistics
        """
        logger.info("Starting daily report cleanup")
        
        cleanup_stats = {
            "started_at": datetime.now(),
            "expired_cleanup": {},
            "orphaned_cleanup": {},
            "errors": []
        }
        
        try:
            # Clean up expired reports
            logger.info("Cleaning up expired reports")
            expired_stats = self.history_service.cleanup_expired_reports()
            cleanup_stats["expired_cleanup"] = expired_stats
            logger.info(f"Expired cleanup completed: {expired_stats}")
            
        except ReportHistoryError as e:
            error_msg = f"Failed to cleanup expired reports: {str(e)}"
            logger.error(error_msg)
            cleanup_stats["errors"].append(error_msg)
        
        try:
            # Clean up orphaned files
            logger.info("Cleaning up orphaned files")
            orphaned_stats = self.history_service.cleanup_orphaned_files()
            cleanup_stats["orphaned_cleanup"] = orphaned_stats
            logger.info(f"Orphaned cleanup completed: {orphaned_stats}")
            
        except ReportHistoryError as e:
            error_msg = f"Failed to cleanup orphaned files: {str(e)}"
            logger.error(error_msg)
            cleanup_stats["errors"].append(error_msg)
        
        cleanup_stats["completed_at"] = datetime.now()
        cleanup_stats["duration_seconds"] = (
            cleanup_stats["completed_at"] - cleanup_stats["started_at"]
        ).total_seconds()
        
        logger.info(f"Daily cleanup completed in {cleanup_stats['duration_seconds']} seconds")
        
        return cleanup_stats
    
    def run_weekly_cleanup(self) -> Dict[str, Any]:
        """
        Run weekly cleanup operations (more thorough).
        
        Returns:
            Dictionary with cleanup statistics
        """
        logger.info("Starting weekly report cleanup")
        
        # Run daily cleanup first
        cleanup_stats = self.run_daily_cleanup()
        
        try:
            # Get storage statistics for monitoring
            storage_stats = self.history_service.get_storage_stats()
            cleanup_stats["storage_stats"] = storage_stats
            logger.info(f"Storage stats: {storage_stats}")
            
            # Log warnings if storage is getting large
            if storage_stats.get("total_file_size_mb", 0) > 1000:  # 1GB
                logger.warning(f"Report storage is large: {storage_stats['total_file_size_mb']} MB")
            
            if storage_stats.get("expired_reports", 0) > 100:
                logger.warning(f"Many expired reports found: {storage_stats['expired_reports']}")
            
        except Exception as e:
            error_msg = f"Failed to get storage stats: {str(e)}"
            logger.error(error_msg)
            cleanup_stats["errors"].append(error_msg)
        
        return cleanup_stats
    
    def cleanup_old_history_records(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        Clean up old report history records (keeping files but removing DB records).
        
        Args:
            days_to_keep: Number of days of history to keep
            
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Find old records without files
            old_records = self.db.query(ReportHistory).filter(
                and_(
                    ReportHistory.generated_at < cutoff_date,
                    ReportHistory.file_path.is_(None)
                )
            ).all()
            
            records_deleted = 0
            for record in old_records:
                try:
                    self.db.delete(record)
                    records_deleted += 1
                except Exception as e:
                    logger.error(f"Failed to delete history record {record.id}: {str(e)}")
            
            self.db.commit()
            
            logger.info(f"Deleted {records_deleted} old history records")
            
            return {
                "records_found": len(old_records),
                "records_deleted": records_deleted,
                "cutoff_date": cutoff_date
            }
            
        except Exception as e:
            self.db.rollback()
            raise ReportHistoryError(f"Failed to cleanup old history records: {str(e)}")
    
    def get_cleanup_recommendations(self) -> Dict[str, Any]:
        """
        Get recommendations for cleanup operations.
        
        Returns:
            Dictionary with recommendations
        """
        try:
            storage_stats = self.history_service.get_storage_stats()
            
            recommendations = {
                "storage_stats": storage_stats,
                "recommendations": []
            }
            
            # Check for expired reports
            if storage_stats.get("expired_reports", 0) > 0:
                recommendations["recommendations"].append({
                    "type": "expired_reports",
                    "message": f"Found {storage_stats['expired_reports']} expired reports that can be cleaned up",
                    "action": "Run expired reports cleanup"
                })
            
            # Check for large storage usage
            storage_mb = storage_stats.get("total_file_size_mb", 0)
            if storage_mb > 500:  # 500MB
                recommendations["recommendations"].append({
                    "type": "large_storage",
                    "message": f"Report storage is using {storage_mb} MB of disk space",
                    "action": "Consider reducing report retention period or running cleanup"
                })
            
            # Check for many reports without files
            total_reports = storage_stats.get("total_reports", 0)
            reports_with_files = storage_stats.get("reports_with_files", 0)
            reports_without_files = total_reports - reports_with_files
            
            if reports_without_files > 100:
                recommendations["recommendations"].append({
                    "type": "old_records",
                    "message": f"Found {reports_without_files} history records without files",
                    "action": "Consider cleaning up old history records"
                })
            
            return recommendations
            
        except Exception as e:
            raise ReportHistoryError(f"Failed to get cleanup recommendations: {str(e)}")


# Standalone function for use in cron jobs or background tasks
def run_scheduled_cleanup():
    """
    Standalone function to run scheduled cleanup.
    Can be called from cron jobs or background task schedulers.
    """
    try:
        db = next(get_db())
        cleanup_service = ReportCleanupService(db)
        
        # Run daily cleanup
        stats = cleanup_service.run_daily_cleanup()
        
        # Log summary
        logger.info(f"Scheduled cleanup completed: {stats}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Scheduled cleanup failed: {str(e)}")
        raise
    finally:
        if 'db' in locals():
            db.close()


# Function for weekly cleanup
def run_weekly_cleanup():
    """
    Standalone function to run weekly cleanup.
    """
    try:
        db = next(get_db())
        cleanup_service = ReportCleanupService(db)
        
        # Run weekly cleanup
        stats = cleanup_service.run_weekly_cleanup()
        
        # Log summary
        logger.info(f"Weekly cleanup completed: {stats}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Weekly cleanup failed: {str(e)}")
        raise
    finally:
        if 'db' in locals():
            db.close()