# Processing Locks Table Fix

## Problem
The application was failing at startup with the error:
```
ERROR:main:❌ Processing lock recovery failed: (psycopg2.errors.UndefinedTable) relation "processing_locks" does not exist
```

## Root Cause
1. The `processing_locks` table migration was created but not applied to tenant databases
2. The startup code in `main.py` was trying to run recovery on the master database instead of tenant databases
3. Processing locks are tenant-specific (they track tenant-specific resources like expenses and bank statements)
4. The `ProcessingLock` model was incorrectly using the master database Base instead of the tenant database Base

## Solution

### 1. Created Migration Script
Created `api/scripts/migrate_tenant_processing_locks.py` to create the `processing_locks` table in all tenant databases.

### 2. Updated Startup Recovery
Modified `api/main.py` to:
- Run processing lock recovery per tenant instead of on master database
- Gracefully handle cases where the table doesn't exist yet
- Aggregate recovery statistics across all tenants

### 3. Applied the Fix
```bash
# Run the migration script
docker-compose exec api python scripts/migrate_tenant_processing_locks.py

# Restart services
docker-compose restart api ocr-worker
```

## Verification
After the fix:
- ✅ No more "processing_locks does not exist" errors
- ✅ API starts successfully with processing lock recovery
- ✅ OCR workers start without errors
- ✅ Processing lock system is operational

## Files Modified
- `api/main.py` - Updated startup recovery to run per-tenant
- `api/models/processing_lock.py` - Fixed to use tenant database Base instead of master database Base
- `api/scripts/migrate_tenant_processing_locks.py` - New migration script (created)

## Important Notes
**The master database does NOT need the `processing_locks` table.** This table is tenant-specific because:
- It tracks tenant-specific resources (expenses, bank statements, invoices)
- All usage is through `get_db()` which returns tenant database sessions
- The model now correctly uses `models.models_per_tenant.Base`

## Future Considerations
- The `processing_locks` table should be added to the standard tenant database schema
- Consider adding this migration to the Alembic migrations for tenant databases
- The table should be created automatically when new tenants are provisioned
