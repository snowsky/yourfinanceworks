# Default Notes Implementation for Invoices

## Summary
Implemented functionality to populate invoice notes with default values from settings when creating new invoices with empty notes.

## Changes Made

### Backend (API)
**File: `api/routers/invoices.py`**
- Added `Settings` import from `models.models_per_tenant`
- The code already had logic to fetch default notes from settings when both `invoice.notes` and `invoice.description` are empty
- Fixed the missing import that was preventing the Settings model from being used

**Code Logic:**
```python
# Get default notes from settings if no notes provided
default_notes = None
if not invoice.notes and not invoice.description:
    try:
        invoice_settings_record = db.query(Settings).filter(Settings.key == "invoice_settings").first()
        if invoice_settings_record and invoice_settings_record.value:
            default_notes = invoice_settings_record.value.get("notes", "")
    except Exception as e:
        logger.warning(f"Failed to retrieve default notes from settings: {e}")

db_invoice = Invoice(
    ...
    notes=invoice.description or invoice.notes or default_notes,
    ...
)
```

### Frontend (UI)
**File: `ui/src/components/invoices/InvoiceForm.tsx`**

**Changes made:**
1. Updated the form's `defaultValues` to include default notes from settings:
   - Changed: `notes: invoice?.notes || ""`
   - To: `notes: invoice?.notes || settings?.invoice_settings?.notes || ""`

2. Added a new `useEffect` hook to populate default notes when settings are loaded:
   ```typescript
   useEffect(() => {
     if (!isEdit && settings?.invoice_settings?.notes) {
       const currentNotes = form.getValues('notes');
       const hasInitialDataNotes = initialData?.notes;

       if (!currentNotes && !hasInitialDataNotes) {
         form.setValue('notes', settings.invoice_settings.notes);
       }
     }
   }, [settings, isEdit, form, initialData]);
   ```

**Why this approach:**
- Settings are loaded asynchronously, so they're not available when the form is first initialized
- The `useEffect` runs after settings are loaded and populates the notes field
- It only applies default notes if the field is empty and initialData didn't provide notes

**Behavior:**
1. When editing an existing invoice: Uses the invoice's existing notes
2. When creating a new invoice: Uses the default notes from settings (once loaded)
3. When initialData has notes: Uses the notes from initialData
4. Fallback: Empty string if no settings are available

**File: `ui/src/components/inventory/InventoryInvoiceForm.tsx`**
- Added logic to populate default notes when settings are loaded for new invoices
- Added in the `loadData` function:
  ```typescript
  if (!isEdit && settingsData?.invoice_settings?.notes) {
    form.setValue("notes", settingsData.invoice_settings.notes);
  }
  ```

**Behavior:**
1. When creating a new inventory invoice: Uses the default notes from settings
2. When editing an existing invoice: Uses the invoice's existing notes

### Mobile App
**File: `mobile/src/screens/NewInvoiceScreen.tsx`**
- Updated the settings loading logic to populate default notes when creating a new invoice
- Added notes field to the form data initialization from settings
- Changed the `loadSettings` function to include:
  ```typescript
  setFormData(prev => ({ 
    ...prev, 
    number: invoiceNumber,
    notes: notes || ''
  }));
  ```

**Behavior:**
1. When the app loads settings, it automatically populates the notes field with default notes
2. User can modify or keep the default notes
3. Edit invoice screen preserves existing notes (no changes needed)

## How It Works

### Settings Structure
The default notes are stored in the `settings` table with:
- **Key**: `invoice_settings`
- **Value**: JSON object containing:
  ```json
  {
    "prefix": "INV-",
    "next_number": "0001",
    "terms": "Net 30 days",
    "notes": "Thank you for your business!",
    "send_copy": true,
    "auto_reminders": true
  }
  ```

### User Flow
1. Admin configures default notes in Settings → Invoice Settings tab
2. When creating a new invoice, the notes field is pre-populated with the default value
3. User can modify or keep the default notes
4. When saving, if notes are still empty, the backend applies the default notes

## Testing
To test this functionality:

1. **Set Default Notes:**
   - Go to Settings → Invoice Settings
   - Set "Default Notes" field (e.g., "Thank you for your business!")
   - Save settings

2. **Create New Invoice (Web UI):**
   - Go to Invoices → Create New Invoice
   - Choose "Manual Create" or "From Inventory"
   - The notes field should be pre-populated with the default notes
   - Complete the invoice and save

3. **Create New Invoice (Mobile App):**
   - Open the mobile app
   - Navigate to Invoices → New Invoice
   - The notes field should be pre-populated with the default notes
   - Complete the invoice and save

4. **Verify:**
   - Check that the saved invoice has the default notes
   - Edit the invoice and verify notes are preserved
   - Create another invoice and verify default notes appear again

5. **Test Edge Cases:**
   - Create invoice from bank statement (should use bank statement notes if provided)
   - Import invoice from PDF (should use PDF notes if provided)
   - Edit existing invoice (should preserve existing notes)

## Benefits
- Consistent messaging across all invoices
- Saves time by not having to type the same notes repeatedly
- Professional appearance with standardized thank you messages
- Configurable per tenant/organization
- Works across web UI and mobile app
- Respects user input when notes are provided via import or prefill
