# Batch Processing API Documentation

## Overview

The Batch Processing API enables external systems and users to upload multiple files (invoices, expenses, bank statements) in a single request, process them asynchronously using OCR, and export the extracted results to configured cloud storage destinations.

## Implementation Status

✅ **Task 9: Batch Upload API Endpoint - COMPLETED**

All subtasks have been successfully implemented:

- ✅ 9.1 Create batch processing router
- ✅ 9.2 Implement POST /api/v1/batch-processing/upload endpoint
- ✅ 9.3 Implement GET /api/v1/batch-processing/jobs/{job_id} endpoint
- ✅ 9.4 Implement GET /api/v1/batch-processing/jobs endpoint

## API Endpoints

### 1. Upload Batch Files

**Endpoint:** `POST /api/v1/batch-processing/upload`

**Description:** Upload up to 50 files for batch OCR processing and export.

**Authentication:** JWT (Bearer token) - API key authentication to be implemented

**Request:**
- Content-Type: `multipart/form-data`
- Body Parameters:
  - `files` (required): List of files to process (max 50, max 20MB each)
  - `export_destination_id` (required): ID of export destination configuration
  - `document_types` (optional): Comma-separated document types (invoice,expense,statement)
  - `custom_fields` (optional): Comma-separated fields to include in export
  - `webhook_url` (optional): Webhook URL for completion notification

**Response (201 Created):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "total_files": 25,
  "estimated_completion_minutes": 15,
  "status_url": "/api/v1/batch-processing/jobs/550e8400-e29b-41d4-a716-446655440000",
  "message": "Batch job created successfully. 25 files enqueued for processing."
}
```

**Validation:**
- Minimum 1 file, maximum 50 files per batch
- Maximum file size: 20MB per file
- Allowed file types: PDF, PNG, JPG, JPEG, CSV
- Export destination must exist and be active for the tenant

**Example using cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/batch-processing/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf" \
  -F "files=@receipt1.jpg" \
  -F "export_destination_id=1" \
  -F "document_types=invoice,expense" \
  -F "webhook_url=https://example.com/webhook"
```

### 2. Get Job Status

**Endpoint:** `GET /api/v1/batch-processing/jobs/{job_id}`

**Description:** Get detailed status and progress of a batch processing job.

**Authentication:** JWT (Bearer token) - API key authentication to be implemented

**Path Parameters:**
- `job_id` (required): Batch job ID (UUID)

**Response (200 OK):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": {
    "total_files": 25,
    "processed_files": 17,
    "successful_files": 16,
    "failed_files": 1,
    "progress_percentage": 68.0
  },
  "export": {
    "destination_type": "s3",
    "export_file_url": null,
    "export_completed_at": null
  },
  "timestamps": {
    "created_at": "2025-11-08T10:30:00Z",
    "updated_at": "2025-11-08T10:35:00Z",
    "completed_at": null
  },
  "estimated_completion_at": "2025-11-08T10:45:00Z",
  "files": [
    {
      "id": 1,
      "filename": "invoice_001.pdf",
      "document_type": "invoice",
      "status": "completed",
      "file_size": 245678,
      "retry_count": 0,
      "created_at": "2025-11-08T10:30:00Z",
      "completed_at": "2025-11-08T10:31:00Z",
      "extracted_data": {
        "vendor": "Acme Corp",
        "amount": 1250.00,
        "currency": "USD",
        "date": "2025-11-01",
        "attachment_paths": "s3://bucket/tenant_1/invoices/001.pdf"
      }
    },
    {
      "id": 2,
      "filename": "receipt_002.jpg",
      "document_type": "expense",
      "status": "failed",
      "file_size": 123456,
      "retry_count": 3,
      "created_at": "2025-11-08T10:30:00Z",
      "completed_at": "2025-11-08T10:32:00Z",
      "error_message": "OCR extraction failed: Image quality too low"
    }
  ]
}
```

**Status Values:**
- `pending`: Job created, files not yet enqueued
- `processing`: Files are being processed
- `completed`: All files processed successfully
- `failed`: All files failed processing
- `partial_failure`: Some files succeeded, some failed

**Example using cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/batch-processing/jobs/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. List Jobs

**Endpoint:** `GET /api/v1/batch-processing/jobs`

**Description:** List all batch processing jobs for the authenticated API client.

**Authentication:** JWT (Bearer token) - API key authentication to be implemented

**Query Parameters:**
- `status_filter` (optional): Filter by status (pending, processing, completed, failed, partial_failure)
- `limit` (optional): Maximum number of jobs to return (default: 20, max: 100)
- `offset` (optional): Number of jobs to skip (default: 0)

**Response (200 OK):**
```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "total_files": 25,
      "processed_files": 25,
      "successful_files": 24,
      "failed_files": 1,
      "progress_percentage": 100.0,
      "document_types": ["invoice", "expense"],
      "export_destination_type": "s3",
      "export_file_url": "https://s3.amazonaws.com/bucket/exports/job_550e8400.csv",
      "export_completed_at": "2025-11-08T10:45:00Z",
      "created_at": "2025-11-08T10:30:00Z",
      "updated_at": "2025-11-08T10:45:00Z",
      "completed_at": "2025-11-08T10:45:00Z"
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

**Example using cURL:**
```bash
# List all jobs
curl -X GET "http://localhost:8000/api/v1/batch-processing/jobs" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# List completed jobs with pagination
curl -X GET "http://localhost:8000/api/v1/batch-processing/jobs?status_filter=completed&limit=10&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Implementation Details

### Router Location
- **File:** `api/routers/batch_processing.py`
- **Prefix:** `/api/v1/batch-processing`
- **Tags:** `["batch-processing"]`

### Dependencies
- **Service:** `BatchProcessingService` (from `services.batch_processing_service`)
- **Models:** 
  - `BatchProcessingJob` (from `models.models_per_tenant`)
  - `BatchFileProcessing` (from `models.models_per_tenant`)
  - `ExportDestinationConfig` (from `models.models_per_tenant`)
- **Authentication:** JWT via `get_current_user` (API key auth placeholder implemented)

### Key Features

1. **File Validation:**
   - File count: 1-50 files per batch
   - File size: Maximum 20MB per file
   - File types: PDF, PNG, JPG, JPEG, CSV
   - Empty file detection

2. **Document Type Detection:**
   - Auto-detection based on filename heuristics
   - Manual specification via `document_types` parameter
   - Validation of document type values

3. **Progress Tracking:**
   - Real-time progress percentage calculation
   - File-level status tracking
   - Estimated completion time calculation (30 seconds per file)

4. **Error Handling:**
   - Comprehensive validation with detailed error messages
   - Graceful handling of partial failures
   - Audit logging for all operations

5. **Tenant Isolation:**
   - All queries filtered by tenant_id
   - Export destinations validated for tenant ownership
   - API client scoping (placeholder for API key auth)

## Authentication Notes

**Current Implementation:**
- Uses JWT authentication via `get_current_user` dependency
- Suitable for testing and internal use

**Future Implementation:**
- API key authentication via `X-API-Key` header
- Rate limiting per API client
- Permission validation (admin/write access)
- API client quota enforcement

The `get_api_key_auth` function is implemented as a placeholder and returns HTTP 501 (Not Implemented) until the full API key authentication system is integrated.

## Testing

### Verification Tests
Run the verification tests to ensure proper integration:

```bash
# In Docker container
python test_batch_processing_simple.py
```

**Expected Results:**
- ✅ Router Module Import
- ✅ Router Endpoints
- ✅ App Routes Registration
- ✅ Endpoint HTTP Methods
- ✅ Service Dependency
- ✅ Database Models

### Manual Testing

1. **Create an export destination** (if not already created):
```bash
curl -X POST "http://localhost:8000/api/v1/export-destinations" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test S3 Bucket",
    "destination_type": "s3",
    "credentials": {
      "access_key_id": "YOUR_ACCESS_KEY",
      "secret_access_key": "YOUR_SECRET_KEY",
      "region": "us-east-1"
    },
    "config": {
      "bucket_name": "my-exports",
      "path_prefix": "batch-results/"
    }
  }'
```

2. **Upload a batch of files:**
```bash
curl -X POST "http://localhost:8000/api/v1/batch-processing/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "files=@test_invoice.pdf" \
  -F "files=@test_receipt.jpg" \
  -F "export_destination_id=1"
```

3. **Check job status:**
```bash
curl -X GET "http://localhost:8000/api/v1/batch-processing/jobs/JOB_ID" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

4. **List all jobs:**
```bash
curl -X GET "http://localhost:8000/api/v1/batch-processing/jobs" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Maximum 50 files allowed per batch. Received 75 files."
}
```

### 401 Unauthorized
```json
{
  "detail": "API key required. Provide X-API-Key header."
}
```

### 404 Not Found
```json
{
  "detail": "Batch job 550e8400-e29b-41d4-a716-446655440000 not found or access denied"
}
```

### 413 Request Entity Too Large
```json
{
  "detail": "File 'large_invoice.pdf' exceeds maximum size of 20MB"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to create batch job: Database connection error"
}
```

### 501 Not Implemented
```json
{
  "detail": "API key authentication not yet implemented. Use JWT authentication for testing."
}
```

## Integration with Other Components

### Batch Processing Service
The router delegates all business logic to `BatchProcessingService`:
- Job creation and validation
- File storage and enqueueing
- Progress tracking
- Status retrieval

### Export Service
When all files are processed, the `ExportService` is triggered:
- CSV generation from extracted data
- Upload to configured destination
- URL generation for download

### Kafka Integration
Files are enqueued to appropriate Kafka topics:
- `invoice_ocr` for invoices
- `expense_ocr` for expenses
- `bank_statements_ocr` for bank statements

### Audit Logging
All operations are logged for audit purposes:
- Batch job creation
- File uploads
- Export operations
- Access attempts

## Next Steps

To complete the batch processing feature:

1. **Implement API Key Authentication:**
   - Create APIClient model
   - Implement API key validation
   - Add rate limiting
   - Add permission checks

2. **Implement Rate Limiting (Task 10):**
   - Per-API-client rate limits
   - Concurrent job limits
   - Custom quota support

3. **Implement Security Features (Task 11):**
   - Enhanced tenant isolation
   - Credential encryption validation
   - Comprehensive audit logging

4. **Create Documentation (Task 12):**
   - API documentation
   - Client examples (Python, JavaScript)
   - UI user guide

5. **Write Tests (Task 13):**
   - Unit tests for endpoints
   - Integration tests
   - Performance tests

## Related Documentation

- [Batch Processing Service](BATCH_PROCESSING_SERVICE.md)
- [Export Service Implementation](EXPORT_SERVICE_IMPLEMENTATION.md)
- [Export Destinations API](EXPORT_DESTINATIONS_API.md)
- [Batch Completion Monitoring](BATCH_COMPLETION_MONITORING.md)

