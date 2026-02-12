"""
File Attachment Repository

This module implements the data access layer for file attachments used in
portfolio holdings import. It provides CRUD operations with proper tenant
isolation and follows the repository pattern to separate data access from
business logic.

All queries automatically filter by tenant context to ensure data isolation.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, timezone

from ..models import FileAttachment, AttachmentStatus, FileType


class FileAttachmentRepository:
    """
    Repository for file attachment data access operations.

    All methods enforce tenant isolation by filtering queries based on the
    tenant context. This ensures users can only access their own file attachments.
    """

    def __init__(self, db_session: Session):
        """
        Initialize the repository with a database session.

        Args:
            db_session: SQLAlchemy session (required)

        Raises:
            ValueError: If db_session is None
        """
        if db_session is None:
            raise ValueError("Database session is required")
        self.db = db_session

    def create(
        self,
        portfolio_id: int,
        tenant_id: int,
        original_filename: str,
        stored_filename: str,
        file_size: int,
        file_type: FileType,
        local_path: str,
        created_by: int,
        cloud_url: Optional[str] = None,
        file_hash: Optional[str] = None
    ) -> FileAttachment:
        """
        Create a new file attachment record.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)
            original_filename: Original filename for display
            stored_filename: Unique stored filename
            file_size: File size in bytes
            file_type: File type (PDF or CSV)
            local_path: Local storage path
            created_by: User ID who uploaded the file
            cloud_url: Optional cloud storage URL
            file_hash: Optional SHA-256 hash for deduplication

        Returns:
            Created FileAttachment instance

        Raises:
            SQLAlchemyError: If database operation fails
        """
        attachment = FileAttachment(
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_size=file_size,
            file_type=file_type,
            local_path=local_path,
            cloud_url=cloud_url,
            file_hash=file_hash,
            status=AttachmentStatus.PENDING,
            extracted_holdings_count=0,
            failed_holdings_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=created_by
        )

        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)

        return attachment

    def get_by_id(self, attachment_id: int, tenant_id: int) -> Optional[FileAttachment]:
        """
        Get a file attachment by ID for a specific tenant.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            FileAttachment instance if found, None otherwise
        """
        return self.db.query(FileAttachment).filter(
            and_(
                FileAttachment.id == attachment_id,
                FileAttachment.tenant_id == tenant_id
            )
        ).first()

    def get_by_portfolio(self, portfolio_id: int, tenant_id: int) -> List[FileAttachment]:
        """
        Get all file attachments for a specific portfolio.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            List of FileAttachment instances
        """
        return self.db.query(FileAttachment).filter(
            and_(
                FileAttachment.portfolio_id == portfolio_id,
                FileAttachment.tenant_id == tenant_id
            )
        ).order_by(FileAttachment.created_at.desc()).all()

    def get_by_hash(
        self,
        portfolio_id: int,
        file_hash: str,
        tenant_id: int
    ) -> Optional[FileAttachment]:
        """
        Find a file attachment by its content hash in a specific portfolio.

        Used for duplicate file detection during upload.

        Args:
            portfolio_id: Portfolio ID
            file_hash: SHA-256 hash of file content
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            FileAttachment instance if found, None otherwise
        """
        return self.db.query(FileAttachment).filter(
            and_(
                FileAttachment.portfolio_id == portfolio_id,
                FileAttachment.file_hash == file_hash,
                FileAttachment.tenant_id == tenant_id
            )
        ).first()

    def get_by_tenant(self, tenant_id: int) -> List[FileAttachment]:
        """
        Get all file attachments for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of FileAttachment instances
        """
        return self.db.query(FileAttachment).filter(
            FileAttachment.tenant_id == tenant_id
        ).order_by(FileAttachment.created_at.desc()).all()

    def update(self, attachment_id: int, tenant_id: int, **updates) -> Optional[FileAttachment]:
        """
        Update a file attachment record.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID (for explicit tenant isolation)
            **updates: Fields to update (e.g., status='completed', extracted_holdings_count=5)

        Returns:
            Updated FileAttachment instance if found, None otherwise

        Raises:
            ValueError: If attempting to update tenant_id or portfolio_id
        """
        # Prevent updating tenant_id or portfolio_id
        if 'tenant_id' in updates or 'portfolio_id' in updates:
            raise ValueError("Cannot update tenant_id or portfolio_id")

        attachment = self.get_by_id(attachment_id, tenant_id)
        if not attachment:
            return None

        # Always update the updated_at timestamp
        updates['updated_at'] = datetime.now(timezone.utc)

        for key, value in updates.items():
            if hasattr(attachment, key):
                setattr(attachment, key, value)

        self.db.commit()
        self.db.refresh(attachment)

        return attachment

    def delete(self, attachment_id: int, tenant_id: int) -> bool:
        """
        Delete a file attachment record.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            True if deleted, False if not found
        """
        attachment = self.get_by_id(attachment_id, tenant_id)
        if not attachment:
            return False

        self.db.delete(attachment)
        self.db.commit()

        return True

    def update_status(
        self,
        attachment_id: int,
        tenant_id: int,
        status: AttachmentStatus,
        processed_at: Optional[datetime] = None
    ) -> Optional[FileAttachment]:
        """
        Update the status of a file attachment.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID (for explicit tenant isolation)
            status: New status
            processed_at: Optional timestamp for when processing completed

        Returns:
            Updated FileAttachment instance if found, None otherwise
        """
        updates = {'status': status}
        if processed_at:
            updates['processed_at'] = processed_at

        return self.update(attachment_id, tenant_id, **updates)

    def update_with_results(
        self,
        attachment_id: int,
        tenant_id: int,
        status: AttachmentStatus,
        extracted_holdings_count: int,
        failed_holdings_count: int,
        extracted_data: Optional[str] = None,
        extraction_error: Optional[str] = None
    ) -> Optional[FileAttachment]:
        """
        Update a file attachment with extraction results.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID (for explicit tenant isolation)
            status: Final status (COMPLETED, FAILED, or PARTIAL)
            extracted_holdings_count: Number of successfully created holdings
            failed_holdings_count: Number of holdings that failed to create
            extracted_data: Optional JSON string with extracted holdings data
            extraction_error: Optional error message if extraction failed

        Returns:
            Updated FileAttachment instance if found, None otherwise
        """
        updates = {
            'status': status,
            'extracted_holdings_count': extracted_holdings_count,
            'failed_holdings_count': failed_holdings_count,
            'processed_at': datetime.now(timezone.utc)
        }

        if extracted_data is not None:
            updates['extracted_data'] = extracted_data

        if extraction_error is not None:
            updates['extraction_error'] = extraction_error

        return self.update(attachment_id, tenant_id, **updates)

    def get_by_status(
        self,
        tenant_id: int,
        status: AttachmentStatus
    ) -> List[FileAttachment]:
        """
        Get all file attachments with a specific status for a tenant.

        Args:
            tenant_id: Tenant ID
            status: Status to filter by

        Returns:
            List of FileAttachment instances
        """
        return self.db.query(FileAttachment).filter(
            and_(
                FileAttachment.tenant_id == tenant_id,
                FileAttachment.status == status
            )
        ).order_by(FileAttachment.created_at.desc()).all()

    def get_pending_for_processing(self, tenant_id: int, limit: int = 10) -> List[FileAttachment]:
        """
        Get pending file attachments ready for processing.

        Args:
            tenant_id: Tenant ID
            limit: Maximum number of attachments to return

        Returns:
            List of FileAttachment instances with PENDING status
        """
        return self.db.query(FileAttachment).filter(
            and_(
                FileAttachment.tenant_id == tenant_id,
                FileAttachment.status == AttachmentStatus.PENDING
            )
        ).order_by(FileAttachment.created_at.asc()).limit(limit).all()

    def count_by_portfolio(self, portfolio_id: int, tenant_id: int) -> int:
        """
        Count file attachments for a specific portfolio.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            Number of attachments
        """
        return self.db.query(func.count(FileAttachment.id)).filter(
            and_(
                FileAttachment.portfolio_id == portfolio_id,
                FileAttachment.tenant_id == tenant_id
            )
        ).scalar() or 0

    def count_by_status(self, tenant_id: int, status: AttachmentStatus) -> int:
        """
        Count file attachments with a specific status for a tenant.

        Args:
            tenant_id: Tenant ID
            status: Status to filter by

        Returns:
            Number of attachments
        """
        return self.db.query(func.count(FileAttachment.id)).filter(
            and_(
                FileAttachment.tenant_id == tenant_id,
                FileAttachment.status == status
            )
        ).scalar() or 0

    def delete_by_portfolio(self, portfolio_id: int, tenant_id: int) -> int:
        """
        Delete all file attachments for a specific portfolio (cascade delete).

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            Number of attachments deleted
        """
        count = self.db.query(FileAttachment).filter(
            and_(
                FileAttachment.portfolio_id == portfolio_id,
                FileAttachment.tenant_id == tenant_id
            )
        ).delete()

        self.db.commit()

        return count

    def exists(self, attachment_id: int, tenant_id: int) -> bool:
        """
        Check if a file attachment exists for a specific tenant.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID (for explicit tenant isolation)

        Returns:
            True if attachment exists, False otherwise
        """
        return self.db.query(
            self.db.query(FileAttachment).filter(
                and_(
                    FileAttachment.id == attachment_id,
                    FileAttachment.tenant_id == tenant_id
                )
            ).exists()
        ).scalar()

    def validate_tenant_access(self, attachment_id: int, tenant_id: int) -> bool:
        """
        Validate that a tenant has access to a file attachment.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID

        Returns:
            True if tenant has access, False otherwise
        """
        return self.exists(attachment_id, tenant_id)

    def close(self):
        """Close the database session."""
        if self.db:
            self.db.close()
