"""
Inventory Attachments API Router

Provides RESTful API endpoints for managing inventory item attachments.
Supports file upload, download, metadata management, and image processing.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Response, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone
import os
from pathlib import Path

from models.database import get_db
from models.models_per_tenant import ItemAttachment, InventoryItem, User
from models.models import MasterUser
from services.attachment_service import AttachmentService
from routers.auth import get_current_user
from schemas.inventory_attachments import (
    AttachmentResponse,
    AttachmentCreate,
    AttachmentUpdate,
    AttachmentListResponse,
    AttachmentOrder
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/inventory/{item_id}/attachments",
    tags=["inventory-attachments"]
)

# Dependency to get attachment service
def get_attachment_service(db: Session = Depends(get_db)) -> AttachmentService:
    return AttachmentService(db)

# === Upload and Management Endpoints ===

@router.post("/", response_model=AttachmentResponse)
@router.post("", response_model=AttachmentResponse)
async def upload_attachment(
    item_id: int,
    file: UploadFile = File(...),
    attachment_type: Optional[str] = Query(None, description="Attachment type: 'image' or 'document' (auto-detected if not provided)"),
    document_type: Optional[str] = Query(None, description="Document type (for documents)"),
    description: Optional[str] = Query(None, description="Optional description"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Upload a new attachment for an inventory item

    - **file**: The file to upload
    - **attachment_type**: 'image' or 'document'
    - **document_type**: Document type (manual, certificate, warranty, etc.)
    - **description**: Optional description of the attachment
    """
    # Check user permissions
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer role cannot upload attachments"
        )

    try:
        # Auto-detect attachment type if not provided
        if not attachment_type:
            # Determine type based on MIME type
            if file.content_type and file.content_type.startswith('image/'):
                attachment_type = 'image'
            else:
                attachment_type = 'document'

        # Validate attachment type
        if attachment_type not in ['image', 'document']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="attachment_type must be 'image' or 'document'"
            )

        # Read file content
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file provided"
            )

        # Get user IP (if available from middleware)
        user_ip = getattr(current_user, 'ip_address', None)

        # Upload attachment
        attachment = await attachment_service.upload_attachment(
            item_id=item_id,
            file_content=file_content,
            original_filename=file.filename,
            attachment_type=attachment_type,
            user_id=current_user.id,
            document_type=document_type,
            description=description,
            user_ip=user_ip
        )

        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to upload attachment"
            )

        # Convert to response model
        response = AttachmentResponse.from_orm(attachment)

        # Add uploader information
        if attachment.uploader:
            response.uploader_name = f"{attachment.uploader.first_name or ''} {attachment.uploader.last_name or ''}".strip()

        logger.info(f"User {current_user.id} uploaded attachment {attachment.id} for item {item_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload attachment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload attachment"
        )


@router.get("/", response_model=List[AttachmentResponse])
@router.get("", response_model=List[AttachmentResponse])
async def get_attachments(
    item_id: int,
    attachment_type: Optional[str] = Query(None, description="Filter by attachment type"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Get all attachments for an inventory item

    - **item_id**: Inventory item ID
    - **attachment_type**: Optional filter ('image', 'document', or None for all)
    """
    try:
        # Verify item exists and user has access
        item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory item not found"
            )

        # Get attachments
        attachments = attachment_service.get_item_attachments(
            item_id=item_id,
            attachment_type=attachment_type
        )

        # Convert to response models
        responses = []
        for attachment in attachments:
            response = AttachmentResponse.from_orm(attachment)
            if attachment.uploader:
                response.uploader_name = f"{attachment.uploader.first_name or ''} {attachment.uploader.last_name or ''}".strip()
            responses.append(response)

        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get attachments for item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve attachments"
        )


@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    item_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Get a specific attachment by ID

    - **item_id**: Inventory item ID
    - **attachment_id**: Attachment ID
    """
    try:
        attachment = attachment_service.get_attachment_by_id(attachment_id)

        if not attachment or attachment.item_id != item_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found"
            )

        response = AttachmentResponse.from_orm(attachment)
        if attachment.uploader:
            response.uploader_name = f"{attachment.uploader.first_name or ''} {attachment.uploader.last_name or ''}".strip()

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get attachment {attachment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve attachment"
        )


@router.put("/{attachment_id}", response_model=AttachmentResponse)
async def update_attachment(
    item_id: int,
    attachment_id: int,
    update_data: AttachmentUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Update attachment metadata

    - **item_id**: Inventory item ID
    - **attachment_id**: Attachment ID
    - **update_data**: Fields to update (description, document_type, alt_text, display_order)
    """
    # Check user permissions
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer role cannot update attachments"
        )

    try:
        # Convert update data to dict
        metadata = update_data.dict(exclude_unset=True)

        # Update attachment
        attachment = await attachment_service.update_attachment_metadata(
            attachment_id=attachment_id,
            metadata=metadata,
            user_id=current_user.id
        )

        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found"
            )

        response = AttachmentResponse.from_orm(attachment)
        if attachment.uploader:
            response.uploader_name = f"{attachment.uploader.first_name or ''} {attachment.uploader.last_name or ''}".strip()

        logger.info(f"User {current_user.id} updated attachment {attachment_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update attachment {attachment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update attachment"
        )


@router.delete("/{attachment_id}")
async def delete_attachment(
    item_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Delete an attachment

    - **item_id**: Inventory item ID
    - **attachment_id**: Attachment ID
    """
    # Check user permissions
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer role cannot delete attachments"
        )

    try:
        success = await attachment_service.delete_attachment(
            attachment_id=attachment_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found"
            )

        logger.info(f"User {current_user.id} deleted attachment {attachment_id}")
        return {"message": "Attachment deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete attachment {attachment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment"
        )


# === Image-Specific Endpoints ===

@router.post("/{attachment_id}/set-primary", response_model=AttachmentResponse)
async def set_primary_image(
    item_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Set an image attachment as the primary image for an inventory item

    - **item_id**: Inventory item ID
    - **attachment_id**: Attachment ID of the image to set as primary
    """
    # Check user permissions
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer role cannot modify primary images"
        )

    try:
        attachment = await attachment_service.set_primary_image(
            item_id=item_id,
            attachment_id=attachment_id
        )

        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to set primary image. Attachment may not exist or may not be an image."
            )

        response = AttachmentResponse.from_orm(attachment)
        if attachment.uploader:
            response.uploader_name = f"{attachment.uploader.first_name or ''} {attachment.uploader.last_name or ''}".strip()

        logger.info(f"User {current_user.id} set attachment {attachment_id} as primary for item {item_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set primary image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set primary image"
        )


@router.post("/reorder")
async def reorder_attachments(
    item_id: int,
    orders: List[AttachmentOrder],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Reorder attachments for display

    - **item_id**: Inventory item ID
    - **orders**: List of attachment orders with attachment_id and order
    """
    # Check user permissions
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer role cannot reorder attachments"
        )

    try:
        updated_attachments = await attachment_service.reorder_attachments(
            item_id=item_id,
            attachment_orders=[order.dict() for order in orders]
        )

        # Convert to response models
        responses = []
        for attachment in updated_attachments:
            response = AttachmentResponse.from_orm(attachment)
            if attachment.uploader:
                response.uploader_name = f"{attachment.uploader.first_name or ''} {attachment.uploader.last_name or ''}".strip()
            responses.append(response)

        logger.info(f"User {current_user.id} reordered {len(responses)} attachments for item {item_id}")
        return {"message": "Attachments reordered successfully", "attachments": responses}

    except Exception as e:
        logger.error(f"Failed to reorder attachments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder attachments"
        )


@router.get("/{attachment_id}/thumbnail/{size}")
async def get_thumbnail(
    item_id: int,
    attachment_id: int,
    size: str,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Get a thumbnail image

    - **item_id**: Inventory item ID
    - **attachment_id**: Attachment ID
    - **size**: Thumbnail size (e.g., "150x150", "300x300")
    """
    try:
        attachment = attachment_service.get_attachment_by_id(attachment_id)

        if not attachment or attachment.item_id != item_id or attachment.attachment_type != 'image':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image attachment not found"
            )

        # Parse size
        try:
            width, height = map(int, size.split('x'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid size format. Use format: WIDTHxHEIGHT (e.g., 150x150)"
            )

        # For now, return the original image (thumbnail generation can be implemented later)
        if not os.path.exists(attachment.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image file not found"
            )

        # Read file and return
        with open(attachment.file_path, 'rb') as f:
            file_content = f.read()

        # Set cache headers for thumbnails
        response = Response(
            content=file_content,
            media_type=attachment.content_type or 'image/jpeg'
        )
        response.headers["Cache-Control"] = "public, max-age=86400"  # Cache for 24 hours

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thumbnail for attachment {attachment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve thumbnail"
        )


# === File Serving Endpoints ===

@router.get("/{attachment_id}/download")
async def download_attachment(
    item_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Download an attachment file

    - **item_id**: Inventory item ID
    - **attachment_id**: Attachment ID
    """
    try:
        attachment = attachment_service.get_attachment_by_id(attachment_id)

        if not attachment or attachment.item_id != item_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found"
            )

        if not os.path.exists(attachment.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on disk"
            )

        # Read file and return
        with open(attachment.file_path, 'rb') as f:
            file_content = f.read()

        # Return file with appropriate headers
        response = Response(
            content=file_content,
            media_type=attachment.content_type or 'application/octet-stream'
        )

        # Set download headers
        filename = attachment.filename or f"attachment_{attachment.id}"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        logger.info(f"User {current_user.id} downloaded attachment {attachment_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download attachment {attachment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download attachment"
        )


# === Utility Endpoints ===

@router.get("/storage/usage")
async def get_storage_usage(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Get storage usage statistics for the current tenant

    - **item_id**: Inventory item ID (used for tenant context)
    """
    try:
        usage = await attachment_service.get_storage_usage()

        return {
            "usage": usage,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get storage usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve storage usage"
        )


@router.get("/primary-image")
async def get_primary_image(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """
    Get the primary image for an inventory item

    - **item_id**: Inventory item ID
    """
    try:
        primary_image = attachment_service.get_primary_image(item_id)

        if not primary_image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No primary image found for this item"
            )

        response = AttachmentResponse.from_orm(primary_image)
        if primary_image.uploader:
            response.uploader_name = f"{primary_image.uploader.first_name or ''} {primary_image.uploader.last_name or ''}".strip()

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get primary image for item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve primary image"
        )
