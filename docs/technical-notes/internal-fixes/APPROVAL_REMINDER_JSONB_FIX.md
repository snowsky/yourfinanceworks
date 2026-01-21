# Approval Reminder JSONB Query Fix

## Issue
When rejecting expenses, the system was throwing a PostgreSQL error:
```
ERROR: operator does not exist: json @> unknown
HINT: No operator matches the given name and argument types. You might need to add explicit type casts.
```

The expense was still being rejected successfully, but the reminder task update was failing.

## Root Cause
The `extra_metadata` column in the `Reminder` table is defined as `JSON` type, but the code was using the PostgreSQL `@>` (contains) operator which only works with `JSONB` type.

The problematic queries were in `api/commercial/workflows/approvals/router.py`:
- Line 436: When approving an expense (completing the reminder)
- Line 568: When rejecting an expense (cancelling the reminder)

## Solution
Cast the `extra_metadata` column to `JSONB` in the query using PostgreSQL's `::jsonb` cast operator:

**Before:**
```python
from sqlalchemy import text
import json
metadata_json = json.dumps({"approval_id": approval_id})
reminder = db.query(Reminder).filter(
    Reminder.assigned_to_id == current_user.id,
    Reminder.status == ReminderStatus.PENDING,
    text(f"extra_metadata @> '{metadata_json}'")
).first()
```

**After:**
```python
reminder = db.query(Reminder).filter(
    Reminder.assigned_to_id == current_user.id,
    Reminder.status == ReminderStatus.PENDING,
    text("extra_metadata::jsonb @> :metadata")
).params(metadata=f'{{"approval_id": {approval_id}}}').first()
```

## Changes Made
1. Added `text` to SQLAlchemy imports
2. Updated both approval and rejection reminder queries to cast `extra_metadata` to `JSONB`
3. Used parameterized queries for better security and readability

## Testing
Test by:
1. Submitting an expense for approval
2. Rejecting the expense with a reason
3. Verify no PostgreSQL errors in logs
4. Verify the reminder task is properly cancelled
5. Verify the expense is successfully rejected
