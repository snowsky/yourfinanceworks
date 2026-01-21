# OCR Cloud Storage Retry - Implementation Details

## Overview

This document provides technical details about the fix for the OCR cloud storage retry issue where files were being re-downloaded from cloud storage on each retry attempt.

## Files Modified

### 1. `api/core/models/models_per_tenant.py`

**Change**: Added `local_cache_path` field to `ExpenseAttachment` model

```python
class ExpenseAttachment(Base):
    # ... existing fields ...
    
    # Cloud Storage Cache - stores local path after downloading from cloud storage
    # This prevents re-downloading the same file on retries
    local_cache_path = Column(String, nullable=True)
```

**Purpose**: Stores the filesystem path of a downloaded cloud storage file for reuse on retries.

### 2. `api/core/services/ocr_service.py`

**Function**: `process_attachment_inline()`

**Changes**:
- Added cache lookup before cloud storage download
- Validates cached file exists and has content
- Stores local path in database after download
- Clears invalid cache entries

**Key Logic**:

```python
# Check for cached local file first
if attachment and hasattr(attachment, 'local_cache_path') and attachment.local_cache_path:
    cached_local_path = attachment.local_cache_path
    if os.path.exists(cached_local_path) and os.path.getsize(cached_local_path) > 0:
        logger.info(f"Using cached local file from previous download: {cached_local_path}")
        file_path = cached_local_path
        is_temp_file = True
    else:
        logger.warning(f"Cached local path exists but file is missing or empty: {cached_local_path}")
        # Clear the invalid cache
        attachment.local_cache_path = None
        db.commit()

# If no valid cache, download from cloud storage
if not is_temp_file:
    # ... download logic ...
    
    # Cache the local path in the attachment record
    if attachment:
        attachment.local_cache_path = temp_path
        db.commit()
        logger.info(f"Cached local file path for attachment {attachment_id}: {temp_path}")
```

### 3. `api/alembic/versions/003_add_local_cache_path_to_expense_attachments.py`

**Migration**: Adds `local_cache_path` column to `expense_attachments` table

```python
def upgrade():
    op.add_column(
        'expense_attachments',
        sa.Column('local_cache_path', sa.String(), nullable=True)
    )

def downgrade():
    op.drop_column('expense_attachments', 'local_cache_path')
```

## Execution Flow

### Scenario 1: First OCR Attempt with Cloud Storage

```
1. Message: {expense_id: 123, attachment_id: 456, file_path: "s3://bucket/file.pdf", attempt: 0}
2. process_attachment_inline() called
3. Check if "s3://bucket/file.pdf" exists locally → NO
4. Query ExpenseAttachment(456) → local_cache_path is NULL
5. Download from cloud storage → /tmp/file_456_xyz.pdf
6. Update ExpenseAttachment(456).local_cache_path = "/tmp/file_456_xyz.pdf"
7. Process OCR with /tmp/file_456_xyz.pdf
8. If fails → republish message with attempt: 1
```

### Scenario 2: Retry Attempt (Cache Hit)

```
1. Message: {expense_id: 123, attachment_id: 456, file_path: "s3://bucket/file.pdf", attempt: 1}
2. process_attachment_inline() called
3. Check if "s3://bucket/file.pdf" exists locally → NO
4. Query ExpenseAttachment(456) → local_cache_path = "/tmp/file_456_xyz.pdf"
5. Verify /tmp/file_456_xyz.pdf exists and has content → YES
6. Use cached file directly (NO cloud storage download)
7. Process OCR with /tmp/file_456_xyz.pdf
8. If fails → republish message with attempt: 2
```

### Scenario 3: Cache Invalidation

```
1. Message: {expense_id: 123, attachment_id: 456, file_path: "s3://bucket/file.pdf", attempt: 2}
2. process_attachment_inline() called
3. Check if "s3://bucket/file.pdf" exists locally → NO
4. Query ExpenseAttachment(456) → local_cache_path = "/tmp/file_456_xyz.pdf"
5. Verify /tmp/file_456_xyz.pdf exists → NO (file was deleted)
6. Clear cache: ExpenseAttachment(456).local_cache_path = NULL
7. Download from cloud storage again → /tmp/file_456_new.pdf
8. Update cache with new path
9. Process OCR
```

## Performance Impact

### Before Fix
- **Attempt 1**: 1 cloud storage download
- **Attempt 2**: 1 cloud storage download (total: 2)
- **Attempt 3**: 1 cloud storage download (total: 3)
- **Attempt 4**: 1 cloud storage download (total: 4)
- **Attempt 5**: 1 cloud storage download (total: 5)

**Total**: 5 cloud storage downloads for a single failed OCR

### After Fix
- **Attempt 1**: 1 cloud storage download
- **Attempt 2**: 0 cloud storage downloads (cache hit)
- **Attempt 3**: 0 cloud storage downloads (cache hit)
- **Attempt 4**: 0 cloud storage downloads (cache hit)
- **Attempt 5**: 0 cloud storage downloads (cache hit)

**Total**: 1 cloud storage download for a single failed OCR

**Improvement**: 80% reduction in cloud storage API calls

## Database Schema

### Before
```sql
CREATE TABLE expense_attachments (
    id INTEGER PRIMARY KEY,
    expense_id INTEGER NOT NULL,
    filename VARCHAR NOT NULL,
    content_type VARCHAR,
    size_bytes INTEGER,
    file_path VARCHAR NOT NULL,
    uploaded_at TIMESTAMP,
    uploaded_by INTEGER,
    analysis_status VARCHAR DEFAULT 'not_started',
    analysis_result JSON,
    analysis_error TEXT,
    extracted_amount FLOAT
);
```

### After
```sql
CREATE TABLE expense_attachments (
    id INTEGER PRIMARY KEY,
    expense_id INTEGER NOT NULL,
    filename VARCHAR NOT NULL,
    content_type VARCHAR,
    size_bytes INTEGER,
    file_path VARCHAR NOT NULL,
    uploaded_at TIMESTAMP,
    uploaded_by INTEGER,
    analysis_status VARCHAR DEFAULT 'not_started',
    analysis_result JSON,
    analysis_error TEXT,
    extracted_amount FLOAT,
    local_cache_path VARCHAR  -- NEW FIELD
);
```

## Error Handling

The implementation handles several edge cases:

1. **Cache file deleted**: Detects missing file and re-downloads
2. **Cache file empty**: Detects zero-size file and re-downloads
3. **Database commit failure**: Logs warning but continues processing
4. **Cloud storage unavailable**: Falls back to existing error handling

## Logging

Key log messages to monitor:

```
# Cache hit
"Using cached local file from previous download: /tmp/file_456_xyz.pdf"

# Cache miss (first download)
"Successfully downloaded cloud file from 's3://bucket/file.pdf' to '/tmp/file_456_xyz.pdf' for OCR processing"

# Cache invalidation
"Cached local path exists but file is missing or empty: /tmp/file_456_xyz.pdf"

# Cache storage
"Cached local file path for attachment 456: /tmp/file_456_xyz.pdf"
```

## Testing

To verify the fix:

1. **Unit Test**: Mock cloud storage service and verify cache is used on retry
2. **Integration Test**: Upload file, trigger OCR failure, verify cache is used on retry
3. **Performance Test**: Monitor cloud storage API calls during retry scenarios

## Deployment

1. Run migration: `alembic upgrade head`
2. Deploy updated code
3. Monitor logs for cache hit messages
4. Verify cloud storage API call reduction

## Future Enhancements

1. **Cache Expiration**: Add TTL to cached files (e.g., 24 hours)
2. **Cache Size Limits**: Prevent disk space issues with large files
3. **Cache Metrics**: Track hit/miss rates for monitoring
4. **Dedicated Cache Directory**: Use specific directory instead of temp files
5. **Cache Cleanup**: Periodic cleanup of expired cache entries
