# Batch File Processing & Export API Reference

## Overview

The Batch File Processing & Export API enables external systems to upload multiple documents (invoices, expenses, bank statements) in a single request, process them asynchronously using OCR, and export structured results to configured cloud storage destinations.

**Key Features:**
- Upload up to 50 files per batch
- Asynchronous OCR processing via Kafka
- Export to AWS S3, Azure Blob Storage, Google Cloud Storage, or Google Drive
- Real-time progress tracking
- Webhook notifications on completion
- Comprehensive error handling with retry logic

## Base URL

```
https://your-domain.com/api/v1
```

## Authentication

All endpoints require authentication using one of the following methods:

### JWT Bearer Token (Current)
```http
Authorization: Bearer <jwt_token>
```

### API Key (Future)
```http
X-API-Key: <api_key>
```

**Note:** API key authentication is planned but not yet implemented. Use JWT authentication for testing.

## Rate Limits

Rate limits are enforced per API client:

| Limit Type | Default | Configurable |
|------------|---------|--------------|
| Per Minute | 60 | Yes |
| Per Hour | 1,000 | Yes |
| Per Day | 10,000 | Yes |
| Concurrent Jobs | 5 | Yes |

**Rate Limit Headers:**
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1699459200
Retry-After: 30
```

**429 Response:**
```json
{
  "detail": "Rate limit exceeded. Try again in 30 seconds.",
  "retry_after": 30
}
```

---

## Batch Processing Endpoints

### 1. Upload Batch Files

Upload multiple files for batch OCR processing and export.

**Endpoint:** `POST /batch-processing/upload`

**Authentication:** Required (JWT or API Key)

**Content-Type:** `multipart/form-data`

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `files` | File[] | Yes | Files to process (1-50 files, max 20MB each) |
| `export_destination_id` | Integer | Yes | ID of configured export destination |
| `document_types` | String | No | Comma-separated types: `invoice,expense,statement` |
| `custom_fields` | String | No | Comma-separated fields to include in export |
| `webhook_url` | String | No | URL for completion notification |

**Supported File Types:**
- PDF (`.pdf`)
- Images (`.png`, `.jpg`, `.jpeg`)
- CSV (`.csv`)

**Request Example:**

```bash
curl -X POST "https://your-domain.com/api/v1/batch-processing/upload" \
  -H "Authorization: Bearer <jwt_token>" \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf" \
  -F "files=@receipt1.jpg" \
  -F "export_destination_id=1" \
  -F "document_types=invoice,expense" \
  -F "webhook_url=https://example.com/webhook"
```

**Response:** `201 Created`

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "total_files": 3,
  "estimated_completion_minutes": 2,
  "status_url": "/api/v1/batch-processing/jobs/550e8400-e29b-41d4-a716-446655440000",
  "message": "Batch job created successfully. 3 files enqueued for processing."
}
```

**Validation Rules:**
- Minimum 1 file, maximum 50 files per batch
- Maximum file size: 20MB per file
- Export destination must exist and be active
- Document types must be valid: `invoice`, `expense`, or `statement`

**Error Responses:**

```json
// 400 Bad Request - Too many files
{
  "detail": "Maximum 50 files allowed per batch. Received 75 files."
}

// 413 Payload Too Large - File too large
{
  "detail": "File 'large_invoice.pdf' exceeds maximum size of 20MB"
}

// 404 Not Found - Invalid destination
{
  "detail": "Export destination 999 not found or inactive"
}
```

---

### 2. Get Job Status

Retrieve detailed status and progress of a batch processing job.

**Endpoint:** `GET /batch-processing/jobs/{job_id}`

**Authentication:** Required (JWT or API Key)

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | UUID | Yes | Batch job identifier |

**Request Example:**

```bash
curl -X GET "https://your-domain.com/api/v1/batch-processing/jobs/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <jwt_token>"
```

**Response:** `200 OK`

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
        "tax_amount": 125.00,
        "line_items": [
          {
            "description": "Consulting Services",
            "quantity": 10,
            "price": 125.00,
            "amount": 1250.00
          }
        ],
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

**Job Status Values:**

| Status | Description |
|--------|-------------|
| `pending` | Job created, files not yet enqueued |
| `processing` | Files are being processed |
| `completed` | All files processed successfully |
| `failed` | All files failed processing |
| `partial_failure` | Some files succeeded, some failed |

**File Status Values:**

| Status | Description |
|--------|-------------|
| `pending` | File queued for processing |
| `processing` | File is being processed |
| `completed` | File processed successfully |
| `failed` | File processing failed (after retries) |

**Error Responses:**

```json
// 404 Not Found
{
  "detail": "Batch job 550e8400-e29b-41d4-a716-446655440000 not found or access denied"
}
```

---

### 3. List Jobs

List all batch processing jobs for the authenticated user/API client.

**Endpoint:** `GET /batch-processing/jobs`

**Authentication:** Required (JWT or API Key)

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status_filter` | String | No | - | Filter by status |
| `limit` | Integer | No | 20 | Max results (1-100) |
| `offset` | Integer | No | 0 | Pagination offset |

**Request Example:**

```bash
# List all jobs
curl -X GET "https://your-domain.com/api/v1/batch-processing/jobs" \
  -H "Authorization: Bearer <jwt_token>"

# List completed jobs with pagination
curl -X GET "https://your-domain.com/api/v1/batch-processing/jobs?status_filter=completed&limit=10&offset=0" \
  -H "Authorization: Bearer <jwt_token>"
```

**Response:** `200 OK`

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

---

## Export Destination Endpoints

### 4. Create Export Destination

Create a new export destination configuration with encrypted credentials.

**Endpoint:** `POST /export-destinations`

**Authentication:** Required (JWT - Non-viewer role)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "name": "Production S3 Bucket",
  "destination_type": "s3",
  "credentials": {
    "access_key_id": "AKIA...",
    "secret_access_key": "...",
    "region": "us-east-1",
    "bucket_name": "my-exports",
    "path_prefix": "batch-results/"
  },
  "config": {
    "retention_days": 30
  },
  "is_default": false
}
```

**Destination Types:**

| Type | Description | Credentials Required |
|------|-------------|---------------------|
| `s3` | AWS S3 | access_key_id, secret_access_key, region, bucket_name |
| `azure` | Azure Blob Storage | connection_string OR (account_name + account_key), container_name |
| `gcs` | Google Cloud Storage | service_account_json OR (project_id + credentials), bucket_name |
| `google_drive` | Google Drive | oauth_token, refresh_token, folder_id |

**Request Example:**

```bash
curl -X POST "https://your-domain.com/api/v1/export-destinations" \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production S3",
    "destination_type": "s3",
    "credentials": {
      "access_key_id": "AKIAIOSFODNN7EXAMPLE",
      "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
      "region": "us-east-1",
      "bucket_name": "my-exports"
    },
    "is_default": true
  }'
```

**Response:** `201 Created`

```json
{
  "id": 1,
  "tenant_id": 1,
  "name": "Production S3 Bucket",
  "destination_type": "s3",
  "is_active": true,
  "is_default": false,
  "config": {
    "retention_days": 30
  },
  "masked_credentials": {
    "access_key_id": "****AKIA",
    "secret_access_key": "****KEY1",
    "region": "****st-1",
    "bucket_name": "****orts",
    "path_prefix": "****lts/"
  },
  "last_test_at": null,
  "last_test_success": null,
  "last_test_error": null,
  "created_at": "2025-11-08T10:30:00Z",
  "updated_at": "2025-11-08T10:30:00Z",
  "created_by": 1
}
```

**Error Responses:**

```json
// 400 Bad Request - Invalid type
{
  "detail": "Invalid destination type. Must be one of: s3, azure, gcs, google_drive"
}

// 403 Forbidden - Insufficient permissions
{
  "detail": "Insufficient permissions to create export destinations"
}
```

---

### 5. List Export Destinations

List all export destinations for the authenticated tenant.

**Endpoint:** `GET /export-destinations`

**Authentication:** Required (JWT)

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `active_only` | Boolean | No | false | Filter to active destinations only |
| `destination_type` | String | No | - | Filter by type (s3, azure, gcs, google_drive) |
| `skip` | Integer | No | 0 | Pagination offset |
| `limit` | Integer | No | 100 | Max results |

**Request Example:**

```bash
curl -X GET "https://your-domain.com/api/v1/export-destinations?active_only=true" \
  -H "Authorization: Bearer <jwt_token>"
```

**Response:** `200 OK`

```json
{
  "destinations": [
    {
      "id": 1,
      "tenant_id": 1,
      "name": "Production S3 Bucket",
      "destination_type": "s3",
      "is_active": true,
      "is_default": true,
      "config": {},
      "masked_credentials": {
        "access_key_id": "****AKIA",
        "secret_access_key": "****KEY1"
      },
      "last_test_at": "2025-11-08T10:35:00Z",
      "last_test_success": true,
      "last_test_error": null,
      "created_at": "2025-11-08T10:30:00Z",
      "updated_at": "2025-11-08T10:35:00Z",
      "created_by": 1
    }
  ],
  "total": 1
}
```

---

### 6. Get Export Destination

Get a specific export destination by ID.

**Endpoint:** `GET /export-destinations/{destination_id}`

**Authentication:** Required (JWT)

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `destination_id` | Integer | Yes | Destination ID |

**Request Example:**

```bash
curl -X GET "https://your-domain.com/api/v1/export-destinations/1" \
  -H "Authorization: Bearer <jwt_token>"
```

**Response:** `200 OK`

```json
{
  "id": 1,
  "tenant_id": 1,
  "name": "Production S3 Bucket",
  "destination_type": "s3",
  "is_active": true,
  "is_default": true,
  "config": {},
  "masked_credentials": {
    "access_key_id": "****AKIA",
    "secret_access_key": "****KEY1"
  },
  "last_test_at": "2025-11-08T10:35:00Z",
  "last_test_success": true,
  "last_test_error": null,
  "created_at": "2025-11-08T10:30:00Z",
  "updated_at": "2025-11-08T10:35:00Z",
  "created_by": 1
}
```

**Error Responses:**

```json
// 404 Not Found
{
  "detail": "Export destination 123 not found"
}
```

---

### 7. Update Export Destination

Update an existing export destination configuration.

**Endpoint:** `PUT /export-destinations/{destination_id}`

**Authentication:** Required (JWT - Non-viewer role)

**Content-Type:** `application/json`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `destination_id` | Integer | Yes | Destination ID |

**Request Body:**

```json
{
  "name": "Updated S3 Bucket",
  "credentials": {
    "access_key_id": "AKIA...",
    "secret_access_key": "..."
  },
  "is_active": true
}
```

**Note:** You can update individual fields without providing all fields. Credentials will be re-encrypted after update.

**Request Example:**

```bash
curl -X PUT "https://your-domain.com/api/v1/export-destinations/1" \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Production S3",
    "is_active": true
  }'
```

**Response:** `200 OK`

```json
{
  "id": 1,
  "tenant_id": 1,
  "name": "Updated S3 Bucket",
  "destination_type": "s3",
  "is_active": true,
  "is_default": true,
  "config": {},
  "masked_credentials": {
    "access_key_id": "****AKIA",
    "secret_access_key": "****KEY2"
  },
  "last_test_at": "2025-11-08T10:35:00Z",
  "last_test_success": true,
  "last_test_error": null,
  "created_at": "2025-11-08T10:30:00Z",
  "updated_at": "2025-11-08T10:40:00Z",
  "created_by": 1
}
```

---

### 8. Test Export Destination Connection

Test connection to an export destination using stored credentials.

**Endpoint:** `POST /export-destinations/{destination_id}/test`

**Authentication:** Required (JWT)

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `destination_id` | Integer | Yes | Destination ID |

**Request Example:**

```bash
curl -X POST "https://your-domain.com/api/v1/export-destinations/1/test" \
  -H "Authorization: Bearer <jwt_token>"
```

**Response:** `200 OK` (Success)

```json
{
  "success": true,
  "message": "Connection test successful",
  "error_details": null,
  "tested_at": "2025-11-08T10:45:00Z"
}
```

**Response:** `200 OK` (Failure)

```json
{
  "success": false,
  "message": "Connection test failed",
  "error_details": "S3 error (AccessDenied): Access Denied",
  "tested_at": "2025-11-08T10:45:00Z"
}
```

---

### 9. Delete Export Destination

Soft delete an export destination (sets `is_active=false`).

**Endpoint:** `DELETE /export-destinations/{destination_id}`

**Authentication:** Required (JWT - Admin role)

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `destination_id` | Integer | Yes | Destination ID |

**Request Example:**

```bash
curl -X DELETE "https://your-domain.com/api/v1/export-destinations/1" \
  -H "Authorization: Bearer <jwt_token>"
```

**Response:** `204 No Content`

**Note:** This endpoint requires admin permissions and validates that no active batch jobs are using this destination.

---

## Credential Schemas

### AWS S3 Credentials

```json
{
  "access_key_id": "string (required)",
  "secret_access_key": "string (required)",
  "region": "string (required)",
  "bucket_name": "string (required)",
  "path_prefix": "string (optional)"
}
```

### Azure Blob Storage Credentials (Connection String)

```json
{
  "connection_string": "string (required)",
  "container_name": "string (required)",
  "path_prefix": "string (optional)"
}
```

### Azure Blob Storage Credentials (Account Key)

```json
{
  "account_name": "string (required)",
  "account_key": "string (required)",
  "container_name": "string (required)",
  "path_prefix": "string (optional)"
}
```

### Google Cloud Storage Credentials

```json
{
  "service_account_json": "string (required - JSON content)",
  "bucket_name": "string (required)",
  "path_prefix": "string (optional)"
}
```

### Google Drive Credentials

```json
{
  "oauth_token": "string (required)",
  "refresh_token": "string (required)",
  "folder_id": "string (required)"
}
```

---

## Environment Variable Fallback

If no credentials are configured for a destination, the system will attempt to use environment variables:

### S3 Fallback Variables

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=my-exports
AWS_S3_PATH_PREFIX=batch-results/  # optional
```

### Azure Fallback Variables

```bash
AZURE_STORAGE_CONNECTION_STRING=your_connection_string
AZURE_STORAGE_CONTAINER=my-container
AZURE_STORAGE_PATH_PREFIX=batch-results/  # optional
```

### GCS Fallback Variables

```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GCS_BUCKET_NAME=my-exports
GCS_PATH_PREFIX=batch-results/  # optional
```

**Note:** Google Drive does not support environment variable fallback (OAuth2 required).

---

## Webhook Notifications

When a batch job completes, the system can send a webhook notification to a configured URL.

### Webhook Request

**Method:** `POST`

**Headers:**
```http
Content-Type: application/json
User-Agent: BatchProcessingSystem/1.0
X-Webhook-Signature: <hmac_signature>
```

**Payload:**

```json
{
  "event": "batch_job_completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "total_files": 25,
  "successful_files": 24,
  "failed_files": 1,
  "progress_percentage": 100.0,
  "export_file_url": "https://s3.amazonaws.com/bucket/exports/job_550e8400.csv",
  "export_completed_at": "2025-11-08T10:45:00Z",
  "created_at": "2025-11-08T10:30:00Z",
  "completed_at": "2025-11-08T10:45:00Z"
}
```

### Webhook Retry Logic

- **Timeout:** 30 seconds
- **Retries:** Up to 3 attempts
- **Backoff:** Exponential (1s, 2s, 4s)
- **Expected Response:** 2xx status code

---

## CSV Export Format

The generated CSV file contains extracted data from all processed files:

### CSV Structure

```csv
file_name,document_type,status,vendor,amount,currency,date,tax_amount,category,line_items,attachment_paths,error_message
invoice_001.pdf,invoice,completed,Acme Corp,1250.00,USD,2025-11-01,125.00,Services,"[{""description"":""Consulting"",""quantity"":10,""price"":125.00}]","s3://bucket/tenant_1/invoices/001.pdf",
receipt_002.jpg,expense,completed,Office Depot,45.99,USD,2025-11-02,3.68,Office Supplies,[],"s3://bucket/tenant_1/expenses/002.jpg",
statement_003.pdf,statement,failed,,,,,,,,"s3://bucket/tenant_1/statements/003.pdf","OCR extraction failed: Image quality too low"
```

### CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `file_name` | String | Original filename |
| `document_type` | String | invoice, expense, or statement |
| `status` | String | completed or failed |
| `vendor` | String | Vendor/merchant name |
| `amount` | Decimal | Total amount |
| `currency` | String | Currency code (USD, EUR, etc.) |
| `date` | Date | Document date (ISO 8601) |
| `tax_amount` | Decimal | Tax amount |
| `category` | String | Expense category |
| `line_items` | JSON | Array of line items (JSON string) |
| `attachment_paths` | String | Comma-separated file paths/URLs |
| `error_message` | String | Error details (if failed) |

### Custom Field Selection

You can specify which fields to include in the CSV export:

```bash
curl -X POST "https://your-domain.com/api/v1/batch-processing/upload" \
  -H "Authorization: Bearer <jwt_token>" \
  -F "files=@invoice.pdf" \
  -F "export_destination_id=1" \
  -F "custom_fields=vendor,amount,date,attachment_paths"
```

---

## Error Handling

### Common HTTP Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 204 | No Content | Resource deleted successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 413 | Payload Too Large | File size exceeds limit |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 501 | Not Implemented | Feature not yet available |
| 503 | Service Unavailable | Service temporarily unavailable |

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "VALIDATION_ERROR",
  "field": "files",
  "retry_after": 30
}
```

### Retry Logic

The system implements automatic retry logic for transient failures:

**File Processing:**
- Maximum 3 retry attempts
- Exponential backoff: 1s, 2s, 4s
- Permanent failure after max retries

**Export Operations:**
- Maximum 5 retry attempts
- Exponential backoff: 2s, 4s, 8s, 16s, 32s
- Job marked as failed after max retries

**Webhook Notifications:**
- Maximum 3 retry attempts
- Exponential backoff: 1s, 2s, 4s
- Logged but doesn't fail job

---

## Security

### Credential Encryption

All export destination credentials are encrypted using tenant-specific encryption keys before storage. Credentials are:

- Encrypted at rest using AES-256
- Decrypted only when needed for operations
- Never returned in API responses (masked)
- Stored in `encrypted_credentials` BLOB column

### Credential Masking

When credentials are returned in API responses, they are masked to show only the last 4 characters:

```json
{
  "access_key_id": "****AKIA",
  "secret_access_key": "****KEY1"
}
```

### Tenant Isolation

All operations respect tenant boundaries:

- Database queries filtered by `tenant_id`
- Export destinations scoped to tenant
- Files stored in tenant-specific paths
- No cross-tenant access allowed

### Audit Logging

All operations are logged for audit purposes:

- Batch job creation and completion
- Export destination configuration changes
- Connection test results
- Failed operations with error details
- User ID, timestamp, and action type

---

## Best Practices

### 1. File Organization

- Group related files in a single batch
- Use consistent naming conventions
- Specify document types when known
- Keep file sizes reasonable (< 10MB recommended)

### 2. Error Handling

- Always check job status after upload
- Handle partial failures gracefully
- Implement webhook handlers for async notifications
- Log all API responses for debugging

### 3. Rate Limiting

- Implement exponential backoff for retries
- Monitor rate limit headers
- Request custom quotas if needed
- Distribute load across time

### 4. Security

- Use HTTPS for all API calls
- Store API keys/tokens securely
- Rotate credentials regularly
- Monitor usage for anomalies
- Use IP restrictions when possible

### 5. Export Destinations

- Test connections before production use
- Use environment variables for development
- Configure separate destinations for dev/staging/prod
- Monitor export success rates
- Set appropriate retention policies

---

## Support

For additional help:

- **Documentation:** See related docs in `api/docs/`
- **Examples:** Check `api/examples/` for code samples
- **Issues:** Report bugs via your issue tracker
- **API Status:** Monitor system health endpoints

## Related Documentation

- [Batch Processing Service](BATCH_PROCESSING_SERVICE.md)
- [Export Service Implementation](EXPORT_SERVICE_IMPLEMENTATION.md)
- [Export Destinations API](EXPORT_DESTINATIONS_API.md)
- [Batch Completion Monitoring](BATCH_COMPLETION_MONITORING.md)
- [Rate Limiting Implementation](../docs/RATE_LIMITING_IMPLEMENTATION_SUMMARY.md)
