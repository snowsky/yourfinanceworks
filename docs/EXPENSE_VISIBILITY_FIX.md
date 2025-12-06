# Expense Visibility Fix - Multi-User Organization Support

## Problem

Users in the same organization (tenant) could not see each other's expenses. Specifically:
- User A (admin role) creates 3 expenses
- User A invites User B (user role) to the organization
- User B logs in but sees 0 expenses instead of the 3 expenses created by User A

## Root Cause

The expenses router was filtering expenses by `user_id`, which meant each user could only see their own expenses:

```python
# OLD CODE (INCORRECT)
query = db.query(Expense).filter(Expense.user_id == current_user.id)
```

This filtering was inappropriate because:
1. The system uses a **multi-tenant architecture** where each tenant has its own database
2. The database connection itself provides tenant isolation
3. All users within a tenant should be able to see all expenses in that tenant
4. The `user_id` field on expenses is for tracking who created the expense, not for access control

## Solution

Removed the `user_id` filter from expense queries. Since each tenant has its own database, tenant isolation is automatically provided by the database connection:

```python
# NEW CODE (CORRECT)
# Note: No user_id filter needed - tenant isolation is provided by the per-tenant database
query = db.query(Expense)
```

## Changes Made

### 1. List Expenses Endpoint (`GET /expenses/`)
**File:** `api/core/routers/expenses.py`

**Before:**
```python
query = db.query(Expense).filter(Expense.user_id == current_user.id)
```

**After:**
```python
# Note: No user_id filter needed - tenant isolation is provided by the per-tenant database
query = db.query(Expense)
```

### 2. Analytics Endpoints

Updated three analytics endpoints to show data for all expenses in the tenant:

- `GET /expenses/analytics/summary` - Expense summary statistics
- `GET /expenses/analytics/trends` - Expense trends over time
- `GET /expenses/analytics/categories` - Expense analytics by category

**Before:**
```python
base_query = db.query(Expense).filter(
    Expense.user_id == current_user.id,
    Expense.status != 'pending_approval'
)
```

**After:**
```python
# Base query for all expenses in tenant (not pending approval)
# Note: No user_id filter needed - tenant isolation is provided by the per-tenant database
base_query = db.query(Expense).filter(
    Expense.status != 'pending_approval'
)
```

## Architecture Context

### Multi-Tenant Database Design

The system uses a **database-per-tenant** architecture:

1. **Master Database** (`master.db`)
   - Contains `MasterUser` table with `tenant_id` foreign key
   - Contains `Tenant` table
   - Manages authentication and tenant membership

2. **Per-Tenant Databases** (`tenant_<id>.db`)
   - Each tenant has its own isolated database
   - Contains `User`, `Expense`, `Invoice`, `Client`, etc.
   - No `tenant_id` column needed in these tables
   - Database connection itself provides tenant isolation

### Authentication Flow

1. User logs in → `MasterUser` authenticated in master database
2. System identifies user's `tenant_id` from `MasterUser.tenant_id`
3. System connects to tenant-specific database (`tenant_<id>.db`)
4. All queries in that session are automatically scoped to that tenant

### Data Visibility Rules

| Resource Type | Visibility Scope | Reason |
|--------------|------------------|---------|
| **Expenses** | All users in tenant | Shared financial data for organization |
| **Invoices** | All users in tenant | Shared financial data for organization |
| **Clients** | All users in tenant | Shared customer data for organization |
| **Bank Statements** | All users in tenant | Shared financial data for organization |
| **Notifications** | Per-user only | Personal notifications |
| **Reminders** | Per-user only | Personal reminders |
| **API Keys** | Per-user only | Personal API access credentials |

## Role-Based Access Control (RBAC)

While all users can **view** expenses, **modification** is controlled by roles:

- **Admin**: Can create, edit, delete expenses and manage approval workflows
- **User**: Can create, edit, delete their own expenses and submit for approval
- **Viewer**: Can only view expenses, cannot create or modify

This is enforced through the `require_non_viewer()` and `require_admin()` functions.

## Testing

A test script has been created to verify the fix:

```bash
cd api
python scripts/test_expense_visibility.py
```

This script:
1. Finds a tenant with multiple users
2. Counts total expenses in the tenant
3. Shows how many expenses each user created
4. Confirms all users should see all expenses

## Migration Notes

**No database migration required** - this is purely a code change to remove incorrect filtering.

Existing data is unaffected. After deploying this fix:
- All users in a tenant will immediately see all expenses in that tenant
- No data needs to be migrated or updated
- The `user_id` field on expenses remains for audit purposes (tracking who created each expense)

## Related Files

- `api/core/routers/expenses.py` - Main expenses router (fixed)
- `api/core/models/models_per_tenant.py` - Per-tenant data models
- `api/core/models/models.py` - Master database models
- `api/core/utils/rbac.py` - Role-based access control utilities
- `api/scripts/test_expense_visibility.py` - Test script

## Future Considerations

If more granular access control is needed in the future (e.g., department-level isolation), consider:

1. Adding a `department_id` field to expenses
2. Adding a `department_id` field to users
3. Filtering by department instead of user
4. This would still allow multiple users to see shared expenses within their department

However, for most small-to-medium organizations, tenant-level isolation is sufficient.
