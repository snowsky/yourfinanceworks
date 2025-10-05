# Approval Permission System

This document describes the approval permission system implemented for the expense approval workflow.

## Overview

The approval permission system provides comprehensive permission checks for the expense approval workflow, including:

- **Approval limit validation** based on user roles and approval rules
- **Permission checks** for approval rule management
- **Delegation permission validation**
- **Complex approval workflow permissions**

## Components

### 1. RBAC Extensions (`utils/rbac.py`)

Extended the existing RBAC utility with approval-specific permission functions:

#### Submission Permissions
- `can_submit_for_approval(user)` - Check if user can submit expenses for approval
- `require_approval_submission(user, action)` - Require submission permissions

#### Approval Permissions
- `can_approve_expenses(user)` - Check if user has basic approval permissions
- `can_approve_amount(user, amount, currency)` - Check if user can approve specific amounts
- `require_approval_permission(user, action)` - Require approval permissions

#### Rule Management Permissions
- `can_manage_approval_rules(user)` - Check if user can manage approval rules
- `require_approval_rule_management(user, action)` - Require rule management permissions

#### Delegation Permissions
- `can_delegate_approvals(user)` - Check if user can set up delegations
- `require_delegation_permission(user, action)` - Require delegation permissions

#### Viewing Permissions
- `can_view_approval_history(user)` - Check if user can view approval history
- `can_view_all_approvals(user)` - Check if user can view all approvals (admin-only)

### 2. Approval Permission Service (`services/approval_permission_service.py`)

Comprehensive service for handling approval-specific permission checks:

#### Key Methods

##### Approval Validation
```python
validate_approval_permission(user, expense, approval_level) -> bool
```
Validates if a user can approve a specific expense at a given approval level.

##### Approval Limits
```python
get_user_approval_limits(user, currency) -> dict
```
Returns the approval limits for a user, including max/min amounts and approval levels.

##### Delegation Management
```python
resolve_effective_approver(approver_id, current_time) -> int
```
Resolves the effective approver considering active delegations.

```python
validate_delegation_setup(approver_id, delegate_id, start_date, end_date)
```
Validates delegation setup for business rules.

##### Permission Checks
```python
validate_rule_management_permission(user)
validate_delegation_permission(user, delegate_user)
```
Validates specific permission types with detailed error handling.

## Permission Levels

### User Roles

#### Admin (`role="admin"`)
- Can approve any amount (unlimited approval authority)
- Can manage approval rules
- Can set up delegations
- Can view all approvals and history

#### User (`role="user"`)
- Can submit expenses for approval
- Can approve expenses within configured limits
- Can set up delegations
- Can view their own approval history
- Approval limits determined by ApprovalRule records

#### Viewer (`role="viewer"`)
- Cannot submit expenses for approval
- Cannot approve expenses
- Cannot manage approval rules
- Cannot set up delegations
- Cannot view approval history

### Approval Limits

Approval limits are enforced through `ApprovalRule` records:

```python
class ApprovalRule:
    min_amount: float          # Minimum amount for this rule
    max_amount: float          # Maximum amount for this rule
    currency: str              # Currency for amounts
    approval_level: int        # Approval level (1, 2, 3, etc.)
    approver_id: int          # User who can approve at this level
    auto_approve_below: float  # Auto-approve below this amount
```

## Integration with Approval Service

The permission system is integrated with the existing `ApprovalService`:

### Submission Checks
```python
# In submit_for_approval()
require_approval_submission(submitter, "submit expenses for approval")
```

### Approval Checks
```python
# In approve_expense()
permission_service.validate_approval_permission(user, expense, approval_level)
```

### Delegation Resolution
```python
# In _can_user_approve()
effective_approver = permission_service.resolve_effective_approver(approval.approver_id)
```

## API Integration

The permission system is integrated into the approval router (`routers/approvals.py`):

### Enhanced Permission Checks
- Submission endpoints use `require_approval_submission()`
- Approval endpoints use `require_approval_permission()`
- Rule management endpoints use `require_approval_rule_management()`

### Permission Service Dependency
```python
def get_approval_permission_service(db: Session = Depends(get_db)) -> ApprovalPermissionService:
    return ApprovalPermissionService(db)
```

## Usage Examples

### Check if User Can Approve
```python
from services.approval_permission_service import ApprovalPermissionService

permission_service = ApprovalPermissionService(db)

# Check basic approval permission
can_approve = permission_service.validate_approval_permission(user, expense, 1)

# Get user's approval limits
limits = permission_service.get_user_approval_limits(user, "USD")
print(f"Max approval amount: {limits['max_amount']}")
```

### Set Up Delegation
```python
# Validate delegation permission
permission_service.validate_delegation_permission(approver, delegate)

# Validate delegation setup
permission_service.validate_delegation_setup(
    approver_id=approver.id,
    delegate_id=delegate.id,
    start_date=start_date,
    end_date=end_date
)
```

### Check Effective Approver
```python
# Resolve who should actually approve (considering delegations)
effective_approver_id = permission_service.resolve_effective_approver(original_approver_id)
```

## Error Handling

The system provides specific exceptions for different permission violations:

- `HTTPException(403)` - Insufficient permissions
- `HTTPException(400)` - Invalid delegation setup
- `HTTPException(422)` - Business rule violations

## Testing

Comprehensive test coverage includes:

### Unit Tests
- `test_rbac_approval_permissions.py` - Tests for RBAC extensions
- `test_approval_permission_service.py` - Tests for permission service

### Integration Tests
- `test_approval_permission_integration.py` - Tests for service integration

### Test Categories
- Basic permission checks
- Approval limit validation
- Delegation resolution
- Rule management permissions
- Error handling scenarios

## Security Considerations

### Access Control
- Only designated approvers can approve expenses within their limits
- Approval rules enforce amount-based restrictions
- Delegation permissions are time-bounded and validated

### Audit Trail
- All permission checks are logged
- Delegation changes are tracked
- Approval decisions include permission validation

### Data Protection
- Permission checks prevent unauthorized access to approval functions
- Sensitive approval data is protected by role-based access
- Input validation prevents permission bypass attempts

## Configuration

### Approval Rules Setup
1. Create `ApprovalRule` records for each approval level
2. Set appropriate amount limits and approvers
3. Configure auto-approval thresholds if needed

### User Role Assignment
1. Set user `role` field to "admin", "user", or "viewer"
2. Ensure active users have `is_active=True`
3. Configure approval rules for users who need approval permissions

### Delegation Configuration
1. Create `ApprovalDelegate` records for temporary delegations
2. Set appropriate start and end dates
3. Ensure delegates have approval permissions

## Best Practices

### Permission Design
- Use least privilege principle
- Implement defense in depth with multiple permission layers
- Validate permissions at both service and API levels

### Approval Limits
- Set reasonable approval limits based on organizational hierarchy
- Use multiple approval levels for high-value expenses
- Configure auto-approval for low-risk expenses

### Delegation Management
- Use time-bounded delegations
- Validate delegate permissions before setup
- Monitor active delegations regularly

### Testing
- Test all permission scenarios
- Include edge cases and error conditions
- Validate integration between components