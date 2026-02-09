"""
Unit tests for Holdings Import Service

This module tests the HoldingsImportService class to ensure proper file upload,
extraction, holdings creation, and error handling for portfolio holdings import.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
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
from plugins.investments.schemas import HoldingCreate
from core.exceptions.base import ValidationError, NotFoundError


class TestHoldingsImportService:
    """Test suite for HoldingsImportService"""

    @pytest.fixture
    def investment_db_session(self):
        """Create an in-memory SQLite database session for investment testing"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )

        # Create investment tables
        InvestmentBase.metadata.create_all(bind=engine)

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()

        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService instance with mocked dependencies"""
        service = HoldingsImportService(investment_db_session)

        # Mock the file storage service
        service.file_storage_service = Mock()
        service.file_storage_service.validate_file = Mock(
            return_value=(True, None, FileType.PDF)
        )
        service.file_storage_service.save_file = AsyncMock(
            return_value=("hf_1_abc123.pdf", "/attachments/tenant_1/holdings_files/hf_1_abc123.pdf", None)
        )
        service.file_storage_service.retrieve_file = AsyncMock(
            return_value=b"PDF content"
        )
        service.file_storage_service.delete_file = AsyncMock(return_value=True)

        # Mock the LLM extraction service
        service.llm_extraction_service = Mock()
        service.llm_extraction_service.extract_holdings_from_pdf = AsyncMock(
            return_value=[
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
        )

        return service

    @pytest.fixture
    def sample_portfolio(self, investment_db_session):
        """Create a sample portfolio for testing"""
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE,
            is_archived=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()
        investment_db_session.refresh(portfolio)
        return portfolio

    def test_service_initialization(self, holdings_import_service):
        """Test that service initializes with required repositories"""
        assert holdings_import_service.db is not None
        assert holdings_import_service.file_attachment_repo is not None
        assert holdings_import_service.portfolio_repo is not None
        assert holdings_import_service.holdings_repo is not None

    @pytest.mark.asyncio
    async def test_upload_files_success(self, holdings_import_service, sample_portfolio):
        """Test successful file upload"""
        # Arrange
        files = [
            (b"PDF content", "holdings.pdf", "application/pdf")
        ]

        # Act
        attachments = await holdings_import_service.upload_files(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            files=files,
            user_id=100
        )

        # Assert
        assert len(attachments) == 1
        assert attachments[0].original_filename == "holdings.pdf"
        assert attachments[0].status == AttachmentStatus.PENDING
        assert attachments[0].portfolio_id == sample_portfolio.id

    @pytest.mark.asyncio
    async def test_upload_files_multiple(self, holdings_import_service, sample_portfolio):
        """Test uploading multiple files"""
        # Arrange
        files = [
            (b"PDF content 1", "holdings1.pdf", "application/pdf"),
            (b"CSV content", "holdings.csv", "text/csv")
        ]

        # Act
        attachments = await holdings_import_service.upload_files(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            files=files,
            user_id=100
        )

        # Assert
        assert len(attachments) == 2
        assert attachments[0].original_filename == "holdings1.pdf"
        assert attachments[1].original_filename == "holdings.csv"

    @pytest.mark.asyncio
    async def test_upload_files_exceeds_limit(self, holdings_import_service, sample_portfolio):
        """Test that uploading more than 12 files is rejected"""
        # Arrange
        from plugins.investments.exceptions import FileValidationError
        files = [(b"content", f"file{i}.pdf", "application/pdf") for i in range(13)]

        # Act & Assert
        with pytest.raises(FileValidationError, match="Maximum 12 files"):
            await holdings_import_service.upload_files(
                portfolio_id=sample_portfolio.id,
                tenant_id=1,
                files=files,
                user_id=100
            )

    @pytest.mark.asyncio
    async def test_upload_files_portfolio_not_found(self, holdings_import_service):
        """Test that uploading to nonexistent portfolio raises error"""
        # Arrange
        files = [(b"content", "holdings.pdf", "application/pdf")]

        # Act & Assert
        with pytest.raises(NotFoundError, match="Portfolio"):
            await holdings_import_service.upload_files(
                portfolio_id=999,
                tenant_id=1,
                files=files,
                user_id=100
            )

    @pytest.mark.asyncio
    async def test_upload_files_invalid_file(self, holdings_import_service, sample_portfolio):
        """Test that invalid file is rejected"""
        # Arrange
        from plugins.investments.exceptions import FileValidationError
        holdings_import_service.file_storage_service.validate_file = Mock(
            return_value=(False, "Unsupported file format", None)
        )
        files = [(b"content", "holdings.txt", "text/plain")]

        # Act & Assert
        with pytest.raises(FileValidationError, match="Unsupported file format"):
            await holdings_import_service.upload_files(
                portfolio_id=sample_portfolio.id,
                tenant_id=1,
                files=files,
                user_id=100
            )

    def test_get_file_attachments_success(self, holdings_import_service, investment_db_session, sample_portfolio):
        """Test retrieving file attachments for a portfolio"""
        # Arrange
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="holdings.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            status=AttachmentStatus.PENDING,
            extracted_holdings_count=0,
            failed_holdings_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=100
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()

        # Act
        attachments = holdings_import_service.get_file_attachments(sample_portfolio.id, 1)

        # Assert
        assert len(attachments) == 1
        assert attachments[0].original_filename == "holdings.pdf"

    def test_get_file_attachments_portfolio_not_found(self, holdings_import_service):
        """Test that getting attachments for nonexistent portfolio raises error"""
        # Act & Assert
        with pytest.raises(NotFoundError, match="Portfolio"):
            holdings_import_service.get_file_attachments(999, 1)

    def test_get_file_attachment_success(self, holdings_import_service, investment_db_session, sample_portfolio):
        """Test retrieving a specific file attachment"""
        # Arrange
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="holdings.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            status=AttachmentStatus.COMPLETED,
            extracted_holdings_count=1,
            failed_holdings_count=0,
            extracted_data='{"holdings": []}',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=100
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()
        investment_db_session.refresh(attachment)

        # Act
        result = holdings_import_service.get_file_attachment(attachment.id, 1)

        # Assert
        assert result.id == attachment.id
        assert result.original_filename == "holdings.pdf"
        assert result.status == AttachmentStatus.COMPLETED

    def test_get_file_attachment_not_found(self, holdings_import_service):
        """Test that getting nonexistent attachment raises error"""
        # Act & Assert
        with pytest.raises(NotFoundError, match="Attachment"):
            holdings_import_service.get_file_attachment(999, 1)

    @pytest.mark.asyncio
    async def test_download_file_success(self, holdings_import_service, investment_db_session, sample_portfolio):
        """Test downloading a file"""
        # Arrange
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="holdings.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            status=AttachmentStatus.COMPLETED,
            extracted_holdings_count=1,
            failed_holdings_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=100
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()
        investment_db_session.refresh(attachment)

        # Act
        content, filename, content_type = await holdings_import_service.download_file(attachment.id, 1)

        # Assert
        assert content == b"PDF content"
        assert filename == "holdings.pdf"
        assert content_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_download_file_fixes_extension(self, holdings_import_service, investment_db_session, sample_portfolio):
        """Test that downloading file adds missing extension"""
        # Arrange
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="holdings",
            stored_filename="hf_1_abc123.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            status=AttachmentStatus.COMPLETED,
            extracted_holdings_count=1,
            failed_holdings_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=100
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()
        investment_db_session.refresh(attachment)

        # Act
        content, filename, content_type = await holdings_import_service.download_file(attachment.id, 1)

        # Assert
        assert filename == "holdings.pdf"
        assert content_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_download_file_not_found(self, holdings_import_service):
        """Test that downloading nonexistent file raises error"""
        # Act & Assert
        with pytest.raises(NotFoundError, match="Attachment"):
            await holdings_import_service.download_file(999, 1)

    def test_delete_file_attachment_success(self, holdings_import_service, investment_db_session, sample_portfolio):
        """Test deleting a file attachment"""
        # Arrange
        attachment = FileAttachment(
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="holdings.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            status=AttachmentStatus.COMPLETED,
            extracted_holdings_count=1,
            failed_holdings_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=100
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()
        investment_db_session.refresh(attachment)

        # Act
        result = holdings_import_service.delete_file_attachment(attachment.id, 1, 100)

        # Assert
        assert result is True
        holdings_import_service.file_storage_service.delete_file.assert_called_once()

    def test_delete_file_attachment_not_found(self, holdings_import_service):
        """Test that deleting nonexistent attachment raises error"""
        # Act & Assert
        with pytest.raises(NotFoundError, match="Attachment"):
            holdings_import_service.delete_file_attachment(999, 1, 100)

    def test_validate_extracted_holding_success(self, holdings_import_service):
        """Test validation of valid extracted holding"""
        # Arrange
        holding_data = {
            "security_symbol": "AAPL",
            "security_name": "Apple Inc.",
            "quantity": 100,
            "cost_basis": 15000,
            "purchase_date": "2023-01-15",
            "security_type": "stock",
            "asset_class": "stocks"
        }

        # Act & Assert - should not raise
        holdings_import_service._validate_extracted_holding(holding_data)

    def test_validate_extracted_holding_missing_field(self, holdings_import_service):
        """Test validation fails for missing required field"""
        # Arrange
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": 100,
            "purchase_date": "2023-01-15",
            "security_type": "stock",
            "asset_class": "stocks"
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Missing required fields"):
            holdings_import_service._validate_extracted_holding(holding_data)

    def test_validate_extracted_holding_negative_quantity(self, holdings_import_service):
        """Test validation fails for negative quantity"""
        # Arrange
        holding_data = {
            "security_symbol": "AAPL",
            "security_name": "Apple Inc.",
            "quantity": -100,
            "cost_basis": 15000,
            "purchase_date": "2023-01-15",
            "security_type": "stock",
            "asset_class": "stocks"
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Quantity must be positive"):
            holdings_import_service._validate_extracted_holding(holding_data)

    def test_validate_extracted_holding_negative_cost_basis(self, holdings_import_service):
        """Test validation fails for negative cost basis"""
        # Arrange
        holding_data = {
            "security_symbol": "AAPL",
            "security_name": "Apple Inc.",
            "quantity": 100,
            "cost_basis": -15000,
            "purchase_date": "2023-01-15",
            "security_type": "stock",
            "asset_class": "stocks"
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Cost basis must be positive"):
            holdings_import_service._validate_extracted_holding(holding_data)

    def test_validate_extracted_holding_invalid_security_type(self, holdings_import_service):
        """Test validation fails for invalid security type"""
        # Arrange
        holding_data = {
            "security_symbol": "AAPL",
            "security_name": "Apple Inc.",
            "quantity": 100,
            "cost_basis": 15000,
            "purchase_date": "2023-01-15",
            "security_type": "INVALID_TYPE",
            "asset_class": "STOCKS"
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid security type"):
            holdings_import_service._validate_extracted_holding(holding_data)

    def test_validate_extracted_holding_invalid_asset_class(self, holdings_import_service):
        """Test validation fails for invalid asset class"""
        # Arrange
        holding_data = {
            "security_symbol": "AAPL",
            "security_name": "Apple Inc.",
            "quantity": 100,
            "cost_basis": 15000,
            "purchase_date": "2023-01-15",
            "security_type": "stock",
            "asset_class": "invalid_class"
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid asset class"):
            holdings_import_service._validate_extracted_holding(holding_data)
