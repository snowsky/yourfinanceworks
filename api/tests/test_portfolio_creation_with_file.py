"""
Tests for Portfolio Creation with File Upload Integration

This module tests the integration of file upload with portfolio creation,
ensuring that portfolios can be created with optional file attachments.
"""

import pytest
import json
from io import BytesIO
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
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
from plugins.investments.schemas import (
    PortfolioCreate,
    PortfolioResponse,
    FileAttachmentResponse,
    PortfolioWithAttachmentResponse
)
from plugins.investments.services.portfolio_service import PortfolioService
from plugins.investments.services.holdings_import_service import HoldingsImportService
from core.models.models import MasterUser
from core.models.models_per_tenant import Base as TenantBase


class TestPortfolioCreationWithFile:
    """Test suite for portfolio creation with optional file upload"""

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
        TenantBase.metadata.create_all(bind=engine)

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()

        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def sample_tenant(self, investment_db_session):
        """Create a sample tenant"""
        class MockTenant:
            id = 1
            name = "Test Tenant"
        return MockTenant()

    @pytest.fixture
    def sample_user(self, investment_db_session, sample_tenant):
        """Create a sample user"""
        class MockUser:
            id = 1
            email = "test@example.com"
            tenant_id = sample_tenant.id
            is_active = True
        return MockUser()

    @pytest.fixture
    def portfolio_service(self, investment_db_session):
        """Create a PortfolioService instance"""
        return PortfolioService(investment_db_session)

    @pytest.fixture
    def holdings_import_service(self, investment_db_session):
        """Create a HoldingsImportService instance"""
        return HoldingsImportService(investment_db_session)

    def test_portfolio_creation_without_file(self, portfolio_service, sample_tenant):
        """Test creating a portfolio without a file attachment"""
        # Arrange
        portfolio_data = PortfolioCreate(
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE
        )

        # Act
        portfolio = portfolio_service.create_portfolio(
            tenant_id=sample_tenant.id,
            portfolio_data=portfolio_data
        )

        # Assert
        assert portfolio is not None
        assert portfolio.name == "Test Portfolio"
        assert portfolio.portfolio_type == PortfolioType.TAXABLE
        assert portfolio.id is not None

    @pytest.mark.asyncio
    async def test_portfolio_creation_with_file_upload(
        self,
        investment_db_session,
        portfolio_service,
        holdings_import_service,
        sample_tenant,
        sample_user
    ):
        """Test creating a portfolio with a file attachment"""
        # Arrange
        portfolio_data = PortfolioCreate(
            name="Portfolio with File",
            portfolio_type=PortfolioType.TAXABLE
        )

        # Create portfolio first
        portfolio = portfolio_service.create_portfolio(
            tenant_id=sample_tenant.id,
            portfolio_data=portfolio_data
        )

        # Create a sample CSV file
        csv_content = b"""Symbol,Quantity,CostBasis
AAPL,100,15000
MSFT,50,12000"""

        # Mock the file storage service to avoid actual file I/O
        with patch.object(
            holdings_import_service.file_storage_service,
            'validate_file',
            return_value=(True, None, FileType.CSV)
        ):
            with patch.object(
                holdings_import_service.file_storage_service,
                'save_file',
                new_callable=AsyncMock,
                return_value=("test_file.csv", "/tmp/test_file.csv", None)
            ):
                with patch(
                    'plugins.investments.services.holdings_import_service.publish_holdings_import_task',
                    return_value=True
                ):
                    # Act
                    attachments = await holdings_import_service.upload_files(
                        portfolio_id=portfolio.id,
                        tenant_id=sample_tenant.id,
                        files=[(csv_content, "test_file.csv", "text/csv")],
                        user_id=sample_user.id
                    )

        # Assert
        assert len(attachments) == 1
        assert attachments[0].original_filename == "test_file.csv"
        assert attachments[0].file_type == FileType.CSV
        assert attachments[0].status == AttachmentStatus.PENDING
        assert attachments[0].portfolio_id == portfolio.id

    @pytest.mark.asyncio
    async def test_portfolio_creation_with_multiple_files(
        self,
        investment_db_session,
        portfolio_service,
        holdings_import_service,
        sample_tenant,
        sample_user
    ):
        """Test creating a portfolio and uploading multiple files"""
        # Arrange
        portfolio_data = PortfolioCreate(
            name="Portfolio with Multiple Files",
            portfolio_type=PortfolioType.RETIREMENT
        )

        # Create portfolio
        portfolio = portfolio_service.create_portfolio(
            tenant_id=sample_tenant.id,
            portfolio_data=portfolio_data
        )

        # Create sample files
        csv_content1 = b"Symbol,Quantity,CostBasis\nAAPL,100,15000"
        csv_content2 = b"Symbol,Quantity,CostBasis\nMSFT,50,12000"

        # Mock file storage
        with patch.object(
            holdings_import_service.file_storage_service,
            'validate_file',
            return_value=(True, None, FileType.CSV)
        ):
            with patch.object(
                holdings_import_service.file_storage_service,
                'save_file',
                new_callable=AsyncMock,
                side_effect=[
                    ("file1.csv", "/tmp/file1.csv", None),
                    ("file2.csv", "/tmp/file2.csv", None)
                ]
            ):
                with patch(
                    'plugins.investments.services.holdings_import_service.publish_holdings_import_task',
                    return_value=True
                ):
                    # Act
                    attachments = await holdings_import_service.upload_files(
                        portfolio_id=portfolio.id,
                        tenant_id=sample_tenant.id,
                        files=[
                            (csv_content1, "file1.csv", "text/csv"),
                            (csv_content2, "file2.csv", "text/csv")
                        ],
                        user_id=sample_user.id
                    )

        # Assert
        assert len(attachments) == 2
        assert attachments[0].original_filename == "file1.csv"
        assert attachments[1].original_filename == "file2.csv"

    @pytest.mark.asyncio
    async def test_portfolio_creation_file_upload_exceeds_limit(
        self,
        investment_db_session,
        portfolio_service,
        holdings_import_service,
        sample_tenant,
        sample_user
    ):
        """Test that uploading more than 12 files is rejected"""
        # Arrange
        portfolio_data = PortfolioCreate(
            name="Portfolio with Too Many Files",
            portfolio_type=PortfolioType.TAXABLE
        )

        # Create portfolio
        portfolio = portfolio_service.create_portfolio(
            tenant_id=sample_tenant.id,
            portfolio_data=portfolio_data
        )

        # Create 13 files (exceeds limit)
        files = [
            (b"content", f"file{i}.csv", "text/csv")
            for i in range(13)
        ]

        # Act & Assert
        from plugins.investments.exceptions import FileValidationError
        with pytest.raises(FileValidationError, match="Maximum 12 files"):
            await holdings_import_service.upload_files(
                portfolio_id=portfolio.id,
                tenant_id=sample_tenant.id,
                files=files,
                user_id=sample_user.id
            )

    @pytest.mark.asyncio
    async def test_portfolio_creation_file_upload_invalid_format(
        self,
        investment_db_session,
        portfolio_service,
        holdings_import_service,
        sample_tenant,
        sample_user
    ):
        """Test that uploading an invalid file format is rejected"""
        # Arrange
        portfolio_data = PortfolioCreate(
            name="Portfolio with Invalid File",
            portfolio_type=PortfolioType.TAXABLE
        )

        # Create portfolio
        portfolio = portfolio_service.create_portfolio(
            tenant_id=sample_tenant.id,
            portfolio_data=portfolio_data
        )

        # Mock file validation to return invalid
        with patch.object(
            holdings_import_service.file_storage_service,
            'validate_file',
            return_value=(False, "Unsupported file format", None)
        ):
            # Act & Assert
            from plugins.investments.exceptions import FileValidationError
            with pytest.raises(FileValidationError, match="Unsupported file format"):
                await holdings_import_service.upload_files(
                    portfolio_id=portfolio.id,
                    tenant_id=sample_tenant.id,
                    files=[(b"invalid", "test.txt", "text/plain")],
                    user_id=sample_user.id
                )

    @pytest.mark.asyncio
    async def test_portfolio_creation_file_upload_returns_immediately(
        self,
        investment_db_session,
        portfolio_service,
        holdings_import_service,
        sample_tenant,
        sample_user
    ):
        """Test that file upload returns immediately with PENDING status"""
        # Arrange
        portfolio_data = PortfolioCreate(
            name="Portfolio with Async File",
            portfolio_type=PortfolioType.TAXABLE
        )

        # Create portfolio
        portfolio = portfolio_service.create_portfolio(
            tenant_id=sample_tenant.id,
            portfolio_data=portfolio_data
        )

        csv_content = b"Symbol,Quantity,CostBasis\nAAPL,100,15000"

        # Mock file storage
        with patch.object(
            holdings_import_service.file_storage_service,
            'validate_file',
            return_value=(True, None, FileType.CSV)
        ):
            with patch.object(
                holdings_import_service.file_storage_service,
                'save_file',
                new_callable=AsyncMock,
                return_value=("test_file.csv", "/tmp/test_file.csv", None)
            ):
                with patch(
                    'plugins.investments.services.holdings_import_service.publish_holdings_import_task',
                    return_value=True
                ):
                    # Act
                    attachments = await holdings_import_service.upload_files(
                        portfolio_id=portfolio.id,
                        tenant_id=sample_tenant.id,
                        files=[(csv_content, "test_file.csv", "text/csv")],
                        user_id=sample_user.id
                    )

        # Assert - should return immediately with PENDING status
        assert len(attachments) == 1
        assert attachments[0].status == AttachmentStatus.PENDING
        assert attachments[0].extracted_holdings_count == 0
        assert attachments[0].failed_holdings_count == 0

    def test_portfolio_with_attachment_response_schema(self):
        """Test the PortfolioWithAttachmentResponse schema"""
        # Arrange
        portfolio_response = PortfolioResponse(
            id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE,
            is_archived=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        attachment_response = FileAttachmentResponse(
            id=1,
            portfolio_id=1,
            original_filename="test.csv",
            file_size=1024,
            file_type=FileType.CSV,
            status=AttachmentStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        # Act
        response = PortfolioWithAttachmentResponse(
            portfolio=portfolio_response,
            attachment=attachment_response
        )

        # Assert
        assert response.portfolio.id == 1
        assert response.attachment.id == 1
        assert response.attachment.status == AttachmentStatus.PENDING

    def test_portfolio_with_attachment_response_without_file(self):
        """Test the PortfolioWithAttachmentResponse schema without file"""
        # Arrange
        portfolio_response = PortfolioResponse(
            id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE,
            is_archived=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        # Act
        response = PortfolioWithAttachmentResponse(
            portfolio=portfolio_response,
            attachment=None
        )

        # Assert
        assert response.portfolio.id == 1
        assert response.attachment is None
