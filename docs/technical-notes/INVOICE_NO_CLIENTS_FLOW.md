# Invoice Creation - No Clients Flow

## Changes Made

### Mobile (NewInvoiceScreen.tsx)

1. **Early Return for No Clients**
   - Added a check at the beginning of the render method
   - When `clients.length === 0`, displays a dedicated empty state screen
   - User cannot proceed with invoice creation until at least one client is added

2. **Empty State UI**
   - Shows a centered message with icon
   - Displays: "No clients found"
   - Subtext: "Please add a client first"
   - Large blue "Add New Client" button to create a client
   - Back button to navigate away

3. **Styling**
   - Added `noClientsContainer` - centered flex container
   - Added `noClientsTitle` - prominent title text
   - Added `noClientsSubtext` - descriptive subtitle
   - Added `addClientButtonLarge` - prominent CTA button
   - Added `headerSpacer` - maintains header layout consistency

### Web UI (InvoiceFormWithApproval.tsx)

1. **Conditional Approval Workflow Section**
   - Approval workflow card is shown only when clients exist
   - Includes checkbox for "Submit for approval"
   - Approver selection dropdown (when approval is checked)
   - License warning shown if approvals are not licensed
   - Automatically fetches available approvers on component mount

2. **Hidden Cancel/Create Buttons When No Clients**
   - Added client check on component mount
   - Buttons are conditionally rendered only when clients exist
   - Uses `clientApi.getClients()` to check if any clients are available
   - Shows loading state while checking for clients
   - Buttons remain hidden if no clients are found
   - Added `onClientCreated` callback to InvoiceForm that triggers a re-check when a new client is created
   - Buttons automatically appear after a client is created

3. **Approval Workflow Logic**
   - When approval is requested and a valid approver is selected, the invoice is submitted for approval after creation
   - Handles license checking - shows warning if approvals feature is not licensed
   - Disables submit button if approval is checked but no approver is selected
   - Approval state is passed to InvoiceForm via `submitForApproval` and `approverIdForApproval` props
   - InvoiceForm submits the invoice for approval immediately after successful creation/update
   - Invoice status is set to "pending_approval" when submitted for approval

## User Experience

### Mobile Flow
1. User navigates to create new invoice
2. If no clients exist:
   - Empty state screen is shown
   - Form is completely hidden
   - User must add a client first
   - After adding client, form becomes available

### Web Flow
1. User navigates to create new invoice
2. If no clients exist:
   - Form is displayed but buttons are hidden
   - User sees the form but cannot submit
   - User must add a client first (via the form's add client modal)
   - After adding client, buttons become visible
3. If clients exist:
   - Form and buttons are displayed normally
   - Approval workflow section is not shown
   - User can create/update invoice

## Translation Keys Used
- `invoices.no_clients_found`
- `invoices.add_client_to_get_started`
- `clients.add_new_client`
- `common.cancel`
- `invoices.create_invoice`
- `invoices.update_invoice`
- `common.saving`
