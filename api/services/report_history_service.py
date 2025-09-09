"""
Report History Service

This service manages report generation history, file storage, and cleanup operations.
Provides secure access control and automatic cleanup of expired reports.
"""

import os
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.models_per_tenant import ReportHistory, ReportTemplate
from schemas.report import (
    ReportHistoryCreate, ReportHistory as ReportHistorySchema,
    ReportStatus, ExportFormat
)


class ReportHistoryError(Exception):
    """Custom exception for report history operations"""
    pass


class ReportHistoryService:
    """
    Service for managing report generation history and file operations.
    
    Handles:
    - Report history tracking
    - Secure file storage and retrieval
    - Access control for report downloads
    - Automatic cleanup of expired reports
    """
    
    def __init__(self, db: Session, storage_path: str = "reports"):
        self.db = db
        self.storage_path = storage_path
        self._ensure_storage_directory()
    
    def _ensure_storage_directory(self) -> None:
        """Ensure the storage directory exists"""
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)
    
    def create_report_history(
        self,
        report_type: str,
        parameters: Dict[str, Any],
        user_id: int,
        template_id: Optional[int] = None,
        expires_in_days: int = 30
    ) -> ReportHistory:
        """
        Create a new report history entry.
        
        Args:
            report_type: Type of report being generated
            parameters: Report generation parameters
            user_id: ID of user generating the report
            template_id: Optional template ID used
            expires_in_days: Number of days until report expires
            
        Returns:
            Created ReportHistory instance
        """
        try:
            expires_at = datetime.now() + timedelta(days=expires_in_days)
            
            report_history = ReportHistory(
                report_type=report_type,
                parameters=parameters,
                status=ReportStatus.PENDING,
                generated_by=user_id,
                template_id=template_id,
                expires_at=expires_at
            )
            
            self.db.add(report_history)
            self.db.commit()
            self.db.refresh(report_history)
            
            return report_history
            
        except Exception as e:
            self.db.rollback()
            raise ReportHistoryError(f"Failed to create report history: {str(e)}")
    
    def update_report_status(
        self,
        report_id: int,
        status: ReportStatus,
        file_path: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> ReportHistory:
        """
        Update the status of a report generation.
        
        Args:
            report_id: ID of the report history entry
            status: New status
            file_path: Path to generated file (if completed)
            error_message: Error message (if failed)
            
        Returns:
            Updated ReportHistory instance
        """
        try:
            report = self.db.query(ReportHistory).filter(
                ReportHistory.id == report_id
            ).first()
            
            if not report:
                raise ReportHistoryError(f"Report history not found: {report_id}")
            
            report.status = status
            if file_path:
                report.file_path = file_path
            if error_message:
                report.error_message = error_message
            
            self.db.commit()
            self.db.refresh(report)
            
            return report
            
        except Exception as e:
            self.db.rollback()
            raise ReportHistoryError(f"Failed to update report status: {str(e)}")
    
    def get_report_history(
        self,
        report_id: int,
        user_id: int
    ) -> Optional[ReportHistory]:
        """
        Get a specific report history entry with access control.
        
        Args:
            report_id: ID of the report
            user_id: ID of the requesting user
            
        Returns:
            ReportHistory instance if found and accessible, None otherwise
        """
        return self.db.query(ReportHistory).filter(
            and_(
                ReportHistory.id == report_id,
                ReportHistory.generated_by == user_id
            )
        ).first()
    
    def list_user_reports(
        self,
        user_id: int,
        report_type: Optional[str] = None,
        status: Optional[ReportStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ReportHistory]:
        """
        List report history for a specific user with optional filtering.
        
        Args:
            user_id: ID of the user
            report_type: Optional report type filter
            status: Optional status filter
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of ReportHistory instances
        """
        query = self.db.query(ReportHistory).filter(
            ReportHistory.generated_by == user_id
        )
        
        if report_type:
            query = query.filter(ReportHistory.report_type == report_type)
        
        if status:
            query = query.filter(ReportHistory.status == status)
        
        return query.order_by(
            ReportHistory.generated_at.desc()
        ).offset(offset).limit(limit).all()
    
    def count_user_reports(
        self,
        user_id: int,
        report_type: Optional[str] = None,
        status: Optional[ReportStatus] = None
    ) -> int:
        """
        Count report history entries for a user with optional filtering.
        
        Args:
            user_id: ID of the user
            report_type: Optional report type filter
            status: Optional status filter
            
        Returns:
            Number of matching reports
        """
        query = self.db.query(ReportHistory).filter(
            ReportHistory.generated_by == user_id
        )
        
        if report_type:
            query = query.filter(ReportHistory.report_type == report_type)
        
        if status:
            query = query.filter(ReportHistory.status == status)
        
        return query.count()
    
    def store_report_file(
        self,
        report_id: int,
        file_content: bytes,
        export_format: ExportFormat,
        filename_prefix: Optional[str] = None
    ) -> str:
        """
        Store a generated report file securely.
        
        Args:
            report_id: ID of the report history entry
            file_content: Binary content of the report file
            export_format: Format of the report file
            filename_prefix: Optional prefix for the filename
            
        Returns:
            Path to the stored file
        """
        try:
            # Generate secure filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = filename_prefix or "report"
            extension = self._get_file_extension(export_format)
            filename = f"{prefix}_{report_id}_{timestamp}.{extension}"
            
            # Create user-specific subdirectory for better organization
            user_dir = os.path.join(self.storage_path, str(report_id // 1000))
            os.makedirs(user_dir, exist_ok=True)
            
            file_path = os.path.join(user_dir, filename)
            
            # Write file content
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Update report history with file path
            self.update_report_status(
                report_id=report_id,
                status=ReportStatus.COMPLETED,
                file_path=file_path
            )
            
            return file_path
            
        except Exception as e:
            raise ReportHistoryError(f"Failed to store report file: {str(e)}")
    
    def get_report_file_path(
        self,
        report_id: int,
        user_id: int
    ) -> Optional[str]:
        """
        Get the file path for a report with access control.
        
        Args:
            report_id: ID of the report
            user_id: ID of the requesting user
            
        Returns:
            File path if accessible, None otherwise
        """
        report = self.get_report_history(report_id, user_id)
        
        if not report:
            return None
        
        if report.status != ReportStatus.COMPLETED:
            return None
        
        if not report.file_path or not os.path.exists(report.file_path):
            return None
        
        # Check if report has expired
        if report.expires_at and datetime.now() > report.expires_at:
            return None
        
        return report.file_path
    
    def delete_report_file(self, report_id: int, user_id: int) -> bool:
        """
        Delete a report file with access control.
        
        Args:
            report_id: ID of the report
            user_id: ID of the requesting user
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            report = self.get_report_history(report_id, user_id)
            
            if not report or not report.file_path:
                return False
            
            # Delete the physical file
            if os.path.exists(report.file_path):
                os.remove(report.file_path)
            
            # Clear file path from database
            report.file_path = None
            self.db.commit()
            
            return True
            
        except Exception as e:
            self.db.rollback()
            raise ReportHistoryError(f"Failed to delete report file: {str(e)}")
    
    def cleanup_expired_reports(self) -> Dict[str, int]:
        """
        Clean up expired report files and update database records.
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            now = datetime.now()
            
            # Find expired reports
            expired_reports = self.db.query(ReportHistory).filter(
                and_(
                    ReportHistory.expires_at < now,
                    ReportHistory.file_path.isnot(None)
                )
            ).all()
            
            files_deleted = 0
            records_updated = 0
            errors = 0
            
            for report in expired_reports:
                try:
                    # Delete physical file if it exists
                    if report.file_path and os.path.exists(report.file_path):
                        os.remove(report.file_path)
                        files_deleted += 1
                    
                    # Clear file path from database
                    report.file_path = None
                    records_updated += 1
                    
                except Exception as e:
                    errors += 1
                    # Log error but continue with other files
                    print(f"Error cleaning up report {report.id}: {str(e)}")
            
            self.db.commit()
            
            return {
                "expired_reports_found": len(expired_reports),
                "files_deleted": files_deleted,
                "records_updated": records_updated,
                "errors": errors
            }
            
        except Exception as e:
            self.db.rollback()
            raise ReportHistoryError(f"Failed to cleanup expired reports: {str(e)}")
    
    def cleanup_orphaned_files(self) -> Dict[str, int]:
        """
        Clean up orphaned report files that no longer have database records.
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            if not os.path.exists(self.storage_path):
                return {"files_deleted": 0, "errors": 0}
            
            files_deleted = 0
            errors = 0
            
            # Get all file paths from database
            db_file_paths = set()
            reports_with_files = self.db.query(ReportHistory).filter(
                ReportHistory.file_path.isnot(None)
            ).all()
            
            for report in reports_with_files:
                if report.file_path:
                    db_file_paths.add(os.path.abspath(report.file_path))
            
            # Walk through storage directory
            for root, dirs, files in os.walk(self.storage_path):
                for file in files:
                    file_path = os.path.abspath(os.path.join(root, file))
                    
                    # Skip if file is referenced in database
                    if file_path in db_file_paths:
                        continue
                    
                    # Skip if file is not a report file (basic check)
                    if not any(file.startswith(prefix) for prefix in ["report_", "client_", "invoice_", "payment_", "expense_", "statement_"]):
                        continue
                    
                    try:
                        os.remove(file_path)
                        files_deleted += 1
                    except Exception as e:
                        errors += 1
                        print(f"Error deleting orphaned file {file_path}: {str(e)}")
            
            return {
                "files_deleted": files_deleted,
                "errors": errors
            }
            
        except Exception as e:
            raise ReportHistoryError(f"Failed to cleanup orphaned files: {str(e)}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about report file storage.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            stats = {
                "total_reports": 0,
                "reports_with_files": 0,
                "total_file_size": 0,
                "expired_reports": 0,
                "storage_path": self.storage_path
            }
            
            # Database statistics
            stats["total_reports"] = self.db.query(ReportHistory).count()
            stats["reports_with_files"] = self.db.query(ReportHistory).filter(
                ReportHistory.file_path.isnot(None)
            ).count()
            
            # Count expired reports
            now = datetime.now()
            stats["expired_reports"] = self.db.query(ReportHistory).filter(
                ReportHistory.expires_at < now
            ).count()
            
            # File system statistics
            if os.path.exists(self.storage_path):
                total_size = 0
                for root, dirs, files in os.walk(self.storage_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            total_size += os.path.getsize(file_path)
                        except OSError:
                            pass  # Skip files that can't be accessed
                
                stats["total_file_size"] = total_size
                stats["total_file_size_mb"] = round(total_size / (1024 * 1024), 2)
            
            return stats
            
        except Exception as e:
            raise ReportHistoryError(f"Failed to get storage stats: {str(e)}")
    
    def _get_file_extension(self, export_format: ExportFormat) -> str:
        """Get file extension for export format"""
        extension_map = {
            ExportFormat.PDF: "pdf",
            ExportFormat.CSV: "csv",
            ExportFormat.EXCEL: "xlsx",
            ExportFormat.JSON: "json"
        }
        return extension_map.get(export_format, "bin")
    
    def regenerate_report(
        self,
        report_id: int,
        user_id: int,
        new_parameters: Optional[Dict[str, Any]] = None
    ) -> ReportHistory:
        """
        Create a new report history entry based on an existing one.
        
        Args:
            report_id: ID of the original report
            user_id: ID of the requesting user
            new_parameters: Optional new parameters to override
            
        Returns:
            New ReportHistory instance
        """
        try:
            original_report = self.get_report_history(report_id, user_id)
            
            if not original_report:
                raise ReportHistoryError("Original report not found or access denied")
            
            # Merge parameters
            parameters = original_report.parameters.copy()
            if new_parameters:
                parameters.update(new_parameters)
            
            # Create new report history entry
            new_report = self.create_report_history(
                report_type=original_report.report_type,
                parameters=parameters,
                user_id=user_id,
                template_id=original_report.template_id
            )
            
            return new_report
            
        except Exception as e:
            raise ReportHistoryError(f"Failed to regenerate report: {str(e)}")