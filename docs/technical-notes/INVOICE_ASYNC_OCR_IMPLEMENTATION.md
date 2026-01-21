# Invoice Async OCR Implementation

## Overview

This document describes the implementation of asynchronous OCR processing for invoice PDF imports, resolving the issue where the API would get stuck during synchronous AI processing.

## Problem

Previously, invoice PDF import endpoints (`/invoices/process-pdf` and `/invoices/{invoice_id}/attachments`) were performing **synchronous AI/OCR processing**, which caused:

- API requests to hang/timeout during long AI processing
- Poor user experience with no feedback during processing
- Scalability issues under load
- Inconsistent behavior compared to expense OCR (which was already async)

## Solution

Implemented **asynchronous OCR processing** using the existing Kafka-based OCR worker infrastructure, matching the pattern used for expenses.

## Architecture

### Flow Diagram

```
User uploads PDF
      ↓
API saves file & queues task
      ↓
Returns task_id immediately
      ↓
OCR Worker picks up task
      ↓
Processes with AI/OCR
      ↓
Saves results to DB
      ↓
Sends notification to user
```

### Components

1. **API Endpoints** (`api/routers/pdf_processor.py`)
   - `POST /invoices/process-pdf` - Queue invoice PDF for processing
   - `GET /invoices/process-status/{task_id}` - Check processing status

2. **Database Model** (`api/models/models_per_tenant.py`)
   - `InvoiceProcessingTask` - Tracks task status and results

3. **OCR Worker** (`api/workers/ocr_consumer.py`)
   - Consumes from `invoices_ocr` Kafka topic
   - Processes PDFs with AI
   - Updates task status and results

4. **Notifications** (`api/utils/ocr_notifications.py`)
   - `notify_invoice_ocr_complete()` - Notifies user when complete

## Changes Made

### 1. Updated PDF Processor Endpoint

**Before:**
```python
# Synchronous processing - blocks request
extracted_data = await process_pdf_with_ai(temp_pdf_path, active_config)
return {'success': True, 'data': extracted_data}
```

**After:**
```python
# Async processing - returns immediately
task_id = str(uuid.uuid4())
publish_invoice_task(message)
return {'success': True, 'task_id': task_id, 'status': 'queued'}
```

### 2. Added Processing Task Model

```python
class InvoiceProcessingTask(Base):
    task_id = Column(String, unique=True, nullable=False)
    status = Column(String, default="queued")  # queued, processing, completed, failed
    result_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    # ... timestamps and relationships
```

### 3. Enhanced OCR Worker

Added invoice processing logic to handle `invoices_ocr` topic:
- Creates/updates `InvoiceProcessingTask` record
- Processes PDF with AI
- Extracts client information
- Saves results to database
- Sends completion notification

### 4. Updated Invoice Attachment Upload

Changed from synchronous OCR to async queueing:
```python
# Queue for async processing instead of blocking
task_id = str(uuid.uuid4())
publish_invoice_task(message)
response["ocr_status"] = "queued"
response["ocr_task_id"] = task_id
```

## Database Migration

Run the migration to add the new table:

```bash
python api/scripts/migrate_invoice_processing_tasks.py
```

Or manually apply:

```sql
CREATE TABLE invoice_processing_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) UNIQUE NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    error_message TEXT,
    result_data JSONB,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_invoice_processing_tasks_task_id ON invoice_processing_tasks(task_id);
CREATE INDEX idx_invoice_processing_tasks_user_id ON invoice_processing_tasks(user_id);
CREATE INDEX idx_invoice_processing_tasks_status ON invoice_processing_tasks(status);
```

## API Usage

### 1. Upload Invoice PDF

```bash
POST /api/v1/invoices/process-pdf
Content-Type: multipart/form-data

{
  "pdf_file": <file>
}
```

**Response:**
```json
{
  "success": true,
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Invoice PDF queued for processing. You will be notified when extraction is complete."
}
```

### 2. Check Processing Status

```bash
GET /api/v1/invoices/process-status/{task_id}
```

**Response (Processing):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Invoice is being processed",
  "created_at": "2024-11-08T10:30:00Z",
  "updated_at": "2024-11-08T10:30:15Z"
}
```

**Response (Completed):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "message": "Invoice data extracted successfully",
  "data": {
    "invoice_data": {
      "date": "2024-11-01",
      "bills_to": "Client Name\nclient@example.com",
      "items": [...],
      "total_amount": 1500.00
    },
    "client_exists": true,
    "existing_client": {...},
    "suggested_client": {...}
  },
  "created_at": "2024-11-08T10:30:00Z",
  "updated_at": "2024-11-08T10:30:45Z",
  "completed_at": "2024-11-08T10:30:45Z"
}
```

**Response (Failed):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "message": "Invoice processing failed",
  "error": "AI processing timeout",
  "created_at": "2024-11-08T10:30:00Z",
  "updated_at": "2024-11-08T10:31:00Z"
}
```

## Frontend Integration

The frontend should:

1. **Upload PDF** and receive `task_id`
2. **Poll status endpoint** every 2-3 seconds
3. **Show progress indicator** while status is "queued" or "processing"
4. **Display results** when status is "completed"
5. **Show error** when status is "failed"

Example polling logic:
```javascript
async function pollInvoiceStatus(taskId) {
  const maxAttempts = 60; // 3 minutes with 3-second intervals
  let attempts = 0;
  
  while (attempts < maxAttempts) {
    const response = await fetch(`/api/v1/invoices/process-status/${taskId}`);
    const data = await response.json();
    
    if (data.status === 'completed') {
      return data.data; // Success!
    } else if (data.status === 'failed') {
      throw new Error(data.error);
    }
    
    // Still processing, wait and retry
    await new Promise(resolve => setTimeout(resolve, 3000));
    attempts++;
  }
  
  throw new Error('Processing timeout');
}
```

## Benefits

1. **Non-blocking API** - Requests return immediately
2. **Better UX** - Users get feedback and can track progress
3. **Scalability** - OCR worker can be scaled independently
4. **Consistency** - Matches expense OCR pattern
5. **Reliability** - Kafka provides retry and error handling
6. **Monitoring** - Task status tracked in database

## Configuration

Ensure these environment variables are set:

```bash
# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_INVOICE_TOPIC=invoices_ocr
KAFKA_OCR_GROUP=invoice-app-ocr

# AI configuration (or use database AI config)
LLM_MODEL=gpt-4
LLM_API_KEY=your-api-key
LLM_API_BASE=https://api.openai.com/v1
```

## Testing

1. **Start OCR worker:**
   ```bash
   python api/workers/ocr_consumer.py
   ```

2. **Upload test invoice:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/invoices/process-pdf \
     -H "Authorization: Bearer $TOKEN" \
     -F "pdf_file=@test_invoice.pdf"
   ```

3. **Check status:**
   ```bash
   curl http://localhost:8000/api/v1/invoices/process-status/{task_id} \
     -H "Authorization: Bearer $TOKEN"
   ```

## Monitoring

Check OCR worker logs for processing status:
```bash
tail -f logs/ocr_worker.log | grep "invoice"
```

Query processing tasks:
```sql
SELECT task_id, status, created_at, updated_at, completed_at
FROM invoice_processing_tasks
ORDER BY created_at DESC
LIMIT 10;
```

## Troubleshooting

### Issue: Tasks stuck in "queued" status
- **Cause:** OCR worker not running or Kafka connection issue
- **Solution:** Check OCR worker logs, verify Kafka is running

### Issue: Tasks failing with timeout
- **Cause:** AI service slow or unavailable
- **Solution:** Check AI config, increase timeout in worker

### Issue: No notification received
- **Cause:** Notification service not configured
- **Solution:** Check notification settings and logs

## Future Enhancements

1. **WebSocket notifications** - Real-time updates instead of polling
2. **Batch processing** - Process multiple invoices at once
3. **Priority queue** - Prioritize certain users/invoices
4. **Result caching** - Cache results for duplicate PDFs
5. **Progress tracking** - Show percentage complete during processing

## Related Files

- `api/routers/pdf_processor.py` - API endpoints
- `api/workers/ocr_consumer.py` - OCR worker
- `api/models/models_per_tenant.py` - Database models
- `api/services/ocr_service.py` - OCR service functions
- `api/utils/ocr_notifications.py` - Notification utilities
- `api/migrations/add_invoice_processing_tasks.sql` - Database migration

## Summary

This implementation resolves the API blocking issue by moving invoice OCR processing to an asynchronous worker pattern, providing better user experience, scalability, and consistency with the existing expense OCR system.
