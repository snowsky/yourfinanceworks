"""
File serving router for local storage provider.

This router provides endpoints for serving files stored locally,
enabling the local storage provider to generate URLs that work
with the unified cloud storage interface.
"""

import logging
import mimetypes
import urllib.parse
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.routers.auth import get_current_user
from core.models.database import get_db
from core.models.models import MasterUser
from config import config as app_config
from core.utils.file_validation import validate_file_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/serve/{encoded_file_key}")
async def serve_file(
    encoded_file_key: str,
    inline: bool = Query(False, description="Whether to display inline or as attachment"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Serve a file from local storage.
    
    This endpoint serves files stored locally by the LocalStorageProvider,
    providing a unified interface for file access across storage providers.
    
    Args:
        encoded_file_key: URL-encoded file key (e.g., "tenant_1/images/file.jpg")
        inline: Whether to display the file inline or as an attachment
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with the requested file
    """
    try:
        # Decode the file key
        file_key = urllib.parse.unquote(encoded_file_key)
        logger.info(f"Serving file: {file_key} for user {current_user.id}")
        
        # Validate file key format and extract tenant info
        if not file_key.startswith('tenant_'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file key format"
            )
        
        # Extract tenant ID from file key
        parts = file_key.split('/')
        if len(parts) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file key format"
            )
        
        tenant_part = parts[0]  # e.g., "tenant_1"
        tenant_id = tenant_part.replace('tenant_', '')
        
        # Verify user has access to this tenant
        # This is a simplified check - in a real implementation, you'd want
        # more sophisticated tenant access validation
        from core.models.database import get_tenant_context
        current_tenant_id = get_tenant_context()
        
        if current_tenant_id and str(current_tenant_id) != tenant_id:
            logger.warning(f"User {current_user.id} attempted to access file from different tenant: {tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to file from different tenant"
            )
        
        # Construct full file path
        base_path = Path(app_config.UPLOAD_PATH)
        file_path = base_path / file_key
        
        # Validate and secure the file path
        try:
            validated_path = validate_file_path(str(file_path))
        except ValueError as e:
            logger.error(f"Invalid file path: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path"
            )
        
        # Check if file exists with fallback paths for backward compatibility
        file_path_obj = Path(validated_path)
        if not file_path_obj.exists():
            # Try alternative paths for backward compatibility
            base_path = Path(app_config.UPLOAD_PATH)
            
            # Try different possible locations
            alternative_paths = [
                base_path / file_key,  # Direct relative path
                base_path / f"tenant_{tenant_id}" / Path(file_key).name,  # Flat structure fallback
            ]
            
            found_path = None
            for alt_path in alternative_paths:
                if alt_path.exists():
                    found_path = alt_path
                    break
            
            if found_path:
                validated_path = str(found_path)
                logger.info(f"File found at alternative path: {validated_path}")
            else:
                logger.warning(f"File not found: {file_key}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(validated_path)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # Get filename for response
        filename = Path(validated_path).name
        
        # Prepare response headers
        if inline:
            headers = {"Content-Disposition": f"inline; filename=\"{filename}\""}
            return FileResponse(
                path=validated_path, 
                media_type=content_type, 
                headers=headers
            )
        else:
            return FileResponse(
                path=validated_path, 
                media_type=content_type, 
                filename=filename
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {encoded_file_key}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve file: {str(e)}"
        )


@router.get("/info/{encoded_file_key}")
async def get_file_info(
    encoded_file_key: str,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get information about a file without downloading it.
    
    Args:
        encoded_file_key: URL-encoded file key
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary with file information
    """
    try:
        # Decode the file key
        file_key = urllib.parse.unquote(encoded_file_key)
        
        # Validate file key format and extract tenant info
        if not file_key.startswith('tenant_'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file key format"
            )
        
        # Extract tenant ID from file key
        parts = file_key.split('/')
        if len(parts) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file key format"
            )
        
        tenant_part = parts[0]
        tenant_id = tenant_part.replace('tenant_', '')
        
        # Verify user has access to this tenant
        from core.models.database import get_tenant_context
        current_tenant_id = get_tenant_context()
        
        if current_tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to file from different tenant"
            )
        
        # Construct full file path
        base_path = Path(app_config.UPLOAD_PATH)
        file_path = base_path / file_key
        
        # Validate file path
        try:
            validated_path = validate_file_path(str(file_path))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path"
            )
        
        # Check if file exists
        path_obj = Path(validated_path)
        if not path_obj.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Get file information
        stat = path_obj.stat()
        content_type, _ = mimetypes.guess_type(validated_path)
        
        return {
            "file_key": file_key,
            "filename": path_obj.name,
            "size": stat.st_size,
            "content_type": content_type,
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
            "exists": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info for {encoded_file_key}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file info: {str(e)}"
        )


@router.get("/migration-status")
async def get_migration_status(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get file migration status for the current tenant.
    Useful for monitoring migration progress and identifying mixed storage scenarios.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary with migration status information
    """
    try:
        from core.services.attachment_service import AttachmentService
        
        attachment_service = AttachmentService(db)
        migration_status = await attachment_service.detect_migration_status()
        
        return {
            "migration_status": migration_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting migration status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration status: {str(e)}"
        )