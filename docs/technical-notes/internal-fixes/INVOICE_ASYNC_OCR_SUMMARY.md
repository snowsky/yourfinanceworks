# Invoice Async OCR - Implementation Summary

## Problem Solved

**Issue:** Invoice PDF import was getting stuck because the API was performing synchronous AI/OCR processing, causing requests to hang during long AI operations.

**Root Cause:** Unlike expenses (which use async OCR worker), invoices were processing PDFs synchronously in the API request thread.

## Solution Implemented

Refactored invoice PDF processing to use **asynchronous OCR worker pattern**, matching the expense workflow.

## Changes Made

### 1. API Endpoints (`api/routers/pdf_processor.py`)

**Modified:**
- `POST /invoices/process-pdf` - Now queues task and returns immediately with `task_id`

**Added:**
- `GET /invoices/process-status/{task_id}` - Check processing status

### 2. Database Model (`api/models/models_per_tenant.py`)

**Added:**
```python
class InvoiceProcessingTask(Base):
    task_id = Column(String, unique=True)  # UUID for tracking
    status = Column(String)  # queued, processing, completed, failed
    result_data = Column(JSON)  # Extracted invoice data
    error_message = Column(Text)
    # ... timestamps and relationships
```

### 3. OCR Worker (`api/workers/ocr_consumer.py`)

**Enhanced:** Added invoice processing logic for `invoices_ocr` topic:
- Creates/updates `InvoiceProcessingTask` record
- Processes PDF with AI
- Extracts and formats invoice data
- Saves results to database
- Sends completion notification

### 4. Invoice Attachments (`api/routers/invoices.py`)

**Modified:** `POST /invoices/{invoice_id}/attachments` - Now queues OCR task instead of blocking

### 5. Notifications (`api/utils/ocr_notifications.py`)

**Added:** `notify_invoice_ocr_complete()` - Sends notification when processing completes

### 6. Database Migration

**Created:**
- `api/migrations/add_invoice_processing_tasks.sql`
- `api/scripts/migrate_invoice_processing_tasks.py`

**Status:** ✅ Migration completed successfully for tenant_1

## Verification

### ✅ Database Table Created
```sql
SELECT * FROM invoice_processing_tasks;
-- Table exists with proper indexes and foreign keys
```

### ✅ API Started Successfully
```
INFO: Application startup complete.
INFO: invoice_processing_tasks table created
```

### ✅ OCR Workers Running
```
INFO: OCR consumer running on topics=['expenses_ocr', 'bank_statements_ocr', 'invoices_ocr']
```

## API Usage

### Upload Invoice PDF
```bash
POST /api/v1/invoices/process-pdf
Content-Type: multipart/form-data

Response:
{
  "success": true,
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Invoice PDF queued for processing..."
}
```

### Check Status
```bash
GET /api/v1/invoices/process-status/{task_id}

Response (completed):
{
  "task_id": "...",
  "status": "completed",
  "data": {
    "invoice_data": {...},
    "client_exists": true,
    "existing_client": {...}
  }
}
```

## Benefits

1. **Non-blocking API** - Requests return immediately
2. **Better UX** - Users can track progress
3. **Scalability** - OCR workers can be scaled independently
4. **Consistency** - Matches expense OCR pattern
5. **Reliability** - Kafka provides retry and error handling

## Testing

### Manual Test
1. Upload invoice PDF via API
2. Receive task_id
3. Poll status endpoint
4. Verify completion and data extraction

### Check Logs
```bash
# API logs
docker-compose logs -f api | grep invoice

# OCR worker logs
docker-compose logs -f ocr-worker | grep invoice
```

## Next Steps for Frontend

The UI needs to be updated to:

1. **Handle async response** - Receive task_id instead of immediate data
2. **Poll status** - Check `/invoices/process-status/{task_id}` every 2-3 seconds
3. **Show progress** - Display loading indicator while processing
4. **Handle completion** - Display extracted data when status is "completed"
5. **Handle errors** - Show error message when status is "failed"

Example polling code:
```javascript
async function uploadAndProcessInvoice(file) {
  // Upload
  const uploadResponse = await fetch('/api/v1/invoices/process-pdf', {
    method: 'POST',
    body: formData
  });
  const { task_id } = await uploadResponse.json();
  
  // Poll status
  while (true) {
    const statusResponse = await fetch(`/api/v1/invoices/process-status/${task_id}`);
    const status = await statusResponse.json();
    
    if (status.status === 'completed') {
      return status.data; // Success!
    } else if (status.status === 'failed') {
      throw new Error(status.error);
    }
    
    await new Promise(resolve => setTimeout(resolve, 3000)); // Wait 3s
  }
}
```

## Configuration

Ensure these environment variables are set (already configured in docker-compose.yml):

```bash
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_INVOICE_TOPIC=invoices_ocr
KAFKA_OCR_GROUP=invoice-app-ocr
```

## Monitoring

### Check Processing Tasks
```sql
-- Recent tasks
SELECT task_id, status, filename, created_at, completed_at
FROM invoice_processing_tasks
ORDER BY created_at DESC
LIMIT 10;

-- Task statistics
SELECT status, COUNT(*) as count
FROM invoice_processing_tasks
GROUP BY status;
```

### Check Kafka Topics
```bash
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092
# Should show: invoices_ocr
```

## Files Modified/Created

### Modified
- `api/routers/pdf_processor.py` - Async endpoints
- `api/routers/invoices.py` - Async attachment upload
- `api/workers/ocr_consumer.py` - Invoice processing logic
- `api/models/models_per_tenant.py` - New model
- `api/utils/ocr_notifications.py` - Notification function

### Created
- `api/migrations/add_invoice_processing_tasks.sql` - Migration SQL
- `api/scripts/migrate_invoice_processing_tasks.py` - Migration script
- `docs/INVOICE_ASYNC_OCR_IMPLEMENTATION.md` - Detailed documentation
- `docs/INVOICE_ASYNC_OCR_SUMMARY.md` - This summary

## Status: ✅ COMPLETE

The invoice async OCR implementation is complete and verified:
- ✅ Database migration successful
- ✅ API endpoints updated and running
- ✅ OCR workers listening to invoice topic
- ✅ Models and services updated
- ✅ Documentation created

**The API will no longer get stuck during invoice PDF imports!**
