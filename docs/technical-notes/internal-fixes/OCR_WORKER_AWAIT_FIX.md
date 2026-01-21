# OCR Worker Await Fix

## Issue
The OCR worker was crashing with the error:
```
ERROR:__main__:Failed to publish OCR result: object bool can't be used in 'await' expression
```

## Root Cause
The `publish_ocr_result()` function in `api/services/ocr_service.py` is a **synchronous** function that returns a boolean:
```python
def publish_ocr_result(...) -> bool:
```

However, in `api/workers/ocr_consumer.py`, the code was incorrectly trying to `await` this synchronous function:
```python
await publish_ocr_result(expense_id, tenant_id, status, details)
```

When you `await` a non-async function, Python tries to await the return value (a boolean in this case), which causes the error.

## Fix
Removed the `await` keyword from all calls to `publish_ocr_result()`:

1. In `_publish_ocr_result()` method (line ~499)
2. In `_send_to_dlq()` method (line ~484)

Changed from:
```python
await publish_ocr_result(expense_id, tenant_id, status, details)
```

To:
```python
publish_ocr_result(expense_id, tenant_id, status, details)
```

## Files Modified
- `api/workers/ocr_consumer.py` - Removed incorrect `await` keywords

## Testing
The fix has been validated with no diagnostic errors in the file.
