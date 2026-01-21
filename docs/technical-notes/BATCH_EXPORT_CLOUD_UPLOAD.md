# Batch Export Cloud Upload Implementation

## Summary

Fixed the OCR worker status issue and added cloud file upload functionality to batch processing with enhanced CSV export columns.

## Changes Made

### 1. Fixed OCR Worker Status Issue

**File:** `api/workers/ocr_consumer.py`

- **Problem:** OCR worker was creating expenses with `status='pending'`, which is not a valid ExpenseStatus value
- **Solution:** Changed status to `'recorded'` (line 305)
- **Impact:** Prevents validation errors when fetching expenses from the database

### 2. Enhanced CSV Export Columns

**File:** `api/services/export_service.py`

Added two new columns to the CSV export:
- `original_filename`: The original name of the uploaded file
- `cloud_file_url`: The URL where the file is stored in cloud storage

**Updated CSV Columns:**
```python
CSV_COLUMNS = [
    'file_name',
    'original_filename',      # NEW
    'cloud_file_url',         # NEW
    'document_type',
    'status',
    'vendor',
    'amount',
    'currency',
    'date',
    'tax_amount',
    'category',
    'line_items',
    'attachment_paths',
    'error_message'
]
```

### 3. Cloud File Upload Functionality

**File:** `api/services/batch_processing_service.py`

Added automatic cloud upload for batch-processed files:

#### New Method: `_upload_file_to_cloud()`
- Uploads files to the configured export destination (S3, Azure, GCS, or Google Drive)
- Generates cloud URLs for each uploaded file
- Stores URLs in the `cloud_file_url` field of `BatchFileProcessing` records

#### Integration Points:
- Files are uploaded to cloud storage immediately after batch job creation
- Upload happens asynchronously to avoid blocking job creation
- Cloud URLs are stored in the database for CSV export
- Failures are logged but don't block the batch processing workflow

### 4. Migration Script

**File:** `api/scripts/migrate_pending_status.py`

Created a migration script to fix existing data:
- Updates all expenses with `status='pending'` to `status='recorded'`
- Processes all tenant databases
- Provides detailed logging of migration progress

## Database Schema

The `BatchFileProcessing` model already includes the `cloud_file_url` field:

```python
cloud_file_url = Column(String(1000), nullable=True)
```

No database migration is required.

## Usage

### CSV Export with Cloud URLs

When exporting batch processing results, the CSV will now include:
1. **original_filename**: The name of the file as uploaded by the user
2. **cloud_file_url**: Direct link to the file in cloud storage (S3, Azure, GCS, or Google Drive)

### Cloud Upload Process

1. User uploads files via batch processing API
2. Files are stored locally in `batch_files/tenant_{id}/{job_id}/`
3. Files are automatically uploaded to the configured export destination
4. Cloud URLs are stored in the database
5. CSV export includes both local and cloud file paths

### Supported Cloud Providers

- **AWS S3**: Generates presigned URLs (24-hour expiry)
- **Azure Blob Storage**: Generates SAS URLs (24-hour expiry)
- **Google Cloud Storage**: Generates signed URLs (24-hour expiry)
- **Google Drive**: Generates shareable links with read permissions

## Error Handling

- Cloud upload failures are logged but don't block batch processing
- If cloud upload fails, `cloud_file_url` remains `NULL`
- CSV export gracefully handles missing cloud URLs (empty string)
- Retry logic is built into the export service for CSV uploads

## Testing

To test the implementation:

1. Create a batch processing job with an export destination configured
2. Upload files through the batch API
3. Check that `cloud_file_url` is populated in the database
4. Export the CSV and verify the new columns are present
5. Verify cloud URLs are accessible

## Benefits

1. **Centralized Storage**: All processed files are automatically backed up to cloud storage
2. **Easy Access**: Cloud URLs provide direct access to original files
3. **Audit Trail**: CSV exports include complete file provenance
4. **Scalability**: Cloud storage handles large file volumes better than local disk
5. **Disaster Recovery**: Files are preserved even if local storage fails

## Notes

- Cloud upload is asynchronous and doesn't block batch job creation
- URLs expire after 24 hours for security (except Google Drive)
- Files remain on local disk for immediate processing
- Cloud upload requires a configured export destination
