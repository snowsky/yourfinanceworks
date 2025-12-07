# TODO: Fix Invoice Items Validation Issues

## Problem
Invoice item validation is causing persistent errors when:
1. Adding new items - shows "Description is required" even after entering description
2. Deleting items - validation errors persist on remaining items with "Expected number, received nan" and "Required" messages
3. Form submission - Save button keeps spinning when there are validation errors

## Root Causes
- Form validation schema using `z.number()` doesn't properly handle string inputs from HTML number inputs
- When array items are deleted, validation errors persist on wrong field indices
- Validation mode (onSubmit vs onBlur) causes stale errors to remain visible

## Attempted Solutions (Failed)
1. `z.coerce.number()` - converts empty strings to NaN
2. `z.union([z.number(), z.string()]).pipe(z.coerce.number())` - complex and still fails
3. `z.any().transform()` - transforms valid numbers to 0
4. `onBlur` mode - doesn't clear errors after deletion
5. `form.clearErrors()` - doesn't work after array operations

## Recommended Fix
- Investigate how react-hook-form handles array field validation
- Consider using `useFieldArray` hook for better array management
- May need to refactor item validation to be more lenient during editing
- Test with proper number type coercion that preserves valid values

## Files to Update
- `/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/ui/src/hooks/useInvoiceForm.ts` - validation schema
- `/Users/hao/dev/github/machine_learning/hao_projects/invoice_app/ui/src/components/invoices/InvoiceItemsSection.tsx` - item rendering and deletion logic
