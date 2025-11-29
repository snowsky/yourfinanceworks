"""
Attachment Service for Inventory Items

Main service for attachment management operations including upload,
download, metadata management, and business logic.

Updated to use CloudStorageService for unified cloud and local storage.
"""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime, timezone
from pathlib import Path

from core.models.models_per_tenant import ItemAttachment, InventoryItem, User
from core.services.file_storage_service import file_storage_service, FileStorageResult
# from commercial.cloud_storage.service import CloudStorageService  # Moved to conditional import
# from commercial.cloud_storage.config import get_cloud_storage_config  # Moved to conditional import

logger = logging.getLogger(__name__)


class AttachmentService:
    """
    Primary service for attachment management operations.
    Handles upload, download, metadata management, and business logic.
    
    Updated to use CloudStorageService for unified cloud and local storage.
    """

    def __init__(self, db: Session):
        self.db = db
        self.file_service = file_storage_service  # Keep for backward compatibility
        self.image_service = image_processing_service
        
        # Initialize cloud storage service
        # Initialize cloud storage service
        try:
            from commercial.cloud_storage.service import CloudStorageService
            from commercial.cloud_storage.config import get_cloud_storage_config
            
            cloud_config = get_cloud_storage_config()
            self.cloud_storage_service = CloudStorageService(db, cloud_config)
            logger.info("Cloud storage service initialized successfully")
        except ImportError:
            logger.info("Commercial CloudStorageService not found, using local storage only")
            self.cloud_storage_service = None
        except Exception as e:
            logger.warning(f"Failed to initialize cloud storage service: {e}")
            self.cloud_storage_service = None

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

            # Store file using cloud storage service with fallback to local storage
            if self.cloud_storage_service:
                try:
                    storage_result = await self.cloud_storage_service.store_file(
                        file_content=file_content,
                        tenant_id=tenant_id,
                        item_id=item_id,
                        attachment_type=storage_type,
                        original_filename=original_filename,
                        user_id=user_id,
                        metadata={
                            'attachment_type': attachment_type,
                            'document_type': document_type,
                            'description': description,
                            'user_ip': user_ip
                        }
                    )
                    
                    if storage_result.success:
                        logger.info(f"File stored successfully using cloud storage: {storage_result.file_key}")
                        # For cloud storage, use the file_key as stored_filename
                        stored_filename = storage_result.file_key
                        file_path = storage_result.file_key  # Store the cloud file key as path
                        file_size = storage_result.file_size
                        content_type = storage_result.content_type
                        file_hash = None  # Cloud storage doesn't return hash directly
                    else:
                        logger.warning(f"Cloud storage failed, falling back to local: {storage_result.error_message}")
                        # Fallback to local storage
                        local_result = await self._store_file_locally(
                            file_content, tenant_id, item_id, storage_type, original_filename
                        )
                        if not local_result.success:
                            logger.error(f"Local storage fallback failed: {local_result.error_message}")
                            return None
                        stored_filename = local_result.stored_filename
                        file_path = local_result.stored_path
                        file_size = local_result.file_size
                        content_type = local_result.content_type
                        file_hash = local_result.file_hash
                        
                except Exception as e:
                    logger.error(f"Cloud storage service error: {e}")
                    # Fallback to local storage
                    local_result = await self._store_file_locally(
                        file_content, tenant_id, item_id, storage_type, original_filename
                    )
                    if not local_result.success:
                        logger.error(f"Local storage fallback failed: {local_result.error_message}")
                        return None
                    stored_filename = local_result.stored_filename
                    file_path = local_result.stored_path
                    file_size = local_result.file_size
                    content_type = local_result.content_type
                    file_hash = local_result.file_hash
            else:
                # Use local storage service directly
                local_result = await self._store_file_locally(
                    file_content, tenant_id, item_id, storage_type, original_filename
                )
                if not local_result.success:
                    logger.error(f"File storage failed: {local_result.error_message}")
                    return None
                stored_filename = local_result.stored_filename
                file_path = local_result.stored_path
                file_size = local_result.file_size
                content_type = local_result.content_type
                file_hash = local_result.file_hash

            # Process image if it's an image attachment
            processing_result = None
            if attachment_type == 'image':
                # For cloud storage, we need to handle image processing differently
                # since the file might not be locally accessible
                if self.cloud_storage_service and not file_path.startswith('/'):
                    # This is a cloud storage file key, skip image processing for now
                    # TODO: Implement cloud-based image processing
                    logger.info(f"Skipping image processing for cloud-stored file: {file_path}")
                    processing_result = None
                else:
                    # Local file, process normally
                    try:
                        safe_stored_path = validate_file_path(file_path)
                        processing_result = await self.image_service.process_image(
                            file_path=Path(safe_stored_path),
                            attachment_id=0,  # Will be set after creation
                            tenant_id=tenant_id_raw  # Use the integer tenant_id for image processing
                        )
                    except ValueError as e:
                        logger.error(f"Invalid stored path: {e}")
                        processing_result = None

            # Create attachment record
            attachment = ItemAttachment(
                item_id=item_id,
                filename=original_filename,
                stored_filename=stored_filename,
                file_path=file_path,
                file_size=file_size,
                content_type=content_type,
                file_hash=file_hash,
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
            tenant_id = str(tenant_id_raw) if tenant_id_raw else "default"

            # Delete physical files with backward compatibility for mixed storage scenarios
            if attachment.file_path:
                await self._delete_file_from_all_storage(attachment, tenant_id, user_id)

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

    async def _store_file_locally(
        self,
        file_content: bytes,
        tenant_id: str,
        item_id: int,
        storage_type: str,
        original_filename: str
    ) -> FileStorageResult:
        """
        Store file using local storage service.
        
        Args:
            file_content: File content as bytes
            tenant_id: Tenant identifier
            item_id: Item identifier
            storage_type: Storage type (images, documents)
            original_filename: Original filename
            
        Returns:
            FileStorageResult with operation details
        """
        return await self.file_service.store_file(
            file_content=file_content,
            tenant_id=tenant_id,
            item_id=item_id,
            attachment_type=storage_type,
            original_filename=original_filename
        )

    async def get_file_url(
        self,
        attachment_id: int,
        user_id: int,
        expiry_seconds: int = 3600
    ) -> Optional[str]:
        """
        Get a temporary URL for accessing an attachment file.
        Handles both cloud storage and local storage with backward compatibility.
        
        Args:
            attachment_id: Attachment ID
            user_id: User requesting the URL
            expiry_seconds: URL expiration time in seconds
            
        Returns:
            Temporary URL or None if not found
        """
        try:
            attachment = self.get_attachment_by_id(attachment_id)
            if not attachment:
                return None
            
            # Get tenant context
            tenant_id_raw = self._get_tenant_context()
            tenant_id = str(tenant_id_raw) if tenant_id_raw else "default"
            
            # Determine storage type based on file_path format
            is_cloud_file = self._is_cloud_storage_path(attachment.file_path)
            
            if is_cloud_file and self.cloud_storage_service:
                try:
                    # Try to get URL from cloud storage
                    result = await self.cloud_storage_service.retrieve_file(
                        file_key=attachment.file_path,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        generate_url=True,
                        expiry_seconds=expiry_seconds
                    )
                    
                    if result.success and result.file_url:
                        logger.debug(f"Generated cloud storage URL for attachment {attachment_id}")
                        return result.file_url
                    else:
                        logger.warning(f"Cloud storage URL generation failed: {result.error_message}")
                        
                except Exception as e:
                    logger.error(f"Cloud storage URL generation error: {e}")
            
            # Handle local storage files or fallback
            return await self._generate_local_file_url(attachment, tenant_id)
            
        except Exception as e:
            logger.error(f"Failed to get file URL for attachment {attachment_id}: {e}")
            return None

    def _is_cloud_storage_path(self, file_path: str) -> bool:
        """
        Determine if a file path represents a cloud storage file key or local path.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if it's a cloud storage file key, False if local path
        """
        if not file_path:
            return False
        
        # Local file paths start with '/' (absolute paths)
        if file_path.startswith('/'):
            return False
        
        # Cloud storage file keys typically follow pattern: tenant_X/type/filename
        # and don't start with '/' or contain drive letters (Windows)
        if file_path.startswith('tenant_') and '/' in file_path:
            return True
        
        # Windows absolute paths (C:\, D:\, etc.)
        if len(file_path) > 2 and file_path[1] == ':':
            return False
        
        # Default to cloud storage for relative paths
        return True

    async def _generate_local_file_url(self, attachment, tenant_id: str) -> Optional[str]:
        """
        Generate URL for local file access with backward compatibility.
        
        Args:
            attachment: ItemAttachment object
            tenant_id: Tenant identifier
            
        Returns:
            Local file URL or None if not accessible
        """
        try:
            # For local files, we need to construct the proper file key
            if attachment.file_path.startswith('/'):
                # This is an absolute local path - try to convert to relative key
                local_file_key = self._convert_local_path_to_key(attachment.file_path, tenant_id)
            else:
                # This might be a relative path or already a file key
                local_file_key = attachment.file_path
            
            # If we still don't have a proper key, construct from stored_filename
            if not local_file_key or not local_file_key.startswith('tenant_'):
                # Determine attachment type for path construction
                attachment_type = 'images' if attachment.attachment_type == 'image' else 'documents'
                local_file_key = f"tenant_{tenant_id}/{attachment_type}/{attachment.stored_filename}"
            
            # Generate local file serving URL
            from urllib.parse import quote
            encoded_key = quote(local_file_key, safe='')
            return f"/api/v1/files/serve/{encoded_key}"
            
        except Exception as e:
            logger.error(f"Failed to generate local file URL: {e}")
            return None

    def _convert_local_path_to_key(self, file_path: str, tenant_id: str) -> Optional[str]:
        """
        Convert absolute local file path to relative file key.
        
        Args:
            file_path: Absolute file path
            tenant_id: Tenant identifier
            
        Returns:
            Relative file key or None if conversion fails
        """
        try:
            from config import config
            base_path = Path(config.UPLOAD_PATH)
            file_path_obj = Path(file_path)
            
            # Try to make path relative to base upload path
            if file_path_obj.is_relative_to(base_path):
                relative_path = file_path_obj.relative_to(base_path)
                return str(relative_path).replace('\\', '/')
            
            # If not under base path, try to extract tenant and filename info
            path_parts = file_path_obj.parts
            for i, part in enumerate(path_parts):
                if part.startswith('tenant_'):
                    # Found tenant directory, construct key from remaining parts
                    remaining_parts = path_parts[i:]
                    return '/'.join(remaining_parts)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to convert local path to key: {e}")
            return None

    async def _delete_file_from_all_storage(self, attachment, tenant_id: str, user_id: int) -> bool:
        """
        Delete file from all possible storage locations (cloud and local).
        Handles mixed storage scenarios during migration.
        
        Args:
            attachment: ItemAttachment object
            tenant_id: Tenant identifier
            user_id: User performing deletion
            
        Returns:
            True if at least one deletion succeeded, False otherwise
        """
        deletion_success = False
        
        try:
            # Determine if this is likely a cloud storage file
            is_cloud_file = self._is_cloud_storage_path(attachment.file_path)
            
            # Try cloud storage deletion if applicable
            if is_cloud_file and self.cloud_storage_service:
                try:
                    success = await self.cloud_storage_service.delete_file(
                        file_key=attachment.file_path,
                        tenant_id=tenant_id,
                        user_id=user_id
                    )
                    if success:
                        logger.info(f"Successfully deleted file from cloud storage: {attachment.file_path}")
                        deletion_success = True
                    else:
                        logger.warning(f"Cloud storage deletion failed for: {attachment.file_path}")
                except Exception as e:
                    logger.error(f"Cloud storage deletion error: {e}")
            
            # Also try local storage deletion (for mixed scenarios or local files)
            try:
                local_deleted = await self._delete_local_file(attachment, tenant_id)
                if local_deleted:
                    logger.info(f"Successfully deleted local file for attachment {attachment.id}")
                    deletion_success = True
            except Exception as e:
                logger.error(f"Local storage deletion error: {e}")
            
            return deletion_success
            
        except Exception as e:
            logger.error(f"Error deleting file from all storage: {e}")
            return False

    async def _delete_local_file(self, attachment, tenant_id: str) -> bool:
        """
        Delete file from local storage with backward compatibility.
        
        Args:
            attachment: ItemAttachment object
            tenant_id: Tenant identifier
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            # Try direct path deletion first (for absolute paths)
            if attachment.file_path.startswith('/'):
                path = Path(attachment.file_path)
                if path.exists():
                    path.unlink()
                    logger.debug(f"Deleted file at absolute path: {attachment.file_path}")
                    return True
            
            # Try using file storage service
            try:
                await self.file_service.delete_file(attachment.file_path)
                return True
            except Exception as e:
                logger.debug(f"File service deletion failed: {e}")
            
            # Try constructing and deleting from possible paths
            from config import config
            base_path = Path(config.UPLOAD_PATH)
            
            possible_paths = []
            
            # 1. Direct relative path from base
            if not attachment.file_path.startswith('/'):
                possible_paths.append(base_path / attachment.file_path)
            
            # 2. Construct from tenant and stored_filename
            if attachment.stored_filename:
                attachment_type = 'images' if attachment.attachment_type == 'image' else 'documents'
                constructed_path = base_path / f"tenant_{tenant_id}" / attachment_type / attachment.stored_filename
                possible_paths.append(constructed_path)
            
            # Delete from each possible path
            deleted_any = False
            for path in possible_paths:
                if path.exists():
                    path.unlink()
                    logger.debug(f"Deleted file at constructed path: {path}")
                    deleted_any = True
            
            return deleted_any
            
        except Exception as e:
            logger.error(f"Error deleting local file: {e}")
            return False

    async def check_file_exists(
        self,
        attachment_id: int,
        user_id: int
    ) -> bool:
        """
        Check if an attachment file exists in storage.
        Handles both cloud storage and local storage with backward compatibility.
        
        Args:
            attachment_id: Attachment ID
            user_id: User checking the file
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            attachment = self.get_attachment_by_id(attachment_id)
            if not attachment:
                return False
            
            # Get tenant context
            tenant_id_raw = self._get_tenant_context()
            tenant_id = str(tenant_id_raw) if tenant_id_raw else "default"
            
            # Determine storage type based on file_path format
            is_cloud_file = self._is_cloud_storage_path(attachment.file_path)
            
            if is_cloud_file and self.cloud_storage_service:
                try:
                    exists, provider = await self.cloud_storage_service.file_exists(
                        file_key=attachment.file_path,
                        tenant_id=tenant_id,
                        user_id=user_id
                    )
                    if exists:
                        logger.debug(f"File exists in cloud storage ({provider}): {attachment.file_path}")
                        return True
                    else:
                        logger.debug(f"File not found in cloud storage: {attachment.file_path}")
                except Exception as e:
                    logger.error(f"Cloud storage file existence check error: {e}")
            
            # Check local storage (either as fallback or primary)
            return await self._check_local_file_exists(attachment, tenant_id)
            
        except Exception as e:
            logger.error(f"Failed to check file existence for attachment {attachment_id}: {e}")
            return False

    async def _check_local_file_exists(self, attachment, tenant_id: str) -> bool:
        """
        Check if file exists in local storage with backward compatibility.
        
        Args:
            attachment: ItemAttachment object
            tenant_id: Tenant identifier
            
        Returns:
            True if file exists locally, False otherwise
        """
        try:
            # Try direct path check first (for absolute paths)
            if attachment.file_path.startswith('/'):
                if Path(attachment.file_path).exists():
                    logger.debug(f"File exists at absolute path: {attachment.file_path}")
                    return True
            
            # Try constructing path from base directory and file_path
            from config import config
            base_path = Path(config.UPLOAD_PATH)
            
            # Handle different path formats
            possible_paths = []
            
            # 1. Direct relative path from base
            if not attachment.file_path.startswith('/'):
                possible_paths.append(base_path / attachment.file_path)
            
            # 2. Construct from tenant and stored_filename
            if attachment.stored_filename:
                attachment_type = 'images' if attachment.attachment_type == 'image' else 'documents'
                constructed_path = base_path / f"tenant_{tenant_id}" / attachment_type / attachment.stored_filename
                possible_paths.append(constructed_path)
            
            # 3. Try with original filename if stored_filename doesn't work
            if attachment.filename:
                attachment_type = 'images' if attachment.attachment_type == 'image' else 'documents'
                original_path = base_path / f"tenant_{tenant_id}" / attachment_type / attachment.filename
                possible_paths.append(original_path)
            
            # Check each possible path
            for path in possible_paths:
                if path.exists():
                    logger.debug(f"File exists at constructed path: {path}")
                    return True
            
            logger.debug(f"File not found in any local paths for attachment {attachment.id}")
            return False
            
        except Exception as e:
            logger.error(f"Error checking local file existence: {e}")
            return False

    async def resolve_file_path(self, attachment_id: int) -> Optional[Dict[str, Any]]:
        """
        Resolve the actual file path and storage location for an attachment.
        Useful for debugging mixed storage scenarios and migration issues.
        
        Args:
            attachment_id: Attachment ID
            
        Returns:
            Dictionary with file path resolution information
        """
        try:
            attachment = self.get_attachment_by_id(attachment_id)
            if not attachment:
                return None
            
            tenant_id_raw = self._get_tenant_context()
            tenant_id = str(tenant_id_raw) if tenant_id_raw else "default"
            
            is_cloud_file = self._is_cloud_storage_path(attachment.file_path)
            
            resolution_info = {
                'attachment_id': attachment_id,
                'stored_file_path': attachment.file_path,
                'stored_filename': attachment.stored_filename,
                'is_cloud_storage_path': is_cloud_file,
                'tenant_id': tenant_id,
                'storage_locations': {}
            }
            
            # Check cloud storage
            if self.cloud_storage_service:
                try:
                    exists, provider = await self.cloud_storage_service.file_exists(
                        file_key=attachment.file_path,
                        tenant_id=tenant_id,
                        user_id=0  # System check
                    )
                    resolution_info['storage_locations']['cloud'] = {
                        'exists': exists,
                        'provider': provider,
                        'file_key': attachment.file_path
                    }
                except Exception as e:
                    resolution_info['storage_locations']['cloud'] = {
                        'exists': False,
                        'error': str(e)
                    }
            
            # Check local storage
            local_exists = await self._check_local_file_exists(attachment, tenant_id)
            resolution_info['storage_locations']['local'] = {
                'exists': local_exists
            }
            
            # Add recommendations
            cloud_exists = resolution_info['storage_locations'].get('cloud', {}).get('exists', False)
            local_exists = resolution_info['storage_locations']['local']['exists']
            
            if cloud_exists and local_exists:
                resolution_info['status'] = 'mixed_storage'
                resolution_info['recommendation'] = 'File exists in both locations - migration in progress'
            elif cloud_exists:
                resolution_info['status'] = 'cloud_only'
                resolution_info['recommendation'] = 'File migrated to cloud storage'
            elif local_exists:
                resolution_info['status'] = 'local_only'
                resolution_info['recommendation'] = 'File not yet migrated to cloud storage'
            else:
                resolution_info['status'] = 'missing'
                resolution_info['recommendation'] = 'File not found in any storage location'
            
            return resolution_info
            
        except Exception as e:
            logger.error(f"Failed to resolve file path for attachment {attachment_id}: {e}")
            return {'error': str(e)}

    def _get_tenant_context(self) -> Optional[str]:
        """
        Get current tenant context

        Returns:
            Tenant ID string or None
        """
        # This should be implemented based on your tenant middleware
        # For now, return a placeholder
        try:
            from core.models.database import get_tenant_context
            return get_tenant_context()
        except Exception:
            logger.warning("Tenant context not available")
            return "default"

    async def retrieve_file_content(
        self,
        attachment_id: int,
        user_id: int
    ) -> Optional[bytes]:
        """
        Retrieve file content from storage with backward compatibility.
        Handles both cloud storage and local storage during migration scenarios.
        
        Args:
            attachment_id: Attachment ID
            user_id: User requesting the file
            
        Returns:
            File content as bytes or None if not found
        """
        try:
            attachment = self.get_attachment_by_id(attachment_id)
            if not attachment:
                return None
            
            # Get tenant context
            tenant_id_raw = self._get_tenant_context()
            tenant_id = str(tenant_id_raw) if tenant_id_raw else "default"
            
            # Determine storage type and try cloud storage first if applicable
            is_cloud_file = self._is_cloud_storage_path(attachment.file_path)
            
            if is_cloud_file and self.cloud_storage_service:
                try:
                    result = await self.cloud_storage_service.retrieve_file(
                        file_key=attachment.file_path,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        generate_url=False  # Get content, not URL
                    )
                    
                    if result.success and result.file_content:
                        logger.debug(f"Retrieved file content from cloud storage: {attachment.file_path}")
                        return result.file_content
                    else:
                        logger.warning(f"Cloud storage retrieval failed: {result.error_message}")
                        
                except Exception as e:
                    logger.error(f"Cloud storage retrieval error: {e}")
            
            # Fallback to local storage
            return await self._retrieve_local_file_content(attachment, tenant_id)
            
        except Exception as e:
            logger.error(f"Failed to retrieve file content for attachment {attachment_id}: {e}")
            return None

    async def _retrieve_local_file_content(self, attachment, tenant_id: str) -> Optional[bytes]:
        """
        Retrieve file content from local storage with backward compatibility.
        
        Args:
            attachment: ItemAttachment object
            tenant_id: Tenant identifier
            
        Returns:
            File content as bytes or None if not found
        """
        try:
            # Try direct path first (for absolute paths)
            if attachment.file_path.startswith('/'):
                path = Path(attachment.file_path)
                if path.exists():
                    return path.read_bytes()
            
            # Try constructing path from base directory
            from config import config
            base_path = Path(config.UPLOAD_PATH)
            
            # Handle different path formats
            possible_paths = []
            
            # 1. Direct relative path from base
            if not attachment.file_path.startswith('/'):
                possible_paths.append(base_path / attachment.file_path)
            
            # 2. Construct from tenant and stored_filename
            if attachment.stored_filename:
                attachment_type = 'images' if attachment.attachment_type == 'image' else 'documents'
                constructed_path = base_path / f"tenant_{tenant_id}" / attachment_type / attachment.stored_filename
                possible_paths.append(constructed_path)
            
            # Check each possible path
            for path in possible_paths:
                if path.exists():
                    logger.debug(f"Reading file content from: {path}")
                    return path.read_bytes()
            
            logger.warning(f"File not found in any local paths for attachment {attachment.id}")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving local file content: {e}")
            return None

    async def detect_migration_status(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Detect the migration status of attachments for a tenant.
        Helps identify mixed storage scenarios during migration.
        
        Args:
            tenant_id: Optional tenant ID filter
            
        Returns:
            Dictionary with migration status information
        """
        try:
            if not tenant_id:
                tenant_id_raw = self._get_tenant_context()
                if tenant_id_raw:
                    tenant_id = str(tenant_id_raw)
                else:
                    return {'error': 'No tenant context available'}
            
            # Query all active attachments for the tenant
            # Note: This assumes we can filter by tenant somehow - adjust based on your tenant model
            attachments = self.db.query(ItemAttachment).filter(
                ItemAttachment.is_active == True
            ).all()
            
            cloud_files = 0
            local_files = 0
            mixed_files = 0
            total_files = len(attachments)
            
            for attachment in attachments:
                is_cloud = self._is_cloud_storage_path(attachment.file_path)
                
                if is_cloud:
                    # Check if file also exists locally (mixed scenario)
                    local_exists = await self._check_local_file_exists(attachment, tenant_id)
                    if local_exists:
                        mixed_files += 1
                    else:
                        cloud_files += 1
                else:
                    local_files += 1
            
            migration_status = {
                'tenant_id': tenant_id,
                'total_attachments': total_files,
                'cloud_only': cloud_files,
                'local_only': local_files,
                'mixed_storage': mixed_files,
                'migration_in_progress': mixed_files > 0,
                'cloud_migration_percentage': (cloud_files + mixed_files) / total_files * 100 if total_files > 0 else 0
            }
            
            return migration_status
            
        except Exception as e:
            logger.error(f"Failed to detect migration status: {e}")
            return {'error': str(e)}

    async def get_storage_usage(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get storage usage statistics from both cloud and local storage

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

            # Get local storage usage
            local_usage = self.file_service.get_tenant_storage_usage(tenant_id)
            
            # Get cloud storage usage if available
            cloud_usage = {}
            if self.cloud_storage_service:
                try:
                    # Get cloud storage metrics
                    cloud_metrics = self.cloud_storage_service.get_operation_metrics(
                        tenant_id=tenant_id,
                        operation_type="upload"
                    )
                    
                    cloud_usage = {
                        'cloud_files_uploaded': cloud_metrics.get('total_operations', 0),
                        'cloud_total_size': cloud_metrics.get('total_file_size', 0),
                        'cloud_success_rate': cloud_metrics.get('success_rate', 0),
                        'cloud_providers_used': cloud_metrics.get('providers_used', [])
                    }
                except Exception as e:
                    logger.warning(f"Failed to get cloud storage metrics: {e}")
                    cloud_usage = {'error': 'Cloud storage metrics unavailable'}
            
            # Get migration status
            migration_status = await self.detect_migration_status(tenant_id)
            
            # Combine local and cloud usage
            combined_usage = {
                'local_storage': local_usage,
                'cloud_storage': cloud_usage,
                'migration_status': migration_status,
                'tenant_id': tenant_id
            }
            
            return combined_usage

        except Exception as e:
            logger.error(f"Failed to get storage usage: {e}")
            return {'error': str(e)}
