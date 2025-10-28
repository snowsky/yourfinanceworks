# Attachment Response Fix

## Problem
The API was returning incorrect attachment information in the invoice response. Even though the database had the correct attachment data:
- `attachment_path=attachments/tenant_1/invoices/invoice_2_Invoice_HcDat-2025-Aug.pdf`
- `attachment_filename=Invoice_HcDat-2025-Aug.pdf`

The API response was returning:
- `has_attachment=False`
- `attachment_filename=None`

## Root Cause
The `read_invoice` endpoint (GET `/invoices/{invoice_id}`) was only checking for **new-style attachments** from the `InvoiceAttachment` table, but the attachment was saved using the **old-style attachment system** (directly on the `Invoice` table with `attachment_path` and `attachment_filename` fields).

### Code Analysis
**Before Fix** (Line ~1079-1080 in `api/routers/invoices.py`):
```python
"has_attachment": len(new_attachments) > 0,
"attachment_filename": new_attachments[0].filename if new_attachments else None,
```

This only checked `new_attachments` from the `InvoiceAttachment` table and ignored the old-style attachment fields on the `Invoice` record.

## Solution
Updated the response construction to check **both** old-style and new-style attachments.

### Code Changes
**After Fix** (Line ~1079-1080 in `api/routers/invoices.py`):
```python
"has_attachment": len(new_attachments) > 0 or bool(invoice.attachment_filename),
"attachment_filename": new_attachments[0].filename if new_attachments else invoice.attachment_filename,
```

### Logic Explanation
1. **has_attachment**: Returns `True` if either:
   - There are new-style attachments (`len(new_attachments) > 0`), OR
   - There's an old-style attachment (`bool(invoice.attachment_filename)`)

2. **attachment_filename**: Returns:
   - New-style attachment filename if available (`new_attachments[0].filename`)
   - Otherwise, old-style attachment filename (`invoice.attachment_filename`)

## Verification
The fix ensures backward compatibility by supporting both attachment systems:
- **New system**: Uses `InvoiceAttachment` table (for future attachments)
- **Old system**: Uses `attachment_filename` and `attachment_path` fields on `Invoice` table (for existing attachments)

## Other Endpoints Status
Checked other invoice endpoints for the same issue:

1. **✅ GET `/invoices/` (list)**: Already correctly uses old-style attachment fields
2. **✅ POST `/invoices/` (create)**: Already handles both old and new-style attachments
3. **✅ GET `/invoices/{invoice_id}` (read)**: **FIXED** - Now handles both systems

## Impact
- **Existing attachments**: Will now be properly displayed in the frontend
- **New attachments**: Continue to work as before
- **Backward compatibility**: Maintained for both attachment systems
- **No breaking changes**: All existing functionality preserved

## Test Scenarios
1. **Invoice with old-style attachment**: Should now show `has_attachment=true` and correct filename
2. **Invoice with new-style attachment**: Should continue to work as before
3. **Invoice with no attachment**: Should show `has_attachment=false` and `attachment_filename=null`
4. **Invoice with both attachment types**: Should prioritize new-style but fall back to old-style