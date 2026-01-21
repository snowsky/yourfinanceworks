# Batch File Processing - Quick Reference Card

## 🚀 Quick Start (5 Minutes)

### 1. Configure Export Destination (UI)
```
Settings → Export Destinations → Add Destination → Select S3 → Enter Credentials → Test → Save
```

### 2. Upload Batch (Python)
```python
from batch_processing_client import BatchProcessingClient

client = BatchProcessingClient("https://api.example.com", "your_token")
job = client.upload_batch(files=['file1.pdf', 'file2.pdf'], export_destination_id=1)
print(f"Job ID: {job['job_id']}")
```

### 3. Check Status
```bash
curl -H "Authorization: Bearer TOKEN" \
  https://api.example.com/api/v1/batch-processing/jobs/JOB_ID
```

---

## 📋 API Endpoints Cheat Sheet

### Batch Processing

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/batch-processing/upload` | POST | Upload files |
| `/batch-processing/jobs/{id}` | GET | Get job status |
| `/batch-processing/jobs` | GET | List all jobs |

### Export Destinations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/export-destinations` | POST | Create destination |
| `/export-destinations` | GET | List destinations |
| `/export-destinations/{id}` | GET | Get destination |
| `/export-destinations/{id}` | PUT | Update destination |
| `/export-destinations/{id}/test` | POST | Test connection |
| `/export-destinations/{id}` | DELETE | Delete destination |

---

## 🔑 Authentication

```bash
# JWT Token (Current)
Authorization: Bearer <jwt_token>

# API Key (Future)
X-API-Key: <api_key>
```

---

## 📊 Rate Limits

| Limit | Default | Header |
|-------|---------|--------|
| Per Minute | 60 | X-RateLimit-Limit |
| Per Hour | 1,000 | X-RateLimit-Remaining |
| Per Day | 10,000 | X-RateLimit-Reset |
| Concurrent Jobs | 5 | - |

---

## 🗂️ Destination Types

### AWS S3
```json
{
  "access_key_id": "AKIA...",
  "secret_access_key": "...",
  "region": "us-east-1",
  "bucket_name": "my-exports"
}
```

### Azure Blob
```json
{
  "connection_string": "DefaultEndpointsProtocol=https;...",
  "container_name": "my-container"
}
```

### Google Cloud Storage
```json
{
  "service_account_json": "{...}",
  "bucket_name": "my-exports"
}
```

### Google Drive
```json
{
  "oauth_token": "...",
  "refresh_token": "...",
  "folder_id": "..."
}
```

---

## 📁 File Limits

| Limit | Value |
|-------|-------|
| Max Files per Batch | 50 |
| Max File Size | 20MB |
| Supported Types | PDF, PNG, JPG, JPEG, CSV |

---

## 📈 Job Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Job created, not yet processing |
| `processing` | Files being processed |
| `completed` | All files successful |
| `failed` | All files failed |
| `partial_failure` | Some succeeded, some failed |

---

## 🔄 Retry Logic

### File Processing
- **Attempts:** 3
- **Backoff:** 1s, 2s, 4s

### Export Operations
- **Attempts:** 5
- **Backoff:** 2s, 4s, 8s, 16s, 32s

### Webhooks
- **Attempts:** 3
- **Backoff:** 1s, 2s, 4s
- **Timeout:** 30s

---

## 🌍 Environment Variables

### AWS S3
```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_S3_BUCKET=my-exports
AWS_S3_PATH_PREFIX=batch-results/
```

### Azure
```bash
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_STORAGE_CONTAINER=my-container
AZURE_STORAGE_PATH_PREFIX=batch-results/
```

### GCS
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GCS_BUCKET_NAME=my-exports
GCS_PATH_PREFIX=batch-results/
```

---

## 🐛 Common Errors

| Code | Error | Solution |
|------|-------|----------|
| 400 | Too many files | Max 50 files per batch |
| 401 | Unauthorized | Check auth token |
| 404 | Job not found | Verify job ID |
| 413 | File too large | Max 20MB per file |
| 429 | Rate limit | Wait and retry |

---

## 📝 CSV Export Format

```csv
file_name,document_type,status,vendor,amount,currency,date,tax_amount,category,line_items,attachment_paths,error_message
invoice.pdf,invoice,completed,Acme Corp,1250.00,USD,2025-11-01,125.00,Services,"[{...}]",s3://...,
```

---

## 🔔 Webhook Payload

```json
{
  "event": "batch_job_completed",
  "job_id": "550e8400-...",
  "status": "completed",
  "total_files": 25,
  "successful_files": 24,
  "failed_files": 1,
  "export_file_url": "https://...",
  "completed_at": "2025-11-08T10:45:00Z"
}
```

---

## 🔍 Testing Connections

### UI
```
Export Destinations → Select Destination → Click Test Button → Review Result
```

### API
```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  https://api.example.com/api/v1/export-destinations/1/test
```

---

## 📚 Documentation Links

| Document | Purpose |
|----------|---------|
| [API Reference](BATCH_FILE_PROCESSING_API_REFERENCE.md) | Complete API docs |
| [Python Examples](../examples/batch_processing_client.py) | Code examples |
| [UI User Guide](../../docs/BATCH_PROCESSING_UI_USER_GUIDE.md) | UI instructions |
| [Documentation Index](BATCH_PROCESSING_DOCUMENTATION_INDEX.md) | All docs |

---

## 💡 Pro Tips

1. **Always test connections** before saving destinations
2. **Use environment variables** for development only
3. **Set up webhooks** for async notifications
4. **Monitor rate limits** in response headers
5. **Check job status** periodically during processing
6. **Download exports** within retention period
7. **Use custom fields** to reduce CSV size
8. **Batch similar files** together for efficiency

---

## 🆘 Quick Help

### Can't upload files?
- Check file count (max 50)
- Check file size (max 20MB each)
- Verify destination is active
- Check authentication

### Connection test fails?
- Verify credentials are correct
- Check bucket/container exists
- Ensure proper permissions
- Test network connectivity

### Job stuck in processing?
- Check OCR worker status
- Review file processing logs
- Verify Kafka is running
- Check for errors in files

### Export not generated?
- Verify all files processed
- Check export destination is valid
- Review export service logs
- Ensure destination has write permissions

---

## 📞 Support

- **Documentation:** See [Documentation Index](BATCH_PROCESSING_DOCUMENTATION_INDEX.md)
- **Examples:** Check `api/examples/` directory
- **Issues:** Review [Troubleshooting Guide](../../docs/BATCH_PROCESSING_UI_USER_GUIDE.md#troubleshooting)

---

**Version:** 1.0  
**Last Updated:** November 8, 2025  
**Print this card for quick reference!**
