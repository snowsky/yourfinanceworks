# Usage Type Selection Implementation Summary

## What Changed

Implemented a new licensing flow where users must explicitly choose between **Personal Use** (free) or **Business Use** (30-day trial) when first setting up the application.

## Key Changes

### 1. Database Schema (`api/models/models_per_tenant.py`)
- Added `usage_type` column (personal/business/null)
- Added `usage_type_selected_at` timestamp
- Made `trial_start_date` and `trial_end_date` nullable
- Changed default `license_status` from `'trial'` to `'invalid'`
- New status: `'personal'` for free personal use

### 2. License Service (`api/services/license_service.py`)
- Added `select_usage_type()` method to handle usage type selection
- Added `get_usage_type_status()` method to check selection status
- Updated `_get_or_create_installation()` to create with `'invalid'` status
- Updated `is_trial_active()` to handle personal use and null trial dates
- Updated `get_trial_status()` to handle null trial dates
- Updated `get_enabled_features()` to enable all features for personal use
- Updated `get_license_status()` to include usage type information

### 3. License Router (`api/routers/license.py`)
- Added `POST /license/select-usage-type` endpoint
- Added `GET /license/usage-type-status` endpoint
- Added request/response models for usage type selection
- Updated `LicenseStatusResponse` to include usage type fields

### 4. Database Migration (`api/alembic/versions/add_usage_type_to_installation.py`)
- Adds new columns for usage type tracking
- Makes trial dates nullable
- Updates default license status
- Migrates existing installations to business/trial status

### 5. Documentation
- Created `docs/USAGE_TYPE_SELECTION.md` - Complete flow documentation
- Created `docs/USAGE_TYPE_IMPLEMENTATION_SUMMARY.md` - This file

## New Flow

### Before (Old Flow)
1. App starts → Automatic 30-day trial
2. Trial expires → Must purchase license

### After (New Flow)
1. App starts → License status: `invalid`
2. User must choose:
   - **Personal Use** → Free forever, all features
   - **Business Use** → 30-day trial, then requires license
3. Selection is permanent (one-time only)

## License Status Values

| Status | Description |
|--------|-------------|
| `invalid` | Initial state, no usage type selected |
| `personal` | Personal use, free forever |
| `trial` | Business trial active (30 days) |
| `active` | Paid license active |
| `expired` | License or trial expired |
| `grace_period` | 7 days after trial expiration |

## API Endpoints

### New Endpoints

#### `POST /api/v1/license/select-usage-type`
Select usage type (one-time only).

**Request:**
```json
{
  "usage_type": "personal"  // or "business"
}
```

#### `GET /api/v1/license/usage-type-status`
Check if usage type has been selected.

**Response:**
```json
{
  "usage_type": "personal",
  "usage_type_selected": true,
  "usage_type_selected_at": "2024-11-19T10:30:00Z",
  "license_status": "personal"
}
```

### Updated Endpoints

#### `GET /api/v1/license/status`
Now includes usage type information:
```json
{
  "usage_type": "personal",
  "usage_type_selected": true,
  "is_personal": true,
  ...
}
```

## Migration Steps

1. **Run Database Migration:**
   ```bash
   cd api
   alembic upgrade head
   ```

2. **Existing Installations:**
   - Automatically migrated to `usage_type='business'` and `license_status='trial'`
   - Trial dates preserved
   - No disruption to existing users

3. **New Installations:**
   - Start with `license_status='invalid'`
   - Must select usage type before using app

## UI Implementation Required

### 1. Usage Type Selection Modal
Show on first launch when `usage_type_selected` is `false`:

```
Welcome! How will you use this app?

[ Personal Use ]          [ Business Use ]
Free forever              30-day trial
All features              Requires license after trial
```

### 2. Check on App Load
```javascript
// Check if usage type selected
const response = await api.get('/license/usage-type-status');

if (!response.usage_type_selected) {
  // Show usage type selection modal
  showUsageTypeModal();
}
```

### 3. Handle Selection
```javascript
// User selects personal or business
const result = await api.post('/license/select-usage-type', {
  usage_type: 'personal'  // or 'business'
});

if (result.success) {
  // Proceed to app
  if (result.usage_type === 'business') {
    // Show trial banner
    showTrialBanner(result.trial_days_remaining);
  }
}
```

## Benefits

1. **Clear Intent**: Users explicitly choose their use case
2. **No Confusion**: Personal users never see trial warnings
3. **Prevents Abuse**: Can't switch from business to personal
4. **Better Compliance**: Clear distinction between personal/commercial use
5. **Improved UX**: Appropriate messaging for each user type

## Testing

### Test Personal Use
```bash
# Select personal
curl -X POST http://localhost:8000/api/v1/license/select-usage-type \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_type": "personal"}'

# Verify all features enabled
curl http://localhost:8000/api/v1/license/status \
  -H "Authorization: Bearer $TOKEN"
# Should show: "license_status": "personal", "has_all_features": true
```

### Test Business Use
```bash
# Select business
curl -X POST http://localhost:8000/api/v1/license/select-usage-type \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_type": "business"}'

# Verify trial started
curl http://localhost:8000/api/v1/license/status \
  -H "Authorization: Bearer $TOKEN"
# Should show: "license_status": "trial", "trial_days_remaining": 30
```

### Test One-Time Selection
```bash
# Try to select again (should fail)
curl -X POST http://localhost:8000/api/v1/license/select-usage-type \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_type": "business"}'
# Expected: 400 error with "ALREADY_SELECTED"
```

## Files Modified

1. `api/models/models_per_tenant.py` - Database schema
2. `api/services/license_service.py` - License logic
3. `api/routers/license.py` - API endpoints
4. `api/alembic/versions/add_usage_type_to_installation.py` - Migration (new)
5. `docs/USAGE_TYPE_SELECTION.md` - Documentation (new)
6. `docs/USAGE_TYPE_IMPLEMENTATION_SUMMARY.md` - This file (new)

## Next Steps

1. Run the database migration
2. Implement UI for usage type selection modal
3. Update frontend to check usage type status on load
4. Test both personal and business flows
5. Update user documentation/onboarding

## Rollback

If needed, rollback the migration:
```bash
cd api
alembic downgrade -1
```

This will:
- Remove usage type columns
- Restore trial dates as non-nullable
- Restore default license status to 'trial'
