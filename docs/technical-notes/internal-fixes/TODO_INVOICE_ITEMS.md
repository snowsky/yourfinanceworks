# FIXED: Invoice Items Validation Issues

## Problem (RESOLVED)
Invoice item validation was causing persistent errors when:
1. Adding new items - showed "Description is required" even after entering description
2. Deleting items - validation errors persisted on remaining items with "Expected number, received nan" and "Required" messages
3. Form submission - Save button kept spinning when there were validation errors

## Root Causes (IDENTIFIED)
- Form validation schema using `z.number()` didn't properly handle string inputs from HTML number inputs
- When array items were deleted, validation errors persisted on wrong field indices
- Validation mode (onSubmit) caused stale errors to remain visible after array operations

## Solution Implemented

### 1. Fixed Number Input Validation (`useInvoiceForm.ts`)
Used `z.preprocess()` to properly handle string-to-number conversion from HTML inputs:
```typescript
quantity: z.preprocess(
  (val) => {
    if (val === "" || val === null || val === undefined) return undefined;
    const num = Number(val);
    return isNaN(num) ? undefined : num;
  },
  z.number().min(0.01, "Quantity must be greater than 0")
)
```

### 2. Changed Validation Mode
Changed from `mode: "onSubmit"` to `mode: "onChange"` for real-time validation feedback

### 3. Improved Array Item Deletion (`InvoiceItemsSection.tsx`)
- Added `shouldValidate: true` flag when setting items
- Added `form.trigger("items")` after deletion to re-validate all items
- Used setTimeout to ensure validation happens after state update

### 4. Enhanced Number Input Handling
Added custom onChange handlers to properly convert string values to numbers:
```typescript
onChange={(e) => {
  const value = e.target.value;
  field.onChange(value === '' ? '' : parseFloat(value) || '');
}}
```

### 5. Added Form Validation Check Before Submit
Prevents spinner from continuing when validation fails:
```typescript
invoiceForm.setSubmitting(true);

const isValid = await invoiceForm.form.trigger();
if (!isValid) {
  toast.error("Please fix validation errors before submitting");
  invoiceForm.setSubmitting(false);
  return;
}
```

### 6. Fixed Submitting State Management
Ensures the submit button always returns to normal state:
- Set `submitting = true` before validation
- Reset `submitting = false` if validation fails
- Reset `submitting = false` in catch block if API call fails
- No reset needed on success since we navigate away

## Files Updated
- `ui/src/hooks/useInvoiceForm.ts` - validation schema with z.preprocess
- `ui/src/components/invoices/InvoiceItemsSection.tsx` - improved deletion and input handling
- `ui/src/components/invoices/InvoiceForm.tsx` - added validation check before submit

## Testing Recommendations
1. Add new items and verify no false validation errors
2. Delete items and verify errors clear properly
3. Submit form with invalid data and verify spinner stops
4. Test with empty, zero, and negative values
5. Test rapid add/delete operations
