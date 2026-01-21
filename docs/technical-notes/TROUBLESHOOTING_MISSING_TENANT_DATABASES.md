# Troubleshooting Missing Tenant Databases

## Problem

You may encounter errors like:
```
psycopg2.OperationalError: connection to server at "postgres-master" (172.18.0.2), port 5432 failed: FATAL:  database "tenant_16" does not exist
```

This happens when:
- A tenant record exists in the master database
- But the corresponding tenant database was never created or was deleted
- The application tries to connect to the missing tenant database

## Root Causes

1. **Migration Issues**: During database migrations, tenant databases might not be created
2. **Manual Database Deletion**: Someone manually deleted a tenant database
3. **Failed Tenant Creation**: Tenant record was created but database creation failed
4. **Database Server Issues**: Database server was restored from backup without tenant databases

## Automatic Fix (Recommended)

The system now automatically detects and creates missing tenant databases:

### 1. Middleware Auto-Creation
The tenant context middleware will automatically try to create missing databases when detected.

### 2. Database Dependency Auto-Creation
The database connection logic will attempt to create missing databases before raising errors.

## Manual Fix Options

### Option 1: Use the Fix Script (Docker)

Run this from your host machine:
```bash
# Enter the API container
docker exec -it invoice_app_api bash

# Run the fix script
bash scripts/run_fix_missing_databases.sh
```

### Option 2: Use the Fix Script (Direct)

If running directly (not in Docker):
```bash
cd api
python scripts/fix_missing_tenant_databases.py check
```

### Option 3: Check Individual Database

```bash
# List all tenant databases and their status
python scripts/fix_missing_tenant_databases.py list

# Recreate a specific tenant database (WARNING: Deletes all data)
python scripts/fix_missing_tenant_databases.py recreate 16
```

## Super Admin Dashboard

Super admins can also manage tenant databases through the web UI:

1. Login as a super user
2. Go to `/super-admin`
3. Click on the "Databases" tab
4. View database status and recreate if needed

## Prevention

To prevent this issue in the future:

### 1. Proper Tenant Creation
Always use the API endpoints to create tenants:
```bash
POST /api/v1/super-admin/tenants
```

### 2. Database Backups
Ensure your backup strategy includes all tenant databases:
```bash
# Backup all databases
for db in $(psql -h postgres-master -U postgres -t -c "SELECT datname FROM pg_database WHERE datname LIKE 'tenant_%'"); do
    pg_dump -h postgres-master -U postgres "$db" > "backup_${db}.sql"
done
```

### 3. Health Checks
Regularly check database health:
```bash
python scripts/fix_missing_tenant_databases.py list
```

### 4. Monitoring
Monitor your logs for tenant database creation attempts:
```bash
# Look for these log messages
grep "Attempting to create missing tenant database" /var/log/app.log
grep "Successfully created tenant database" /var/log/app.log
```

## Quick Fix Summary

**For the specific error you're seeing:**

1. **Quick Fix** (Docker):
   ```bash
   docker exec -it invoice_app_api python scripts/fix_missing_tenant_databases.py check
   ```

2. **Verify Fix**:
   ```bash
   docker exec -it invoice_app_api python scripts/fix_missing_tenant_databases.py list
   ```

3. **Restart Application**:
   ```bash
   docker-compose restart api
   ```

## Understanding the Fix

The fix process:
1. Queries the master database for all tenants
2. Attempts to connect to each tenant database
3. Creates missing databases with proper schema
4. Initializes default data (currencies, etc.)
5. Reports success/failure for each tenant

After running the fix, your application should work normally without the "database does not exist" errors.

## Long-term Solution

The enhanced middleware and database logic will automatically handle this issue going forward, so manual intervention should rarely be needed after the initial fix. 