# Reporting Router Database Fix

## Issue
The reporting router was incorrectly using `get_master_db` (master database) instead of `get_db` (tenant database) for feature gate checks and report operations. This caused feature gate checks to fail because:

1. License information is stored in the **tenant database**, not the master database
2. The `InstallationInfo` table is in the **tenant database**
3. Feature gate checks need to access the tenant's license information
4. Using the wrong database meant the license service couldn't find the license data

## Root Cause
The reporting router had multiple endpoints that were incorrectly configured:
- `preview_report` - used `get_master_db` for report generation
- `create_report_template` - used `get_master_db` for template creation
- `delete_report_template` - used `get_master_db` for template deletion
- `create_scheduled_report` - used `get_master_db` for scheduling
- `delete_report_file` - used `get_master_db` for file deletion
- `get_storage_stats` - used `get_master_db` for stats retrieval
- `_generate_report_background` - used `get_master_db` to fetch user email

## Solution
Changed all endpoints to use `get_db` (tenant database) instead of `get_master_db`. This ensures:

1. Feature gate checks access the correct tenant's license information
2. Report operations work with the tenant's data
3. Consistency with other commercial modules (e.g., prompt_management)

### Changes Made

#### 1. Import Statement
```python
# Before
from core.models.database import get_db, get_master_db

# After
from core.models.database import get_db
```

#### 2. Endpoint Dependencies
All endpoints changed from:
```python
db: Session = Depends(get_master_db),
tenant_db: Session = Depends(get_db),
```

To:
```python
db: Session = Depends(get_db),
```

#### 3. Background Task Function
The `_generate_report_background` function was updated to:
- Accept `user_email` as a parameter instead of querying the master database
- Remove the `get_master_db` call entirely
- Pass `current_user.email` when calling the background task

**Why this is correct:**
- The `ReportAuditService.log_report_generation()` method already expects `user_email` as a parameter
- We have access to `current_user.email` in the endpoint where the background task is created
- Passing the email directly is more efficient than querying the master database
- The background task doesn't need the full user object - it only needs the email for audit logging
- This follows the principle of passing only the data needed, not entire objects

## Affected Endpoints
1. `POST /api/v1/reports/preview` - Report preview generation
2. `POST /api/v1/reports/templates` - Template creation
3. `DELETE /api/v1/reports/templates/{template_id}` - Template deletion
4. `POST /api/v1/reports/scheduled` - Scheduled report creation
5. `DELETE /api/v1/reports/history/{report_id}` - Report file deletion
6. `GET /api/v1/reports/storage/stats` - Storage statistics

## Testing
After this fix, the reporting feature should:
1. ✅ Correctly check if "reporting" feature is licensed
2. ✅ Return 402 Payment Required only when the feature is not licensed
3. ✅ Work correctly with active licenses
4. ✅ Work correctly during trial periods
5. ✅ Work correctly during grace periods

## Architecture Notes
- Each tenant has its own database with its own `InstallationInfo` table
- License information is stored in the tenant database, not the master database
- The master database only contains user and organization information
- Feature gate checks must use the tenant database to access license information
- This is consistent with the multi-tenant architecture where each tenant's data is isolated

## Design Decision: Removing Master Database Query from Background Task
The original code queried the master database to fetch the user's email for audit logging:
```python
master_db = next(get_master_db())
user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
user_email = user.email if user else "unknown@system"
```

This was replaced by passing `user_email` as a parameter from the endpoint. Here's why:

1. **Efficiency**: Passing a string parameter is more efficient than opening a new database connection and querying
2. **Simplicity**: The background task only needs the email for audit logging, not the entire user object
3. **Consistency**: The `ReportAuditService.log_report_generation()` method already expects `user_email` as a parameter
4. **Availability**: We have access to `current_user.email` in the endpoint where the background task is created
5. **Separation of Concerns**: The background task doesn't need to know about the master database structure

This is a cleaner design that reduces unnecessary database queries and keeps the background task focused on its core responsibility: generating reports and logging audit events.

## Related Files
- `api/commercial/reporting/router.py` - Fixed endpoints
- `api/commercial/prompt_management/router.py` - Reference implementation (correct pattern)
- `api/core/utils/feature_gate.py` - Feature gate implementation
- `api/core/services/license_service.py` - License service
