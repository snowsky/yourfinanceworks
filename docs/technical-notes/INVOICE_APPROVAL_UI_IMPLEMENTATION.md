# Invoice Approval UI Implementation

## Overview
Added approval workflow UI to the invoice creation process, allowing users to submit invoices for approval immediately after creation.

## Changes Made

### 1. New Component: InvoiceFormWithApproval
**File:** `ui/src/components/invoices/InvoiceFormWithApproval.tsx`

A wrapper component that combines the existing `InvoiceForm` with approval workflow UI. This component:
- Wraps the `InvoiceForm` component
- Adds an "Approval Workflow" card below the form
- Provides a checkbox to enable approval submission
- Shows an approver selection dropdown when enabled
- Handles license errors gracefully

**Features:**
- Fetches available approvers on component mount
- Detects license errors and displays a helpful message
- Only shows approval UI for new invoices (not edits)
- Reuses the same error handling pattern as expenses

### 2. Updated Page: NewInvoiceManual
**File:** `ui/src/pages/NewInvoiceManual.tsx`

Changed from using `InvoiceForm` directly to using `InvoiceFormWithApproval`, which adds the approval workflow UI.

## User Experience

### Before
- Users created invoices with no approval option
- Approval had to be done separately after creation

### After
- When creating a new invoice manually, users see an "Approval Workflow" section
- Users can check "Submit this invoice for approval after creation"
- When checked, a dropdown appears to select an approver
- The approver is notified immediately after the invoice is created

## Implementation Details

### Component Structure
```typescript
<InvoiceFormWithApproval
  invoice={invoice}
  isEdit={isEdit}
  onInvoiceUpdate={onInvoiceUpdate}
  initialData={initialData}
  attachment={attachment}
  prefillNewClient={prefillNewClient}
  openNewClientOnInit={openNewClientOnInit}
/>
```

### State Management
- `submitForApproval`: Boolean flag for approval checkbox
- `selectedApproverId`: Selected approver ID
- `availableApprovers`: List of available approvers
- `approvalsNotLicensed`: Flag indicating if feature is not licensed

### Error Handling
- Detects 402 Payment Required errors from the API
- Displays an amber alert when the feature is not licensed
- Hides the approver dropdown when not licensed
- Logs other errors to console for debugging

## Integration Points

### API Calls
- `approvalApi.getApprovers()` - Fetches list of available approvers

### Components Used
- `InvoiceForm` - The main invoice creation form
- `Card`, `CardContent`, `CardHeader`, `CardTitle` - UI containers
- `Checkbox` - Approval toggle
- `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue` - Approver selection
- `Alert`, `AlertDescription` - License warning
- `Label` - Form labels
- Icons: `AlertCircle`, `Users` - Visual indicators

### Translations
Uses the following translation keys:
- `invoices.approval_workflow` - Section title
- `invoices.submit_this_invoice_for_approval_after_creation` - Checkbox label
- `invoices.this_invoice_will_be_submitted_for_approval` - Info message
- `invoices.select_approver` - Dropdown label
- `invoices.choose_an_approver` - Dropdown placeholder
- `common.feature_not_licensed` - License error message

## Future Enhancements

1. **Approval Submission Dialog**
   - Add a confirmation dialog before submitting for approval
   - Allow users to add notes to the approval request
   - Show invoice details in the confirmation

2. **Approval Status Display**
   - Show approval status on the invoice list
   - Display current approver information
   - Show approval history

3. **Invoice PDF Integration**
   - Include approval status in generated PDFs
   - Show approver information in PDF

4. **Approval Rules**
   - Support automatic approver assignment based on invoice amount
   - Support approval rules based on invoice category or client

5. **Multi-level Approvals**
   - Support multiple approval levels for invoices
   - Show approval chain in UI

## Testing Recommendations

1. **Without License**
   - Create a new invoice manually
   - Check "Submit for approval"
   - Verify the license warning appears
   - Verify the approver dropdown is hidden

2. **With License**
   - Activate a commercial license with approvals enabled
   - Create a new invoice manually
   - Check "Submit for approval"
   - Verify the approver dropdown shows available users
   - Verify no license warning appears

3. **Approver Selection**
   - Create a new invoice
   - Check "Submit for approval"
   - Verify the dropdown shows all available approvers
   - Verify you cannot select yourself as approver (if implemented)

4. **Error Handling**
   - Test with network errors
   - Test with invalid approver IDs
   - Verify error messages are displayed

## Files Modified
- `ui/src/pages/NewInvoiceManual.tsx` - Updated to use InvoiceFormWithApproval
- `ui/src/components/invoices/InvoiceFormWithApproval.tsx` - New component

## Related Files
- `ui/src/components/invoices/InvoiceForm.tsx` - Main invoice form (unchanged)
- `ui/src/pages/NewInvoice.tsx` - PDF import page (uses InvoiceForm directly)
- `ui/src/pages/EditInvoice.tsx` - Invoice editing page (uses InvoiceForm directly)
- `ui/src/lib/api.ts` - API client with approvalApi methods
