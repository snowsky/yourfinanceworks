# OCR Cloud Storage Retry Fix

## Problem

When OCR processing failed and cloud storage was enabled, the OCR worker would repeatedly download the same file from cloud storage on each retry attempt. This caused:

- Excessive cloud storage API calls and bandwidth usage
- Increased latency on retries
- Potential rate limiting issues with cloud storage providers
- Unnecessary costs for cloud storage operations

### Root Cause

The issue occurred in the retry flow:

1. User uploads an expense receipt to cloud storage
2. OCR worker receives a message with `file_path` pointing to the cloud storage key
3. OCR processing fails (timeout, API error, etc.)
4. Worker republishes the message with `attempt` incremented
5. On retry, `process_attachment_inline()` checks if the file exists locally
6. Since the `file_path` is a cloud storage key (not a local path), it doesn't exist
7. The function downloads the file from cloud storage again
8. This repeats for each retry attempt (up to 5 times by default)

## Solution

The fix implements **local file caching** after the first cloud storage download:

### Changes Made

1. **Added `local_cache_path` field to `ExpenseAttachment` model**
   - Stores the local filesystem path of a downloaded cloud storage file
   - Prevents re-downloading the same file on retries

2. **Updated `process_attachment_inline()` function**
   - Checks if a cached local path exists before downloading from cloud storage
   - If cache exists and file is valid, uses the cached file
   - After downloading from cloud storage, stores the local path in the database
   - Clears invalid cache entries if the file is missing or empty

3. **Created database migration**
   - Migration: `003_add_local_cache_path_to_expense_attachments.py`
   - Adds the `local_cache_path` column to the `expense_attachments` table

### How It Works

**First Attempt:**
```
1. Message received with file_path = "s3://bucket/tenant-1/file-abc123.pdf"
2. File doesn't exist locally
3. Download from cloud storage → /tmp/file_abc123_123.pdf
4. Store local_cache_path = "/tmp/file_abc123_123.pdf" in database
5. Process OCR
6. If fails, republish message
```

**Retry Attempts:**
```
1. Message received with file_path = "s3://bucket/tenant-1/file-abc123.pdf"
2. Query attachment record, find local_cache_path = "/tmp/file_abc123_123.pdf"
3. Verify file exists and has content
4. Use cached file directly (no cloud storage download)
5. Process OCR
6. If fails again, republish message
```

### Benefits

- **Reduced cloud storage calls**: Only downloads once per attachment, regardless of retry count
- **Faster retries**: Subsequent attempts use local cached file
- **Lower costs**: Fewer API calls and bandwidth usage
- **Better reliability**: Less dependent on cloud storage availability during retries
- **Automatic cleanup**: Invalid cache entries are detected and cleared

### Migration

To apply this fix:

```bash
# Run the migration
cd api
alembic upgrade head
```

The migration adds the `local_cache_path` column to the `expense_attachments` table. Existing attachments will have `NULL` values, and the cache will be populated on the next OCR processing attempt.

### Backward Compatibility

- Fully backward compatible
- Existing attachments continue to work without modification
- Cache is optional - if not present, file is downloaded as before
- No changes to API or message format

### Monitoring

To verify the fix is working:

1. Check logs for "Using cached local file from previous download" messages
2. Monitor cloud storage API call counts - should decrease significantly
3. Check retry success rates - should improve due to faster processing

### Future Improvements

- Add cache expiration policy (e.g., delete cached files after 24 hours)
- Add cache size limits to prevent disk space issues
- Add metrics for cache hit/miss rates
- Consider using a dedicated cache directory instead of temp files
