# Batch File Upload Scripts

This directory contains scripts for uploading multiple files to the batch processing API.

## Scripts

### 1. `batch_upload_files.py` - Full-Featured Upload Script

A comprehensive script with validation, progress monitoring, and error handling.

**Features:**
- File validation (type, size, existence)
- Progress monitoring
- Webhook support
- Custom field selection
- Wildcard file selection
- Directory upload

**Basic Usage:**
```bash
# Upload specific files
python batch_upload_files.py --files invoice1.pdf invoice2.pdf receipt.jpg

# Upload all PDFs in current directory
python batch_upload_files.py --files *.pdf

# Upload all files from a directory
python batch_upload_files.py --directory /path/to/files

# Upload with monitoring
python batch_upload_files.py --files *.pdf --monitor

# Upload with custom export destination
python batch_upload_files.py --files *.pdf --export-destination 2

# Upload with webhook notification
python batch_upload_files.py --files *.pdf --webhook https://example.com/webhook

# Upload with custom fields
python batch_upload_files.py --files *.pdf --custom-fields vendor amount date
```

**Environment Variables:**
```bash
export API_URL="http://localhost:8000"
export API_CLIENT_ID="your_client_id"
export API_CLIENT_SECRET="your_client_secret"
```

**Command Line Options:**
```
--files FILE [FILE ...]       List of files to upload (supports wildcards)
--directory DIR               Directory containing files to upload
--api-url URL                 API base URL (default: http://localhost:8000)
--api-client-id ID            API client ID for authentication
--api-client-secret SECRET    API client secret for authentication
--export-destination ID       Export destination ID (default: 1)
--webhook URL                 Webhook URL for completion notification
--custom-fields FIELD [...]   Custom fields to include in export
--monitor                     Monitor job progress until completion
--poll-interval SECONDS       Seconds between status checks (default: 5)
```

### 2. `simple_batch_upload.py` - Simple Example

A minimal example showing the basic API usage.

**Usage:**
```bash
# Edit the script to set your API credentials and file paths
python simple_batch_upload.py
```

**What it does:**
- Uploads a predefined list of files
- Shows basic error handling
- Demonstrates job status checking

## Prerequisites

Install required Python packages:
```bash
pip install requests
```

## API Authentication

You need API client credentials to use these scripts. You can:

1. **Use existing API client credentials** from your `.env` file
2. **Create new API client** via the API:
   ```bash
   curl -X POST http://localhost:8000/api/api-clients \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Batch Upload Script",
       "description": "Script for batch file uploads"
     }'
   ```

## Export Destinations

Before uploading files, you need to configure an export destination:

1. **Via API:**
   ```bash
   curl -X POST http://localhost:8000/api/export-destinations \
     -H "Content-Type: application/json" \
     -d '{
       "name": "My S3 Bucket",
       "destination_type": "s3",
       "credentials": {
         "access_key_id": "YOUR_ACCESS_KEY",
         "secret_access_key": "YOUR_SECRET_KEY",
         "region": "us-east-1",
         "bucket_name": "my-bucket"
       }
     }'
   ```

2. **Via UI:** Navigate to Settings → Export Destinations

## File Requirements

- **Supported formats:** PDF, PNG, JPG, JPEG, CSV
- **Maximum file size:** 20MB per file
- **Maximum batch size:** 50 files per batch

## Examples

### Example 1: Upload invoices from a folder
```bash
python batch_upload_files.py \
  --directory ~/Documents/invoices \
  --export-destination 1 \
  --monitor
```

### Example 2: Upload with webhook notification
```bash
python batch_upload_files.py \
  --files invoice*.pdf \
  --export-destination 1 \
  --webhook https://myapp.com/api/batch-complete \
  --monitor
```

### Example 3: Upload with custom fields
```bash
python batch_upload_files.py \
  --files *.pdf \
  --export-destination 1 \
  --custom-fields file_name vendor amount date category
```

### Example 4: Using environment variables
```bash
export API_URL="https://api.mycompany.com"
export API_CLIENT_ID="client_abc123"
export API_CLIENT_SECRET="secret_xyz789"

python batch_upload_files.py --files *.pdf --monitor
```

## Monitoring Job Progress

### Option 1: Monitor during upload
```bash
python batch_upload_files.py --files *.pdf --monitor
```

### Option 2: Check status later
```bash
# Get job ID from upload response
JOB_ID="550e8400-e29b-41d4-a716-446655440000"

# Check status via API
curl http://localhost:8000/api/batch-processing/jobs/$JOB_ID \
  -u "client_id:client_secret"
```

### Option 3: Use the simple script
```python
# In simple_batch_upload.py
check_job_status("your-job-id-here")
```

## Troubleshooting

### Authentication Errors
```
❌ Upload failed: 401 Client Error: Unauthorized
```
**Solution:** Check your API client ID and secret are correct.

### File Too Large
```
✗ File too large (25.3MB): large_file.pdf
```
**Solution:** Files must be under 20MB. Split or compress large files.

### Invalid File Type
```
✗ Invalid file type '.docx': document.docx
```
**Solution:** Only PDF, PNG, JPG, JPEG, and CSV files are supported.

### Export Destination Not Found
```
❌ Upload failed: Export destination 999 not found
```
**Solution:** Create an export destination first or use an existing ID.

### Rate Limiting
```
❌ Upload failed: 429 Too Many Requests
```
**Solution:** Wait a moment and try again. Check your API client's rate limits.

## API Response Format

### Successful Upload Response
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "total_files": 3,
  "document_types": ["invoice", "expense"],
  "export_destination_type": "s3",
  "created_at": "2025-11-08T10:30:00Z"
}
```

### Job Status Response
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": {
    "total_files": 3,
    "processed_files": 3,
    "successful_files": 3,
    "failed_files": 0,
    "progress_percentage": 100.0
  },
  "export": {
    "destination_type": "s3",
    "export_file_url": "https://s3.amazonaws.com/bucket/export.csv",
    "export_completed_at": "2025-11-08T10:35:00Z"
  }
}
```

## See Also

- [Batch Processing API Documentation](../docs/BATCH_FILE_PROCESSING_API_REFERENCE.md)
- [Batch Processing Client Example](../examples/batch_processing_client.py)
- [Export Destinations API](../docs/EXPORT_DESTINATIONS_API.md)
