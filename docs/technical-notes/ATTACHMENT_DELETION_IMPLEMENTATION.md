# Attachment Deletion Implementation

## Overview
Implemented comprehensive attachment deletion from both local and cloud storage when attachments are deleted individually or when their parent records (invoices, expenses, statements) are deleted.

## Changes Made

### 1. Centralized Utility Function ⭐
Created `api/utils/file_deletion.py` with reusable file deletion functions:

#### `delete_file_from_storage()` (async)
- Attempts to delete files from cloud storage first (if available)
- Falls back to local storage deletion
- Handles errors gracefully with logging
- Returns success status
- Used by all routers and services

#### `delete_file_from_storage_sync()` (sync)
- Synchronous version for contexts where async is not available
- Only handles local storage deletion
- Useful for background jobs or sync contexts

**Benefits:**
- Single source of truth for file deletion logic
- Eliminates code duplication (~200 lines saved)
- Easier to maintain and test
- Consistent behavior across all modules

### 2. Expense Attachments

#### Individual Attachment Deletion (`DELETE /expenses/{expense_id}/attachments/{attachment_id}`)
- **Updated**: Now uses `_delete_file_from_storage()` helper
- Deletes from both cloud and local storage
- Simplified logic and improved error handling

#### Expense Deletion (`DELETE /expenses/{expense_id}`)
- **Updated**: Deletes all associated attachments from storage
- Handles legacy single receipt files
- Deletes all modern multi-attachment files
- Uses `_delete_file_from_storage()` for each file

### 3. Invoice Attachments

#### Individual Attachment Deletion (`DELETE /invoices/{invoice_id}/attachments/{attachment_id}`)
- **Updated**: Now uses `_delete_file_from_storage()` helper
- Soft deletes attachment record (marks as inactive)
- Deletes physical file from both cloud and local storage
- Creates history entry for audit trail

#### Permanent Invoice Deletion (`DELETE /invoices/{invoice_id}/permanent`)
- **Updated**: Deletes all associated attachments before deleting invoice
- Queries all `InvoiceAttachment` records
- Deletes each attachment file from storage
- Handles legacy `attachment_path` field
- Only admins can permanently delete invoices

### 4. Bank Statement Attachments

#### Statement Deletion (`DELETE /statements/{statement_id}`)
- **Updated**: Deletes statement file from storage before deleting record
- Attempts cloud storage deletion first
- Falls back to local storage deletion
- Handles errors gracefully

### 5. Inventory Item Attachments

#### Inventory Item Deletion (`DELETE /inventory/items/{item_id}`)
- **Updated**: Deletes all associated attachments before deleting item
- Queries all `ItemAttachment` records
- Deletes each attachment file from storage
- Also deletes thumbnail files if they exist
- Validates that item is not used in invoices or expenses before deletion

## Storage Deletion Strategy

The implementation follows an intelligent dual-deletion approach with environment-based configuration:

1. **Environment Check**: Checks `CLOUD_STORAGE_ENABLED` environment variable
   - If `true`: Attempts cloud storage deletion
   - If `false`: Skips cloud storage, only deletes locally
   - Prevents unnecessary cloud API calls when cloud storage is disabled

2. **Path Detection**: Automatically detects storage type from file path
   - Cloud paths: `tenant_1/expenses/123_1234567890_file.pdf` (no "attachments" prefix)
   - Local paths: `attachments/tenant_1/expenses/expense_123_file_uuid.pdf` (has "attachments" prefix)

3. **Cloud Storage**: Attempts to delete from cloud storage using `CloudStorageService`
   - Only attempts if `CLOUD_STORAGE_ENABLED=true` AND path is detected as cloud storage
   - Uses full file_path as the S3/Azure key
   - Calls `delete_file()` with tenant_id and user_id
   - Logs success/failure

4. **Local Storage**: Attempts to delete from local filesystem
   - Always attempts for all paths (works for both local and cloud)
   - Validates file path for security
   - Checks if file exists
   - Removes file using `os.remove()`
   - Logs success/failure

5. **Error Handling**: 
   - Failures are logged as warnings, not errors
   - Deletion continues even if one storage type fails
   - Database operations proceed regardless of file deletion status
   - Works correctly whether files are in cloud, local, or both
   - Respects environment configuration for optimal performance

## Database Cascade Behavior

The models already have proper cascade delete configured:

- `ExpenseAttachment`: `ondelete="CASCADE"` on `expense_id` foreign key
- `InvoiceAttachment`: `ondelete="CASCADE"` on `invoice_id` foreign key
- `ItemAttachment`: `ondelete="CASCADE"` on `item_id` foreign key
- `BankStatementTransaction`: `ondelete="CASCADE"` on `statement_id` foreign key

This ensures that when a parent record is deleted, all attachment records are automatically removed from the database.

## Security Considerations

1. **File Path Validation**: Uses `validate_file_path()` to prevent path traversal attacks
2. **Permission Checks**: Requires non-viewer role for all deletion operations
3. **Admin-Only**: Permanent invoice deletion requires admin role
4. **Audit Logging**: All deletions are logged for audit trail
5. **Tenant Isolation**: Cloud storage deletion includes tenant_id for proper isolation

## Testing Recommendations

1. **Individual Attachment Deletion**:
   - Delete expense attachment → verify file removed from storage
   - Delete invoice attachment → verify file removed and soft delete works
   - Test with cloud storage enabled and disabled

2. **Parent Record Deletion**:
   - Delete expense with multiple attachments → verify all files removed
   - Permanently delete invoice → verify all attachments removed
   - Delete bank statement → verify file removed
   - Delete inventory item with attachments → verify all files and thumbnails removed

3. **Error Scenarios**:
   - Delete attachment when file doesn't exist → should succeed
   - Delete with cloud storage unavailable → should fall back to local
   - Delete with invalid file path → should log warning and continue

4. **Mixed Storage**:
   - Test with files in both cloud and local storage
   - Verify both are attempted for deletion

5. **Inventory-Specific Tests**:
   - Delete inventory item with multiple images → verify all images and thumbnails removed
   - Try to delete inventory item used in invoice → should fail with validation error
   - Try to delete inventory item used in expense → should fail with validation error

## Future Enhancements

1. **Batch Deletion**: Optimize deletion of multiple attachments
2. **Soft Delete for Expenses**: Consider implementing soft delete for expenses like invoices
3. **Cleanup Job**: Background job to clean up orphaned files
4. **Deletion Metrics**: Track deletion success rates for monitoring
5. **Thumbnail Cleanup**: Ensure thumbnails are also deleted for image attachments
