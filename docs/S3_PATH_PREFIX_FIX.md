# S3 Path Prefix Fix for Export Destinations

## Problem

When downloading expense attachments from S3, the system was failing with a `NoSuchKey` error due to two issues:

1. **Local vs Cloud Detection**: Files stored locally (e.g., `api/batch_files/tenant_1/...`) were incorrectly being treated as cloud files
2. **Missing Path Prefix**: For actual cloud files, the S3 key construction didn't account for the path prefix configured in the Export Destination settings

### Error Message
```
ERROR:routers.expenses:S3 download exception: An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist.
```

### Root Cause

1. **Local File Misidentification**: Files stored in local paths like `api/batch_files/tenant_1/...` were not being recognized as local files, causing the system to attempt S3 downloads
2. **Path Prefix Not Applied**: For actual cloud files, the path prefix from Export Destination settings (e.g., `f06221e5-da6b-4944-bb5d-35bd9dc0cd70`) was not being prepended to the S3 key

The path prefix is configured in the Export Destination settings under the "Path Prefix (Optional)" field, which allows users to organize their S3 files under a specific prefix/folder structure.

## Solution

Updated the expense attachment download endpoint (`/expenses/{expense_id}/attachments/{attachment_id}/download`) to:

1. **Correctly Identify Local vs Cloud Files**: 
   - Local files: Start with `/`, `attachments/`, or `api/batch_files/`
   - Cloud files: Everything else (typically `tenant_{id}/{type}/{file}`)

2. **For Cloud Files Only**:
   - Retrieve Export Destination Configuration: Query the active S3 export destination for the tenant
   - Extract Path Prefix: Decrypt and extract the `path_prefix` from the export destination credentials
   - Construct Correct S3 Key:
     - Strip any local path prefixes that shouldn't be in S3
     - Apply the export destination's `path_prefix` if configured
     - Otherwise, use the default pattern: `tenant_{tenant_id}/{attachment_type}`

3. **For Local Files**: Serve directly using `FileResponse` without attempting S3 access

### Code Changes

**File**: `api/routers/expenses.py`

**Location**: `download_expense_attachment` endpoint (around line 1230)

**Key Logic**:
```python
# Step 1: Identify if file is local or cloud
is_local_file = (
    att.file_path.startswith('/') or 
    att.file_path.startswith('attachments') or
    att.file_path.startswith('api/batch_files/')
)

if not is_local_file:
    # Step 2: For cloud files, get export destination config
    export_dest = db.query(ExportDestinationConfig).filter(
        ExportDestinationConfig.tenant_id == current_user.tenant_id,
        ExportDestinationConfig.destination_type == 's3',
        ExportDestinationConfig.is_active == True
    ).order_by(ExportDestinationConfig.is_default.desc()).first()
    
    if export_dest:
        credentials = export_service.get_decrypted_credentials(export_dest.id)
        if credentials:
            path_prefix = credentials.get('path_prefix')
    
    # Step 3: Construct S3 key
    s3_key = att.file_path
    
    # Remove local file system prefixes if present
    import re
    local_prefixes = [
        r'^api/batch_files/tenant_\d+/',
        r'^attachments/tenant_\d+/',
        r'^tenant_\d+/',
    ]
    
    for pattern in local_prefixes:
        s3_key = re.sub(pattern, '', s3_key)
    
    # Apply path prefix if configured
    if path_prefix:
        normalized_prefix = path_prefix.strip('/')
        if normalized_prefix and not s3_key.startswith(f'{normalized_prefix}/'):
            s3_key = f'{normalized_prefix}/{s3_key}'
    
    # Download from S3...
else:
    # Step 4: For local files, serve directly
    return FileResponse(path=validated_path, filename=att.filename)
```

## Testing

Created test script `api/scripts/test_s3_download_with_prefix.py` to verify the S3 key construction logic.

### Test Cases

1. ✅ File with export destination prefix: `Receipt-GoodLife.jpg` → `f06221e5-da6b-4944-bb5d-35bd9dc0cd70/Receipt-GoodLife.jpg`
2. ✅ File with tenant prefix: `tenant_1/expenses/123_receipt.jpg` → `f06221e5-da6b-4944-bb5d-35bd9dc0cd70/expenses/123_receipt.jpg` (tenant prefix replaced)
3. ✅ File with structure (has /): `expenses/456_receipt.jpg` → unchanged
4. ✅ Path prefix with trailing slash: Normalized correctly
5. ✅ Path prefix with leading slash: Normalized correctly
6. ✅ **Batch file with local path**: `api/batch_files/tenant_1/f06221e5-da6b-4944-bb5d-35bd9dc0cd70/file.jpeg` → `f06221e5-da6b-4944-bb5d-35bd9dc0cd70/file.jpeg`
7. ✅ Batch file without path prefix: `api/batch_files/tenant_2/expenses/receipt.jpg` → `expenses/receipt.jpg`

## Impact

- **Fixes**: S3 download errors for tenants using export destinations with path prefixes
- **Fixes**: Incorrect S3 access attempts for local files (batch uploads, local attachments)
- **Backward Compatible**: Falls back to default tenant-based paths if no export destination is configured
- **Preserves Local Storage**: Files stored locally (batch files, local attachments) are served correctly without S3 access attempts

## Configuration

To use this feature, configure an S3 export destination in Settings → Export Destinations:

1. Set **Destination Type**: AWS S3
2. Configure AWS credentials (Access Key ID, Secret Access Key, Region, Bucket Name)
3. Set **Path Prefix (Optional)**: e.g., `f06221e5-da6b-4944-bb5d-35bd9dc0cd70` or any custom prefix
4. Mark as **Default** if you want it to be used for downloads

## Related Files

- `api/routers/expenses.py` - Main fix implementation
- `api/schemas/export_destination.py` - Export destination schema with path_prefix field
- `api/models/models_per_tenant.py` - ExportDestinationConfig model
- `api/services/export_destination_service.py` - Service for managing export destinations
- `api/scripts/test_s3_download_with_prefix.py` - Test script

## Future Improvements

- Apply the same fix to invoice and statement attachment downloads
- Consider caching export destination configuration to reduce database queries
- Add support for multiple export destinations per tenant with priority ordering
