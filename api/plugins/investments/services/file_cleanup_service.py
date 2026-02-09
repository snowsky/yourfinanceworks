"""
File Cleanup Service

This module provides administrative tools for managing file attachments and storage.
It handles cleanup of old or failed import files, retention policies, and storage
management operations.

Features:
- Cleanup old or failed import files
- Retention policy enforcement
- Storage statistics and reporting
- Cascade deletion when portfolios are deleted
- Administrative cleanup tools
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ..models import FileAttachment, AttachmentStatus
from ..repositories.file_attachment_repository import FileAttachmentRepository
from .file_storage_service import FileStorageService

logger = logging.getLogger(__name__)


class FileCleanupService:
    """
    Service for managing file attachment cleanup and retention policies.

    Provides administrative tools for:
    - Cleaning up old or failed import files
    - Enforcing retention policies
    - Reporting storage statistics
    - Cascade deletion of attachments

    Requirements: 4.5, 14.1, 14.2, 14.3, 14.4, 14.5
    """

    def __init__(self, db: Session):
        """
        Initialize the file cleanup service.

        Args:
            db: Database session
        """
        self.db = db
        self.file_attachment_repo = FileAttachmentRepository(db)
        self.file_storage_service = FileStorageService(db)

    async def cleanup_failed_files(
        self,
        tenant_id: Optional[int] = None,
        days_old: int = 30,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean up failed import files older than specified days.

        Deletes file attachments with FAILED status that are older than the
        specified number of days, along with their associated files from storage.

        Args:
            tenant_id: Optional tenant ID to limit cleanup to specific tenant
            days_old: Minimum age in days for files to be cleaned up (default: 30)
            dry_run: If True, only report what would be deleted without deleting

        Returns:
            Dictionary with cleanup statistics:
            {
                "files_deleted": int,
                "files_skipped": int,
                "storage_freed_bytes": int,
                "errors": List[str]
            }

        Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
        """
        logger.info(f"Starting cleanup of failed files (dry_run={dry_run})")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        files_deleted = 0
        files_skipped = 0
        storage_freed = 0
        errors = []

        try:
            # Query failed files older than cutoff date
            query = self.db.query(FileAttachment).filter(
                and_(
                    FileAttachment.status == AttachmentStatus.FAILED,
                    FileAttachment.created_at < cutoff_date
                )
            )

            # Filter by tenant if specified
            if tenant_id:
                query = query.filter(FileAttachment.tenant_id == tenant_id)

            failed_files = query.all()
            logger.info(f"Found {len(failed_files)} failed files to clean up")

            for attachment in failed_files:
                try:
                    storage_freed += attachment.file_size

                    if not dry_run:
                        # Delete file from storage
                        try:
                            await self.file_storage_service.delete_file(
                                attachment.stored_filename,
                                attachment.tenant_id,
                                user_id=0  # System cleanup
                            )
                        except Exception as e:
                            logger.warning(f"Failed to delete file from storage: {e}")
                            # Continue with database deletion

                        # Delete attachment record
                        self.file_attachment_repo.delete(attachment.id, attachment.tenant_id)
                        files_deleted += 1
                        logger.info(f"Deleted failed file: {attachment.original_filename}")
                    else:
                        files_deleted += 1
                        logger.info(f"[DRY RUN] Would delete: {attachment.original_filename}")

                except Exception as e:
                    files_skipped += 1
                    error_msg = f"Error cleaning up {attachment.original_filename}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            logger.info(f"Cleanup completed: {files_deleted} deleted, {files_skipped} skipped")

            return {
                "files_deleted": files_deleted,
                "files_skipped": files_skipped,
                "storage_freed_bytes": storage_freed,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {
                "files_deleted": files_deleted,
                "files_skipped": files_skipped,
                "storage_freed_bytes": storage_freed,
                "errors": [str(e)]
            }

    async def cleanup_old_files(
        self,
        tenant_id: Optional[int] = None,
        days_old: int = 365,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean up old processed files (retention policy).

        Deletes file attachments with COMPLETED or PARTIAL status that are older
        than the specified number of days, along with their associated files from storage.

        This implements a retention policy for processed files. By default, files
        older than 1 year are cleaned up.

        Args:
            tenant_id: Optional tenant ID to limit cleanup to specific tenant
            days_old: Minimum age in days for files to be cleaned up (default: 365)
            dry_run: If True, only report what would be deleted without deleting

        Returns:
            Dictionary with cleanup statistics:
            {
                "files_deleted": int,
                "files_skipped": int,
                "storage_freed_bytes": int,
                "errors": List[str]
            }

        Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
        """
        logger.info(f"Starting cleanup of old processed files (dry_run={dry_run})")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        files_deleted = 0
        files_skipped = 0
        storage_freed = 0
        errors = []

        try:
            # Query old processed files
            query = self.db.query(FileAttachment).filter(
                and_(
                    FileAttachment.status.in_([AttachmentStatus.COMPLETED, AttachmentStatus.PARTIAL]),
                    FileAttachment.processed_at < cutoff_date
                )
            )

            # Filter by tenant if specified
            if tenant_id:
                query = query.filter(FileAttachment.tenant_id == tenant_id)

            old_files = query.all()
            logger.info(f"Found {len(old_files)} old processed files to clean up")

            for attachment in old_files:
                try:
                    storage_freed += attachment.file_size

                    if not dry_run:
                        # Delete file from storage
                        try:
                            await self.file_storage_service.delete_file(
                                attachment.stored_filename,
                                attachment.tenant_id,
                                user_id=0  # System cleanup
                            )
                        except Exception as e:
                            logger.warning(f"Failed to delete file from storage: {e}")
                            # Continue with database deletion

                        # Delete attachment record
                        self.file_attachment_repo.delete(attachment.id, attachment.tenant_id)
                        files_deleted += 1
                        logger.info(f"Deleted old file: {attachment.original_filename}")
                    else:
                        files_deleted += 1
                        logger.info(f"[DRY RUN] Would delete: {attachment.original_filename}")

                except Exception as e:
                    files_skipped += 1
                    error_msg = f"Error cleaning up {attachment.original_filename}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            logger.info(f"Cleanup completed: {files_deleted} deleted, {files_skipped} skipped")

            return {
                "files_deleted": files_deleted,
                "files_skipped": files_skipped,
                "storage_freed_bytes": storage_freed,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {
                "files_deleted": files_deleted,
                "files_skipped": files_skipped,
                "storage_freed_bytes": storage_freed,
                "errors": [str(e)]
            }

    async def cleanup_portfolio_files(
        self,
        portfolio_id: int,
        tenant_id: int,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean up all files associated with a portfolio (cascade delete).

        Deletes all file attachments for a portfolio, along with their associated
        files from storage. This is typically called when a portfolio is deleted.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for isolation
            dry_run: If True, only report what would be deleted without deleting

        Returns:
            Dictionary with cleanup statistics:
            {
                "files_deleted": int,
                "files_skipped": int,
                "storage_freed_bytes": int,
                "errors": List[str]
            }

        Requirements: 4.5, 14.1, 14.2, 14.3, 14.4, 14.5
        """
        logger.info(f"Starting cleanup of files for portfolio {portfolio_id} (dry_run={dry_run})")

        files_deleted = 0
        files_skipped = 0
        storage_freed = 0
        errors = []

        try:
            # Get all attachments for portfolio
            attachments = self.file_attachment_repo.get_by_portfolio(portfolio_id, tenant_id)
            logger.info(f"Found {len(attachments)} files to clean up for portfolio {portfolio_id}")

            for attachment in attachments:
                try:
                    storage_freed += attachment.file_size

                    if not dry_run:
                        # Delete file from storage
                        try:
                            await self.file_storage_service.delete_file(
                                attachment.stored_filename,
                                attachment.tenant_id,
                                user_id=0  # System cleanup
                            )
                        except Exception as e:
                            logger.warning(f"Failed to delete file from storage: {e}")
                            # Continue with database deletion

                        # Delete attachment record
                        self.file_attachment_repo.delete(attachment.id, attachment.tenant_id)
                        files_deleted += 1
                        logger.info(f"Deleted file: {attachment.original_filename}")
                    else:
                        files_deleted += 1
                        logger.info(f"[DRY RUN] Would delete: {attachment.original_filename}")

                except Exception as e:
                    files_skipped += 1
                    error_msg = f"Error cleaning up {attachment.original_filename}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            logger.info(f"Portfolio cleanup completed: {files_deleted} deleted, {files_skipped} skipped")

            return {
                "files_deleted": files_deleted,
                "files_skipped": files_skipped,
                "storage_freed_bytes": storage_freed,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Error during portfolio cleanup: {e}")
            return {
                "files_deleted": files_deleted,
                "files_skipped": files_skipped,
                "storage_freed_bytes": storage_freed,
                "errors": [str(e)]
            }

    def get_storage_statistics(
        self,
        tenant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get storage statistics for file attachments.

        Returns statistics about file attachments including total size, count by status,
        and breakdown by portfolio.

        Args:
            tenant_id: Optional tenant ID to limit statistics to specific tenant

        Returns:
            Dictionary with storage statistics:
            {
                "total_files": int,
                "total_size_bytes": int,
                "total_size_mb": float,
                "by_status": {
                    "pending": {"count": int, "size_bytes": int},
                    "processing": {"count": int, "size_bytes": int},
                    "completed": {"count": int, "size_bytes": int},
                    "failed": {"count": int, "size_bytes": int},
                    "partial": {"count": int, "size_bytes": int}
                },
                "by_file_type": {
                    "pdf": {"count": int, "size_bytes": int},
                    "csv": {"count": int, "size_bytes": int}
                }
            }

        Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
        """
        logger.info(f"Getting storage statistics for tenant {tenant_id}")

        try:
            query = self.db.query(FileAttachment)

            if tenant_id:
                query = query.filter(FileAttachment.tenant_id == tenant_id)

            # Get all attachments
            attachments = query.all()

            # Calculate statistics
            total_files = len(attachments)
            total_size = sum(a.file_size for a in attachments)

            # Group by status
            by_status = {}
            for status in AttachmentStatus:
                status_files = [a for a in attachments if a.status == status]
                by_status[status.value] = {
                    "count": len(status_files),
                    "size_bytes": sum(a.file_size for a in status_files)
                }

            # Group by file type
            by_file_type = {}
            for file_type in ["pdf", "csv"]:
                type_files = [a for a in attachments if a.file_type.value == file_type]
                by_file_type[file_type] = {
                    "count": len(type_files),
                    "size_bytes": sum(a.file_size for a in type_files)
                }

            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "by_status": by_status,
                "by_file_type": by_file_type
            }

        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "by_status": {},
                "by_file_type": {},
                "error": str(e)
            }

    def get_cleanup_recommendations(
        self,
        tenant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get recommendations for cleanup operations.

        Analyzes file attachments and provides recommendations for cleanup,
        including number of files that could be cleaned up and estimated
        storage that could be freed.

        Args:
            tenant_id: Optional tenant ID to limit recommendations to specific tenant

        Returns:
            Dictionary with cleanup recommendations:
            {
                "failed_files_cleanup": {
                    "count": int,
                    "size_bytes": int,
                    "days_old": int
                },
                "old_files_cleanup": {
                    "count": int,
                    "size_bytes": int,
                    "days_old": int
                },
                "total_potential_cleanup_bytes": int,
                "total_potential_cleanup_mb": float
            }

        Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
        """
        logger.info(f"Getting cleanup recommendations for tenant {tenant_id}")

        try:
            # Failed files older than 30 days
            failed_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            query_failed = self.db.query(FileAttachment).filter(
                and_(
                    FileAttachment.status == AttachmentStatus.FAILED,
                    FileAttachment.created_at < failed_cutoff
                )
            )

            if tenant_id:
                query_failed = query_failed.filter(FileAttachment.tenant_id == tenant_id)

            failed_files = query_failed.all()
            failed_size = sum(a.file_size for a in failed_files)

            # Old processed files older than 365 days
            old_cutoff = datetime.now(timezone.utc) - timedelta(days=365)
            query_old = self.db.query(FileAttachment).filter(
                and_(
                    FileAttachment.status.in_([AttachmentStatus.COMPLETED, AttachmentStatus.PARTIAL]),
                    FileAttachment.processed_at < old_cutoff
                )
            )

            if tenant_id:
                query_old = query_old.filter(FileAttachment.tenant_id == tenant_id)

            old_files = query_old.all()
            old_size = sum(a.file_size for a in old_files)

            total_cleanup = failed_size + old_size

            return {
                "failed_files_cleanup": {
                    "count": len(failed_files),
                    "size_bytes": failed_size,
                    "days_old": 30
                },
                "old_files_cleanup": {
                    "count": len(old_files),
                    "size_bytes": old_size,
                    "days_old": 365
                },
                "total_potential_cleanup_bytes": total_cleanup,
                "total_potential_cleanup_mb": round(total_cleanup / (1024 * 1024), 2)
            }

        except Exception as e:
            logger.error(f"Error getting cleanup recommendations: {e}")
            return {
                "failed_files_cleanup": {"count": 0, "size_bytes": 0, "days_old": 30},
                "old_files_cleanup": {"count": 0, "size_bytes": 0, "days_old": 365},
                "total_potential_cleanup_bytes": 0,
                "total_potential_cleanup_mb": 0,
                "error": str(e)
            }

    def list_files_by_status(
        self,
        status: AttachmentStatus,
        tenant_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List file attachments by status.

        Args:
            status: Status to filter by
            tenant_id: Optional tenant ID to limit to specific tenant
            limit: Maximum number of files to return

        Returns:
            List of file attachment dictionaries

        Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
        """
        logger.info(f"Listing files with status {status.value}")

        try:
            query = self.db.query(FileAttachment).filter(
                FileAttachment.status == status
            )

            if tenant_id:
                query = query.filter(FileAttachment.tenant_id == tenant_id)

            files = query.order_by(FileAttachment.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": f.id,
                    "portfolio_id": f.portfolio_id,
                    "tenant_id": f.tenant_id,
                    "original_filename": f.original_filename,
                    "file_size": f.file_size,
                    "status": f.status.value,
                    "created_at": f.created_at.isoformat(),
                    "processed_at": f.processed_at.isoformat() if f.processed_at else None,
                    "extracted_holdings_count": f.extracted_holdings_count,
                    "failed_holdings_count": f.failed_holdings_count
                }
                for f in files
            ]

        except Exception as e:
            logger.error(f"Error listing files by status: {e}")
            return []
