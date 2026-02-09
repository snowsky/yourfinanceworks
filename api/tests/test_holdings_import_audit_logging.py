"""
Unit tests for Holdings Import Audit Logging

This module tests audit logging functionality for portfolio holdings import,
including file upload events, extraction events, and holdings creation events.

Requirements: 20.1, 20.2, 20.3, 20.4, 20.5
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from plugins.investments.services.holdings_import_service import HoldingsImportService
from plugins.investments.models import (
    InvestmentPortfolio, FileAttachment, AttachmentStatus, FileType
)
from core.models.models_per_tenant import AuditLog
from core.utils.audit import log_audit_event


class TestHoldingsImportAuditLogging:
    """Test audit logging for holdings import operations"""

    @pytest.fixture
    def investment_db_session(self):
        """Create a test database session"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from plugins.investments.models import Base as InvestmentBase
        from core.models.models_per_tenant import Base as TenantBase

        engine = create_engine("sqlite:///:memory:")
        InvestmentBase.metadata.create_all(engine)
        TenantBase.metadata.create_all(engine)

        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        yield session
        session.close()

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService instance"""
        return HoldingsImportService(investment_db_session)

    @pytest.fixture
    def sample_portfolio(self, investment_db_session):
        """Create a sample portfolio for testing"""
        portfolio = InvestmentPortfolio(
            name="Test Portfolio",
            portfolio_type="TAXABLE",
            tenant_id=1
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()
        investment_db_session.refresh(portfolio)
        return portfolio

    @pytest.mark.asyncio
    async def test_upload_files_creates_audit_log(
        self, holdings_import_service, investment_db_session, sample_portfolio
    ):
        """Test that file upload creates an audit log entry"""
        # Arrange
        files = [(b"PDF content", "holdings.pdf", "application/pdf")]
        user_email = "test@example.com"

        # Mock file storage
        with patch.object(
            holdings_import_service.file_storage_service,
            "validate_file",
            return_value=(True, None, FileType.PDF)
        ):
            with patch.object(
                holdings_import_service.file_storage_service,
                "save_file",
                new_callable=AsyncMock,
                return_value=("stored_file.pdf", "/path/to/file", None)
            ):
                with patch(
                    "plugins.investments.services.holdings_import_service.publish_holdings_import_task",
                    return_value=True
                ):
                    # Act
                    attachments = await holdings_import_service.upload_files(
                        portfolio_id=sample_portfolio.id,
                        tenant_id=1,
                        files=files,
                        user_id=100,
                        user_email=user_email
                    )

        # Assert
        assert len(attachments) == 1

        # Check that audit log was created
        audit_logs = investment_db_session.query(AuditLog).filter(
            AuditLog.action == "UPLOAD",
            AuditLog.resource_type == "holdings_file"
        ).all()

        assert len(audit_logs) == 1
        audit_log = audit_logs[0]
        assert audit_log.user_id == 100
        assert audit_log.user_email == user_email
        assert audit_log.resource_name == "holdings.pdf"
        assert audit_log.status == "success"
        assert audit_log.details["portfolio_id"] == sample_portfolio.id
        assert audit_log.details["file_type"] == "pdf"

    @pytest.mark.asyncio
    async def test_process_file_creates_extraction_start_audit_log(
        self, holdings_import_service, investment_db_session, sample_portfolio
    ):
        """Test that file processing creates extraction start audit log"""
        # Arrange
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="holdings.pdf",
            stored_filename="stored_file.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/path/to/file",
            created_by=100,
            status=AttachmentStatus.PENDING
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()
        investment_db_session.refresh(attachment)

        user_email = "test@example.com"

        # Mock extraction and holdings creation
        with patch.object(
            holdings_import_service,
            "extract_holdings_from_file",
            new_callable=AsyncMock,
            return_value={"holdings": []}
        ):
            with patch.object(
                holdings_import_service,
                "create_holdings_from_extracted_data",
                new_callable=AsyncMock,
                return_value=(0, 0)
            ):
                # Act
                result = await holdings_import_service.process_file(
                    attachment_id=attachment.id,
                    tenant_id=1,
                    user_email=user_email
                )

        # Assert
        audit_logs = investment_db_session.query(AuditLog).filter(
            AuditLog.action == "EXTRACTION_START",
            AuditLog.resource_type == "holdings_file"
        ).all()

        assert len(audit_logs) == 1
        audit_log = audit_logs[0]
        assert audit_log.user_id == 100
        assert audit_log.user_email == user_email
        assert audit_log.status == "success"

    @pytest.mark.asyncio
    async def test_process_file_creates_extraction_completed_audit_log(
        self, holdings_import_service, investment_db_session, sample_portfolio
    ):
        """Test that successful file processing creates extraction completed audit log"""
        # Arrange
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="holdings.pdf",
            stored_filename="stored_file.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/path/to/file",
            created_by=100,
            status=AttachmentStatus.PENDING
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()
        investment_db_session.refresh(attachment)

        user_email = "test@example.com"

        # Mock extraction and holdings creation
        with patch.object(
            holdings_import_service,
            "extract_holdings_from_file",
            new_callable=AsyncMock,
            return_value={"holdings": []}
        ):
            with patch.object(
                holdings_import_service,
                "create_holdings_from_extracted_data",
                new_callable=AsyncMock,
                return_value=(0, 0)
            ):
                # Act
                result = await holdings_import_service.process_file(
                    attachment_id=attachment.id,
                    tenant_id=1,
                    user_email=user_email
                )

        # Assert
        audit_logs = investment_db_session.query(AuditLog).filter(
            AuditLog.action == "EXTRACTION_COMPLETED",
            AuditLog.resource_type == "holdings_file"
        ).all()

        assert len(audit_logs) == 1
        audit_log = audit_logs[0]
        assert audit_log.user_id == 100
        assert audit_log.user_email == user_email
        assert audit_log.status == "success"
        assert audit_log.details["status"] == "completed"
        assert audit_log.details["created_holdings"] == 0
        assert audit_log.details["failed_holdings"] == 0

    @pytest.mark.asyncio
    async def test_process_file_creates_extraction_failed_audit_log(
        self, holdings_import_service, investment_db_session, sample_portfolio
    ):
        """Test that failed file processing creates extraction failed audit log"""
        # Arrange
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="holdings.pdf",
            stored_filename="stored_file.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/path/to/file",
            created_by=100,
            status=AttachmentStatus.PENDING
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()
        investment_db_session.refresh(attachment)

        user_email = "test@example.com"
        error_message = "Failed to extract holdings"

        # Mock extraction to fail
        with patch.object(
            holdings_import_service,
            "extract_holdings_from_file",
            new_callable=AsyncMock,
            side_effect=Exception(error_message)
        ):
            # Act
            result = await holdings_import_service.process_file(
                attachment_id=attachment.id,
                tenant_id=1,
                user_email=user_email
            )

        # Assert
        audit_logs = investment_db_session.query(AuditLog).filter(
            AuditLog.action == "EXTRACTION_FAILED",
            AuditLog.resource_type == "holdings_file"
        ).all()

        assert len(audit_logs) == 1
        audit_log = audit_logs[0]
        assert audit_log.user_id == 100
        assert audit_log.user_email == user_email
        assert audit_log.status == "error"
        assert audit_log.error_message == error_message

    def test_audit_log_contains_required_fields(self, investment_db_session):
        """Test that audit logs contain all required fields"""
        # Arrange
        user_id = 100
        user_email = "test@example.com"
        action = "UPLOAD"
        resource_type = "holdings_file"
        resource_id = "1"
        resource_name = "holdings.pdf"
        details = {
            "portfolio_id": 1,
            "file_size": 1024,
            "file_type": "pdf"
        }

        # Act
        audit_log = log_audit_event(
            db=investment_db_session,
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
            status="success"
        )

        # Assert
        assert audit_log.user_id == user_id
        assert audit_log.user_email == user_email
        assert audit_log.action == action
        assert audit_log.resource_type == resource_type
        assert audit_log.resource_id == resource_id
        assert audit_log.resource_name == resource_name
        assert audit_log.details == details
        assert audit_log.status == "success"
        assert audit_log.created_at is not None
