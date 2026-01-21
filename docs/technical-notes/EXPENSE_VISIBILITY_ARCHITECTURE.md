# Expense Visibility - Architecture Explanation

## Multi-Tenant Database Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Master Database                          │
│                      (master.db)                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  MasterUser Table:                                           │
│  ┌────┬──────────────────┬───────────┬────────┐            │
│  │ ID │ Email            │ Tenant ID │ Role   │            │
│  ├────┼──────────────────┼───────────┼────────┤            │
│  │ 1  │ alice@acme.com   │ 1         │ admin  │            │
│  │ 2  │ bob@acme.com     │ 1         │ user   │            │
│  │ 3  │ carol@xyz.com    │ 2         │ admin  │            │
│  └────┴──────────────────┴───────────┴────────┘            │
│                                                               │
│  Tenant Table:                                               │
│  ┌────┬──────────────┐                                      │
│  │ ID │ Name         │                                      │
│  ├────┼──────────────┤                                      │
│  │ 1  │ Acme Corp    │                                      │
│  │ 2  │ XYZ Inc      │                                      │
│  └────┴──────────────┘                                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Authentication
                            ▼
        ┌───────────────────────────────────┐
        │   User logs in with credentials   │
        │   System identifies tenant_id     │
        └───────────────────────────────────┘
                            │
                            │ Connect to tenant DB
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Tenant 1 Database (tenant_1.db)                 │
│                    Acme Corp Data                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Expense Table:                                              │
│  ┌────┬─────────┬──────────┬──────────┬─────────┐          │
│  │ ID │ Amount  │ Vendor   │ User ID  │ Date    │          │
│  ├────┼─────────┼──────────┼──────────┼─────────┤          │
│  │ 1  │ $100.00 │ Walmart  │ 1        │ 2024-01 │ ← Alice │
│  │ 2  │ $50.00  │ Target   │ 1        │ 2024-01 │ ← Alice │
│  │ 3  │ $75.00  │ Amazon   │ 1        │ 2024-01 │ ← Alice │
│  │ 4  │ $200.00 │ Costco   │ 2        │ 2024-02 │ ← Bob   │
│  └────┴─────────┴──────────┴──────────┴─────────┘          │
│                                                               │
│  ✅ Both Alice and Bob can see ALL 4 expenses               │
│  ✅ user_id is for tracking who created it, not filtering   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Tenant 2 Database (tenant_2.db)                 │
│                     XYZ Inc Data                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Expense Table:                                              │
│  ┌────┬─────────┬──────────┬──────────┬─────────┐          │
│  │ ID │ Amount  │ Vendor   │ User ID  │ Date    │          │
│  ├────┼─────────┼──────────┼──────────┼─────────┤          │
│  │ 1  │ $300.00 │ Dell     │ 3        │ 2024-01 │ ← Carol │
│  └────┴─────────┴──────────┴──────────┴─────────┘          │
│                                                               │
│  ✅ Carol can only see XYZ Inc expenses                     │
│  ✅ Carol CANNOT see Acme Corp expenses                     │
└─────────────────────────────────────────────────────────────┘
```

## The Problem (Before Fix)

```python
# WRONG: Filtered by user_id
query = db.query(Expense).filter(Expense.user_id == current_user.id)
```

**What happened:**
```
Alice logs in (tenant_id=1, user_id=1)
  → Connects to tenant_1.db
  → Query: SELECT * FROM expenses WHERE user_id = 1
  → Result: Sees expenses 1, 2, 3 (only Alice's) ✅

Bob logs in (tenant_id=1, user_id=2)
  → Connects to tenant_1.db
  → Query: SELECT * FROM expenses WHERE user_id = 2
  → Result: Sees expense 4 (only Bob's) ❌
  → PROBLEM: Bob can't see Alice's expenses!
```

## The Solution (After Fix)

```python
# CORRECT: No user_id filter needed
query = db.query(Expense)
```

**What happens now:**
```
Alice logs in (tenant_id=1, user_id=1)
  → Connects to tenant_1.db
  → Query: SELECT * FROM expenses
  → Result: Sees expenses 1, 2, 3, 4 (all Acme Corp expenses) ✅

Bob logs in (tenant_id=1, user_id=2)
  → Connects to tenant_1.db
  → Query: SELECT * FROM expenses
  → Result: Sees expenses 1, 2, 3, 4 (all Acme Corp expenses) ✅
  → SUCCESS: Bob can see Alice's expenses!

Carol logs in (tenant_id=2, user_id=3)
  → Connects to tenant_2.db
  → Query: SELECT * FROM expenses
  → Result: Sees expense 1 (only XYZ Inc expenses) ✅
  → SECURITY: Carol cannot see Acme Corp data!
```

## Tenant Isolation

```
┌──────────────────────────────────────────────────────────┐
│                   How Isolation Works                     │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  1. User Authentication                                   │
│     ↓                                                      │
│  2. Identify tenant_id from MasterUser                    │
│     ↓                                                      │
│  3. Connect to tenant-specific database                   │
│     ↓                                                      │
│  4. All queries automatically scoped to that database     │
│     ↓                                                      │
│  5. No way to access other tenant's data                  │
│                                                            │
│  ✅ Isolation = Database-level (strongest possible)       │
│  ✅ No need for WHERE tenant_id = X in queries           │
│  ✅ No need for WHERE user_id = X in queries             │
└──────────────────────────────────────────────────────────┘
```

## Role-Based Access Control (RBAC)

```
┌─────────────────────────────────────────────────────────┐
│                  Visibility vs Permissions               │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  VISIBILITY (What you can see):                          │
│  ✅ All users in tenant see all expenses                │
│  ✅ Controlled by database connection                   │
│                                                           │
│  PERMISSIONS (What you can do):                          │
│  ┌──────────┬──────┬────────┬────────┬────────┐        │
│  │ Role     │ View │ Create │ Edit   │ Delete │        │
│  ├──────────┼──────┼────────┼────────┼────────┤        │
│  │ Admin    │ ✅   │ ✅     │ ✅     │ ✅     │        │
│  │ User     │ ✅   │ ✅     │ Own    │ Own    │        │
│  │ Viewer   │ ✅   │ ❌     │ ❌     │ ❌     │        │
│  └──────────┴──────┴────────┴────────┴────────┘        │
│  ✅ Controlled by RBAC middleware                       │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## Data Flow Comparison

### Before Fix (Incorrect)
```
User Request: GET /expenses/
    ↓
Authentication: Verify user credentials
    ↓
Get tenant_id from MasterUser
    ↓
Connect to tenant_X.db
    ↓
Query: SELECT * FROM expenses WHERE user_id = current_user.id  ❌
    ↓
Return: Only current user's expenses  ❌
```

### After Fix (Correct)
```
User Request: GET /expenses/
    ↓
Authentication: Verify user credentials
    ↓
Get tenant_id from MasterUser
    ↓
Connect to tenant_X.db
    ↓
Query: SELECT * FROM expenses  ✅
    ↓
Return: All expenses in tenant  ✅
```

## Security Guarantees

```
┌─────────────────────────────────────────────────────────┐
│              Security is NOT Compromised                 │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ✅ Tenant Isolation: Still enforced by database        │
│  ✅ Authentication: Still required to access API        │
│  ✅ Authorization: RBAC still controls modifications    │
│  ✅ Encryption: Sensitive fields still encrypted        │
│  ✅ Audit Logs: Still track who created each expense    │
│                                                           │
│  What Changed:                                           │
│  - Users in same tenant can see each other's expenses   │
│                                                           │
│  What Didn't Change:                                     │
│  - Users in different tenants still isolated            │
│  - Role-based permissions still enforced                │
│  - Data encryption still active                         │
│  - Audit trails still maintained                        │
└─────────────────────────────────────────────────────────┘
```

## Use Cases

### ✅ Enabled by This Fix

1. **Team Collaboration**
   - Finance team can see all company expenses
   - Managers can review team member expenses
   - Accountants can access all expenses for reporting

2. **Approval Workflows**
   - Approvers can see expenses submitted by others
   - Admins can review pending expenses
   - Auditors can access all expense records

3. **Analytics & Reporting**
   - Dashboard shows company-wide expense trends
   - Reports include all team expenses
   - Budget tracking across all users

### ❌ Still Prevented (Security)

1. **Cross-Tenant Access**
   - Acme Corp users cannot see XYZ Inc expenses
   - Database-level isolation prevents data leakage

2. **Unauthorized Modifications**
   - Viewers cannot edit expenses (RBAC enforced)
   - Users cannot delete others' expenses (unless admin)
   - Role permissions still strictly enforced

## Summary

**Key Insight**: In a database-per-tenant architecture, the database connection provides tenant isolation. There's no need to filter by `user_id` for shared resources like expenses.

**The Fix**: Remove `user_id` filter → Enable team collaboration while maintaining security.
