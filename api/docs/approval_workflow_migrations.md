# Approval Workflow Database Migrations

This document describes the database migrations implemented for the expense approval workflow system.

## Migration Files Created

### 1. `add_expense_approval_workflow_tables.py`
**Status**: ✅ Already exists
- Creates the core approval workflow tables:
  - `expense_approvals`: Tracks individual approval decisions
  - `approval_rules`: Defines approval rules and criteria
  - `approval_delegates`: Manages approval delegation relationships

### 2. `add_expense_approval_status_values.py`
**Status**: ✅ Already exists (Fixed for SQLite compatibility)
- Updates the `expenses` table to support approval workflow status values
- Adds check constraint for valid expense status values:
  - `draft`, `recorded`, `reimbursed`, `pending_approval`, `approved`, `rejected`, `resubmitted`

### 3. `update_approval_workflow_indexes.py`
**Status**: ✅ Newly created
- Adds comprehensive indexes for optimal query performance
- Adds data integrity constraints
- Uses SQLite-compatible batch mode for constraint operations

## Database Schema

### ExpenseApproval Table
```sql
CREATE TABLE expense_approvals (
    id INTEGER PRIMARY KEY,
    expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    approver_id INTEGER NOT NULL REFERENCES users(id),
    approval_rule_id INTEGER REFERENCES approval_rules(id),
    status VARCHAR NOT NULL DEFAULT 'pending',
    rejection_reason TEXT,
    notes TEXT,
    submitted_at DATETIME NOT NULL,
    decided_at DATETIME,
    approval_level INTEGER NOT NULL DEFAULT 1,
    is_current_level BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

### ApprovalRule Table
```sql
CREATE TABLE approval_rules (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    min_amount FLOAT,
    max_amount FLOAT,
    category_filter VARCHAR,
    currency VARCHAR NOT NULL DEFAULT 'USD',
    approval_level INTEGER NOT NULL DEFAULT 1,
    approver_id INTEGER NOT NULL REFERENCES users(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 0,
    auto_approve_below FLOAT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

### ApprovalDelegate Table
```sql
CREATE TABLE approval_delegates (
    id INTEGER PRIMARY KEY,
    approver_id INTEGER NOT NULL REFERENCES users(id),
    delegate_id INTEGER NOT NULL REFERENCES users(id),
    start_date DATETIME NOT NULL,
    end_date DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE(approver_id, delegate_id, start_date)
);
```

## Indexes Created

### ExpenseApproval Indexes
- `ix_expense_approvals_expense_id`: Fast lookup by expense
- `ix_expense_approvals_approver_id`: Fast lookup by approver
- `ix_expense_approvals_status`: Filter by approval status
- `ix_expense_approvals_approval_level`: Filter by approval level
- `ix_expense_approvals_is_current_level`: Find current level approvals
- `ix_expense_approvals_submitted_at`: Sort by submission date
- `ix_expense_approvals_status_approver`: Composite index for approver dashboard
- `ix_expense_approvals_expense_level`: Composite index for expense workflow

### ApprovalRule Indexes
- `ix_approval_rules_approver_id`: Fast lookup by approver
- `ix_approval_rules_is_active`: Filter active rules
- `ix_approval_rules_priority`: Sort by priority
- `ix_approval_rules_approval_level`: Filter by level
- `ix_approval_rules_currency`: Filter by currency
- `ix_approval_rules_active_priority`: Composite index for rule matching
- `ix_approval_rules_currency_active`: Composite index for currency filtering

### ApprovalDelegate Indexes
- `ix_approval_delegates_approver_id`: Fast lookup by approver
- `ix_approval_delegates_delegate_id`: Fast lookup by delegate
- `ix_approval_delegates_is_active`: Filter active delegations
- `ix_approval_delegates_start_date`: Filter by start date
- `ix_approval_delegates_end_date`: Filter by end date
- `ix_approval_delegates_active_dates`: Composite index for date range queries
- `ix_approval_delegates_approver_active`: Composite index for active delegations

## Data Integrity Constraints

### ExpenseApproval Constraints
- Status must be one of: `pending`, `approved`, `rejected`
- Approval level must be positive (> 0)

### ApprovalRule Constraints
- Priority must be non-negative (>= 0)
- Approval level must be positive (> 0)
- Min amount must be <= max amount when both are set
- Auto-approve amount must be positive when set

### ApprovalDelegate Constraints
- Start date must be < end date
- Approver cannot delegate to themselves (approver_id != delegate_id)

## Migration Rollback Testing

A comprehensive test suite has been created to verify migration rollback scenarios:

### Test Script: `scripts/test_approval_migration_rollback.py`
- ✅ Tests forward migration to each step
- ✅ Tests rollback from each migration
- ✅ Tests re-migration after rollback
- ✅ Tests constraint validation
- ✅ Tests data integrity preservation

### Test Results

#### Pytest Test Suite: ✅ All 7 tests passing
```
=============================== test session starts ===============================
tests/test_approval_migrations.py::TestApprovalMigrations::test_approval_workflow_tables_creation PASSED
tests/test_approval_migrations.py::TestApprovalMigrations::test_approval_status_values_migration PASSED  
tests/test_approval_migrations.py::TestApprovalMigrations::test_approval_indexes_migration PASSED
tests/test_approval_migrations.py::TestApprovalMigrations::test_approval_constraints_validation PASSED
tests/test_approval_migrations.py::TestApprovalMigrations::test_migration_rollback_scenarios PASSED
tests/test_approval_migrations.py::TestApprovalMigrations::test_migration_idempotency PASSED
tests/test_approval_migrations.py::TestApprovalMigrations::test_data_integrity_after_migration PASSED
================================ 7 passed in 0.54s ================================
```

#### Rollback Test Script: ✅ All scenarios passing
```
🧪 Testing Approval Workflow Migration Rollback Scenarios
============================================================
1️⃣ Testing Forward Migration...
   ✅ Approval workflow tables created successfully
   ✅ Expense status values updated successfully
   ✅ Approval workflow indexes created successfully

2️⃣ Testing Rollback Scenarios...
   ✅ Successfully rolled back indexes migration
   ✅ Successfully rolled back status values migration
   ✅ Successfully rolled back workflow tables migration

3️⃣ Testing Re-migration After Rollback...
   ✅ Successfully re-applied all migrations

4️⃣ Testing Database Constraints...
   ✅ All constraint validation tests passed!

🏆 All tests completed successfully!
```

## Usage

### Running Migrations
```bash
# Apply all approval workflow migrations
alembic upgrade update_approval_workflow_indexes

# Rollback to before indexes
alembic downgrade add_expense_approval_status_values

# Rollback to before status values
alembic downgrade add_expense_approval_workflow_tables

# Complete rollback
alembic downgrade base
```

### Testing Rollback Scenarios
```bash
# Run the comprehensive rollback test
python scripts/test_approval_migration_rollback.py
```

## SQLite Compatibility

All migrations use SQLite-compatible batch mode for constraint operations:
- Check constraints are added using `batch_alter_table`
- Indexes are created using standard `create_index` operations
- Foreign key constraints are handled properly during table creation

## Performance Considerations

The indexes are designed to optimize common query patterns:
- Approver dashboard queries (status + approver_id)
- Expense workflow queries (expense_id + approval_level)
- Rule matching queries (currency + is_active + priority)
- Delegation lookup queries (approver_id + is_active + date ranges)

## Requirements Satisfied

This implementation satisfies the following task requirements:
- ✅ Create Alembic migration for ExpenseApproval table
- ✅ Add migration for ApprovalRule table with indexes
- ✅ Create migration for ApprovalDelegate table
- ✅ Update existing expense status values migration
- ✅ Test migration rollback scenarios
- ✅ Database schema implementation