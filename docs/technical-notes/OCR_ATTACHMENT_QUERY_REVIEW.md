# OCR Attachment Query Review - Multiple Attachments Support

## Question
"Seeing this line `attachment = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()` - is refactoring needed to support multiple attachments?"

## Answer
**No refactoring needed for multiple attachments support.** The current implementation is correct and already supports multiple attachments properly.

## Why `.first()` is Correct

### 1. Primary Key Query
```python
attachment = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()
```

- `ExpenseAttachment.id` is a **primary key** (unique identifier)
- Querying by primary key will return **at most one result**
- Using `.first()` is the idiomatic SQLAlchemy way to get a single result
- This is equivalent to `SELECT * FROM expense_attachments WHERE id = ? LIMIT 1`

### 2. Single Attachment Processing by Design
The `process_attachment_inline()` function is designed to process **one attachment at a time**:

```python
async def process_attachment_inline(
    db: Session, 
    expense_id: int, 
    attachment_id: int,  # <-- Single attachment ID
    file_path: str, 
    tenant_id: int
) -> None:
```

This is the correct design because:
- Each attachment is processed independently
- Each attachment has its own OCR task in the message queue
- Retries are per-attachment, not per-expense
- Cache is stored per-attachment

### 3. Multiple Attachments are Handled at a Higher Level

When an expense has multiple attachments, they are processed separately:

```python
# From ocr_consumer.py - processing multiple attachments
for attachment in attachments:
    await queue_or_process_attachment(
        db=db,
        tenant_id=tenant_id,
        expense_id=expense.id,
        attachment_id=attachment.id,  # <-- Each attachment gets its own task
        file_path=str(attachment.file_path)
    )
```

Each attachment gets its own:
- Kafka message
- OCR processing task
- Retry logic
- Cache entry

## Improvements Made

While the `.first()` usage was correct, I added **better error handling**:

### Before
```python
attachment = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()

cached_local_path = None
if attachment and hasattr(attachment, 'local_cache_path') and attachment.local_cache_path:
    # ... use cache
```

### After
```python
attachment = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()

if not attachment:
    logger.error(f"Attachment {attachment_id} not found in database for expense {expense_id}")
    raise Exception(f"Attachment {attachment_id} not found")

cached_local_path = None
if hasattr(attachment, 'local_cache_path') and attachment.local_cache_path:
    # ... use cache
```

**Benefits:**
- Explicit error handling if attachment doesn't exist
- Better logging for debugging
- Fails fast with clear error message
- Prevents silent failures

### Cache Storage Improvement

Also improved the cache storage logic:

```python
# Before
try:
    if attachment:
        attachment.local_cache_path = temp_path
        db.commit()
        logger.info(f"Cached local file path for attachment {attachment_id}: {temp_path}")
except Exception as cache_error:
    logger.warning(f"Failed to cache local file path: {cache_error}")

# After
try:
    attachment.local_cache_path = temp_path
    db.commit()
    logger.info(f"Cached local file path for attachment {attachment_id}: {temp_path}")
except Exception as cache_error:
    logger.warning(f"Failed to cache local file path for attachment {attachment_id}: {cache_error}")
    db.rollback()
```

**Benefits:**
- Removed redundant `if attachment` check (already validated above)
- Added `db.rollback()` on error to prevent transaction issues
- Better error logging with attachment ID

## Architecture for Multiple Attachments

```
Expense (1) ──── (Many) ExpenseAttachment
    │
    └─ attachment_1.pdf
    │  ├─ OCR Task 1
    │  ├─ Cache: /tmp/file_1.pdf
    │  └─ Status: done
    │
    ├─ attachment_2.pdf
    │  ├─ OCR Task 2
    │  ├─ Cache: /tmp/file_2.pdf
    │  └─ Status: processing
    │
    └─ attachment_3.pdf
       ├─ OCR Task 3
       ├─ Cache: /tmp/file_3.pdf
       └─ Status: queued
```

Each attachment:
- Has its own database record
- Gets its own OCR task
- Has its own cache entry
- Can be retried independently
- Can fail independently

## Query Performance

The query is optimal:

```python
db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()
```

**Query Plan:**
```sql
SELECT * FROM expense_attachments 
WHERE id = ? 
LIMIT 1
```

- Uses primary key index
- O(1) lookup time
- Returns immediately after finding one result
- No full table scan

## Conclusion

✅ **No refactoring needed**

The current implementation:
- Correctly uses `.first()` for primary key queries
- Properly supports multiple attachments per expense
- Processes attachments independently
- Has been improved with better error handling
- Is performant and maintainable

The `.first()` method is the correct choice for this use case.
