# Batch Processing & External API Access

YourFinanceWORKS provides a comprehensive batch processing system that enables external systems to upload, process, and export large volumes of financial documents through secure API key authentication.

## 🚀 Key Features

- **Bulk File Upload**: Submit up to 50 files per request (invoices, expenses, bank statements)
- **Asynchronous Processing**: Files are processed in the background using existing OCR infrastructure
- **Multi-Destination Export**: Export results to AWS S3, Azure Blob Storage, Google Cloud Storage, or Google Drive
- **API Key Authentication**: Secure, granular access control with rate limiting and quotas
- **Progress Tracking**: Real-time job status monitoring with file-level details
- **Webhook Notifications**: Receive alerts when batch jobs complete or fail
- **Error Resilience**: Automatic retry logic with partial failure support
- **Tenant Isolation**: All operations respect multi-tenant boundaries with encrypted credentials

## 🏗️ Architecture Overview

The batch processing system integrates three core components:

```
External API Access (Authentication Layer)
    ↓
    ├─→ Batch Processing (Orchestration)
    │   └─→ External Transactions (Data)
    │
    └─→ Direct transaction imports
        └─→ External Transactions (Individual records)
```

### Component Breakdown

**External API Access**
- Provides authenticated API endpoints for external systems
- Issues and manages API keys with granular permissions
- Enforces rate limiting and access quotas
- Enables third-party integrations

**Batch Processing**
- Orchestrates bulk file operations
- Manages asynchronous job queues
- Tracks progress across multiple files
- Handles export to configured destinations

**External Transactions**
- Represents individual financial transactions from external sources
- Stores extracted data (vendor, amount, date, line items, etc.)
- Supports attribution and reconciliation
- Integrates with approval workflows

## 🔑 Authentication

All batch processing endpoints require API key authentication:

```bash
# Header-based authentication
X-API-Key: your_api_key

# Alternative
Authorization: Bearer your_api_key
```

API keys are created and managed through the admin interface or programmatically via the API.

## 📤 Batch Upload Workflow

### 1. Create Batch Job

Submit multiple files in a single request:

```bash
curl -X POST https://api.yourfinanceworks.com/api/v1/batch-processing/upload \
  -H "X-API-Key: your_api_key" \
  -F "files=@invoice_001.pdf" \
  -F "files=@invoice_002.pdf" \
  -F "files=@expense_receipt.jpg" \
  -F "document_types=invoice,invoice,expense" \
  -F "export_destination_id=5" \
  -F "webhook_url=https://your-system.com/webhooks/batch-complete"
```

**Request Parameters:**
- `files` (required): Up to 50 files (PDF, PNG, JPG, CSV)
- `document_types` (optional): Specify type for each file (auto-detected if omitted)
- `export_destination_id` (required): ID of configured export destination
- `custom_fields` (optional): Comma-separated list of fields to include in export
- `webhook_url` (optional): URL to notify when job completes

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "total_files": 3,
  "estimated_completion_minutes": 5,
  "status_url": "/api/v1/batch-processing/jobs/550e8400-e29b-41d4-a716-446655440000"
}
```

### 2. Monitor Job Progress

Poll the status endpoint to track processing:

```bash
curl -X GET https://api.yourfinanceworks.com/api/v1/batch-processing/jobs/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: your_api_key"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress_percentage": 68.0,
  "total_files": 3,
  "processed_files": 2,
  "successful_files": 2,
  "failed_files": 0,
  "export_file_url": null,
  "created_at": "2025-11-08T10:30:00Z",
  "estimated_completion_at": "2025-11-08T10:35:00Z",
  "files": [
    {
      "filename": "invoice_001.pdf",
      "status": "completed",
      "document_type": "invoice",
      "extracted_data": {
        "vendor": "Acme Corp",
        "amount": 1250.00,
        "currency": "USD",
        "date": "2025-11-01",
        "attachment_paths": "s3://bucket/tenant_1/invoices/001.pdf"
      }
    },
    {
      "filename": "invoice_002.pdf",
      "status": "processing",
      "document_type": "invoice"
    },
    {
      "filename": "expense_receipt.jpg",
      "status": "pending",
      "document_type": "expense"
    }
  ]
}
```

### 3. Retrieve Results

Once complete, download the CSV export:

```bash
curl -X GET https://api.yourfinanceworks.com/api/v1/batch-processing/jobs/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: your_api_key" | jq '.export_file_url'
```

The CSV is automatically uploaded to your configured export destination (S3, Azure, GCS, or Google Drive).

## 📊 Export Destinations

Configure where batch results are exported:

### Supported Destinations

- **AWS S3**: Bucket-based cloud storage
- **Azure Blob Storage**: Microsoft cloud storage
- **Google Cloud Storage**: Google's cloud storage
- **Google Drive**: Cloud file storage with folder organization

### Configure via UI

1. Navigate to **Settings** → **Export Destinations**
2. Select destination type from dropdown
3. Enter credentials (encrypted and stored securely)
4. Test connection before saving
5. Set as default for batch uploads

### Configure via API

```bash
# Create export destination
curl -X POST https://api.yourfinanceworks.com/api/v1/export-destinations \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production S3 Bucket",
    "destination_type": "s3",
    "credentials": {
      "access_key_id": "AKIA...",
      "secret_access_key": "...",
      "region": "us-east-1"
    },
    "config": {
      "bucket_name": "my-exports",
      "path_prefix": "batch-results/"
    }
  }'

# Test connection
curl -X POST https://api.yourfinanceworks.com/api/v1/export-destinations/5/test \
  -H "X-API-Key: your_api_key"

# List destinations
curl -X GET https://api.yourfinanceworks.com/api/v1/export-destinations \
  -H "X-API-Key: your_api_key"
```

## 🔐 Security & Access Control

### API Key Management

- **Granular Permissions**: Assign specific permissions to each API key
- **Rate Limiting**: Enforce per-minute, per-hour, and per-day quotas
- **Concurrent Job Limits**: Default 5 concurrent jobs per API client
- **Audit Logging**: All batch operations logged with user ID and timestamp

### Credential Security

- **Encrypted Storage**: Export destination credentials encrypted with tenant-specific keys
- **Masked Display**: Credentials shown only as masked values (last 4 characters visible)
- **Fallback Support**: Environment variables used as fallback if no credentials configured

### Tenant Isolation

- All batch jobs scoped to authenticated tenant
- Export destinations accessible only to owning tenant
- Tenant-specific encryption keys for sensitive data
- Cross-tenant access prevented at database query level

## 📋 CSV Export Format

The generated CSV includes the following columns:

```csv
file_name,document_type,status,vendor,amount,currency,date,tax_amount,category,line_items,attachment_paths,error_message
invoice_001.pdf,invoice,completed,Acme Corp,1250.00,USD,2025-11-01,125.00,Services,"[{""description"":""Consulting"",""quantity"":10,""price"":125.00}]","s3://bucket/tenant_1/invoices/001.pdf",
receipt_002.jpg,expense,completed,Office Depot,45.99,USD,2025-11-02,3.68,Office Supplies,[],"s3://bucket/tenant_1/expenses/002.jpg",
statement_003.pdf,statement,failed,,,,,,,,"s3://bucket/tenant_1/statements/003.pdf","OCR extraction failed: Image quality too low"
```

**Column Descriptions:**
- `file_name`: Original uploaded filename
- `document_type`: Type of document (invoice, expense, statement)
- `status`: Processing status (completed, failed, pending)
- `vendor`: Extracted vendor/merchant name
- `amount`: Transaction amount
- `currency`: Currency code (USD, EUR, etc.)
- `date`: Transaction date (ISO 8601 format)
- `tax_amount`: Extracted tax amount
- `category`: Categorized expense category
- `line_items`: JSON array of line items (for invoices)
- `attachment_paths`: Comma-separated URLs to uploaded files
- `error_message`: Error details if processing failed

## ⚙️ Error Handling & Retry Logic

### Automatic Retries

- **File Processing**: Up to 3 retries with exponential backoff
- **Export Upload**: Up to 5 retries with exponential backoff
- **Webhook Notifications**: Up to 3 retries

### Partial Failure Handling

If some files fail:
- Job status set to `partial_failure`
- Successful files included in CSV export
- Failed files marked with error messages
- No data loss—all results retained

### Common Error Scenarios

| Error | Cause | Resolution |
|-------|-------|-----------|
| `OCR extraction failed` | Image quality too low | Ensure clear, high-resolution scans |
| `Destination unreachable` | Cloud storage credentials invalid | Test connection in Settings |
| `Rate limit exceeded` | Too many concurrent jobs | Wait for jobs to complete or increase quota |
| `File too large` | File exceeds 20MB limit | Split into smaller files |
| `Invalid file format` | Unsupported file type | Use PDF, PNG, JPG, or CSV |

## 🔔 Webhook Notifications

Receive real-time alerts when batch jobs complete:

```bash
# Configure webhook URL in batch upload request
curl -X POST https://api.yourfinanceworks.com/api/v1/batch-processing/upload \
  -H "X-API-Key: your_api_key" \
  -F "files=@invoice.pdf" \
  -F "export_destination_id=5" \
  -F "webhook_url=https://your-system.com/webhooks/batch-complete"
```

**Webhook Payload:**
```json
{
  "event": "batch.completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "total_files": 3,
  "successful_files": 3,
  "failed_files": 0,
  "export_file_url": "https://s3.amazonaws.com/my-exports/batch-550e8400.csv",
  "completed_at": "2025-11-08T10:35:00Z"
}
```

## 📚 Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/batch-processing/upload` | POST | Submit batch upload request |
| `/api/v1/batch-processing/jobs` | GET | List all batch jobs |
| `/api/v1/batch-processing/jobs/{job_id}` | GET | Get job status and details |
| `/api/v1/export-destinations` | GET | List export destinations |
| `/api/v1/export-destinations` | POST | Create export destination |
| `/api/v1/export-destinations/{id}` | PUT | Update export destination |
| `/api/v1/export-destinations/{id}` | DELETE | Delete export destination |
| `/api/v1/export-destinations/{id}/test` | POST | Test destination connection |

## 💡 Best Practices

1. **Use Webhooks**: Implement webhook handlers instead of polling for job completion
2. **Handle Partial Failures**: Always check the CSV for error messages in failed rows
3. **Organize Exports**: Use path prefixes to organize results by date or source
4. **Monitor Quotas**: Track API usage to stay within rate limits
5. **Test First**: Use sandbox API keys to test integrations before production
6. **Secure Credentials**: Never hardcode API keys; use environment variables
7. **Batch Efficiently**: Group related documents to minimize API calls

## 🔗 Related Features

- [External Transactions & API Integration](./EXTERNAL_TRANSACTIONS.md)
- [Cloud Storage Integration](./CLOUD_STORAGE.md)
- [AI Services](./AI_SERVICES.md)

## 📖 For More Information

- [Batch Processing Design Document](.kiro/specs/batch-file-processing-export/design.md)
- [API Usage Examples](../technical-notes/EXTERNAL_API_USAGE.md)
- [Admin Guide - Batch Processing](../admin-guide/BATCH_PROCESSING_GUIDE.md)
