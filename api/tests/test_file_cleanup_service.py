"""
Tests for File Cleanup Service

Tests the file cleanup and storage management functionality including:
- Cleanup of failed files
- Cleanup of old processed files
- Cascade deletion of portfolio files
- Storage statistics and reporting
- Cleanup recommendations
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy.orm import Session

from plugins.investments.models import (
    InvestmentPortfolio, FileAttachment, AttachmentStatus, FileType, PortfolioType
)
from plugins.investments.services.file_cleanup_service import FileCleanupService
from plugins.investments.repositories.file_attachment_repository import FileAttachmentRepository
from plugins.investments.repositories.portfolio_repository import PortfolioRepository


@pytest.fixture
def portfolio_repo(db_session: Session):
    """Create a portfolio repository."""
    return PortfolioRepository(db_session)


@pytest.fixture
def file_attachment_repo(db_session: Session):
    """Create a file attachment repository."""
    return FileAttachmentRepository(db_session)


@pytest.fixture
def cleanup_service(db_session: Session):
    """Create a file cleanup service."""
    return FileCleanupService(db_session)


@pytest.fixture
def test_portfolio(db_session: Session, portfolio_repo):
    """Create a test portfolio."""
    portfolio = portfolio_repo.create(
        tenant_id=1,
        name="Test Portfolio",
        portfolio_type=PortfolioType.TAXABLE
    )
    return portfolio


@pytest.fixture
def test_file_attachment(db_session: Session, file_attachment_repo, test_portfolio):
    """Create a test file attachment."""
    attachment = file_attachment_repo.create(
        portfolio_id=test_portfolio.id,
        tenant_id=1,
        original_filename="test.pdf",
        stored_filename="hf_1_abc123.pdf",
        file_size=1024 * 100,  # 100 KB
        file_type=FileType.PDF,
        local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
        created_by=1
    )
    return attachment


class TestFileCleanupService:
    """Test suite for FileCleanupService."""

    def test_cleanup_service_initialization(self, cleanup_service):
        """Test that cleanup service initializes correctly."""
        assert cleanup_service is not None
        assert cleanup_service.db is not None
        assert cleanup_service.file_attachment_repo is not None
        assert cleanup_service.file_storage_service is not None

    @pytest.mark.asyncio
    async def test_cleanup_failed_files_dry_run(
        self,
        db_session: Session,
        cleanup_service,
        file_attachment_repo,
        test_portfolio
    ):
        """Test cleanup of failed files in dry-run mode."""
        # Create failed file older than 30 days
        old_date = datetime.now(timezone.utc) - timedelta(days=31)
        attachment = file_attachment_repo.create(
            portfolio_id=test_portfolio.id,
            tenant_id=1,
            original_filename="failed.pdf",
            stored_filename="hf_1_failed.pdf",
            file_size=1024 * 50,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_failed.pdf",
            created_by=1
        )

        # Update to failed status with old date
        file_attachment_repo.update(
            attachment.id,
            1,
            status=AttachmentStatus.FAILED,
            created_at=old_date
        )

        # Run cleanup in dry-run mode
        result = await cleanup_service.cleanup_failed_files(
            tenant_id=1,
            days_old=30,
            dry_run=True
        )

        # Verify results
        assert result["files_deleted"] == 1
        assert result["files_skipped"] == 0
        assert result["storage_freed_bytes"] == 1024 * 50
        assert len(result["errors"]) == 0

        # Verify file still exists in database
        still_exists = file_attachment_repo.get_by_id(attachment.id, 1)
        assert still_exists is not None

    @pytest.mark.asyncio
    async def test_cleanup_old_files_dry_run(
        self,
        db_session: Session,
        cleanup_service,
        file_attachment_repo,
        test_portfolio
    ):
        """Test cleanup of old processed files in dry-run mode."""
        # Create completed file older than 365 days
        old_date = datetime.now(timezone.utc) - timedelta(days=366)
        attachment = file_attachment_repo.create(
            portfolio_id=test_portfolio.id,
            tenant_id=1,
            original_filename="old.pdf",
            stored_filename="hf_1_old.pdf",
            file_size=1024 * 75,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_old.pdf",
            created_by=1
        )

        # Update to completed status with old processed date
        file_attachment_repo.update(
            attachment.id,
            1,
            status=AttachmentStatus.COMPLETED,
            processed_at=old_date
        )

        # Run cleanup in dry-run mode
        result = await cleanup_service.cleanup_old_files(
            tenant_id=1,
            days_old=365,
            dry_run=True
        )

        # Verify results
        assert result["files_deleted"] == 1
        assert result["files_skipped"] == 0
        assert result["storage_freed_bytes"] == 1024 * 75
        assert len(result["errors"]) == 0

        # Verify file still exists in database
        still_exists = file_attachment_repo.get_by_id(attachment.id, 1)
        assert still_exists is not None

    @pytest.mark.asyncio
    async def test_cleanup_portfolio_files_dry_run(
        self,
        db_session: Session,
        cleanup_service,
        file_attachment_repo,
        test_portfolio
    ):
        """Test cascade deletion of portfolio files in dry-run mode."""
        # Create multiple files for portfolio
        for i in range(3):
            file_attachment_repo.create(
                portfolio_id=test_portfolio.id,
                tenant_id=1,
                original_filename=f"file{i}.pdf",
                stored_filename=f"hf_1_file{i}.pdf",
                file_size=1024 * (50 + i * 10),
                file_type=FileType.PDF,
                local_path=f"/attachments/tenant_1/holdings_files/hf_1_file{i}.pdf",
                created_by=1
            )

        # Run cleanup in dry-run mode
        result = await cleanup_service.cleanup_portfolio_files(
            portfolio_id=test_portfolio.id,
            tenant_id=1,
            dry_run=True
        )

        # Verify results
        assert result["files_deleted"] == 3
        assert result["files_skipped"] == 0
        assert result["storage_freed_bytes"] == (1024 * 50) + (1024 * 60) + (1024 * 70)
        assert len(result["errors"]) == 0

        # Verify files still exist in database
        attachments = file_attachment_repo.get_by_portfolio(test_portfolio.id, 1)
        assert len(attachments) == 3

    def test_get_storage_statistics(
        self,
        db_session: Session,
        cleanup_service,
        file_attachment_repo,
        test_portfolio
    ):
        """Test storage statistics calculation."""
        # Create files with different statuses
        for status in [AttachmentStatus.PENDING, AttachmentStatus.COMPLETED, AttachmentStatus.FAILED]:
            attachment = file_attachment_repo.create(
                portfolio_id=test_portfolio.id,
                tenant_id=1,
                original_filename=f"{status.value}.pdf",
                stored_filename=f"hf_1_{status.value}.pdf",
                file_size=1024 * 100,
                file_type=FileType.PDF,
                local_path=f"/attachments/tenant_1/holdings_files/hf_1_{status.value}.pdf",
                created_by=1
            )

            file_attachment_repo.update(attachment.id, 1, status=status)

        # Get statistics
        stats = cleanup_service.get_storage_statistics(tenant_id=1)

        # Verify statistics
        assert stats["total_files"] == 3
        assert stats["total_size_bytes"] == 1024 * 300
        assert stats["total_size_mb"] == 0.29  # Approximately
        assert stats["by_status"]["pending"]["count"] == 1
        assert stats["by_status"]["completed"]["count"] == 1
        assert stats["by_status"]["failed"]["count"] == 1
        assert stats["by_file_type"]["pdf"]["count"] == 3

    def test_get_cleanup_recommendations(
        self,
        db_session: Session,
        cleanup_service,
        file_attachment_repo,
        test_portfolio
    ):
        """Test cleanup recommendations."""
        # Create failed file older than 30 days
        old_failed_date = datetime.now(timezone.utc) - timedelta(days=31)
        failed_attachment = file_attachment_repo.create(
            portfolio_id=test_portfolio.id,
            tenant_id=1,
            original_filename="failed.pdf",
            stored_filename="hf_1_failed.pdf",
            file_size=1024 * 50,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_failed.pdf",
            created_by=1
        )
        file_attachment_repo.update(
            failed_attachment.id,
            1,
            status=AttachmentStatus.FAILED,
            created_at=old_failed_date
        )

        # Create old completed file older than 365 days
        old_completed_date = datetime.now(timezone.utc) - timedelta(days=366)
        completed_attachment = file_attachment_repo.create(
            portfolio_id=test_portfolio.id,
            tenant_id=1,
            original_filename="old.pdf",
            stored_filename="hf_1_old.pdf",
            file_size=1024 * 75,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_old.pdf",
            created_by=1
        )
        file_attachment_repo.update(
            completed_attachment.id,
            1,
            status=AttachmentStatus.COMPLETED,
            processed_at=old_completed_date
        )

        # Get recommendations
        recommendations = cleanup_service.get_cleanup_recommendations(tenant_id=1)

        # Verify recommendations
        assert recommendations["failed_files_cleanup"]["count"] == 1
        assert recommendations["failed_files_cleanup"]["size_bytes"] == 1024 * 50
        assert recommendations["old_files_cleanup"]["count"] == 1
        assert recommendations["old_files_cleanup"]["size_bytes"] == 1024 * 75
        assert recommendations["total_potential_cleanup_bytes"] == (1024 * 50) + (1024 * 75)

    def test_list_files_by_status(
        self,
        db_session: Session,
        cleanup_service,
        file_attachment_repo,
        test_portfolio
    ):
        """Test listing files by status."""
        # Create files with different statuses
        for i, status in enumerate([AttachmentStatus.PENDING, AttachmentStatus.COMPLETED, AttachmentStatus.FAILED]):
            attachment = file_attachment_repo.create(
                portfolio_id=test_portfolio.id,
                tenant_id=1,
                original_filename=f"{status.value}_{i}.pdf",
                stored_filename=f"hf_1_{status.value}_{i}.pdf",
                file_size=1024 * (50 + i * 10),
                file_type=FileType.PDF,
                local_path=f"/attachments/tenant_1/holdings_files/hf_1_{status.value}_{i}.pdf",
                created_by=1
            )

            file_attachment_repo.update(attachment.id, 1, status=status)

        # List files by status
        pending_files = cleanup_service.list_files_by_status(
            AttachmentStatus.PENDING,
            tenant_id=1
        )

        # Verify results
        assert len(pending_files) == 1
        assert pending_files[0]["status"] == "pending"
        assert pending_files[0]["file_size"] == 1024 * 50

    def test_storage_statistics_empty(self, cleanup_service):
        """Test storage statistics with no files."""
        stats = cleanup_service.get_storage_statistics(tenant_id=999)

        assert stats["total_files"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["total_size_mb"] == 0

    def test_cleanup_recommendations_empty(self, cleanup_service):
        """Test cleanup recommendations with no files."""
        recommendations = cleanup_service.get_cleanup_recommendations(tenant_id=999)

        assert recommendations["failed_files_cleanup"]["count"] == 0
        assert recommendations["old_files_cleanup"]["count"] == 0
        assert recommendations["total_potential_cleanup_bytes"] == 0
