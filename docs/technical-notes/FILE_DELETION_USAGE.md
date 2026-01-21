# File Deletion Utility - Usage Guide

## Overview
The `delete_file_from_storage()` utility provides a centralized way to delete files from both cloud and local storage across the application.

## Location
`api/utils/file_deletion.py`

## Functions

### `delete_file_from_storage()` (Async)

Primary function for deleting files from both cloud and local storage.

#### Signature
```python
async def delete_file_from_storage(
    file_path: str,
    tenant_id: int,
    user_id: int,
    db: Optional[Session] = None
) -> bool
```

#### Parameters
- `file_path` (str): Path to the file to delete (can be local path or cloud key)
- `tenant_id` (int): Tenant ID for cloud storage operations and logging
- `user_id` (int): User ID for audit logging
- `db` (Optional[Session]): Database session for cloud storage service (optional)

#### Returns
- `bool`: True if file was deleted from at least one storage location, False otherwise

#### Example Usage

```python
from utils.file_deletion import delete_file_from_storage

# In an async endpoint
@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    # Get the item
    item = db.query(Item).filter(Item.id == item_id).first()
    
    # Delete associated file
    if item.file_path:
        await delete_file_from_storage(
            file_path=item.file_path,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            db=db
        )
    
    # Delete the database record
    db.delete(item)
    db.commit()
    
    return {"message": "Item deleted"}
```

### `delete_file_from_storage_sync()` (Sync)

Synchronous version for contexts where async is not available. Only handles local storage.

#### Signature
```python
def delete_file_from_storage_sync(
    file_path: str,
    tenant_id: int,
    user_id: int,
    db: Optional[Session] = None
) -> bool
```

#### Parameters
Same as async version.

#### Returns
- `bool`: True if file was deleted from local storage, False otherwise

#### Example Usage

```python
from utils.file_deletion import delete_file_from_storage_sync

# In a synchronous context (e.g., background job)
def cleanup_old_files(file_paths: List[str], tenant_id: int, user_id: int):
    for file_path in file_paths:
        success = delete_file_from_storage_sync(
            file_path=file_path,
            tenant_id=tenant_id,
            user_id=user_id
        )
        if success:
            logger.info(f"Deleted: {file_path}")
```

## Behavior

### Deletion Strategy
1. **Environment Check**: Checks `CLOUD_STORAGE_ENABLED` environment variable first
2. **Cloud Storage**: Attempts to delete from cloud storage (only if enabled and path is cloud-based)
3. **Local Storage**: Always attempts to delete from local filesystem
4. **Best Effort**: Continues even if one storage type fails
5. **Logging**: Logs success/failure for each storage type
6. **Performance**: Skips cloud API calls when cloud storage is disabled

### Error Handling
- **Graceful Degradation**: Logs warnings instead of raising exceptions
- **File Not Found**: Returns False but doesn't fail
- **Invalid Path**: Validates path and logs warning
- **Cloud Unavailable**: Skips cloud deletion and tries local

### Security
- **Path Validation**: Uses `validate_file_path()` to prevent path traversal
- **Tenant Isolation**: Cloud storage operations include tenant_id
- **Audit Trail**: Logs all deletion attempts with user_id

## When to Use

### Use Async Version When:
- In FastAPI endpoints (async by default)
- Need to delete from cloud storage
- Have access to database session
- Want comprehensive deletion (cloud + local)

### Use Sync Version When:
- In background jobs or workers
- In synchronous contexts
- Only need local file deletion
- Cloud storage is not available

## Common Patterns

### Pattern 1: Delete Single Attachment
```python
# Delete individual attachment
if attachment.file_path:
    await delete_file_from_storage(
        attachment.file_path,
        current_user.tenant_id,
        current_user.id,
        db
    )
db.delete(attachment)
db.commit()
```

### Pattern 2: Delete Multiple Attachments
```python
# Delete all attachments for a record
attachments = db.query(Attachment).filter(
    Attachment.parent_id == parent_id
).all()

for att in attachments:
    if att.file_path:
        await delete_file_from_storage(
            att.file_path,
            current_user.tenant_id,
            current_user.id,
            db
        )

# Database cascade will delete attachment records
db.delete(parent_record)
db.commit()
```

### Pattern 3: Delete with Thumbnail
```python
# Delete both main file and thumbnail
if item.file_path:
    await delete_file_from_storage(
        item.file_path,
        current_user.tenant_id,
        current_user.id,
        db
    )

if item.thumbnail_path:
    await delete_file_from_storage(
        item.thumbnail_path,
        current_user.tenant_id,
        current_user.id,
        db
    )
```

### Pattern 4: Batch Deletion
```python
# Delete multiple files efficiently
file_paths = [att.file_path for att in attachments if att.file_path]

for file_path in file_paths:
    await delete_file_from_storage(
        file_path,
        current_user.tenant_id,
        current_user.id,
        db
    )
```

## Logging

The utility logs at different levels:

- **INFO**: Successful deletions
- **DEBUG**: Skipped operations (cloud not available, file not found)
- **WARNING**: Failed deletions, invalid paths

Example log output:
```
INFO: Successfully deleted file from cloud storage: attachments/tenant_1/invoice_123.pdf
INFO: Successfully deleted local file: attachments/tenant_1/invoice_123.pdf
WARNING: Failed to delete file from cloud storage: Connection timeout
DEBUG: Cloud storage not available, skipping cloud deletion
```

## Testing

### Unit Test Example
```python
import pytest
from utils.file_deletion import delete_file_from_storage

@pytest.mark.asyncio
async def test_delete_file_from_storage(mock_db, tmp_path):
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Delete the file
    result = await delete_file_from_storage(
        str(test_file),
        tenant_id=1,
        user_id=42,
        db=mock_db
    )
    
    # Verify
    assert result is True
    assert not test_file.exists()
```

## Best Practices

1. **Always provide tenant_id and user_id** for audit trail
2. **Pass db session** when available for cloud storage support
3. **Check file_path exists** before calling (avoid unnecessary calls)
4. **Don't fail operations** if file deletion fails (it's logged)
5. **Delete files before database records** to avoid orphaned files
6. **Use async version** in FastAPI endpoints for cloud support

## Troubleshooting

### File not deleted from cloud storage
- Check cloud storage configuration
- Verify tenant_id is correct
- Check network connectivity
- Review cloud storage logs

### File not deleted from local storage
- Verify file path is correct
- Check file permissions
- Ensure file exists
- Review file validation logs

### Function returns False
- Check logs for specific error
- Verify file_path is not empty
- Ensure at least one storage type is available
- Check if file was already deleted
