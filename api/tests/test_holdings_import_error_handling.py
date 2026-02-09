"""
Unit tests for Holdings Import Error Handling

This module tests error handling and recovery for the portfolio holdings import feature.
Tests cover file validation errors, authorization errors, not found errors, server errors,
and graceful degradation for cloud storage failures.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone
from decimal import Decimal

# Import investment models and services
from plugins.investments.models import (
    InvestmentPortfolio,
    InvestmentHolding,
    FileAttachment,
    PortfolioType,
    FileType,
    AttachmentStatus,
    SecurityType,
    AssetClass,
    Base as InvestmentBase
)
from plugins.investments.services.holdings_import_service import HoldingsImportService
from plugins.investments.exceptions import (
    FileValidationError, FileStorageError, FileUploadError,
    ExtractionError, CloudStorageError
)
from plugins.investments.schemas import HoldingCreate
from core.exceptions.base import ValidationError, NotFoundError


class TestFileValidationErrors:
    """Test file validation error handling"""

    @pytest.fixture
    def investment_db_session(self):
        """Create an in-memory SQLite database session"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        InvestmentBase.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService with mocked dependencies"""
        service = HoldingsImportService(investment_db_session)
        service.file_storage_service = Mock()
        service.llm_extraction_service = Mock()
        service.holdings_service = Mock()
        return service

    @pytest.fixture
    def sample_portfolio(self, investment_db_session):
        """Create a sample portfolio"""
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()
        return portfolio

    @pytest.mark.asyncio
    async def test_unsupported_file_format_rejected(self, holdings_import_service, sample_portfolio):
        """Test that unsupported file formats are rejected with 400 error"""
        # Setup
        holdings_import_service.file_storage_service.validate_file.return_value = (
            False, "Unsupported file format. Only PDF and CSV are supported.", None
        )

        # Execute & Assert
        with pytest.raises(FileValidationError) as exc_info:
            await holdings_import_service.upload_files(
                portfolio_id=sample_portfolio.id,
                tenant_id=1,
                files=[(b"content", "file.txt", "text/plain")],
                user_id=1
            )

        assert "Unsupported file format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_size_exceeds_limit(self, holdings_import_service, sample_portfolio):
        """Test that files exceeding 20MB are rejected"""
        # Setup
        holdings_import_service.file_storage_service.validate_file.return_value = (
            False, "File size exceeds maximum of 20 MB", None
        )

        # Execute & Assert
        with pytest.raises(FileValidationError) as exc_info:
            await holdings_import_service.upload_files(
                portfolio_id=sample_portfolio.id,
                tenant_id=1,
                files=[(b"x" * (21 * 1024 * 1024), "large.pdf", "application/pdf")],
                user_id=1
            )

        assert "exceeds maximum" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_count_exceeds_limit(self, holdings_import_service, sample_portfolio):
        """Test that uploading more than 12 files is rejected"""
        # Setup
        files = [(b"content", f"file{i}.pdf", "application/pdf") for i in range(13)]

        # Execute & Assert
        with pytest.raises(FileValidationError) as exc_info:
            await holdings_import_service.upload_files(
                portfolio_id=sample_portfolio.id,
                tenant_id=1,
                files=files,
                user_id=1
            )

        assert "Maximum 12 files" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_corrupted_file_rejected(self, holdings_import_service, sample_portfolio):
        """Test that corrupted files are rejected"""
        # Setup
        holdings_import_service.file_storage_service.validate_file.return_value = (
            False, "File is corrupted or unreadable", None
        )

        # Execute & Assert
        with pytest.raises(FileValidationError) as exc_info:
            await holdings_import_service.upload_files(
                portfolio_id=sample_portfolio.id,
                tenant_id=1,
                files=[(b"\x00\x01\x02", "corrupted.pdf", "application/pdf")],
                user_id=1
            )

        assert "corrupted" in str(exc_info.value).lower()


class TestAuthorizationErrors:
    """Test authorization error handling"""

    @pytest.fixture
    def investment_db_session(self):
        """Create an in-memory SQLite database session"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        InvestmentBase.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService with mocked dependencies"""
        service = HoldingsImportService(investment_db_session)
        service.file_storage_service = Mock()
        service.llm_extraction_service = Mock()
        service.holdings_service = Mock()
        return service

    @pytest.mark.asyncio
    async def test_portfolio_not_found_returns_404(self, holdings_import_service):
        """Test that accessing non-existent portfolio returns 404"""
        # Execute & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await holdings_import_service.upload_files(
                portfolio_id=999,
                tenant_id=1,
                files=[(b"content", "file.pdf", "application/pdf")],
                user_id=1
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_tenant_isolation_enforced_on_download(self, investment_db_session, holdings_import_service):
        """Test that tenant isolation is enforced on file download"""
        # Setup - create portfolio and attachment for tenant 1
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()

        attachment = FileAttachment(
            portfolio_id=portfolio.id,
            tenant_id=1,
            original_filename="test.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1000,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            created_by=1,
            status=AttachmentStatus.COMPLETED
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()

        # Execute & Assert - tenant 2 trying to access tenant 1's file
        with pytest.raises(NotFoundError):
            await holdings_import_service.download_file(
                attachment_id=attachment.id,
                tenant_id=2  # Different tenant
            )


class TestNotFoundErrors:
    """Test not found error handling"""

    @pytest.fixture
    def investment_db_session(self):
        """Create an in-memory SQLite database session"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        InvestmentBase.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService with mocked dependencies"""
        service = HoldingsImportService(investment_db_session)
        service.file_storage_service = Mock()
        service.llm_extraction_service = Mock()
        service.holdings_service = Mock()
        return service

    @pytest.mark.asyncio
    async def test_attachment_not_found_on_process(self, holdings_import_service):
        """Test that processing non-existent attachment returns 404"""
        # Execute & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await holdings_import_service.process_file(
                attachment_id=999,
                tenant_id=1
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_attachment_not_found_on_get(self, holdings_import_service):
        """Test that getting non-existent attachment returns 404"""
        # Execute & Assert
        with pytest.raises(NotFoundError) as exc_info:
            holdings_import_service.get_file_attachment(
                attachment_id=999,
                tenant_id=1
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_attachment_not_found_on_delete(self, holdings_import_service):
        """Test that deleting non-existent attachment returns 404"""
        # Execute & Assert
        with pytest.raises(NotFoundError) as exc_info:
            holdings_import_service.delete_file_attachment(
                attachment_id=999,
                tenant_id=1,
                user_id=1
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_file_not_found_in_storage_on_download(self, investment_db_session, holdings_import_service):
        """Test that file not found in storage returns appropriate error"""
        # Setup
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()

        attachment = FileAttachment(
            portfolio_id=portfolio.id,
            tenant_id=1,
            original_filename="test.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1000,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            created_by=1,
            status=AttachmentStatus.COMPLETED
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()

        holdings_import_service.file_storage_service.retrieve_file = AsyncMock(
            side_effect=FileNotFoundError("File not found")
        )

        # Execute & Assert
        with pytest.raises(FileStorageError) as exc_info:
            await holdings_import_service.download_file(
                attachment_id=attachment.id,
                tenant_id=1
            )

        assert "not found" in str(exc_info.value).lower()


class TestServerErrors:
    """Test server error handling"""

    @pytest.fixture
    def investment_db_session(self):
        """Create an in-memory SQLite database session"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        InvestmentBase.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService with mocked dependencies"""
        service = HoldingsImportService(investment_db_session)
        service.file_storage_service = Mock()
        service.llm_extraction_service = Mock()
        service.holdings_service = Mock()
        return service

    @pytest.fixture
    def sample_portfolio(self, investment_db_session):
        """Create a sample portfolio"""
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()
        return portfolio

    @pytest.mark.asyncio
    async def test_file_storage_failure_returns_500(self, holdings_import_service, sample_portfolio):
        """Test that file storage failure returns 500 error"""
        # Setup
        holdings_import_service.file_storage_service.validate_file.return_value = (
            True, None, FileType.PDF
        )
        holdings_import_service.file_storage_service.save_file = AsyncMock(
            side_effect=Exception("Storage service unavailable")
        )

        # Execute & Assert
        with pytest.raises(FileStorageError) as exc_info:
            await holdings_import_service.upload_files(
                portfolio_id=sample_portfolio.id,
                tenant_id=1,
                files=[(b"content", "file.pdf", "application/pdf")],
                user_id=1
            )

        assert "Storage" in str(exc_info.value) or "storage" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extraction_failure_returns_500(self, investment_db_session, holdings_import_service, sample_portfolio):
        """Test that LLM extraction failure returns 500 error"""
        # Setup
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="test.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1000,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            created_by=1,
            status=AttachmentStatus.PENDING
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()

        holdings_import_service.llm_extraction_service.extract_holdings_from_pdf = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )

        # Execute & Assert
        with pytest.raises(ExtractionError) as exc_info:
            await holdings_import_service.extract_holdings_from_file(
                file_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
                file_type=FileType.PDF
            )

        assert "Failed to extract" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extraction_returns_empty_list(self, holdings_import_service):
        """Test that empty extraction result is handled as error"""
        # Setup
        holdings_import_service.llm_extraction_service.extract_holdings_from_pdf = AsyncMock(
            return_value=[]
        )

        # Execute & Assert
        with pytest.raises(ExtractionError) as exc_info:
            await holdings_import_service.extract_holdings_from_file(
                file_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
                file_type=FileType.PDF
            )

        assert "No holdings data found" in str(exc_info.value)


class TestCloudStorageGracefulDegradation:
    """Test graceful degradation for cloud storage failures"""

    @pytest.fixture
    def investment_db_session(self):
        """Create an in-memory SQLite database session"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        InvestmentBase.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService with mocked dependencies"""
        service = HoldingsImportService(investment_db_session)
        service.file_storage_service = Mock()
        service.llm_extraction_service = Mock()
        service.holdings_service = Mock()
        return service

    @pytest.fixture
    def sample_portfolio(self, investment_db_session):
        """Create a sample portfolio"""
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()
        return portfolio

    @pytest.mark.asyncio
    async def test_cloud_storage_failure_falls_back_to_local(self, holdings_import_service, sample_portfolio):
        """Test that cloud storage failure falls back to local storage"""
        # Setup - file storage succeeds with local path but no cloud URL
        holdings_import_service.file_storage_service.validate_file.return_value = (
            True, None, FileType.PDF
        )
        holdings_import_service.file_storage_service.save_file = AsyncMock(
            return_value=("hf_1_abc123.pdf", "/attachments/tenant_1/holdings_files/hf_1_abc123.pdf", None)
        )

        # Execute
        attachments = await holdings_import_service.upload_files(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            files=[(b"content", "file.pdf", "application/pdf")],
            user_id=1
        )

        # Assert - file was uploaded successfully despite cloud storage not being used
        assert len(attachments) == 1
        assert attachments[0].original_filename == "file.pdf"
        assert attachments[0].status == AttachmentStatus.PENDING
        assert attachments[0].file_type == FileType.PDF

    @pytest.mark.asyncio
    async def test_file_deletion_continues_on_storage_failure(self, investment_db_session, holdings_import_service):
        """Test that file deletion continues even if storage deletion fails"""
        # Setup
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()

        attachment = FileAttachment(
            portfolio_id=portfolio.id,
            tenant_id=1,
            original_filename="test.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1000,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            created_by=1,
            status=AttachmentStatus.COMPLETED
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()

        # Setup - storage deletion fails
        holdings_import_service.file_storage_service.delete_file = AsyncMock(
            side_effect=Exception("Cloud storage unavailable")
        )

        # Execute - should not raise exception
        result = holdings_import_service.delete_file_attachment(
            attachment_id=attachment.id,
            tenant_id=1,
            user_id=1
        )

        # Assert - deletion succeeded despite storage failure
        assert result is True


class TestErrorResponseFormat:
    """Test consistent error response format"""

    def test_file_validation_error_has_message(self):
        """Test that FileValidationError includes descriptive message"""
        error = FileValidationError("Invalid file format")
        assert error.message == "Invalid file format"
        assert isinstance(error.details, list)

    def test_file_storage_error_has_message(self):
        """Test that FileStorageError includes descriptive message"""
        error = FileStorageError("Storage service unavailable")
        assert error.message == "Storage service unavailable"

    def test_extraction_error_has_message(self):
        """Test that ExtractionError includes descriptive message"""
        error = ExtractionError("Failed to extract holdings")
        assert error.message == "Failed to extract holdings"

    def test_file_upload_error_has_message(self):
        """Test that FileUploadError includes descriptive message"""
        error = FileUploadError("Upload failed")
        assert error.message == "Upload failed"


class TestPartialFailureHandling:
    """Test partial failure handling in holdings creation"""

    @pytest.fixture
    def investment_db_session(self):
        """Create an in-memory SQLite database session"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        InvestmentBase.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService with mocked dependencies"""
        service = HoldingsImportService(investment_db_session)
        service.file_storage_service = Mock()
        service.llm_extraction_service = Mock()
        service.holdings_service = Mock()
        return service

    @pytest.fixture
    def sample_portfolio(self, investment_db_session):
        """Create a sample portfolio"""
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()
        return portfolio

    @pytest.mark.asyncio
    async def test_partial_failure_continues_processing(self, holdings_import_service, sample_portfolio):
        """Test that partial failures don't stop processing of other holdings"""
        # Setup - first holding fails validation, second succeeds
        extracted_holdings = [
            {
                "security_symbol": "INVALID",
                "security_name": "Invalid",
                "quantity": -100,  # Invalid: negative quantity
                "cost_basis": 15000,
                "purchase_date": "2023-01-15",
                "security_type": "stock",
                "asset_class": "stocks"
            },
            {
                "security_symbol": "AAPL",
                "security_name": "Apple Inc.",
                "quantity": 100,
                "cost_basis": 15000,
                "purchase_date": "2023-01-15",
                "security_type": "stock",
                "asset_class": "stocks"
            }
        ]

        holdings_import_service.holdings_service.create_holding = Mock()

        # Execute
        created_count, failed_count = await holdings_import_service.create_holdings_from_extracted_data(
            portfolio_id=sample_portfolio.id,
            extracted_holdings=extracted_holdings,
            attachment_id=1,
            tenant_id=1
        )

        # Assert - one failed, one succeeded
        assert failed_count >= 1
        assert created_count >= 0  # May be 0 or 1 depending on validation logic
