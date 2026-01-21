# Batch Upload Filename Fix

## Issue

Expense, invoice, and statement attachments created through batch upload were all named "batch_file" instead of using the original filename.

## Root Cause

The Kafka message payload sent to the OCR workers did not include the `original_filename` and `file_size` fields. The OCR consumer was trying to read these fields from the payload but they were missing, causing it to fall back to the default value "batch_file".

## Solution

### 1. Updated Batch Processing Service

**File:** `api/services/batch_processing_service.py`

#### Modified `_publish_to_kafka()` method:
- Added `original_filename` parameter
- Added `file_size` parameter
- Included both fields in the Kafka message payload

```python
message = {
    "batch_job_id": job_id,
    "batch_file_id": file_id,
    "file_path": file_path,
    "original_filename": original_filename,  # NEW
    "file_size": file_size,                  # NEW
    "tenant_id": tenant_id,
    "user_id": user_id,
    "document_type": document_type,
    "message_id": message_id,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "attempt": 0
}
```

#### Updated method calls:
- `enqueue_files_to_kafka()`: Now passes `original_filename` and `file_size` to `_publish_to_kafka()`
- `retry_file()`: Now passes `original_filename` and `file_size` to `_publish_to_kafka()`

### 2. OCR Consumer Already Correct

**File:** `api/workers/ocr_consumer.py`

The OCR consumer was already correctly trying to read the filename from the payload:

#### Expense Attachments:
```python
attachment = ExpenseAttachment(
    expense_id=expense.id,
    filename=payload.get("original_filename", "batch_file"),  # Already correct
    file_path=file_path,
    size_bytes=payload.get("file_size", 0),
    content_type='application/octet-stream'
)
```

#### Invoice Attachments:
```python
original_filename = payload.get("original_filename", "batch_file")
attachment = InvoiceAttachment(
    invoice_id=invoice.id,
    filename=original_filename,  # Already correct
    stored_filename=payload.get("stored_filename", original_filename),
    file_path=file_path,
    file_size=payload.get("file_size", 0),
    content_type='application/pdf',
    attachment_type='document',
    uploaded_by=user_id
)
```

#### Bank Statement Records:
```python
statement = BankStatement(
    tenant_id=tenant_id,
    original_filename=payload.get("original_filename", "batch_file"),  # Already correct
    stored_filename=payload.get("stored_filename", "batch_file"),
    file_path=file_path,
    status='processed',
    extracted_count=len(txns) if txns else 0,
    notes=f"Batch processed from job {batch_job_id}"
)
```

## Impact

- **Expenses**: Attachments now show the original filename (e.g., "receipt_2024.pdf" instead of "batch_file")
- **Invoices**: Attachments now show the original filename (e.g., "invoice_001.pdf" instead of "batch_file")
- **Bank Statements**: Records now show the original filename (e.g., "statement_jan.csv" instead of "batch_file")

## File Content

The file content was already correct. The files are stored on disk with the correct content, and the `file_path` in the Kafka message correctly points to the stored file. The OCR service reads the file from disk using this path, so the content processing was never affected - only the displayed filename in the attachment records was wrong.

## Testing

To verify the fix:

1. Upload files through the batch processing API
2. Wait for processing to complete
3. Check the created expense/invoice/statement records
4. Verify that attachments show the original filename
5. Download the attachment and verify the content is correct

## Example

**Before:**
- Upload: `my_receipt_2024.pdf`
- Attachment shown: `batch_file`

**After:**
- Upload: `my_receipt_2024.pdf`
- Attachment shown: `my_receipt_2024.pdf`

## Notes

- This fix applies to all new batch uploads after deployment
- Existing records with "batch_file" names will not be automatically updated
- The actual file content and processing were never affected - only the displayed filename
- No database migration is required
