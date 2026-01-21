# Approval Workflows Enhancements

## Overview
This document summarizes the enhancements made to the approval workflows system to fix the license bypass vulnerability and add invoice approval support.

## Changes Made

### 1. License Bypass Fix

**File: `api/core/utils/feature_gate.py`**

**Issue:** The `check_feature()` function had a fallback that allowed access to features when they were enabled via environment variables or config defaults, bypassing license validation.

**Fix:** Removed the fallback check that called `FeatureConfigService.is_enabled(feature_id, db, check_license=False)`. Now the function strictly enforces license validation for all commercial features.

**Before:**
```python
# Check if feature is enabled via config service (fallback to env/default)
# This handles the case where license status is "invalid" (fresh install)
from core.services.feature_config_service import FeatureConfigService
if FeatureConfigService.is_enabled(feature_id, db, check_license=False):
    # Feature enabled via config/env, allow access
    return
```

**After:**
The fallback is completely removed. License validation is now mandatory for all commercial features.

### 2. Invoice Approval Support

#### 2.1 Database Model

**File: `api/core/models/models_per_tenant.py`**

Added new `InvoiceApproval` model:
- Mirrors the structure of `ExpenseApproval`
- Supports multi-level approval workflows for invoices
- Tracks approval status, decisions, and audit trails
- Includes relationships to Invoice, User (approver), and ApprovalRule

Added relationship to Invoice model:
```python
approvals = relationship("InvoiceApproval", back_populates="invoice", cascade="all, delete-orphan")
```

#### 2.2 API Schemas

**File: `api/core/schemas/approval.py`**

Added new schemas for invoice approvals:
- `InvoiceApprovalBase`: Base schema for invoice approvals
- `InvoiceApprovalCreate`: Schema for creating invoice approvals (submission)
- `InvoiceApprovalDecision`: Schema for invoice approval decisions
- `InvoiceApproval`: Response schema for invoice approvals
- `InvoiceApprovalHistory`: Complete approval history for invoices
- `InvoiceWithApprovalStatus`: Invoice with approval status information

#### 2.3 Approval Service

**File: `api/commercial/workflows/approvals/services/approval_service.py`**

Added new methods to support invoice approvals:

1. **`submit_invoice_for_approval()`**
   - Submit an invoice for approval
   - Validates invoice exists and is not already in approval workflow
   - Creates approval record and updates invoice status
   - Sends notifications to approver

2. **`approve_invoice()`**
   - Approve an invoice at a specific approval level
   - Validates approver permissions
   - Updates approval and invoice status
   - Sends notifications

3. **`reject_invoice()`**
   - Reject an invoice with required rejection reason
   - Validates approver permissions
   - Updates approval and invoice status
   - Sends notifications

4. **`get_pending_invoice_approvals()`**
   - Get pending invoice approvals for a specific approver
   - Supports pagination with limit and offset

5. **`get_invoice_approval_history()`**
   - Get complete approval history for an invoice
   - Returns audit trail with all approval decisions

6. **`_send_invoice_approval_notification()`**
   - Send notifications for invoice approval events
   - Handles different event types (submitted, approved, rejected)

#### 2.4 API Endpoints

**File: `api/commercial/workflows/approvals/router.py`**

Added new endpoints for invoice approvals:

1. **POST `/approvals/invoices/{invoice_id}/submit-approval`**
   - Submit an invoice for approval
   - Requires approver_id and optional notes
   - Returns list of created approval records

2. **GET `/approvals/invoices/pending`**
   - Get pending invoice approvals for current user
   - Supports pagination with limit and offset
   - Returns approvals list and total count

3. **POST `/approvals/invoices/{approval_id}/approve`**
   - Approve an invoice
   - Optional notes field
   - Returns updated approval record

4. **POST `/approvals/invoices/{approval_id}/reject`**
   - Reject an invoice
   - Requires rejection_reason field
   - Optional notes field
   - Returns updated approval record

5. **GET `/approvals/invoices/history/{invoice_id}`**
   - Get complete approval history for an invoice
   - Returns InvoiceApprovalHistory with audit trail

## Feature Description Update

The feature description in `api/core/services/feature_config_service.py` now accurately reflects the expanded functionality:

```python
'approvals': {
    'name': 'Approval Workflows',
    'description': 'Multi-level expense and invoice approval workflows',
    'category': 'advanced',
    'env_var': 'FEATURE_APPROVALS_ENABLED',
    'default': False,
    'license_tier': 'commercial'
}
```

## Security Implications

### License Enforcement
- All approval workflow endpoints now require a valid commercial license
- The feature gate decorator properly enforces license checks without fallbacks
- Attempting to use approval features without a license returns HTTP 402 (Payment Required)

### Invoice Approval Permissions
- Invoice approvals follow the same permission model as expense approvals
- Approvers must be explicitly assigned to approve invoices
- Users cannot approve their own submissions
- All approval decisions are logged for audit trails

## Migration Notes

### For Existing Installations
- No database migration required for existing expense approvals
- New `invoice_approvals` table will be created on next migration
- Existing expense approval workflows continue to work unchanged

### For New Installations
- Both expense and invoice approval tables are created
- Feature is disabled by default (requires license)
- Can be enabled via `FEATURE_APPROVALS_ENABLED` environment variable or license activation

## Testing Recommendations

1. **License Bypass Prevention**
   - Verify that approval endpoints return 402 without valid license
   - Test with environment variable enabled but no license
   - Confirm license check is enforced

2. **Invoice Approval Workflow**
   - Test invoice submission for approval
   - Test approval and rejection decisions
   - Verify approval history is tracked
   - Test pending approvals retrieval
   - Verify notifications are sent

3. **Permission Validation**
   - Test that users cannot approve their own invoices
   - Test that only assigned approvers can approve
   - Test that invalid approvers are rejected

4. **Audit Trail**
   - Verify all approval decisions are logged
   - Check that audit events include relevant details
   - Confirm approval history is complete and accurate

## API Usage Examples

### Submit Invoice for Approval
```bash
POST /approvals/invoices/123/submit-approval
{
  "approver_id": 456,
  "notes": "Please review this invoice"
}
```

### Get Pending Invoice Approvals
```bash
GET /approvals/invoices/pending?limit=10&offset=0
```

### Approve Invoice
```bash
POST /approvals/invoices/789/approve
{
  "notes": "Approved for payment"
}
```

### Reject Invoice
```bash
POST /approvals/invoices/789/reject
{
  "rejection_reason": "Invoice amount exceeds budget",
  "notes": "Please resubmit with corrected amount"
}
```

### Get Invoice Approval History
```bash
GET /approvals/invoices/history/123
```

## Backward Compatibility

- All existing expense approval endpoints remain unchanged
- Expense approval workflows continue to function as before
- New invoice approval endpoints are additive and don't affect existing functionality
- Feature gate behavior is more restrictive (better security) but maintains same interface
