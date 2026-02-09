"""
Unit tests for File Attachment Repository

This module tests the FileAttachmentRepository class to ensure proper CRUD operations,
tenant isolation, and data integrity for file attachments used in portfolio holdings import.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone

# Import investment models and repository
from plugins.investments.models import (
    InvestmentPortfolio,
    FileAttachment,
    PortfolioType,
    FileType,
    AttachmentStatus,
    Base as InvestmentBase
)
from plugins.investments.repositories.file_attachment_repository import FileAttachmentRepository


class TestFileAttachmentRepository:
    """Test suite for FileAttachmentRepository"""

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
    def file_attachment_repository(self, investment_db_session):
        """Create a FileAttachmentRepository instance with test database session"""
        return FileAttachmentRepository(investment_db_session)

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

    @pytest.fixture
    def sample_attachment_data(self, sample_portfolio):
        """Sample file attachment data for testing"""
        return {
            "portfolio_id": sample_portfolio.id,
            "tenant_id": 1,
            "original_filename": "holdings.pdf",
            "stored_filename": "hf_1_abc123.pdf",
            "file_size": 1024000,
            "file_type": FileType.PDF,
            "local_path": "/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            "created_by": 100
        }

    def test_repository_initialization_with_none_session(self):
        """Test that repository raises error when initialized with None session"""
        with pytest.raises(ValueError, match="Database session is required"):
            FileAttachmentRepository(None)

    def test_create_attachment_success(self, file_attachment_repository, sample_attachment_data):
        """Test successful file attachment creation"""
        # Act
        attachment = file_attachment_repository.create(**sample_attachment_data)

        # Assert
        assert attachment is not None
        assert attachment.id is not None
        assert attachment.portfolio_id == sample_attachment_data["portfolio_id"]
        assert attachment.tenant_id == sample_attachment_data["tenant_id"]
        assert attachment.original_filename == sample_attachment_data["original_filename"]
        assert attachment.stored_filename == sample_attachment_data["stored_filename"]
        assert attachment.file_size == sample_attachment_data["file_size"]
        assert attachment.file_type == sample_attachment_data["file_type"]
        assert attachment.local_path == sample_attachment_data["local_path"]
        assert attachment.status == AttachmentStatus.PENDING
        assert attachment.extracted_holdings_count == 0
        assert attachment.failed_holdings_count == 0
        assert attachment.created_at is not None
        assert attachment.updated_at is not None
        assert attachment.created_by == sample_attachment_data["created_by"]

    def test_create_attachment_with_cloud_url(self, file_attachment_repository, sample_attachment_data):
        """Test creating attachment with cloud URL"""
        # Arrange
        cloud_url = "https://s3.amazonaws.com/bucket/tenant_1/holdings_files/hf_1_abc123.pdf"
        sample_attachment_data["cloud_url"] = cloud_url

        # Act
        attachment = file_attachment_repository.create(**sample_attachment_data)

        # Assert
        assert attachment.cloud_url == cloud_url

    def test_get_by_id_existing_attachment(self, file_attachment_repository, sample_attachment_data):
        """Test retrieving an existing attachment by ID"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act
        retrieved_attachment = file_attachment_repository.get_by_id(
            created_attachment.id,
            sample_attachment_data["tenant_id"]
        )

        # Assert
        assert retrieved_attachment is not None
        assert retrieved_attachment.id == created_attachment.id
        assert retrieved_attachment.original_filename == sample_attachment_data["original_filename"]

    def test_get_by_id_nonexistent_attachment(self, file_attachment_repository):
        """Test retrieving a nonexistent attachment returns None"""
        # Act
        attachment = file_attachment_repository.get_by_id(999, 1)

        # Assert
        assert attachment is None

    def test_get_by_id_wrong_tenant(self, file_attachment_repository, sample_attachment_data):
        """Test that get_by_id enforces tenant isolation"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act
        attachment = file_attachment_repository.get_by_id(created_attachment.id, 999)

        # Assert
        assert attachment is None

    def test_get_by_portfolio(self, file_attachment_repository, sample_attachment_data):
        """Test retrieving all attachments for a portfolio"""
        # Arrange
        attachment1 = file_attachment_repository.create(**sample_attachment_data)

        # Create second attachment with different filename
        data2 = sample_attachment_data.copy()
        data2["original_filename"] = "holdings2.pdf"
        data2["stored_filename"] = "hf_1_def456.pdf"
        attachment2 = file_attachment_repository.create(**data2)

        # Act
        attachments = file_attachment_repository.get_by_portfolio(
            sample_attachment_data["portfolio_id"],
            sample_attachment_data["tenant_id"]
        )

        # Assert
        assert len(attachments) == 2
        assert attachment1.id in [a.id for a in attachments]
        assert attachment2.id in [a.id for a in attachments]

    def test_get_by_portfolio_empty(self, file_attachment_repository, sample_portfolio):
        """Test retrieving attachments for portfolio with no attachments"""
        # Act
        attachments = file_attachment_repository.get_by_portfolio(sample_portfolio.id, 1)

        # Assert
        assert len(attachments) == 0

    def test_get_by_portfolio_tenant_isolation(self, file_attachment_repository, sample_attachment_data):
        """Test that get_by_portfolio enforces tenant isolation"""
        # Arrange
        file_attachment_repository.create(**sample_attachment_data)

        # Act
        attachments = file_attachment_repository.get_by_portfolio(
            sample_attachment_data["portfolio_id"],
            999  # Different tenant
        )

        # Assert
        assert len(attachments) == 0

    def test_get_by_tenant(self, file_attachment_repository, sample_attachment_data, investment_db_session):
        """Test retrieving all attachments for a tenant"""
        # Arrange
        # Create second portfolio for same tenant
        portfolio2 = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio 2",
            portfolio_type=PortfolioType.RETIREMENT,
            is_archived=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        investment_db_session.add(portfolio2)
        investment_db_session.commit()
        investment_db_session.refresh(portfolio2)

        attachment1 = file_attachment_repository.create(**sample_attachment_data)

        data2 = sample_attachment_data.copy()
        data2["portfolio_id"] = portfolio2.id
        data2["original_filename"] = "holdings2.pdf"
        data2["stored_filename"] = "hf_2_def456.pdf"
        attachment2 = file_attachment_repository.create(**data2)

        # Act
        attachments = file_attachment_repository.get_by_tenant(1)

        # Assert
        assert len(attachments) == 2
        assert attachment1.id in [a.id for a in attachments]
        assert attachment2.id in [a.id for a in attachments]

    def test_update_attachment_success(self, file_attachment_repository, sample_attachment_data):
        """Test successful attachment update"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)
        original_updated_at = created_attachment.updated_at

        # Act
        updated_attachment = file_attachment_repository.update(
            created_attachment.id,
            sample_attachment_data["tenant_id"],
            status=AttachmentStatus.COMPLETED,
            extracted_holdings_count=5
        )

        # Assert
        assert updated_attachment is not None
        assert updated_attachment.status == AttachmentStatus.COMPLETED
        assert updated_attachment.extracted_holdings_count == 5
        assert updated_attachment.updated_at >= original_updated_at

    def test_update_attachment_nonexistent(self, file_attachment_repository):
        """Test updating a nonexistent attachment returns None"""
        # Act
        attachment = file_attachment_repository.update(999, 1, status=AttachmentStatus.COMPLETED)

        # Assert
        assert attachment is None

    def test_update_attachment_prevents_portfolio_id_change(self, file_attachment_repository, sample_attachment_data):
        """Test that update prevents changing portfolio_id"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot update tenant_id or portfolio_id"):
            file_attachment_repository.update(
                created_attachment.id,
                sample_attachment_data["tenant_id"],
                portfolio_id=999
            )

    def test_delete_attachment_success(self, file_attachment_repository, sample_attachment_data):
        """Test successful attachment deletion"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act
        result = file_attachment_repository.delete(
            created_attachment.id,
            sample_attachment_data["tenant_id"]
        )

        # Assert
        assert result is True
        assert file_attachment_repository.get_by_id(created_attachment.id, sample_attachment_data["tenant_id"]) is None

    def test_delete_attachment_nonexistent(self, file_attachment_repository):
        """Test deleting a nonexistent attachment returns False"""
        # Act
        result = file_attachment_repository.delete(999, 1)

        # Assert
        assert result is False

    def test_delete_attachment_wrong_tenant(self, file_attachment_repository, sample_attachment_data):
        """Test that delete enforces tenant isolation"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act
        result = file_attachment_repository.delete(created_attachment.id, 999)

        # Assert
        assert result is False
        # Verify attachment still exists
        assert file_attachment_repository.get_by_id(created_attachment.id, sample_attachment_data["tenant_id"]) is not None

    def test_update_status_success(self, file_attachment_repository, sample_attachment_data):
        """Test successful status update"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act
        updated_attachment = file_attachment_repository.update_status(
            created_attachment.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.PROCESSING
        )

        # Assert
        assert updated_attachment is not None
        assert updated_attachment.status == AttachmentStatus.PROCESSING

    def test_update_status_with_processed_at(self, file_attachment_repository, sample_attachment_data):
        """Test status update with processed_at timestamp"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)
        processed_at = datetime.now(timezone.utc)

        # Act
        updated_attachment = file_attachment_repository.update_status(
            created_attachment.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.COMPLETED,
            processed_at=processed_at
        )

        # Assert
        assert updated_attachment is not None
        assert updated_attachment.status == AttachmentStatus.COMPLETED
        assert updated_attachment.processed_at is not None

    def test_update_with_results_success(self, file_attachment_repository, sample_attachment_data):
        """Test successful update with extraction results"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)
        extracted_data = '{"holdings": [{"symbol": "AAPL", "quantity": 100}]}'

        # Act
        updated_attachment = file_attachment_repository.update_with_results(
            created_attachment.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.COMPLETED,
            extracted_holdings_count=1,
            failed_holdings_count=0,
            extracted_data=extracted_data
        )

        # Assert
        assert updated_attachment is not None
        assert updated_attachment.status == AttachmentStatus.COMPLETED
        assert updated_attachment.extracted_holdings_count == 1
        assert updated_attachment.failed_holdings_count == 0
        assert updated_attachment.extracted_data == extracted_data
        assert updated_attachment.processed_at is not None

    def test_update_with_results_partial_failure(self, file_attachment_repository, sample_attachment_data):
        """Test update with results for partial failure"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)
        error_msg = "Some holdings failed validation"

        # Act
        updated_attachment = file_attachment_repository.update_with_results(
            created_attachment.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.PARTIAL,
            extracted_holdings_count=3,
            failed_holdings_count=2,
            extraction_error=error_msg
        )

        # Assert
        assert updated_attachment is not None
        assert updated_attachment.status == AttachmentStatus.PARTIAL
        assert updated_attachment.extracted_holdings_count == 3
        assert updated_attachment.failed_holdings_count == 2
        assert updated_attachment.extraction_error == error_msg

    def test_get_by_status(self, file_attachment_repository, sample_attachment_data):
        """Test retrieving attachments by status"""
        # Arrange
        attachment1 = file_attachment_repository.create(**sample_attachment_data)

        data2 = sample_attachment_data.copy()
        data2["original_filename"] = "holdings2.pdf"
        data2["stored_filename"] = "hf_1_def456.pdf"
        attachment2 = file_attachment_repository.create(**data2)

        # Update one to PROCESSING
        file_attachment_repository.update_status(
            attachment1.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.PROCESSING
        )

        # Act
        pending = file_attachment_repository.get_by_status(sample_attachment_data["tenant_id"], AttachmentStatus.PENDING)
        processing = file_attachment_repository.get_by_status(sample_attachment_data["tenant_id"], AttachmentStatus.PROCESSING)

        # Assert
        assert len(pending) == 1
        assert pending[0].id == attachment2.id
        assert len(processing) == 1
        assert processing[0].id == attachment1.id

    def test_get_pending_for_processing(self, file_attachment_repository, sample_attachment_data):
        """Test retrieving pending attachments for processing"""
        # Arrange
        attachment1 = file_attachment_repository.create(**sample_attachment_data)

        data2 = sample_attachment_data.copy()
        data2["original_filename"] = "holdings2.pdf"
        data2["stored_filename"] = "hf_1_def456.pdf"
        attachment2 = file_attachment_repository.create(**data2)

        # Update one to PROCESSING
        file_attachment_repository.update_status(
            attachment1.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.PROCESSING
        )

        # Act
        pending = file_attachment_repository.get_pending_for_processing(sample_attachment_data["tenant_id"])

        # Assert
        assert len(pending) == 1
        assert pending[0].id == attachment2.id

    def test_count_by_portfolio(self, file_attachment_repository, sample_attachment_data):
        """Test counting attachments for a portfolio"""
        # Arrange
        file_attachment_repository.create(**sample_attachment_data)

        data2 = sample_attachment_data.copy()
        data2["original_filename"] = "holdings2.pdf"
        data2["stored_filename"] = "hf_1_def456.pdf"
        file_attachment_repository.create(**data2)

        # Act
        count = file_attachment_repository.count_by_portfolio(
            sample_attachment_data["portfolio_id"],
            sample_attachment_data["tenant_id"]
        )

        # Assert
        assert count == 2

    def test_count_by_status(self, file_attachment_repository, sample_attachment_data):
        """Test counting attachments by status"""
        # Arrange
        attachment1 = file_attachment_repository.create(**sample_attachment_data)

        data2 = sample_attachment_data.copy()
        data2["original_filename"] = "holdings2.pdf"
        data2["stored_filename"] = "hf_1_def456.pdf"
        attachment2 = file_attachment_repository.create(**data2)

        # Update one to PROCESSING
        file_attachment_repository.update_status(
            attachment1.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.PROCESSING
        )

        # Act
        pending_count = file_attachment_repository.count_by_status(
            sample_attachment_data["tenant_id"],
            AttachmentStatus.PENDING
        )
        processing_count = file_attachment_repository.count_by_status(
            sample_attachment_data["tenant_id"],
            AttachmentStatus.PROCESSING
        )

        # Assert
        assert pending_count == 1
        assert processing_count == 1

    def test_delete_by_portfolio(self, file_attachment_repository, sample_attachment_data, investment_db_session):
        """Test cascade deletion of attachments for a portfolio"""
        # Arrange
        attachment1 = file_attachment_repository.create(**sample_attachment_data)
        attachment1_id = attachment1.id

        data2 = sample_attachment_data.copy()
        data2["original_filename"] = "holdings2.pdf"
        data2["stored_filename"] = "hf_1_def456.pdf"
        attachment2 = file_attachment_repository.create(**data2)
        attachment2_id = attachment2.id

        # Create attachment for different portfolio
        portfolio2 = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio 2",
            portfolio_type=PortfolioType.RETIREMENT,
            is_archived=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        investment_db_session.add(portfolio2)
        investment_db_session.commit()
        investment_db_session.refresh(portfolio2)

        data3 = sample_attachment_data.copy()
        data3["portfolio_id"] = portfolio2.id
        data3["original_filename"] = "holdings3.pdf"
        data3["stored_filename"] = "hf_2_ghi789.pdf"
        attachment3 = file_attachment_repository.create(**data3)
        attachment3_id = attachment3.id

        # Act
        deleted_count = file_attachment_repository.delete_by_portfolio(
            sample_attachment_data["portfolio_id"],
            sample_attachment_data["tenant_id"]
        )

        # Assert
        assert deleted_count == 2
        assert file_attachment_repository.get_by_id(attachment1_id, sample_attachment_data["tenant_id"]) is None
        assert file_attachment_repository.get_by_id(attachment2_id, sample_attachment_data["tenant_id"]) is None
        assert file_attachment_repository.get_by_id(attachment3_id, sample_attachment_data["tenant_id"]) is not None

    def test_exists_true(self, file_attachment_repository, sample_attachment_data):
        """Test exists returns True for existing attachment"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act
        exists = file_attachment_repository.exists(
            created_attachment.id,
            sample_attachment_data["tenant_id"]
        )

        # Assert
        assert exists is True

    def test_exists_false(self, file_attachment_repository):
        """Test exists returns False for nonexistent attachment"""
        # Act
        exists = file_attachment_repository.exists(999, 1)

        # Assert
        assert exists is False

    def test_validate_tenant_access_true(self, file_attachment_repository, sample_attachment_data):
        """Test validate_tenant_access returns True for valid access"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act
        has_access = file_attachment_repository.validate_tenant_access(
            created_attachment.id,
            sample_attachment_data["tenant_id"]
        )

        # Assert
        assert has_access is True

    def test_validate_tenant_access_false(self, file_attachment_repository, sample_attachment_data):
        """Test validate_tenant_access returns False for invalid access"""
        # Arrange
        created_attachment = file_attachment_repository.create(**sample_attachment_data)

        # Act
        has_access = file_attachment_repository.validate_tenant_access(
            created_attachment.id,
            999  # Different tenant
        )

        # Assert
        assert has_access is False

    def test_file_types_supported(self, file_attachment_repository, sample_attachment_data):
        """Test that both PDF and CSV file types are supported"""
        # Test PDF
        attachment_pdf = file_attachment_repository.create(**sample_attachment_data)
        assert attachment_pdf.file_type == FileType.PDF

        # Test CSV
        data_csv = sample_attachment_data.copy()
        data_csv["file_type"] = FileType.CSV
        data_csv["original_filename"] = "holdings.csv"
        data_csv["stored_filename"] = "hf_1_csv123.csv"
        attachment_csv = file_attachment_repository.create(**data_csv)
        assert attachment_csv.file_type == FileType.CSV

    def test_attachment_status_transitions(self, file_attachment_repository, sample_attachment_data):
        """Test all valid status transitions"""
        # Arrange
        attachment = file_attachment_repository.create(**sample_attachment_data)
        assert attachment.status == AttachmentStatus.PENDING

        # PENDING -> PROCESSING
        attachment = file_attachment_repository.update_status(
            attachment.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.PROCESSING
        )
        assert attachment.status == AttachmentStatus.PROCESSING

        # PROCESSING -> COMPLETED
        attachment = file_attachment_repository.update_status(
            attachment.id,
            sample_attachment_data["tenant_id"],
            AttachmentStatus.COMPLETED
        )
        assert attachment.status == AttachmentStatus.COMPLETED

    def test_attachment_ordering_by_created_at(self, file_attachment_repository, sample_attachment_data):
        """Test that attachments are ordered by created_at descending"""
        # Arrange
        attachment1 = file_attachment_repository.create(**sample_attachment_data)

        data2 = sample_attachment_data.copy()
        data2["original_filename"] = "holdings2.pdf"
        data2["stored_filename"] = "hf_1_def456.pdf"
        attachment2 = file_attachment_repository.create(**data2)

        # Act
        attachments = file_attachment_repository.get_by_portfolio(
            sample_attachment_data["portfolio_id"],
            sample_attachment_data["tenant_id"]
        )

        # Assert - most recent first
        assert attachments[0].id == attachment2.id
        assert attachments[1].id == attachment1.id
