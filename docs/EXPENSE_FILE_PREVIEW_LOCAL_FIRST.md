# Expense File Preview - Local First Strategy & MIME Type Fix

## Overview
Updated the expense attachment download/preview endpoint to prioritize local files before attempting cloud storage downloads, and fixed MIME type detection for proper file preview.

## Changes Made

### File Modified
- `api/routers/expenses.py` - `download_expense_attachment()` function

### New Logic Flow

**Priority 1: Check Local File First**
1. Attempt to validate and check if file exists locally using `validate_file_path()`
2. If local file exists, serve it immediately
3. Log success and return the file with proper headers

**Priority 2: Try Cloud Storage**
4. Only if local file doesn't exist AND cloud storage is enabled
5. Attempt to download from S3
6. If successful, return the cloud file

**Priority 3: Error Handling**
7. If both local and cloud fail, return 404 with descriptive error

### Benefits

1. **Performance**: Local files are served faster (no S3 API calls)
2. **Cost**: Reduces S3 bandwidth costs for files that exist locally
3. **Reliability**: Local files are more reliable (no network dependency)
4. **Fallback**: Still supports cloud storage when local files are unavailable

### Code Structure

```python
# 1. Check local file first
local_file_exists = False
try:
    validated_path = validate_file_path(att.file_path)
    local_file_exists = os.path.exists(validated_path)
except Exception:
    pass

# 2. Serve local file if it exists
if local_file_exists:
    # Serve directly from disk
    return StreamingResponse(...)

# 3. Try cloud storage if enabled
if cloud_enabled and is_cloud_file:
    try:
        # Download from S3
        return StreamingResponse(...)
    except Exception:
        # Both failed
        raise HTTPException(404)

# 4. Neither local nor cloud available
raise HTTPException(404)
```

### Use Cases

- **Development**: Local files served directly without S3 configuration
- **Production with local storage**: Fast file serving from disk
- **Production with cloud storage**: Automatic fallback to S3 when needed
- **Hybrid deployments**: Supports both local and cloud files simultaneously

## MIME Type Detection Fix

### Problem
Batch uploaded files were being stored with `content_type='application/octet-stream'`, causing the UI to show "This file type cannot be previewed" even for images and PDFs.

### Solution

**1. Fixed Batch Processing (`api/workers/ocr_consumer.py`)**
- Now detects MIME type from original filename using `mimetypes.guess_type()`
- Sets correct `content_type` when creating `ExpenseAttachment` records
- Example: `Receipt-Walmart.jpeg` → `image/jpeg`

**2. Fixed Download Endpoint (`api/routers/expenses.py`)**
- Added MIME type detection fallback for local files
- If `content_type` is missing or `application/octet-stream`, guesses from filename
- Ensures proper Content-Type header for browser preview

### Code Changes

```python
# In ocr_consumer.py - Batch processing
import mimetypes
original_filename = payload.get("original_filename", "batch_file")
content_type, _ = mimetypes.guess_type(original_filename)
if not content_type:
    content_type = 'application/octet-stream'

attachment = ExpenseAttachment(
    expense_id=expense.id,
    filename=original_filename,
    file_path=file_path,
    size_bytes=payload.get("file_size", 0),
    content_type=content_type  # Now correctly detected
)
```

```python
# In expenses.py - Download endpoint
import mimetypes

# Determine content type - try to guess from filename first
media_type = att.content_type
if not media_type or media_type == 'application/octet-stream':
    guessed_type, _ = mimetypes.guess_type(att.filename or validated_path)
    if guessed_type:
        media_type = guessed_type
```

### Testing

The endpoint supports both preview (inline) and download modes:
- Preview: `GET /api/v1/expenses/{id}/attachments/{id}/download?inline=true`
- Download: `GET /api/v1/expenses/{id}/attachments/{id}/download?inline=false`

Both modes now:
1. Check local files first before attempting cloud downloads
2. Correctly detect and serve MIME types for proper browser preview

### Supported File Types for Preview
- Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg`
- PDFs: `.pdf`
- Other types will show download option
