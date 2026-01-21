# FIXED: Submit Button Stuck in Saving State

## Problem
When saving an invoice and a validation error occurred at the same time, the submit button would remain in the "Saving..." state with a spinning loader, even though the form was not actually submitting.

## Root Cause
The submitting state was managed in TWO separate components:

1. **InvoiceForm**: Has its own `submitting` state from `useInvoiceForm` hook
2. **InvoiceFormWithApproval**: Has its own `isSubmitting` state for the external button

**The Problem**: When the external button in `InvoiceFormWithApproval` was clicked:
- It set `isSubmitting = true` 
- It triggered the hidden submit button in `InvoiceForm`
- If validation failed in `InvoiceForm`, it reset its own state
- But `InvoiceFormWithApproval` never knew about the failure
- Result: Button stuck in "Saving..." state

## Solution
Added a callback mechanism to sync state between the two components:

```typescript
// InvoiceFormWithApproval passes callback to InvoiceForm
<InvoiceForm
  onSubmitStateChange={setIsSubmitting}
  // ... other props
/>

// InvoiceForm calls the callback to update parent state
const onSubmit = async (data: any) => {
  invoiceForm.setSubmitting(true);
  onSubmitStateChange?.(true); // ✅ Notify parent

  const isValid = await invoiceForm.form.trigger();
  if (!isValid) {
    invoiceForm.setSubmitting(false);
    onSubmitStateChange?.(false); // ✅ Notify parent of failure
    return;
  }

  try {
    // ... API calls ...
  } catch (error) {
    invoiceForm.setSubmitting(false);
    onSubmitStateChange?.(false); // ✅ Notify parent of error
  }
};
```

## Key Changes

### 1. Added onSubmitStateChange Callback Prop
- `InvoiceForm` now accepts `onSubmitStateChange?: (isSubmitting: boolean) => void`
- Allows parent component to be notified of submission state changes

### 2. InvoiceFormWithApproval Passes Callback
- Passes `setIsSubmitting` as `onSubmitStateChange` prop
- Removes setTimeout hack and manual state management

### 3. InvoiceForm Calls Callback on State Changes
- Calls `onSubmitStateChange?.(true)` when submission starts
- Calls `onSubmitStateChange?.(false)` when validation fails
- Calls `onSubmitStateChange?.(false)` when API call fails

### 4. Simplified handleFormSubmit
- Removed manual `setIsSubmitting` calls
- Just triggers the hidden submit button
- State is managed by callback from child component

## Files Modified
- `ui/src/components/invoices/InvoiceForm.tsx` - Added onSubmitStateChange callback prop and calls it on state changes
- `ui/src/components/invoices/InvoiceFormWithApproval.tsx` - Passes setIsSubmitting callback to InvoiceForm

## Testing Scenarios
1. ✅ Submit with validation errors → Button returns to normal state
2. ✅ Submit with API errors → Button returns to normal state  
3. ✅ Submit successfully → Button stays in loading state until navigation
4. ✅ Rapid clicks → Prevented by early return check
5. ✅ Mixed validation and API errors → Button always resets properly

## Why This Approach?
- **Proper separation of concerns**: Child component controls its own state and notifies parent
- **No race conditions**: No setTimeout or polling needed
- **Type-safe**: Callback is properly typed and optional
- **Reusable**: Pattern can be used for other forms with external buttons

## Related Issues
- This fix complements the validation improvements in TODO_INVOICE_ITEMS.md
- Ensures consistent UX when form submission fails for any reason
- Solves the state synchronization problem between parent and child components
