"""
Pydantic schemas for Inventory Attachments API

Defines request/response models for attachment operations.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class AttachmentBase(BaseModel):
    """Base schema for attachment data"""
    filename: str = Field(..., description="Original filename")
    stored_filename: str = Field(..., description="Secure stored filename")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    attachment_type: str = Field(..., description="Attachment type: 'image' or 'document'")
    document_type: Optional[str] = Field(None, description="Document type (for documents)")
    description: Optional[str] = Field(None, description="Optional description")
    alt_text: Optional[str] = Field(None, description="Accessibility text for images")
    is_primary: bool = Field(False, description="Whether this is the primary image")
    display_order: int = Field(0, description="Display order for sorting")

    # Image-specific fields
    image_width: Optional[int] = Field(None, description="Image width in pixels")
    image_height: Optional[int] = Field(None, description="Image height in pixels")
    has_thumbnail: bool = Field(False, description="Whether thumbnail exists")

    # Metadata
    uploaded_by: int = Field(..., description="User ID who uploaded")
    upload_ip: Optional[str] = Field(None, description="IP address of uploader")
    is_active: bool = Field(True, description="Whether attachment is active")

    class Config:
        from_attributes = True


class AttachmentCreate(BaseModel):
    """Schema for creating new attachments"""
    attachment_type: str = Field(..., description="Attachment type: 'image' or 'document'")
    document_type: Optional[str] = Field(None, description="Document type (for documents)")
    description: Optional[str] = Field(None, description="Optional description")

    @validator('attachment_type')
    def validate_attachment_type(cls, v):
        if v not in ['image', 'document']:
            raise ValueError('attachment_type must be "image" or "document"')
        return v

    @validator('document_type')
    def validate_document_type(cls, v):
        if v is not None:
            valid_types = ['manual', 'certificate', 'warranty', 'specification', 'invoice', 'receipt', 'other']
            if v not in valid_types:
                raise ValueError(f'document_type must be one of: {valid_types}')
        return v


class AttachmentUpdate(BaseModel):
    """Schema for updating attachment metadata"""
    description: Optional[str] = Field(None, description="Optional description")
    document_type: Optional[str] = Field(None, description="Document type (for documents)")
    alt_text: Optional[str] = Field(None, description="Accessibility text for images")
    display_order: Optional[int] = Field(None, description="Display order for sorting")

    @validator('document_type')
    def validate_document_type(cls, v):
        if v is not None:
            valid_types = ['manual', 'certificate', 'warranty', 'specification', 'invoice', 'receipt', 'other']
            if v not in valid_types:
                raise ValueError(f'document_type must be one of: {valid_types}')
        return v


class AttachmentResponse(AttachmentBase):
    """Response schema for attachment data"""
    id: int = Field(..., description="Attachment ID")
    item_id: int = Field(..., description="Inventory item ID")
    file_path: str = Field(..., description="Relative file path")
    file_hash: str = Field(..., description="SHA-256 file hash")
    thumbnail_path: Optional[str] = Field(None, description="Thumbnail file path")
    uploader_name: Optional[str] = Field(None, description="Name of uploader")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AttachmentOrder(BaseModel):
    """Schema for reordering attachments"""
    attachment_id: int = Field(..., description="Attachment ID")
    order: int = Field(..., description="New display order")


class AttachmentListResponse(BaseModel):
    """Response schema for attachment lists"""
    attachments: List[AttachmentResponse] = Field(..., description="List of attachments")
    total_count: int = Field(..., description="Total number of attachments")
    images_count: int = Field(..., description="Number of image attachments")
    documents_count: int = Field(..., description="Number of document attachments")


class StorageUsageResponse(BaseModel):
    """Response schema for storage usage statistics"""
    total_files: int = Field(..., description="Total number of files")
    total_size: int = Field(..., description="Total storage size in bytes")
    images_count: int = Field(..., description="Number of image files")
    documents_count: int = Field(..., description="Number of document files")
    images_size: int = Field(..., description="Total size of images in bytes")
    documents_size: int = Field(..., description="Total size of documents in bytes")
    usage_percentage: Optional[float] = Field(None, description="Percentage of quota used")
    quota_limit: Optional[int] = Field(None, description="Storage quota limit in bytes")


class AttachmentSearchFilters(BaseModel):
    """Schema for attachment search filters"""
    query: Optional[str] = Field(None, description="Search query for filename/description")
    attachment_type: Optional[str] = Field(None, description="Filter by attachment type")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    uploaded_by: Optional[int] = Field(None, description="Filter by uploader")
    date_from: Optional[datetime] = Field(None, description="Filter by upload date from")
    date_to: Optional[datetime] = Field(None, description="Filter by upload date to")
    has_thumbnail: Optional[bool] = Field(None, description="Filter by thumbnail availability")


class AttachmentSearchResponse(BaseModel):
    """Response schema for attachment search results"""
    results: List[AttachmentResponse] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total number of matching attachments")
    query: str = Field(..., description="Original search query")
    filters: AttachmentSearchFilters = Field(..., description="Applied filters")


class BatchUploadRequest(BaseModel):
    """Schema for batch upload requests"""
    files: List[Dict[str, Any]] = Field(..., description="List of files to upload")
    attachment_type: str = Field(..., description="Common attachment type for all files")
    document_type: Optional[str] = Field(None, description="Common document type for all files")


class BatchUploadResponse(BaseModel):
    """Response schema for batch upload results"""
    successful_uploads: List[AttachmentResponse] = Field(..., description="Successfully uploaded attachments")
    failed_uploads: List[Dict[str, Any]] = Field(..., description="Failed uploads with error details")
    total_attempted: int = Field(..., description="Total number of upload attempts")
    total_successful: int = Field(..., description="Number of successful uploads")
    total_failed: int = Field(..., description="Number of failed uploads")


class AttachmentStatsResponse(BaseModel):
    """Response schema for attachment statistics"""
    total_attachments: int = Field(..., description="Total number of attachments")
    image_attachments: int = Field(..., description="Number of image attachments")
    document_attachments: int = Field(..., description="Number of document attachments")
    total_size: int = Field(..., description="Total storage size in bytes")
    average_file_size: float = Field(..., description="Average file size in bytes")
    largest_file: Optional[Dict[str, Any]] = Field(None, description="Largest file information")
    most_recent_upload: Optional[datetime] = Field(None, description="Most recent upload timestamp")
    storage_usage_trend: List[Dict[str, Any]] = Field(default_factory=list, description="Storage usage over time")


# Error response schemas
class AttachmentErrorResponse(BaseModel):
    """Schema for attachment operation errors"""
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    attachment_id: Optional[int] = Field(None, description="Related attachment ID if applicable")


# Validation schemas
class FileValidationRequest(BaseModel):
    """Schema for file validation requests"""
    filename: str = Field(..., description="Filename to validate")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    attachment_type: str = Field(..., description="Expected attachment type")


class FileValidationResponse(BaseModel):
    """Schema for file validation responses"""
    is_valid: bool = Field(..., description="Whether file passes validation")
    errors: List[str] = Field(default_factory=list, description="Validation error messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    suggested_filename: Optional[str] = Field(None, description="Suggested secure filename")
