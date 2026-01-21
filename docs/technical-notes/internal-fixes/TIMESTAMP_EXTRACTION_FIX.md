# Receipt Timestamp Extraction Fix

## Problem
Receipt timestamps were not being extracted during OCR processing. The `receipt_timestamp` field remained `None` and `receipt_time_extracted` was `False`.

## Root Cause
The unified OCR service prompt for expense receipts did not include `receipt_timestamp` in the list of required fields to extract. The LLM was only extracting the fields explicitly mentioned in the prompt.

## Solution
Updated the prompt in `api/services/unified_ocr_service.py` to explicitly request timestamp extraction with clear instructions:

```python
"Required keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, "
"total_amount, payment_method, reference_number, notes, receipt_timestamp (YYYY-MM-DD HH:MM:SS if time is visible on receipt). "
"IMPORTANT: For receipt_timestamp, look carefully for any time information on the receipt (like '14:32', '2:45 PM', '10:15 AM', etc.). "
"If you find a time, combine it with the date to create a full timestamp. If only date is visible, set receipt_timestamp to null. "
```

## Verification
After the fix, tested with expense ID 1:

**Before:**
- receipt_timestamp: `None`
- receipt_time_extracted: `False`

**After:**
- receipt_timestamp: `2025-06-26 14:04:00+00`
- receipt_time_extracted: `True`
- expense_date: `2025-06-26 00:00:00+00`

The system successfully extracted the transaction time of **14:04** (2:04 PM) from the receipt.

## Files Modified
- `api/services/unified_ocr_service.py` - Updated EXPENSE_RECEIPT prompt to include receipt_timestamp

## Benefits
- More accurate expense tracking with exact transaction times
- Better audit trail for expense submissions
- Improved data quality for expense analytics
- Helps detect duplicate submissions based on timestamp
