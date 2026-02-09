"""
Unit tests for Holdings Import Background Task Processing

This module tests the background task processing for portfolio holdings import,
including status transitions, error handling, and retry logic.
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
from plugins.investments.repositories.file_attachment_repository import FileAttachmentRepository
from core.exceptions.base import ValidationError, NotFoundError


class TestBackgroundTaskProcessing:
    """Test suite for background task processing"""

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

        yield session
        session.close()

    @pytest.fixture
    def sample_portfolio(self, investment_db_session):
        """Create a sample portfolio for testing"""
        portfolio = InvestmentPortfolio(
            id=1,
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        investment_db_session.add(portfolio)
        investment_db_session.commit()
        return portfolio

    @pytest.fixture
    def sample_attachment(self, investment_db_session, sample_portfolio):
        """Create a sample file attachment for testing"""
        attachment = FileAttachment(
            id=1,
            portfolio_id=sample_portfolio.id,
            tenant_id=1,
            original_filename="test_holdings.pdf",
            stored_filename="hf_1_abc123.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            local_path="/attachments/tenant_1/holdings_files/hf_1_abc123.pdf",
            status=AttachmentStatus.PENDING,
            created_by=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        investment_db_session.add(attachment)
        investment_db_session.commit()
        return attachment

    def test_attachment_status_pending_on_creation(self, investment_db_session, sample_attachment):
        """Test that attachment status is PENDING when created"""
        repo = FileAttachmentRepository(investment_db_session)
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)

        assert attachment is not None
        assert attachment.status == AttachmentStatus.PENDING

    def test_attachment_status_transitions_to_processing(self, investment_db_session, sample_attachment):
        """Test that attachment status transitions from PENDING to PROCESSING"""
        repo = FileAttachmentRepository(investment_db_session)

        # Update status to PROCESSING
        repo.update_status(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.PROCESSING
        )

        # Verify status changed
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.status == AttachmentStatus.PROCESSING

    def test_attachment_status_transitions_to_completed(self, investment_db_session, sample_attachment):
        """Test that attachment status transitions to COMPLETED"""
        repo = FileAttachmentRepository(investment_db_session)

        # Update status to COMPLETED with results
        repo.update_with_results(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.COMPLETED,
            extracted_holdings_count=5,
            failed_holdings_count=0
        )

        # Verify status changed
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.status == AttachmentStatus.COMPLETED
        assert attachment.extracted_holdings_count == 5
        assert attachment.failed_holdings_count == 0
        assert attachment.processed_at is not None

    def test_attachment_status_transitions_to_failed(self, investment_db_session, sample_attachment):
        """Test that attachment status transitions to FAILED with error message"""
        repo = FileAttachmentRepository(investment_db_session)

        # Update status to FAILED
        error_msg = "LLM extraction failed: timeout"
        repo.update_with_results(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.FAILED,
            extracted_holdings_count=0,
            failed_holdings_count=0,
            extraction_error=error_msg
        )

        # Verify status changed
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.status == AttachmentStatus.FAILED
        assert attachment.extraction_error == error_msg

    def test_attachment_status_transitions_to_partial(self, investment_db_session, sample_attachment):
        """Test that attachment status transitions to PARTIAL when some holdings fail"""
        repo = FileAttachmentRepository(investment_db_session)

        # Update status to PARTIAL
        repo.update_with_results(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.PARTIAL,
            extracted_holdings_count=3,
            failed_holdings_count=2
        )

        # Verify status changed
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.status == AttachmentStatus.PARTIAL
        assert attachment.extracted_holdings_count == 3
        assert attachment.failed_holdings_count == 2

    def test_attachment_timestamps_updated_on_status_change(self, investment_db_session, sample_attachment):
        """Test that updated_at timestamp is updated on status change"""
        repo = FileAttachmentRepository(investment_db_session)

        original_updated_at = sample_attachment.updated_at

        # Wait a moment and update status
        import time
        time.sleep(0.01)

        repo.update_status(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.PROCESSING
        )

        # Verify timestamp changed
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.updated_at > original_updated_at

    def test_attachment_processed_at_set_on_completion(self, investment_db_session, sample_attachment):
        """Test that processed_at timestamp is set when processing completes"""
        repo = FileAttachmentRepository(investment_db_session)

        # Initially processed_at should be None
        assert sample_attachment.processed_at is None

        # Update status to COMPLETED
        repo.update_with_results(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.COMPLETED,
            extracted_holdings_count=5,
            failed_holdings_count=0
        )

        # Verify processed_at is set
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.processed_at is not None

    def test_attachment_error_message_stored_on_failure(self, investment_db_session, sample_attachment):
        """Test that error message is stored when processing fails"""
        repo = FileAttachmentRepository(investment_db_session)

        # Initially extraction_error should be None
        assert sample_attachment.extraction_error is None

        # Update status to FAILED with error
        error_msg = "File format not recognized"
        repo.update_with_results(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.FAILED,
            extracted_holdings_count=0,
            failed_holdings_count=0,
            extraction_error=error_msg
        )

        # Verify error message is stored
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.extraction_error == error_msg

    def test_holdings_count_tracking(self, investment_db_session, sample_attachment):
        """Test that holdings creation counts are tracked correctly"""
        repo = FileAttachmentRepository(investment_db_session)

        # Initially counts should be 0
        assert sample_attachment.extracted_holdings_count == 0
        assert sample_attachment.failed_holdings_count == 0

        # Update with counts
        repo.update_with_results(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.PARTIAL,
            extracted_holdings_count=10,
            failed_holdings_count=2
        )

        # Verify counts are stored
        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.extracted_holdings_count == 10
        assert attachment.failed_holdings_count == 2

    @pytest.mark.asyncio
    async def test_kafka_task_publisher_publishes_task(self):
        """Test that Kafka task publisher publishes tasks correctly"""
        from plugins.investments.services.kafka_task_publisher import KafkaTaskPublisher

        with patch('plugins.investments.services.kafka_task_publisher.Producer') as mock_producer_class:
            mock_producer = MagicMock()
            mock_producer_class.return_value = mock_producer

            publisher = KafkaTaskPublisher()
            result = publisher.publish_task(
                attachment_id=1,
                tenant_id=1,
                portfolio_id=1
            )

            # Verify producer was called
            assert mock_producer.produce.called
            assert mock_producer.flush.called

    def test_status_transition_sequence(self, investment_db_session, sample_attachment):
        """Test the complete status transition sequence"""
        repo = FileAttachmentRepository(investment_db_session)

        # Start: PENDING
        assert sample_attachment.status == AttachmentStatus.PENDING

        # Transition 1: PENDING → PROCESSING
        repo.update_status(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.PROCESSING
        )

        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.status == AttachmentStatus.PROCESSING

        # Transition 2: PROCESSING → COMPLETED
        repo.update_with_results(
            sample_attachment.id,
            sample_attachment.tenant_id,
            AttachmentStatus.COMPLETED,
            extracted_holdings_count=5,
            failed_holdings_count=0
        )

        attachment = repo.get_by_id(sample_attachment.id, sample_attachment.tenant_id)
        assert attachment.status == AttachmentStatus.COMPLETED
        assert attachment.extracted_holdings_count == 5
