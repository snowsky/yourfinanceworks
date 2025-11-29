"""
Utility functions for bulk file deletion operations.

This module provides optimized bulk deletion for scenarios where many files
need to be deleted at once, such as tenant deletion or bulk invoice/expense cleanup.
"""
import os
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def bulk_delete_by_prefix(
    prefix: str,
    tenant_id: int,
    user_id: int,
    db: Optional[Session] = None
) -> bool:
    """
    Delete all files with a given prefix using folder deletion.
    
    This is optimized for bulk operations where many files share a common prefix.
    Much faster than deleting files individually when dealing with hundreds or
    thousands of files.
    
    Args:
        prefix: Common prefix for files to delete (e.g., "tenant_1/invoices/")
        tenant_id: Tenant ID for cloud storage operations
        user_id: User ID for audit logging
        db: Optional database session for cloud storage service
        
    Returns:
        True if files were deleted successfully, False otherwise
        
    Example:
        >>> # Delete all invoice files for a tenant
        >>> await bulk_delete_by_prefix(
        ...     prefix="tenant_1/invoices/",
        ...     tenant_id=1,
        ...     user_id=42,
        ...     db=db_session
        ... )
        True
    """
    if not prefix:
        logger.warning("bulk_delete_by_prefix called with empty prefix")
        return False
    
    deletion_success = False
    
    # Check if cloud storage is enabled
    cloud_storage_enabled = os.getenv('CLOUD_STORAGE_ENABLED', 'false').lower() == 'true'
    
    # Try to delete from cloud storage using folder deletion
    if cloud_storage_enabled and db:
        try:
            from commercial.cloud_storage.service import CloudStorageService
            from commercial.cloud_storage.config import get_cloud_storage_config
            
            cloud_config = get_cloud_storage_config()
            cloud_storage_service = CloudStorageService(db, cloud_config)
            
            # Use folder deletion for efficient bulk deletion
            cloud_deleted = await cloud_storage_service.delete_folder(
                folder_prefix=prefix,
                tenant_id=str(tenant_id)
            )
            
            if cloud_deleted:
                logger.info(f"Successfully deleted files with prefix from cloud storage: {prefix}")
                deletion_success = True
            else:
                logger.warning(f"Cloud storage folder deletion returned False for prefix: {prefix}")
                
        except ImportError:
            logger.debug("Cloud storage not available, skipping cloud deletion")
        except Exception as e:
            logger.warning(f"Failed to delete folder from cloud storage: {e}")
    else:
        logger.debug("Cloud storage is disabled or no DB session, skipping cloud deletion")
    
    # Try to delete from local storage
    # Note: Local storage doesn't have efficient folder deletion, so we skip it
    # Individual files should be deleted through normal delete_file_from_storage
    
    return deletion_success


async def bulk_delete_tenant_files(
    tenant_id: int,
    user_id: int,
    db: Optional[Session] = None,
    file_types: Optional[List[str]] = None
) -> dict:
    """
    Delete all files for a tenant across all file types.
    
    This is useful for tenant deletion or data cleanup operations.
    
    Args:
        tenant_id: Tenant ID to delete files for
        user_id: User ID for audit logging
        db: Optional database session for cloud storage service
        file_types: Optional list of file types to delete (e.g., ["invoices", "expenses"])
                   If None, deletes all types
        
    Returns:
        Dictionary with deletion results per file type
        
    Example:
        >>> # Delete all files for a tenant
        >>> results = await bulk_delete_tenant_files(
        ...     tenant_id=1,
        ...     user_id=42,
        ...     db=db_session
        ... )
        >>> print(results)
        {'invoices': True, 'expenses': True, 'batch_files': True}
    """
    if file_types is None:
        file_types = ["invoices", "expenses", "images", "documents"]
    
    results = {}
    
    for file_type in file_types:
        prefix = f"tenant_{tenant_id}/{file_type}/"
        
        try:
            success = await bulk_delete_by_prefix(
                prefix=prefix,
                tenant_id=tenant_id,
                user_id=user_id,
                db=db
            )
            results[file_type] = success
            
            if success:
                logger.info(f"Successfully deleted {file_type} files for tenant {tenant_id}")
            else:
                logger.warning(f"Failed to delete {file_type} files for tenant {tenant_id}")
                
        except Exception as e:
            logger.error(f"Error deleting {file_type} files for tenant {tenant_id}: {e}")
            results[file_type] = False
    
    # Also delete batch files if they exist
    try:
        batch_prefix = f"api/batch_files/tenant_{tenant_id}/"
        batch_success = await bulk_delete_by_prefix(
            prefix=batch_prefix,
            tenant_id=tenant_id,
            user_id=user_id,
            db=db
        )
        results["batch_files"] = batch_success
    except Exception as e:
        logger.error(f"Error deleting batch files for tenant {tenant_id}: {e}")
        results["batch_files"] = False
    
    return results


async def bulk_delete_invoice_files(
    invoice_ids: List[int],
    tenant_id: int,
    user_id: int,
    db: Session
) -> int:
    """
    Delete all attachment files for multiple invoices.
    
    This is optimized for bulk operations but still uses individual file deletion
    since invoice files don't share a common prefix (each has a unique timestamp).
    
    Args:
        invoice_ids: List of invoice IDs to delete files for
        tenant_id: Tenant ID for cloud storage operations
        user_id: User ID for audit logging
        db: Database session
        
    Returns:
        Number of files successfully deleted
        
    Example:
        >>> # Delete files for multiple invoices
        >>> deleted_count = await bulk_delete_invoice_files(
        ...     invoice_ids=[1, 2, 3, 4, 5],
        ...     tenant_id=1,
        ...     user_id=42,
        ...     db=db_session
        ... )
        >>> print(f"Deleted {deleted_count} files")
    """
    from core.models.models_per_tenant import InvoiceAttachment
    from core.utils.file_deletion import delete_file_from_storage
    
    deleted_count = 0
    
    # Get all attachments for these invoices
    attachments = db.query(InvoiceAttachment).filter(
        InvoiceAttachment.invoice_id.in_(invoice_ids)
    ).all()
    
    # Delete each attachment
    for att in attachments:
        if att.file_path:
            try:
                success = await delete_file_from_storage(
                    att.file_path,
                    tenant_id,
                    user_id,
                    db
                )
                if success:
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete attachment {att.file_path}: {e}")
    
    logger.info(f"Deleted {deleted_count} attachment files for {len(invoice_ids)} invoices")
    return deleted_count


async def bulk_delete_expense_files(
    expense_ids: List[int],
    tenant_id: int,
    user_id: int,
    db: Session
) -> int:
    """
    Delete all attachment files for multiple expenses.
    
    This is optimized for bulk operations but still uses individual file deletion
    since expense files don't share a common prefix (each has a unique timestamp).
    
    Args:
        expense_ids: List of expense IDs to delete files for
        tenant_id: Tenant ID for cloud storage operations
        user_id: User ID for audit logging
        db: Database session
        
    Returns:
        Number of files successfully deleted
        
    Example:
        >>> # Delete files for multiple expenses
        >>> deleted_count = await bulk_delete_expense_files(
        ...     expense_ids=[1, 2, 3, 4, 5],
        ...     tenant_id=1,
        ...     user_id=42,
        ...     db=db_session
        ... )
        >>> print(f"Deleted {deleted_count} files")
    """
    from core.models.models_per_tenant import ExpenseAttachment
    from core.utils.file_deletion import delete_file_from_storage
    
    deleted_count = 0
    
    # Get all attachments for these expenses
    attachments = db.query(ExpenseAttachment).filter(
        ExpenseAttachment.expense_id.in_(expense_ids)
    ).all()
    
    # Delete each attachment
    for att in attachments:
        if att.file_path:
            try:
                success = await delete_file_from_storage(
                    att.file_path,
                    tenant_id,
                    user_id,
                    db
                )
                if success:
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete attachment {att.file_path}: {e}")
    
    logger.info(f"Deleted {deleted_count} attachment files for {len(expense_ids)} expenses")
    return deleted_count
