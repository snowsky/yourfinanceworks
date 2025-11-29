"""
Utility functions for deleting files from both local and cloud storage.
"""
import os
import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def delete_file_from_storage(
    file_path: str,
    tenant_id: int,
    user_id: int,
    db: Optional[Session] = None
) -> bool:
    """
    Delete a file from both local and cloud storage.
    
    This function attempts to delete files from all available storage locations:
    1. Cloud storage (if configured)
    2. Local filesystem
    
    The function is designed to be resilient - it will attempt both deletions
    and log warnings for failures without raising exceptions.
    
    Args:
        file_path: Path to the file to delete (can be local path or cloud key)
        tenant_id: Tenant ID for cloud storage operations
        user_id: User ID for audit logging
        db: Optional database session for cloud storage service
        
    Returns:
        True if file was deleted from at least one storage location, False otherwise
        
    Example:
        >>> await delete_file_from_storage(
        ...     "attachments/tenant_1/invoice_123.pdf",
        ...     tenant_id=1,
        ...     user_id=42,
        ...     db=db_session
        ... )
        True
    """
    if not file_path:
        logger.warning("delete_file_from_storage called with empty file_path")
        return False
    
    deletion_success = False
    
    # Check if cloud storage is enabled via environment variable
    cloud_storage_enabled = os.getenv('CLOUD_STORAGE_ENABLED', 'false').lower() == 'true'
    
    # Try to delete from cloud storage first (only if enabled)
    if cloud_storage_enabled:
        try:
            from commercial.cloud_storage.service import CloudStorageService
            from commercial.cloud_storage.config import get_cloud_storage_config
            
            if db is None:
                logger.debug("No database session provided, skipping cloud storage deletion")
            else:
                cloud_config = get_cloud_storage_config()
                cloud_storage_service = CloudStorageService(db, cloud_config)
                
                # Determine if this is a cloud storage path or local path
                # Cloud storage paths: tenant_1/expenses/123_1234567890_file.pdf (no "attachments" prefix)
                # Local storage paths: attachments/tenant_1/expenses/expense_123_file_uuid.pdf (has "attachments" prefix)
                is_cloud_path = not file_path.startswith('attachments/')
                
                if is_cloud_path:
                    # Use the full file_path as the key for cloud storage
                    file_key = file_path
                    
                    cloud_deleted = await cloud_storage_service.delete_file(
                        file_key=file_key,
                        tenant_id=str(tenant_id),
                        user_id=user_id
                    )
                    if cloud_deleted:
                        logger.info(f"Successfully deleted file from cloud storage: {file_path}")
                        deletion_success = True
                    else:
                        logger.debug(f"Cloud storage deletion returned False for: {file_path}")
                else:
                    logger.debug(f"Skipping cloud deletion for local path: {file_path}")
        except ImportError:
            logger.debug("Cloud storage not available, skipping cloud deletion")
        except Exception as e:
            logger.warning(f"Failed to delete file from cloud storage: {e}")
    else:
        logger.debug("Cloud storage is disabled (CLOUD_STORAGE_ENABLED=false), skipping cloud deletion")
    
    # Try to delete from local storage
    try:
        from core.utils.file_validation import validate_file_path
        
        # Validate the file path for security
        safe_path = validate_file_path(file_path)
        
        if os.path.exists(safe_path):
            os.remove(safe_path)
            logger.info(f"Successfully deleted local file: {file_path}")
            deletion_success = True
        else:
            logger.debug(f"Local file not found (may have been deleted already): {file_path}")
    except ValueError as e:
        logger.warning(f"Invalid file path for deletion: {e}")
    except Exception as e:
        logger.warning(f"Failed to delete local file: {e}")
    
    if not deletion_success:
        logger.warning(f"File was not deleted from any storage location: {file_path}")
    
    return deletion_success


def delete_file_from_storage_sync(
    file_path: str,
    tenant_id: int,
    user_id: int,
    db: Optional[Session] = None
) -> bool:
    """
    Synchronous wrapper for delete_file_from_storage.
    
    This function provides a synchronous interface for contexts where async
    is not available. It only handles local file deletion since cloud storage
    operations require async.
    
    Args:
        file_path: Path to the file to delete
        tenant_id: Tenant ID (for logging purposes)
        user_id: User ID (for logging purposes)
        db: Optional database session (not used in sync version)
        
    Returns:
        True if file was deleted from local storage, False otherwise
        
    Note:
        This function does NOT delete from cloud storage. For full deletion
        including cloud storage, use the async version.
    """
    if not file_path:
        logger.warning("delete_file_from_storage_sync called with empty file_path")
        return False
    
    deletion_success = False
    
    # Only handle local storage in sync version
    try:
        from core.utils.file_validation import validate_file_path
        
        safe_path = validate_file_path(file_path)
        
        if os.path.exists(safe_path):
            os.remove(safe_path)
            logger.info(f"Successfully deleted local file: {file_path}")
            deletion_success = True
        else:
            logger.debug(f"Local file not found: {file_path}")
    except ValueError as e:
        logger.warning(f"Invalid file path for deletion: {e}")
    except Exception as e:
        logger.warning(f"Failed to delete local file: {e}")
    
    if not deletion_success:
        logger.warning(f"File was not deleted from local storage: {file_path}")
    
    return deletion_success
