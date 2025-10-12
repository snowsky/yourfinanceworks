"""
Attachment Service for Inventory Items

Main service for attachment management operations including upload,
download, metadata management, and business logic.
"""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime, timezone
from pathlib import Path

from models.models_per_tenant import ItemAttachment, InventoryItem, User
from services.file_storage_service import file_storage_service, FileStorageResult
from services.image_processing_service import image_processing_service, ImageProcessingResult
from services.file_security_service import file_security_service, ValidationResult
from config import config

logger = logging.getLogger(__name__)


class AttachmentService:
    """
    Primary service for attachment management operations.
    Handles upload, download, metadata management, and business logic.
    """

    def __init__(self, db: Session):
        self.db = db
        self.file_service = file_storage_service
        self.image_service = image_processing_service

    async def upload_attachment(
        self,
        item_id: int,
        file_content: bytes,
        original_filename: str,
        attachment_type: str,
        user_id: int,
        document_type: Optional[str] = None,
        description: Optional[str] = None,
        user_ip: Optional[str] = None
    ) -> Optional[ItemAttachment]:
        """
        Upload and process a new attachment with comprehensive security validation

        Args:
            item_id: Inventory item ID
            file_content: File content as bytes
            original_filename: Original filename
            attachment_type: 'image' or 'document'
            user_id: User ID who uploaded
            document_type: Document type (for documents)
            description: Optional description
            user_ip: User IP address

        Returns:
            ItemAttachment if successful, None otherwise
        """
        try:
            # Verify item exists and user has access
            item = self.db.query(InventoryItem).filter(
                and_(InventoryItem.id == item_id, InventoryItem.is_active == True)
            ).first()

            if not item:
                logger.warning(f"Inventory item {item_id} not found or inactive")
                return None

            # Security validation - map attachment type to security service format
            security_attachment_type = attachment_type + 's' if attachment_type in ['image', 'document'] else attachment_type
            logger.info(f"Performing security validation for file: {original_filename}")
            validation_result: ValidationResult = await file_security_service.validate_file(
                file_content=file_content,
                filename=original_filename,
                attachment_type=security_attachment_type,
                user_id=user_id
            )

            if not validation_result.is_valid:
                logger.warning(f"File validation failed for {original_filename}: {validation_result.errors}")
                # In a production system, you might want to log this security event
                return None

            # Log security warnings if any
            if validation_result.warnings:
                logger.warning(f"Security warnings for {original_filename}: {validation_result.warnings}")

            # Log security scan results
            if validation_result.security_result:
                security = validation_result.security_result
                logger.info(f"Security scan result for {original_filename}: safe={security.is_safe}, risk={security.risk_level}")
                if security.threats_detected:
                    logger.warning(f"Threats detected in {original_filename}: {security.threats_detected}")

            # Get tenant context (assuming middleware sets this)
            tenant_id_raw = self._get_tenant_context()
            if not tenant_id_raw:
                logger.error("No tenant context available")
                return None

            # Convert tenant ID to string for file storage
            tenant_id = str(tenant_id_raw)

            # Map attachment type to storage type
            storage_type = 'images' if attachment_type == 'image' else 'documents'

            # Store file
            storage_result = await self.file_service.store_file(
                file_content=file_content,
                tenant_id=tenant_id,
                item_id=item_id,
                attachment_type=storage_type,
                original_filename=original_filename
            )

            if not storage_result.success:
                logger.error(f"File storage failed: {storage_result.error_message}")
                return None

            # Generate secure filename for stored file
            stored_filename = storage_result.stored_filename

            # Process image if it's an image attachment
            processing_result = None
            if attachment_type == 'image':
                processing_result = await self.image_service.process_image(
                    file_path=Path(storage_result.stored_path),
                    attachment_id=0,  # Will be set after creation
                    tenant_id=tenant_id_raw  # Use the integer tenant_id for image processing
                )

            # Create attachment record
            attachment = ItemAttachment(
                item_id=item_id,
                filename=original_filename,
                stored_filename=stored_filename,
                file_path=storage_result.stored_path,
                file_size=storage_result.file_size,
                content_type=storage_result.content_type,
                file_hash=storage_result.file_hash,
                attachment_type=attachment_type,
                document_type=document_type,
                description=description,
                is_primary=False,  # Will be set later if needed
                display_order=self._get_next_display_order(item_id),
                uploaded_by=user_id,
                upload_ip=user_ip,
                is_active=True
            )

            # Set image-specific fields
            if processing_result and processing_result.success:
                attachment.image_width = processing_result.original_dimensions[0] if processing_result.original_dimensions else None
                attachment.image_height = processing_result.original_dimensions[1] if processing_result.original_dimensions else None
                attachment.has_thumbnail = len(processing_result.thumbnails or []) > 0
                if processing_result.thumbnails:
                    attachment.thumbnail_path = processing_result.thumbnails[0].path

            # Add to database
            self.db.add(attachment)
            self.db.commit()
            self.db.refresh(attachment)

            logger.info(f"Successfully created attachment {attachment.id} for item {item_id}")
            return attachment

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to upload attachment: {e}")
            return None

    async def delete_attachment(self, attachment_id: int, user_id: int) -> bool:
        """
        Delete an attachment and its files

        Args:
            attachment_id: Attachment ID
            user_id: User ID performing deletion

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Find attachment
            attachment = self.db.query(ItemAttachment).filter(
                and_(ItemAttachment.id == attachment_id, ItemAttachment.is_active == True)
            ).first()

            if not attachment:
                logger.warning(f"Attachment {attachment_id} not found or already inactive")
                return False

            # Get tenant context for cleanup
            tenant_id_raw = self._get_tenant_context()

            # Delete physical files
            if attachment.file_path:
                await self.file_service.delete_file(attachment.file_path)

            # Delete thumbnail files if they exist
            if attachment.attachment_type == 'image' and tenant_id_raw:
                await self.image_service.cleanup_thumbnails(attachment.id, tenant_id_raw)

            # Mark as inactive (soft delete)
            attachment.is_active = False
            attachment.updated_at = datetime.now(timezone.utc)

            self.db.commit()

            logger.info(f"Successfully deleted attachment {attachment_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete attachment {attachment_id}: {e}")
            return False

    async def update_attachment_metadata(
        self,
        attachment_id: int,
        metadata: Dict[str, Any],
        user_id: int
    ) -> Optional[ItemAttachment]:
        """
        Update attachment metadata (description, document type, etc.)

        Args:
            attachment_id: Attachment ID
            metadata: Dictionary of metadata to update
            user_id: User ID performing update

        Returns:
            Updated ItemAttachment if successful, None otherwise
        """
        try:
            attachment = self.db.query(ItemAttachment).filter(
                and_(ItemAttachment.id == attachment_id, ItemAttachment.is_active == True)
            ).first()

            if not attachment:
                logger.warning(f"Attachment {attachment_id} not found")
                return None

            # Update allowed fields
            allowed_fields = ['description', 'document_type', 'alt_text', 'display_order']

            for field, value in metadata.items():
                if field in allowed_fields and hasattr(attachment, field):
                    setattr(attachment, field, value)

            attachment.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(attachment)

            logger.info(f"Successfully updated attachment {attachment_id}")
            return attachment

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update attachment {attachment_id}: {e}")
            return None

    async def set_primary_image(self, item_id: int, attachment_id: int) -> Optional[ItemAttachment]:
        """
        Set an image as the primary image for an item

        Args:
            item_id: Inventory item ID
            attachment_id: Attachment ID to set as primary

        Returns:
            Updated ItemAttachment if successful, None otherwise
        """
        try:
            # Find the attachment to set as primary
            attachment = self.db.query(ItemAttachment).filter(
                and_(
                    ItemAttachment.id == attachment_id,
                    ItemAttachment.item_id == item_id,
                    ItemAttachment.attachment_type == 'image',
                    ItemAttachment.is_active == True
                )
            ).first()

            if not attachment:
                logger.warning(f"Image attachment {attachment_id} not found for item {item_id}")
                return None

            # Remove primary status from all other images for this item
            self.db.query(ItemAttachment).filter(
                and_(
                    ItemAttachment.item_id == item_id,
                    ItemAttachment.attachment_type == 'image',
                    ItemAttachment.id != attachment_id,
                    ItemAttachment.is_primary == True
                )
            ).update({'is_primary': False})

            # Set this attachment as primary
            attachment.is_primary = True
            attachment.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(attachment)

            logger.info(f"Successfully set attachment {attachment_id} as primary for item {item_id}")
            return attachment

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to set primary image: {e}")
            return None

    async def reorder_attachments(self, item_id: int, attachment_orders: List[Dict[str, int]]) -> List[ItemAttachment]:
        """
        Update display order for multiple attachments

        Args:
            item_id: Inventory item ID
            attachment_orders: List of dicts with attachment_id and order

        Returns:
            List of updated ItemAttachment objects
        """
        try:
            updated_attachments = []

            for order_info in attachment_orders:
                attachment_id = order_info.get('attachment_id')
                display_order = order_info.get('order')

                if attachment_id is None or display_order is None:
                    continue

                attachment = self.db.query(ItemAttachment).filter(
                    and_(
                        ItemAttachment.id == attachment_id,
                        ItemAttachment.item_id == item_id,
                        ItemAttachment.is_active == True
                    )
                ).first()

                if attachment:
                    attachment.display_order = display_order
                    attachment.updated_at = datetime.now(timezone.utc)
                    updated_attachments.append(attachment)

            self.db.commit()

            # Refresh all updated attachments
            for attachment in updated_attachments:
                self.db.refresh(attachment)

            logger.info(f"Successfully reordered {len(updated_attachments)} attachments for item {item_id}")
            return updated_attachments

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reorder attachments: {e}")
            return []

    def get_item_attachments(
        self,
        item_id: int,
        attachment_type: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[ItemAttachment]:
        """
        Get all attachments for an item, optionally filtered by type

        Args:
            item_id: Inventory item ID
            attachment_type: Filter by attachment type ('image', 'document', or None for all)
            include_inactive: Whether to include inactive attachments

        Returns:
            List of ItemAttachment objects
        """
        try:
            query = self.db.query(ItemAttachment).filter(ItemAttachment.item_id == item_id)

            if not include_inactive:
                query = query.filter(ItemAttachment.is_active == True)

            if attachment_type:
                query = query.filter(ItemAttachment.attachment_type == attachment_type)

            # Order by display_order, then by creation date
            attachments = query.order_by(
                ItemAttachment.display_order,
                desc(ItemAttachment.created_at)
            ).all()

            return attachments

        except Exception as e:
            logger.error(f"Failed to get attachments for item {item_id}: {e}")
            return []

    async def duplicate_check(self, file_hash: str, item_id: int) -> Optional[ItemAttachment]:
        """
        Check if file already exists for this item

        Args:
            file_hash: SHA-256 hash of file
            item_id: Inventory item ID

        Returns:
            Existing ItemAttachment if duplicate found, None otherwise
        """
        try:
            attachment = self.db.query(ItemAttachment).filter(
                and_(
                    ItemAttachment.file_hash == file_hash,
                    ItemAttachment.item_id == item_id,
                    ItemAttachment.is_active == True
                )
            ).first()

            return attachment

        except Exception as e:
            logger.error(f"Failed to check for duplicate: {e}")
            return None

    def get_attachment_by_id(self, attachment_id: int) -> Optional[ItemAttachment]:
        """
        Get attachment by ID

        Args:
            attachment_id: Attachment ID

        Returns:
            ItemAttachment if found, None otherwise
        """
        try:
            return self.db.query(ItemAttachment).filter(
                and_(ItemAttachment.id == attachment_id, ItemAttachment.is_active == True)
            ).first()
        except Exception as e:
            logger.error(f"Failed to get attachment {attachment_id}: {e}")
            return None

    def get_primary_image(self, item_id: int) -> Optional[ItemAttachment]:
        """
        Get the primary image for an item

        Args:
            item_id: Inventory item ID

        Returns:
            Primary ItemAttachment if found, None otherwise
        """
        try:
            return self.db.query(ItemAttachment).filter(
                and_(
                    ItemAttachment.item_id == item_id,
                    ItemAttachment.attachment_type == 'image',
                    ItemAttachment.is_primary == True,
                    ItemAttachment.is_active == True
                )
            ).first()
        except Exception as e:
            logger.error(f"Failed to get primary image for item {item_id}: {e}")
            return None

    def _get_next_display_order(self, item_id: int) -> int:
        """
        Get the next display order for a new attachment

        Args:
            item_id: Inventory item ID

        Returns:
            Next display order number
        """
        try:
            max_order = self.db.query(ItemAttachment.display_order).filter(
                and_(ItemAttachment.item_id == item_id, ItemAttachment.is_active == True)
            ).order_by(desc(ItemAttachment.display_order)).first()

            return (max_order[0] + 1) if max_order and max_order[0] is not None else 0

        except Exception:
            return 0

    def _get_tenant_context(self) -> Optional[str]:
        """
        Get current tenant context

        Returns:
            Tenant ID string or None
        """
        # This should be implemented based on your tenant middleware
        # For now, return a placeholder
        try:
            from models.database import get_tenant_context
            return get_tenant_context()
        except Exception:
            logger.warning("Tenant context not available")
            return "default"

    async def get_storage_usage(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get storage usage statistics

        Args:
            tenant_id: Optional tenant ID filter

        Returns:
            Dictionary with storage usage statistics
        """
        try:
            if not tenant_id:
                tenant_id_raw = self._get_tenant_context()
                if tenant_id_raw:
                    tenant_id = str(tenant_id_raw)
                else:
                    return {'error': 'No tenant context available'}
            else:
                # If tenant_id was provided as parameter, ensure it's a string
                tenant_id = str(tenant_id)

            return self.file_service.get_tenant_storage_usage(tenant_id)

        except Exception as e:
            logger.error(f"Failed to get storage usage: {e}")
            return {'error': str(e)}
