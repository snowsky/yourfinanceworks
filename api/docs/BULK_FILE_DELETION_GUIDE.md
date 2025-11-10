# Bulk File Deletion Guide

## Quick Reference

Choose the right deletion method based on your use case:

### 1. Delete Files for a Single Item

**Use Case**: Deleting one invoice, expense, or statement

```python
from utils.file_deletion import delete_file_from_storage

# Delete a single file
await delete_file_from_storage(
    file_path="tenant_1/invoices/123_1234567890_invoice.pdf",
    tenant_id=1,
    user_id=42,
    db=db
)
```

**When to use:**
- Deleting a single invoice/expense
- Removing individual attachments
- Standard CRUD operations

**Performance**: < 1 second for 1-5 files

---

### 2. Delete Files for Multiple Items

**Use Case**: Bulk deletion of invoices or expenses (e.g., empty recycle bin)

```python
from utils.bulk_file_deletion import bulk_delete_invoice_files, bulk_delete_expense_files

# Delete files for multiple invoices
deleted_count = await bulk_delete_invoice_files(
    invoice_ids=[1, 2, 3, 4, 5],
    tenant_id=1,
    user_id=42,
    db=db
)

# Delete files for multiple expenses
deleted_count = await bulk_delete_expense_files(
    expense_ids=[10, 11, 12, 13, 14],
    tenant_id=1,
    user_id=42,
    db=db
)
```

**When to use:**
- Empty recycle bin
- Bulk invoice/expense deletion
- Cleanup operations affecting multiple items

**Performance**: 10-50 seconds for 100-500 files

---

### 3. Delete All Files by Prefix (Folder Deletion)

**Use Case**: Delete all files in a logical folder

```python
from utils.bulk_file_deletion import bulk_delete_by_prefix

# Delete all files with a specific prefix
await bulk_delete_by_prefix(
    prefix="exported/job-123/",
    tenant_id=1,
    user_id=42,
    db=db
)
```

**When to use:**
- Batch processing cleanup
- Deleting all files for a specific job
- Any scenario where files share a common prefix

**Performance**: 5-30 seconds for 1000+ files

---

### 4. Delete All Files for a Tenant

**Use Case**: Tenant offboarding or complete data deletion

```python
from utils.bulk_file_deletion import bulk_delete_tenant_files

# Delete ALL files for a tenant
results = await bulk_delete_tenant_files(
    tenant_id=1,
    user_id=42,
    db=db,
    file_types=["invoices", "expenses", "images", "documents"]  # Optional
)

# Results: {'invoices': True, 'expenses': True, 'batch_files': True, ...}
```

**When to use:**
- Tenant deletion/offboarding
- Complete data cleanup
- GDPR data removal requests

**Performance**: 10-60 seconds for 10,000+ files

---

## Implementation Examples

### Example 1: Empty Recycle Bin

```python
@router.post("/recycle-bin/empty")
async def empty_recycle_bin(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    # Get all deleted invoices
    deleted_invoices = db.query(Invoice).filter(Invoice.is_deleted == True).all()
    invoice_ids = [inv.id for inv in deleted_invoices]
    
    # Delete all attachments efficiently
    from utils.bulk_file_deletion import bulk_delete_invoice_files
    deleted_count = await bulk_delete_invoice_files(
        invoice_ids=invoice_ids,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        db=db
    )
    
    # Delete invoice records
    for invoice in deleted_invoices:
        db.delete(invoice)
    db.commit()
    
    return {"deleted_count": len(deleted_invoices), "files_deleted": deleted_count}
```

### Example 2: Batch Job Cleanup

```python
@router.delete("/batch/{job_id}")
async def delete_batch_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    from services.cloud_storage_service import CloudStorageService
    
    storage_service = CloudStorageService(db)
    
    # Delete all files for this batch job
    success = await storage_service.delete_folder(
        folder_prefix=f"exported/{job_id}/",
        tenant_id=str(current_user.tenant_id)
    )
    
    return {"success": success}
```

### Example 3: Tenant Deletion

```python
@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    from utils.bulk_file_deletion import bulk_delete_tenant_files
    
    # Delete all files for the tenant
    results = await bulk_delete_tenant_files(
        tenant_id=tenant_id,
        user_id=current_user.id,
        db=db
    )
    
    # Delete tenant database records
    # ... (your database cleanup logic)
    
    return {"file_deletion_results": results}
```

---

## Performance Guidelines

### When to Use Individual Deletion
- **< 10 files**: Always use individual deletion
- **10-50 files**: Individual deletion is acceptable
- **Simple operations**: Single item CRUD

### When to Use Batch Individual Deletion
- **50-500 files**: Use bulk utilities
- **Multiple items**: Empty recycle bin, bulk operations
- **No common prefix**: Files have unique timestamps

### When to Use Folder Deletion
- **500+ files**: Always use folder deletion
- **Common prefix**: All files in same logical folder
- **Tenant-wide**: Deleting all data for a tenant

---

## Error Handling

All deletion functions are designed to be resilient:

```python
# Individual deletion - logs warnings, doesn't raise
try:
    success = await delete_file_from_storage(file_path, tenant_id, user_id, db)
    if not success:
        logger.warning(f"File not deleted: {file_path}")
except Exception as e:
    logger.error(f"Deletion error: {e}")
```

```python
# Bulk deletion - returns counts and continues on errors
deleted_count = await bulk_delete_invoice_files(invoice_ids, tenant_id, user_id, db)
# Returns count of successfully deleted files, logs warnings for failures
```

```python
# Folder deletion - returns boolean, logs errors
success = await storage_service.delete_folder(prefix, tenant_id)
# Returns True if at least one provider succeeded
```

---

## Cloud Provider Support

All deletion methods work across all configured cloud providers:

- ✅ **AWS S3**: Batch deletion (up to 1000 objects per request)
- ✅ **Azure Blob Storage**: Iterative deletion with batching
- ✅ **Google Cloud Storage**: Iterative deletion with batching
- ✅ **Local Storage**: Individual file deletion

The system automatically tries all configured providers and succeeds if any provider completes the deletion.

---

## Best Practices

1. **Always provide database session** for cloud storage operations
2. **Use appropriate method** based on file count (see guidelines above)
3. **Log deletion operations** for audit trails
4. **Handle errors gracefully** - don't fail entire operation if one file fails
5. **Delete files before database records** to prevent orphaned files
6. **Consider async operations** for large deletions to avoid timeouts

---

## Migration Notes

If you have existing code using individual deletion in loops:

**Before:**
```python
for invoice in deleted_invoices:
    attachments = db.query(InvoiceAttachment).filter(
        InvoiceAttachment.invoice_id == invoice.id
    ).all()
    for att in attachments:
        await delete_file_from_storage(att.file_path, tenant_id, user_id, db)
```

**After:**
```python
from utils.bulk_file_deletion import bulk_delete_invoice_files

invoice_ids = [inv.id for inv in deleted_invoices]
deleted_count = await bulk_delete_invoice_files(invoice_ids, tenant_id, user_id, db)
```

This is **10-50x faster** for large batches!

---

## Related Documentation

- [Cloud Storage Folder Deletion](../docs/CLOUD_STORAGE_FOLDER_DELETION.md) - Technical implementation details
- [File Deletion Utils](../utils/file_deletion.py) - Individual file deletion
- [Bulk Deletion Utils](../utils/bulk_file_deletion.py) - Bulk deletion utilities
