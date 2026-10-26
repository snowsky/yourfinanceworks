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


def _resolve_tenant_file(encoded_file_key: str):
    """Resolve every storage candidate inside the authenticated tenant root."""
    from core.models.database import get_tenant_context

    current_tenant_id = get_tenant_context()
    try:
        if isinstance(current_tenant_id, bool) or current_tenant_id is None:
            raise ValueError()
        tenant_id = int(str(current_tenant_id))
        if tenant_id <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Tenant context required")

    file_key = urllib.parse.unquote(encoded_file_key)
    parts = file_key.split('/')
    if (len(parts) < 2 or not parts[0].startswith('tenant_')
            or any(part in ('', '.', '..') for part in parts)
            or '\\' in file_key or '\x00' in file_key):
        raise HTTPException(status_code=400, detail="Invalid file key format")
    raw_tenant_id = parts[0][len('tenant_'):]
    if not raw_tenant_id.isascii() or not raw_tenant_id.isdecimal():
        raise HTTPException(status_code=400, detail="Invalid file key format")
    if int(raw_tenant_id) != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied to file from different tenant")

    base_path = Path(app_config.UPLOAD_PATH).resolve()
    tenant_root = base_path / f"tenant_{tenant_id}"
    try:
        # A tenant directory itself must not redirect to another tenant or outside storage.
        if tenant_root.is_symlink():
            raise ValueError()
        tenant_root = tenant_root.resolve()
        candidates = [tenant_root.joinpath(*parts[1:]), tenant_root / parts[-1]]
        for candidate in candidates:
            validated = validate_file_path(str(candidate), must_exist=False, base_dir=str(tenant_root))
            if Path(validated).is_file():
                return file_key, Path(validated)
    except (ValueError, OSError, RuntimeError):
        raise HTTPException(status_code=400, detail="Invalid file path")
    raise HTTPException(status_code=404, detail="File not found")


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
        file_key, path_obj = _resolve_tenant_file(encoded_file_key)
        validated_path = str(path_obj)

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
            detail="Failed to serve file"
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
        file_key, path_obj = _resolve_tenant_file(encoded_file_key)
        validated_path = str(path_obj)

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
            detail="Failed to get file info"
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