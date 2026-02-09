"""
Holdings Import Service

This module implements the main orchestrator for portfolio holdings import.
It coordinates file upload, storage, LLM extraction, and holdings creation.

The service provides high-level operations for:
- Uploading and validating files
- Storing files in local and cloud storage
- Creating file attachment records
- Processing files asynchronously
- Extracting holdings from files
- Creating holdings from extracted data
- Managing file attachments

The service enforces tenant isolation and proper error handling throughout
the import pipeline.
"""

import json
import logging
from typing import List, Optional, Tuple, Dict, Any
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models import (
    FileAttachment, AttachmentStatus, FileType, InvestmentHolding,
    SecurityType, AssetClass
)
from ..repositories.file_attachment_repository import FileAttachmentRepository
from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.holdings_repository import HoldingsRepository
from ..schemas import FileAttachmentResponse, FileAttachmentDetailResponse, HoldingCreate
from ..services.file_storage_service import FileStorageService
from ..services.llm_extraction_service import LLMExtractionService
from ..services.holdings_service import HoldingsService
from ..services.holdings_validator import HoldingsValidator, DuplicateHandlingMode
from ..services.kafka_task_publisher import publish_holdings_import_task
from ..exceptions import (
    FileValidationError, FileStorageError, ExtractionError,
    CloudStorageError, FileUploadError
)
from core.exceptions.base import ValidationError, NotFoundError, ForbiddenError
from core.utils.audit import log_audit_event

logger = logging.getLogger(__name__)


class HoldingsImportService:
    """
    Main orchestrator service for portfolio holdings import.

    Coordinates file upload, storage, extraction, and holdings creation.
    Enforces tenant isolation and proper error handling throughout the pipeline.

    Requirements: 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 7.1, 7.2, 7.3, 7.4, 7.5
    """

    def __init__(self, db: Session):
        """
        Initialize the holdings import service.

        Args:
            db: Database session
        """
        self.db = db
        self.file_attachment_repo = FileAttachmentRepository(db)
        self.portfolio_repo = PortfolioRepository(db)
        self.holdings_repo = HoldingsRepository(db)
        self.file_storage_service = FileStorageService(db)
        self.llm_extraction_service = LLMExtractionService(db)
        self.holdings_service = HoldingsService(db)
        self.holdings_validator = HoldingsValidator(self.holdings_repo, DuplicateHandlingMode.MERGE)

    async def upload_files(
        self,
        portfolio_id: int,
        tenant_id: int,
        files: List[Tuple[bytes, str, Optional[str]]],
        user_id: int,
        user_email: Optional[str] = None
    ) -> List[FileAttachmentResponse]:
        """
        Upload one or more files to a portfolio.

        Validates files, stores them in local and cloud storage, creates attachment
        records, and enqueues background tasks for processing.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for isolation
            files: List of tuples (file_content, original_filename, content_type)
            user_id: User ID who uploaded the files
            user_email: User email for audit logging

        Returns:
            List of FileAttachmentResponse objects

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant
            FileValidationError: If file validation fails
            FileUploadError: If file upload fails

        Requirements: 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 17.1, 17.2, 20.1, 8.1, 8.2, 8.3, 8.4, 8.5
        """
        logger.info(f"Uploading {len(files)} files to portfolio {portfolio_id}")

        try:
            # Validate portfolio exists and belongs to tenant
            portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
            if not portfolio:
                logger.warning(f"Portfolio {portfolio_id} not found for tenant {tenant_id}")
                raise NotFoundError(f"Portfolio {portfolio_id} not found")

            # Validate file count
            if len(files) > 12:
                logger.warning(f"File count {len(files)} exceeds maximum of 12")
                raise FileValidationError("Maximum 12 files can be uploaded at once")

            attachments = []

            for file_content, original_filename, content_type in files:
                try:
                    # Validate file
                    is_valid, error_msg, file_type = self.file_storage_service.validate_file(
                        file_content, original_filename, content_type
                    )

                    if not is_valid:
                        logger.warning(f"File validation failed for {original_filename}: {error_msg}")
                        raise FileValidationError(error_msg)

                    # Store file
                    try:
                        stored_filename, local_path, cloud_url = await self.file_storage_service.save_file(
                            file_content=file_content,
                            original_filename=original_filename,
                            portfolio_id=portfolio_id,
                            tenant_id=tenant_id,
                            file_type=file_type,
                            user_id=user_id
                        )
                    except Exception as e:
                        logger.error(f"File storage failed for {original_filename}: {e}")
                        raise FileStorageError(f"Failed to store file {original_filename}: {str(e)}")

                    logger.info(f"File stored: {stored_filename}")

                    # Create attachment record
                    try:
                        attachment = self.file_attachment_repo.create(
                            portfolio_id=portfolio_id,
                            tenant_id=tenant_id,
                            original_filename=original_filename,
                            stored_filename=stored_filename,
                            file_size=len(file_content),
                            file_type=file_type,
                            local_path=local_path,
                            created_by=user_id,
                            cloud_url=cloud_url
                        )
                    except Exception as e:
                        logger.error(f"Failed to create attachment record: {e}")
                        raise FileUploadError(f"Failed to create attachment record: {str(e)}")

                    logger.info(f"Attachment record created: {attachment.id}")

                    # Log file upload event (Requirement 20.1)
                    if user_email:
                        try:
                            log_audit_event(
                                db=self.db,
                                user_id=user_id,
                                user_email=user_email,
                                action="UPLOAD",
                                resource_type="holdings_file",
                                resource_id=str(attachment.id),
                                resource_name=original_filename,
                                details={
                                    "portfolio_id": portfolio_id,
                                    "file_size": len(file_content),
                                    "file_type": file_type.value,
                                    "stored_filename": stored_filename
                                },
                                status="success"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to log audit event: {e}")
                            # Continue - audit logging failure shouldn't block upload

                    # Enqueue background task for processing
                    task_published = publish_holdings_import_task(
                        attachment_id=attachment.id,
                        tenant_id=tenant_id,
                        portfolio_id=portfolio_id
                    )

                    if not task_published:
                        logger.warning(
                            f"Failed to publish background task for attachment {attachment.id}, "
                            f"but attachment record was created. Worker will process it on retry."
                        )

                    attachments.append(FileAttachmentResponse.from_orm(attachment))

                except (FileValidationError, FileStorageError, FileUploadError):
                    raise
                except Exception as e:
                    logger.error(f"Error uploading file {original_filename}: {e}")
                    raise FileUploadError(f"Failed to upload file {original_filename}: {str(e)}")

            logger.info(f"Successfully uploaded {len(attachments)} files")
            return attachments

        except (FileValidationError, FileStorageError, FileUploadError, NotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {e}")
            raise FileUploadError(f"Unexpected error during file upload: {str(e)}")

    async def process_file(
        self,
        attachment_id: int,
        tenant_id: int,
        user_email: Optional[str] = None
    ) -> FileAttachmentDetailResponse:
        """
        Process a file attachment (background task entry point).

        Extracts holdings from the file and creates holding records in the portfolio.
        Updates attachment status as processing progresses.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID for isolation
            user_email: User email for audit logging

        Returns:
            Updated FileAttachmentDetailResponse

        Raises:
            NotFoundError: If attachment doesn't exist or doesn't belong to tenant

        Requirements: 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 7.1, 7.2, 7.3, 7.4, 7.5, 20.2, 20.3, 20.4, 8.1, 8.2, 8.3, 8.4, 8.5
        """
        logger.info(f"Processing file attachment {attachment_id}")

        try:
            # Get attachment
            attachment = self.file_attachment_repo.get_by_id(attachment_id, tenant_id)
            if not attachment:
                logger.warning(f"Attachment {attachment_id} not found for tenant {tenant_id}")
                raise NotFoundError(f"Attachment {attachment_id} not found")

            try:
                # Update status to PROCESSING
                self.file_attachment_repo.update_status(
                    attachment_id, tenant_id, AttachmentStatus.PROCESSING
                )
                logger.info(f"Attachment status updated to PROCESSING")
            except Exception as e:
                logger.error(f"Failed to update attachment status: {e}")
                raise FileStorageError(f"Failed to update attachment status: {str(e)}")

            # Log extraction start event (Requirement 20.2)
            if user_email:
                try:
                    log_audit_event(
                        db=self.db,
                        user_id=attachment.created_by,
                        user_email=user_email,
                        action="EXTRACTION_START",
                        resource_type="holdings_file",
                        resource_id=str(attachment_id),
                        resource_name=attachment.original_filename,
                        details={
                            "portfolio_id": attachment.portfolio_id,
                            "file_type": attachment.file_type.value,
                            "file_size": attachment.file_size
                        },
                        status="success"
                    )
                except Exception as e:
                    logger.warning(f"Failed to log extraction start event: {e}")
                    # Continue - audit logging failure shouldn't block processing

            # Extract holdings from file
            try:
                extracted_holdings = await self.extract_holdings_from_file(
                    attachment.local_path,
                    attachment.file_type
                )
            except Exception as e:
                logger.error(f"Extraction failed: {e}")
                # Update attachment with error and return
                attachment = self.file_attachment_repo.update_with_results(
                    attachment_id,
                    tenant_id,
                    AttachmentStatus.FAILED,
                    0,
                    0,
                    extraction_error=str(e)
                )

                # Log extraction failure event
                if user_email:
                    try:
                        log_audit_event(
                            db=self.db,
                            user_id=attachment.created_by,
                            user_email=user_email,
                            action="EXTRACTION_FAILED",
                            resource_type="holdings_file",
                            resource_id=str(attachment_id),
                            resource_name=attachment.original_filename,
                            details={
                                "portfolio_id": attachment.portfolio_id,
                                "error": str(e)
                            },
                            status="error",
                            error_message=str(e)
                        )
                    except Exception as audit_e:
                        logger.warning(f"Failed to log extraction failure event: {audit_e}")

                return FileAttachmentDetailResponse.from_orm(attachment)

            logger.info(f"Extracted {len(extracted_holdings)} holdings from file")

            # Create holdings from extracted data
            try:
                created_count, failed_count = await self.create_holdings_from_extracted_data(
                    attachment.portfolio_id,
                    extracted_holdings,
                    attachment_id,
                    tenant_id,
                    user_email,
                    attachment.created_by
                )
            except Exception as e:
                logger.error(f"Failed to create holdings: {e}")
                # Update attachment with error
                attachment = self.file_attachment_repo.update_with_results(
                    attachment_id,
                    tenant_id,
                    AttachmentStatus.FAILED,
                    0,
                    len(extracted_holdings),
                    extraction_error=f"Failed to create holdings: {str(e)}"
                )

                # Log extraction failure event
                if user_email:
                    try:
                        log_audit_event(
                            db=self.db,
                            user_id=attachment.created_by,
                            user_email=user_email,
                            action="EXTRACTION_FAILED",
                            resource_type="holdings_file",
                            resource_id=str(attachment_id),
                            resource_name=attachment.original_filename,
                            details={
                                "portfolio_id": attachment.portfolio_id,
                                "error": str(e)
                            },
                            status="error",
                            error_message=str(e)
                        )
                    except Exception as audit_e:
                        logger.warning(f"Failed to log extraction failure event: {audit_e}")

                return FileAttachmentDetailResponse.from_orm(attachment)

            logger.info(f"Created {created_count} holdings, {failed_count} failed")

            # Determine final status
            if created_count == 0 and failed_count > 0:
                final_status = AttachmentStatus.FAILED
            elif created_count > 0 and failed_count > 0:
                final_status = AttachmentStatus.PARTIAL
            else:
                final_status = AttachmentStatus.COMPLETED

            # Update attachment with results
            try:
                attachment = self.file_attachment_repo.update_with_results(
                    attachment_id,
                    tenant_id,
                    final_status,
                    created_count,
                    failed_count,
                    extracted_data=json.dumps(extracted_holdings),
                    extraction_error=None
                )
            except Exception as e:
                logger.error(f"Failed to update attachment with results: {e}")
                raise FileStorageError(f"Failed to update attachment with results: {str(e)}")

            logger.info(f"Attachment processing completed with status {final_status}")

            # Log extraction completion event (Requirement 20.3)
            if user_email:
                try:
                    log_audit_event(
                        db=self.db,
                        user_id=attachment.created_by,
                        user_email=user_email,
                        action="EXTRACTION_COMPLETED",
                        resource_type="holdings_file",
                        resource_id=str(attachment_id),
                        resource_name=attachment.original_filename,
                        details={
                            "portfolio_id": attachment.portfolio_id,
                            "status": final_status.value,
                            "created_holdings": created_count,
                            "failed_holdings": failed_count,
                            "total_extracted": len(extracted_holdings)
                        },
                        status="success"
                    )
                except Exception as e:
                    logger.warning(f"Failed to log extraction completion event: {e}")
                    # Continue - audit logging failure shouldn't block processing

            return FileAttachmentDetailResponse.from_orm(attachment)

        except NotFoundError:
            raise
        except FileStorageError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing attachment {attachment_id}: {e}")
            raise FileStorageError(f"Unexpected error processing attachment: {str(e)}")

    async def extract_holdings_from_file(
        self,
        file_path: str,
        file_type: FileType
    ) -> List[Dict[str, Any]]:
        """
        Extract holdings from a file using LLM.

        Delegates to LLMExtractionService based on file type.

        Args:
            file_path: Path to the file
            file_type: Type of file (PDF or CSV)

        Returns:
            List of extracted holdings dictionaries

        Raises:
            ExtractionError: If extraction fails

        Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2, 8.3, 8.4, 8.5
        """
        logger.info(f"Extracting holdings from {file_type.value} file: {file_path}")

        try:
            if file_type == FileType.PDF:
                holdings = await self.llm_extraction_service.extract_holdings_from_pdf(file_path)
            elif file_type == FileType.CSV:
                holdings = await self.llm_extraction_service.extract_holdings_from_csv(file_path)
            else:
                logger.error(f"Unsupported file type: {file_type}")
                raise ExtractionError(f"Unsupported file type: {file_type}")

            if not holdings:
                logger.warning(f"No holdings extracted from file")
                raise ExtractionError("No holdings data found in file")

            logger.info(f"Extracted {len(holdings)} holdings")
            return holdings

        except ExtractionError:
            raise
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise ExtractionError(f"Failed to extract holdings from file: {str(e)}")

    async def create_holdings_from_extracted_data(
        self,
        portfolio_id: int,
        extracted_holdings: List[Dict[str, Any]],
        attachment_id: int,
        tenant_id: int,
        user_email: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Create holdings from extracted data.

        Validates each holding, detects duplicates, and creates holding records.
        Handles partial failures gracefully.

        Args:
            portfolio_id: Portfolio ID
            extracted_holdings: List of extracted holdings dictionaries
            attachment_id: Attachment ID (for error tracking)
            tenant_id: Tenant ID for isolation
            user_email: User email for audit logging
            user_id: User ID for audit logging

        Returns:
            Tuple of (created_count, failed_count)

        Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.1, 11.2, 11.3, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5, 20.5, 8.1, 8.2, 8.3, 8.4, 8.5
        """
        logger.info(f"Creating holdings from {len(extracted_holdings)} extracted records")

        created_count = 0
        failed_count = 0
        failed_holdings = []

        for holding_data in extracted_holdings:
            try:
                # Validate extracted holding
                try:
                    self._validate_extracted_holding(holding_data)
                except ValidationError as e:
                    failed_count += 1
                    failed_holdings.append({
                        "security_symbol": holding_data.get("security_symbol"),
                        "error": str(e)
                    })
                    logger.warning(f"Validation failed for holding: {e}")
                    continue

                # Check for duplicate and handle based on configuration
                try:
                    is_duplicate, duplicate_action = self.holdings_validator.handle_duplicate(
                        portfolio_id,
                        holding_data.get("security_symbol"),
                        Decimal(str(holding_data.get("quantity"))),
                        Decimal(str(holding_data.get("cost_basis")))
                    )

                    if is_duplicate:
                        logger.info(f"Duplicate holding detected for {holding_data.get('security_symbol')}")
                except Exception as e:
                    failed_count += 1
                    failed_holdings.append({
                        "security_symbol": holding_data.get("security_symbol"),
                        "error": f"Duplicate detection failed: {str(e)}"
                    })
                    logger.warning(f"Duplicate detection failed: {e}")
                    continue

                # Create holding
                try:
                    # Normalize enum values to lowercase
                    security_type_str = str(holding_data.get("security_type", "")).lower()
                    asset_class_str = str(holding_data.get("asset_class", "")).lower()

                    # Map LLM outputs to internal enums
                    if "equities" in asset_class_str or "stock" in asset_class_str:
                        asset_class_str = AssetClass.STOCKS.value
                    elif "fixed_income" in asset_class_str or "bond" in asset_class_str:
                        asset_class_str = AssetClass.BONDS.value
                    elif "cash" in asset_class_str:
                        asset_class_str = AssetClass.CASH.value
                    elif "real_estate" in asset_class_str or "reit" in asset_class_str:
                        asset_class_str = AssetClass.REAL_ESTATE.value
                    elif "commod" in asset_class_str:
                        asset_class_str = AssetClass.COMMODITIES.value

                    holding_create = HoldingCreate(
                        security_symbol=holding_data.get("security_symbol").upper(),
                        security_name=holding_data.get("security_name"),
                        security_type=SecurityType(security_type_str),
                        asset_class=AssetClass(asset_class_str),
                        quantity=Decimal(str(holding_data.get("quantity"))),
                        cost_basis=Decimal(str(holding_data.get("cost_basis"))),
                        purchase_date=holding_data.get("purchase_date")
                    )

                    # Create holding via holdings service
                    self.holdings_service.create_holding(tenant_id, portfolio_id, holding_create)

                    created_count += 1
                    logger.info(f"Created holding: {holding_data.get('security_symbol')}")

                except ValidationError as e:
                    failed_count += 1
                    failed_holdings.append({
                        "security_symbol": holding_data.get("security_symbol"),
                        "error": str(e)
                    })
                    logger.warning(f"Failed to create holding: {e}")

                except Exception as e:
                    failed_count += 1
                    failed_holdings.append({
                        "security_symbol": holding_data.get("security_symbol"),
                        "error": str(e)
                    })
                    logger.error(f"Error creating holding: {e}")
                    continue

                # Log holdings creation event (Requirement 20.5)
                if user_email and user_id:
                    try:
                        log_audit_event(
                            db=self.db,
                            user_id=user_id,
                            user_email=user_email,
                            action="HOLDING_CREATED",
                            resource_type="holding",
                            resource_id=str(portfolio_id),
                            resource_name=holding_data.get("security_symbol"),
                            details={
                                "portfolio_id": portfolio_id,
                                "attachment_id": attachment_id,
                                "security_symbol": holding_data.get("security_symbol"),
                                "security_name": holding_data.get("security_name"),
                                "quantity": str(holding_data.get("quantity")),
                                "cost_basis": str(holding_data.get("cost_basis")),
                                "is_duplicate": is_duplicate
                            },
                            status="success"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log holding creation event: {e}")
                        # Continue - audit logging failure shouldn't block processing

            except Exception as e:
                failed_count += 1
                failed_holdings.append({
                    "security_symbol": holding_data.get("security_symbol"),
                    "error": str(e)
                })
                logger.error(f"Unexpected error processing holding: {e}")

        logger.info(f"Holdings creation completed: {created_count} created, {failed_count} failed")

        return created_count, failed_count

    def get_file_attachments(
        self,
        portfolio_id: int,
        tenant_id: int
    ) -> List[FileAttachmentResponse]:
        """
        Get all file attachments for a portfolio.

        Args:
            portfolio_id: Portfolio ID
            tenant_id: Tenant ID for isolation

        Returns:
            List of FileAttachmentResponse objects

        Raises:
            NotFoundError: If portfolio doesn't exist or doesn't belong to tenant

        Requirements: 10.2, 10.3
        """
        logger.info(f"Getting file attachments for portfolio {portfolio_id}")

        # Validate portfolio exists and belongs to tenant
        portfolio = self.portfolio_repo.get_by_id(portfolio_id, tenant_id)
        if not portfolio:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")

        # Get attachments
        attachments = self.file_attachment_repo.get_by_portfolio(portfolio_id, tenant_id)

        return [FileAttachmentResponse.from_orm(a) for a in attachments]

    def get_file_attachment(
        self,
        attachment_id: int,
        tenant_id: int
    ) -> FileAttachmentDetailResponse:
        """
        Get details of a specific file attachment.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID for isolation

        Returns:
            FileAttachmentDetailResponse object

        Raises:
            NotFoundError: If attachment doesn't exist or doesn't belong to tenant

        Requirements: 10.3, 10.4
        """
        logger.info(f"Getting file attachment {attachment_id}")

        # Get attachment
        attachment = self.file_attachment_repo.get_by_id(attachment_id, tenant_id)
        if not attachment:
            raise NotFoundError(f"Attachment {attachment_id} not found")

        return FileAttachmentDetailResponse.from_orm(attachment)

    async def download_file(
        self,
        attachment_id: int,
        tenant_id: int
    ) -> Tuple[bytes, str, str]:
        """
        Download the original uploaded file.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID for isolation

        Returns:
            Tuple of (file_content, original_filename, content_type)

        Raises:
            NotFoundError: If attachment doesn't exist or doesn't belong to tenant
            FileStorageError: If file is not found in storage

        Requirements: 10.5, 8.1, 8.2, 8.3, 8.4, 8.5
        """
        logger.info(f"Downloading file attachment {attachment_id}")

        try:
            # Get attachment
            attachment = self.file_attachment_repo.get_by_id(attachment_id, tenant_id)
            if not attachment:
                logger.warning(f"Attachment {attachment_id} not found for tenant {tenant_id}")
                raise NotFoundError(f"Attachment {attachment_id} not found")

            # Retrieve file
            try:
                file_content = await self.file_storage_service.retrieve_file(
                    attachment.stored_filename,
                    tenant_id
                )
            except FileNotFoundError as e:
                logger.error(f"File not found in storage: {e}")
                raise FileStorageError(f"File not found in storage: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to retrieve file from storage: {e}")
                raise FileStorageError(f"Failed to retrieve file: {str(e)}")

            # Determine content type and ensure filename extension
            filename = attachment.original_filename
            content_type = "application/octet-stream"

            if attachment.file_type == FileType.PDF:
                content_type = "application/pdf"
                if not filename.lower().endswith('.pdf'):
                    filename += ".pdf"
            elif attachment.file_type == FileType.CSV:
                content_type = "text/csv"
                if not filename.lower().endswith('.csv'):
                    filename += ".csv"

            logger.info(f"File downloaded: {filename} ({content_type})")

            return file_content, filename, content_type

        except (NotFoundError, FileStorageError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {e}")
            raise FileStorageError(f"Unexpected error downloading file: {str(e)}")

    def delete_file_attachment(
        self,
        attachment_id: int,
        tenant_id: int,
        user_id: int
    ) -> bool:
        """
        Delete a file attachment and associated files.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID for isolation
            user_id: User ID performing the deletion

        Returns:
            True if deleted, False if not found

        Raises:
            NotFoundError: If attachment doesn't exist or doesn't belong to tenant

        Requirements: 14.1, 14.2, 8.1, 8.2, 8.3, 8.4, 8.5
        """
        logger.info(f"Deleting file attachment {attachment_id}")

        try:
            # Get attachment
            attachment = self.file_attachment_repo.get_by_id(attachment_id, tenant_id)
            if not attachment:
                logger.warning(f"Attachment {attachment_id} not found for tenant {tenant_id}")
                raise NotFoundError(f"Attachment {attachment_id} not found")

            # Delete file from storage (graceful degradation for cloud storage failures)
            try:
                import asyncio
                asyncio.run(self.file_storage_service.delete_file(
                    attachment.stored_filename,
                    tenant_id,
                    user_id
                ))
                logger.info(f"File deleted from storage: {attachment.stored_filename}")
            except Exception as e:
                logger.warning(f"Failed to delete file from storage: {e}")
                # Continue with database deletion even if file deletion fails
                # This implements graceful degradation for cloud storage failures

            # Delete attachment record
            try:
                deleted = self.file_attachment_repo.delete(attachment_id, tenant_id)
            except Exception as e:
                logger.error(f"Failed to delete attachment record: {e}")
                raise FileStorageError(f"Failed to delete attachment record: {str(e)}")

            logger.info(f"File attachment deleted: {attachment_id}")

            return deleted

        except (NotFoundError, FileStorageError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting file attachment: {e}")
            raise FileStorageError(f"Unexpected error deleting file attachment: {str(e)}")

    async def reprocess_file(
        self,
        attachment_id: int,
        tenant_id: int,
        user_email: Optional[str] = None
    ) -> FileAttachmentDetailResponse:
        """
        Reprocess a previously uploaded file.

        Resets status to PENDING and publishes a new processing task.
        Allows retrying failed extractions without re-uploading.

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID for isolation
            user_email: User email for audit logging

        Returns:
            Updated FileAttachmentDetailResponse

        Raises:
            NotFoundError: If attachment doesn't exist
            FileStorageError: If status update fails
        """
        logger.info(f"Reprocessing file attachment {attachment_id}")

        # Get attachment with tenant verification
        attachment = self.file_attachment_repo.get_by_id(attachment_id, tenant_id)
        if not attachment:
            logger.warning(f"Attachment {attachment_id} not found for tenant {tenant_id}")
            raise NotFoundError(f"Attachment {attachment_id} not found")

        # Update status to PENDING and clear error
        try:
            attachment = self.file_attachment_repo.update_with_results(
                attachment_id,
                tenant_id,
                AttachmentStatus.PENDING,
                0,
                0,
                extracted_data=None,
                extraction_error=None
            )
            logger.info(f"Attachment status reset to PENDING for reprocessing")
        except Exception as e:
            logger.error(f"Failed to reset attachment status: {e}")
            raise FileStorageError(f"Failed to reset attachment status: {str(e)}")

        # Log reprocess event
        if user_email:
            try:
                log_audit_event(
                    db=self.db,
                    user_id=attachment.created_by,
                    user_email=user_email,
                    action="REPROCESS",
                    resource_type="holdings_file",
                    resource_id=str(attachment_id),
                    resource_name=attachment.original_filename,
                    details={
                        "portfolio_id": attachment.portfolio_id,
                        "previous_status": str(attachment.status)
                    },
                    status="success"
                )
            except Exception as e:
                logger.warning(f"Failed to log reprocess event: {e}")

        # Republish processing task
        task_published = publish_holdings_import_task(
            attachment_id=attachment.id,
            tenant_id=tenant_id,
            portfolio_id=attachment.portfolio_id
        )

        if not task_published:
            logger.warning(f"Failed to publish reprocess task for attachment {attachment_id}")

        return FileAttachmentDetailResponse.from_orm(attachment)

    def _validate_extracted_holding(self, holding_data: Dict[str, Any]) -> None:
        """
        Validate extracted holding data using HoldingsValidator.

        Args:
            holding_data: Extracted holding dictionary

        Raises:
            ValidationError: If validation fails

        Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
        """
        # Map LLM outputs to internal enums for asset class
        # This modifies the dictionary in-place, which is desired as it's used later for creation
        asset_class_str = str(holding_data.get("asset_class", "")).lower()

        if "equities" in asset_class_str or "stock" in asset_class_str:
            holding_data["asset_class"] = AssetClass.STOCKS.value
        elif "fixed_income" in asset_class_str or "bond" in asset_class_str:
            holding_data["asset_class"] = AssetClass.BONDS.value
        elif "cash" in asset_class_str:
            holding_data["asset_class"] = AssetClass.CASH.value
        elif "real_estate" in asset_class_str or "reit" in asset_class_str:
            holding_data["asset_class"] = AssetClass.REAL_ESTATE.value
        elif "commod" in asset_class_str:
            holding_data["asset_class"] = AssetClass.COMMODITIES.value

        # Also ensure security_type is normalized to lowercase
        if "security_type" in holding_data:
            holding_data["security_type"] = str(holding_data["security_type"]).lower()

        is_valid, error_msg = self.holdings_validator.validate_holding(holding_data)
        if not is_valid:
            raise ValidationError(error_msg)
