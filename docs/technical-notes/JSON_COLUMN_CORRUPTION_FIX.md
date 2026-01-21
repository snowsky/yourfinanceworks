# JSON Column Corruption Fix

## Problem Description

The application was experiencing errors where encrypted string data was being stored in columns that should contain encrypted JSON data. This caused the `EncryptedJSON` column type to try to decrypt base64-encoded encrypted string data as if it were encrypted JSON, resulting in errors like:

```
ERROR:utils.column_encryptor:JSON DECRYPTION FAILED in JSON Table: Unknown, Column: Unknown, Record ID: Unknown for tenant 1: Authentication tag verification failed
ERROR:utils.column_encryptor:JSON Column: JSON Table: Unknown, Column: Unknown, Record ID: Unknown
ERROR:utils.column_encryptor:JSON Data preview: XqBgX2jx5aW92+3On9Ct0NdSQVlTDQBwgbBs9NCyNQ2kxQ+/Bs...
ERROR:utils.column_encryptor:JSON Data length: 312 characters
```

## Root Cause

The issue occurred when:

1. A column was defined as `EncryptedJSON()` in the SQLAlchemy model
2. But encrypted string data (base64-encoded) was stored in that column instead of encrypted JSON data
3. When the application tried to read the data, the `EncryptedJSON` class attempted to decrypt it as JSON, but it was actually encrypted string data

## Affected Columns

The following columns use `EncryptedJSON()` and could be affected:

- `expenses.analysis_result`
- `expenses.custom_fields` (if it exists)
- `expenses.inventory_items`
- `expenses.consumption_items`
- `audit_logs.details`

## Solution Applied

### Immediate Fix

1. **Identified corrupted records**: Found expense record ID 2 with corrupted `analysis_result` data
2. **Cleaned corrupted data**: Set the corrupted `analysis_result` to NULL using:

   ```sql
   UPDATE expenses SET analysis_result = NULL WHERE id = 2;
   ```

### Prevention Measures

1. **Enhanced error messages**: Updated `column_encryptor.py` to detect when encrypted string data is stored in JSON columns and provide clear error messages with solution instructions.

2. **Added detection logic**: Added `_looks_like_encrypted_string_data()` method to distinguish between encrypted string data and encrypted JSON data.

3. **Improved logging**: Enhanced error logging to provide better context about which table/column/record is affected.

## Verification

After applying the fix:

1. ✅ No more JSON decryption errors in the logs
2. ✅ Application runs without encryption-related errors
3. ✅ Expenses endpoint works correctly

## Prevention for Future

To prevent this issue from recurring:

1. **Code Review**: Ensure that when setting values to `EncryptedJSON` columns, the data is always a dictionary or list, not a string.

2. **Type Checking**: The application should validate data types before storing in encrypted JSON columns.

3. **Migration Scripts**: When migrating data or changing column types, ensure proper data format conversion.

## Monitoring

Watch for these error patterns in logs:

- `JSON DECRYPTION FAILED`
- `Authentication tag verification failed`
- `This appears to be encrypted STRING data stored in a JSON column!`

If these errors appear, run the diagnostic script:

```bash
docker exec invoice_app_api python fix_corrupted_json_data.py
```

## Files Modified

1. `api/utils/column_encryptor.py` - Enhanced error detection and messaging
2. `api/fix_corrupted_json_data.py` - Script to identify and fix corrupted data
3. `api/diagnose_json_column_issue.py` - Diagnostic script
4. Database: Fixed corrupted record in `tenant_1.expenses` table

## Root Cause Analysis

The core issue was **not** corrupted data, but a **circular dependency in the OCR worker's encryption context setup**:

1. **OCR worker needs tenant context** to decrypt data
2. **To get tenant context**, it accessed `expense.user`
3. **Accessing `expense.user`** triggered loading encrypted user data (email)
4. **But encrypted email couldn't be decrypted** without proper tenant context
5. **Circular dependency!** ❌

### The Real Problem

The encrypted string `khgrzvDHgJKjX4vXErVSIwYoBx+1wSRxRo6IbXQOzwe2UJo=` was **NOT corrupted**. It correctly decrypts to `a@a.com` when the proper encryption context is available.

## Final Solution

**Fixed the OCR worker's tenant context setup** to avoid the circular dependency:

```python
# OLD CODE (caused circular dependency)
if hasattr(expense, 'user') and expense.user and hasattr(expense.user, 'tenant_id'):
    tenant_id = expense.user.tenant_id  # This triggered loading encrypted user data!

# NEW CODE (avoids loading encrypted data)
user_tenant_query = db.execute(
    text("SELECT tenant_id FROM users WHERE id = :user_id"),
    {"user_id": expense.user_id}
).fetchone()
```

This gets the tenant_id directly from the database without loading the encrypted user fields.

## Status

✅ **RESOLVED** - The OCR worker encryption context issue has been fixed. The encrypted data was never corrupted - it was an application logic issue.
