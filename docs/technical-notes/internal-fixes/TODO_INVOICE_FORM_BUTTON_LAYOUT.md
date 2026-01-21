# TODO: Invoice Form Button Layout Refactoring

## Overview
Refactor the invoice form to move action buttons (Cancel, Create Invoice, Update Invoice) outside of the form card and below the "Approval Workflow" section, matching the layout pattern used in the expenses page.

## Current State
- Action buttons are currently inside the `InvoiceForm` component
- Buttons are rendered within the form card/box
- Approval workflow section is separate from the main form buttons

## Desired State
- Action buttons should be moved outside the form card
- Buttons should appear below the "Approval Workflow" section
- Layout should match the expenses page pattern for consistency

## Files to Modify

### 1. `ui/src/components/invoices/InvoiceFormWithApproval.tsx`
- Extract button rendering logic from `InvoiceForm` component
- Move buttons to parent component level
- Position buttons below the approval workflow section
- Maintain existing button functionality (save, cancel, approval submission)

### 2. `ui/src/components/invoices/InvoiceForm.tsx` (if separate)
- Remove button rendering from the form component
- Expose form submission handlers via props/callbacks
- Keep form focused on input fields only

### 3. Layout Structure
```tsx
<div>
  {/* Invoice Form Card */}
  <Card>
    <InvoiceForm ... />
  </Card>
  
  {/* Approval Workflow Section */}
  <ApprovalWorkflowSection ... />
  
  {/* Action Buttons - NEW LOCATION */}
  <div className="action-buttons">
    <Button variant="outline" onClick={handleCancel}>Cancel</Button>
    <Button onClick={handleSave}>
      {isEdit ? 'Update Invoice' : 'Create Invoice'}
    </Button>
  </div>
</div>
```

## Refactoring Considerations

### Component Separation
- Separate form logic from button logic
- Use callback props to communicate between components
- Maintain form validation state across components

### State Management
- Ensure form state is accessible to buttons outside the form
- Handle form submission from external buttons
- Preserve approval workflow integration

### Styling
- Match button layout from expenses page
- Ensure responsive design
- Maintain consistent spacing and alignment

### Functionality to Preserve
- Form validation before submission
- Approval workflow submission after invoice save
- Loading states during save operations
- Error handling and toast notifications
- Cancel navigation

## Reference Implementation
See `ui/src/pages/ExpensesNew.tsx` and `ui/src/pages/ExpensesEdit.tsx` for the pattern to follow.

## Testing Checklist
- [ ] Buttons appear below approval workflow section
- [ ] Create invoice functionality works
- [ ] Update invoice functionality works
- [ ] Cancel button navigates correctly
- [ ] Approval submission still triggers after save
- [ ] Form validation prevents submission when invalid
- [ ] Loading states display correctly
- [ ] Error messages show appropriately
- [ ] Layout is responsive on mobile
- [ ] Visual consistency with expenses page

## Priority
Medium - UI/UX improvement for consistency across the application

## Estimated Effort
2-3 hours (requires careful refactoring to maintain all existing functionality)
