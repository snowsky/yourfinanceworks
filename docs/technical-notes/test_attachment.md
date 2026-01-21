# Attachment Upload Test

## Steps to test attachment upload:

1. **Create New Invoice**:
   - Go to `/invoices/new`
   - Fill in basic invoice details (client, items, etc.)
   - Look for "Attachment" section near the bottom of the form
   - Should see "Upload Attachment (Optional)" with file input

2. **Edit Existing Invoice**:
   - Go to any existing invoice edit page
   - Look for "Attachment" section
   - Should see file upload input if no attachment exists
   - Should see existing attachment with download button if attachment exists

## Expected Behavior:

### New Invoice:
- Attachment section should be visible with file input
- Accepts: PDF, DOC, DOCX, JPG, PNG files
- Max size: 10MB
- Shows selected file name and size after selection
- Has "Remove" button to clear selection

### Edit Invoice:
- Shows existing attachment (if any) with download button
- Shows file upload input if no attachment exists
- Can upload new attachment

## Troubleshooting:

If attachment section is not visible:
1. Check browser console for errors
2. Verify the form is rendering completely
3. Check if the section is being hidden by CSS
4. Verify the attachment state variables are working

## Code Location:
- Frontend: `ui/src/components/invoices/InvoiceForm.tsx` (lines ~1800-1850)
- Backend: `api/routers/invoices.py` (upload/download endpoints)
- API: `ui/src/lib/api.ts` (uploadAttachment, downloadAttachment methods)